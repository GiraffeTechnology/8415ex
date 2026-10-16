"""Three declared registration sources share one original read-only backend."""
from copy import deepcopy
from dataclasses import dataclass
from html import escape
from types import MappingProxyType
import re
from .model import WarehouseReceipt
from .original_task_journal_reader import OriginalTaskJournalReader


SOURCES = MappingProxyType({
    'REG-DIRECT': ('REG_DIRECT', 'Direct registration source',
        'Simulated direct registrar; the Oracle alone accepts and records its voucher.'),
    'REG-ELECTRONIC': ('REG_ELECTRONIC', 'Electronic registration source',
        'Simulated electronic registrar; electronic form does not relax Oracle verification.'),
    'REG-INTERMEDIARY': ('REG_INTERMEDIARY', 'Intermediary registration source',
        'Simulated intermediary; forwarding does not authorize EX to verify originals or change holder.'),
})


class RegistrationSourceRefused(ValueError):
    pass


@dataclass(frozen=True)
class SourceTaskBinding:
    receipt: WarehouseReceipt
    voucher_format_id: str
    voucher_format_version: str
    required_voucher_fields: tuple
    principal: dict
    native_operation_id: str
    expected_wallet: str


def _identifier(value):
    return type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', value) is not None


class RegistrationSourceWorkbench:
    """Resolve existing mint/task identity; never accept an off-chain voucher."""
    def __init__(self, original_reader, resolve_binding):
        if not isinstance(original_reader, OriginalTaskJournalReader) or not callable(resolve_binding):
            raise RegistrationSourceRefused('one original reader and existing binding resolver required')
        self.reader = original_reader
        self.resolve_binding = resolve_binding

    def read_source(self, source, receipt_id):
        if type(source) is not str or source not in SOURCES or not _identifier(receipt_id):
            raise RegistrationSourceRefused('known declared source and receipt required')
        try:
            binding = deepcopy(self.resolve_binding(source, receipt_id))
        except Exception:
            raise RegistrationSourceRefused('existing mint/task source binding unavailable') from None
        if (not isinstance(binding, SourceTaskBinding)
                or not isinstance(binding.receipt, WarehouseReceipt)
                or binding.receipt.receipt_id != receipt_id
                or binding.receipt.registration_path != SOURCES[source][0]
                or not _identifier(binding.voucher_format_id)
                or not _identifier(binding.voucher_format_version)
                or type(binding.required_voucher_fields) is not tuple
                or not binding.required_voucher_fields
                or any(not _identifier(name) for name in binding.required_voucher_fields)
                or len(set(binding.required_voucher_fields)) != len(binding.required_voucher_fields)):
            raise RegistrationSourceRefused('source must match existing mint format and original task binding')
        projection = self.reader.read(binding.principal, binding.native_operation_id,
                                      binding.receipt.asset.chain_id, binding.expected_wallet)
        return {'receiptId': receipt_id, 'source': source, 'domainPath': SOURCES[source][0],
                'sourceLabel': SOURCES[source][1], 'sourceExplanation': SOURCES[source][2],
                'simulatedRole': True, 'voucherFormatId': binding.voucher_format_id,
                'voucherFormatVersion': binding.voucher_format_version,
                'requiredVoucherFields': list(binding.required_voucher_fields),
                'taskProjection': projection, 'canExecute': False,
                'oracleRecord': 'UNBOUND', 'ownerHolderEvidence': 'UNBOUND',
                'principalFunds': 'NOT_VERIFIED', 'gasFunds': 'NOT_VERIFIED'}

    def render_source(self, source, receipt_id):
        data = self.read_source(source, receipt_id)
        native = data['taskProjection']['nativeOperation']
        def esc(value):
            return escape(str(value), quote=True)
        def row(label, value):
            return '<dt>' + esc(label) + '</dt><dd>' + esc(value) + '</dd>'
        fields = [('Receipt', data['receiptId']), ('Source', data['source']),
            ('Mint-declared voucher format', data['voucherFormatId'] + ' / ' + data['voucherFormatVersion']),
            ('Required voucher fields', ', '.join(data['requiredVoucherFields'])),
            ('Original native operation', native['id']), ('Original task status only', native['status']),
            ('Original revision', native['revision']), ('Observed update', native['updatedAt']),
            ('Original transaction identity', native.get('transactionHash', 'NOT_OBSERVED')),
            ('Oracle chain record', data['oracleRecord']),
            ('Owner / holder authority', data['ownerHolderEvidence']),
            ('Principal funds', data['principalFunds']), ('Gas funds', data['gasFunds'])]
        return ('<section><h2>' + esc(data['sourceLabel']) + '</h2>'
            '<p role="status">Simulated source role. Installed runtime and registration acceptance '
            'are not proved by this view.</p><p>' + esc(data['sourceExplanation']) + '</p><dl>'
            + ''.join(row(label, value) for label, value in fields) + '</dl>'
            '<p>Original task status is not Oracle registration or payment completion. '
            'This interface accepts no original voucher, signs nothing and moves no funds.</p></section>')

    @staticmethod
    def render_choices(receipt_id, entry_path):
        if (not _identifier(receipt_id) or type(entry_path) is not str
                or not entry_path.startswith('/') or entry_path.startswith('//')
                or chr(92) in entry_path or any(ord(c) < 32 for c in entry_path)):
            raise RegistrationSourceRefused('explicit existing same-origin read route required')
        options = ''.join('<option value="' + escape(key, quote=True) + '">'
            + escape(value[1], quote=True) + '</option>' for key, value in SOURCES.items())
        return ('<form method="get" action="' + escape(entry_path, quote=True) + '">'
            '<input type="hidden" name="receipt" value="' + escape(receipt_id, quote=True) + '">'
            '<label>Registration source<select name="source">' + options + '</select></label>'
            '<button type="submit">Read original source task</button></form>')
