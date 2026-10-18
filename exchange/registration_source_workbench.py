"""Three declared registration sources share one original read-only backend."""
from copy import deepcopy
from dataclasses import dataclass
from html import escape
from types import MappingProxyType
import re
from .registration_source_locales import WORDS
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

    @staticmethod
    def _words(locale):
        if type(locale) is not str or locale not in WORDS:
            raise RegistrationSourceRefused('supported registration locale required')
        return WORDS[locale]

    def render_source(self, source, receipt_id, locale="en"):
        words = self._words(locale)
        data = self.read_source(source, receipt_id)
        native = data['taskProjection']['nativeOperation']
        def esc(value):
            return escape(str(value), quote=True)
        def row(key, value):
            return '<dt>' + esc(words[key]) + '</dt><dd>' + esc(value) + '</dd>'
        fields = [('receipt', data['receiptId']), ('source', data['source']),
            ('format', data['voucherFormatId'] + ' / ' + data['voucherFormatVersion']),
            ('fields', ', '.join(data['requiredVoucherFields'])),
            ('operation', native['id']), ('status', native['status']),
            ('revision', native['revision']), ('updated', native['updatedAt']),
            ('transaction', native.get('transactionHash', 'NOT_OBSERVED')),
            ('oracle', data['oracleRecord']), ('authority', data['ownerHolderEvidence']),
            ('principal', data['principalFunds']), ('gas', data['gasFunds'])]
        source_key = {'REG-DIRECT': 'direct', 'REG-ELECTRONIC': 'electronic',
                      'REG-INTERMEDIARY': 'intermediary'}[source]
        return ('<section lang="' + locale + '"><h2>' + esc(words[source_key]) + '</h2>'
            '<p role="status">' + esc(words['simulated']) + '</p><p>'
            + esc(words[source_key + 'Explanation']) + '</p><dl>'
            + ''.join(row(key, value) for key, value in fields) + '</dl><p>'
            + esc(words['boundary']) + '</p></section>')

    @staticmethod
    def render_choices(receipt_id, entry_path, locale="en"):
        words = RegistrationSourceWorkbench._words(locale)
        if (not _identifier(receipt_id) or type(entry_path) is not str
                or not entry_path.startswith('/') or entry_path.startswith('//')
                or chr(92) in entry_path or any(ord(c) < 32 for c in entry_path)):
            raise RegistrationSourceRefused('explicit existing same-origin read route required')
        labels = {'REG-DIRECT': 'direct', 'REG-ELECTRONIC': 'electronic',
                  'REG-INTERMEDIARY': 'intermediary'}
        options = ''.join('<option value="' + escape(key, quote=True) + '">'
            + escape(words[labels[key]], quote=True) + '</option>' for key in SOURCES)
        language = ('' if locale == 'en' else
            '<input type="hidden" name="lang" value="' + locale + '">')
        return ('<form lang="' + locale + '" method="get" action="'
            + escape(entry_path, quote=True) + '">' + language
            + '<input type="hidden" name="receipt" value="' + escape(receipt_id, quote=True) + '">'
            '<label>' + escape(words['source'], quote=True) + '<select name="source">'
            + options + '</select></label><button type="submit">'
            + escape(words['read'], quote=True) + '</button></form>')

