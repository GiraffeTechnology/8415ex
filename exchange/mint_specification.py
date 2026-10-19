"""Complete mint declarations for one bill of lading; no mint or secret I/O."""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
import re
from .model import WarehouseReceipt, REGISTRATION_PATHS


class MintSpecificationRefused(ValueError):
    pass


def _text(value):
    if type(value) is not str or not value.strip():
        raise MintSpecificationRefused('required non-empty public field missing')
    return value


def _identifier(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', value):
        raise MintSpecificationRefused('opaque non-secret identifier required')
    return value


def _names(value):
    if type(value) is not tuple or len(value) != len(set(value)):
        raise MintSpecificationRefused('unique declared field tuple required')
    for name in value:
        _identifier(name)
    return value


def _time(value):
    if type(value) is not int or value < 0:
        raise MintSpecificationRefused('exact UTC epoch-second timestamp required')
    return value


@dataclass(frozen=True)
class CommodityTemplate:
    template_id: str
    version: str
    commodity_scope: str
    standard_reference: str
    applicable_fields: tuple
    required_fields: tuple

    def __post_init__(self):
        _identifier(self.template_id)
        _identifier(self.version)
        _text(self.commodity_scope)
        _text(self.standard_reference)
        _names(self.applicable_fields)
        _names(self.required_fields)
        if not set(self.required_fields) <= set(self.applicable_fields):
            raise MintSpecificationRefused('required fields outside applicable template')


@dataclass(frozen=True)
class RegistrationFormat:
    format_id: str
    version: str
    required_fields: tuple
    path: str

    def __post_init__(self):
        _identifier(self.format_id)
        _identifier(self.version)
        _names(self.required_fields)
        if not self.required_fields or self.path not in REGISTRATION_PATHS:
            raise MintSpecificationRefused('declared Oracle voucher format and path required')


@dataclass(frozen=True)
class MintSpecification:
    receipt: WarehouseReceipt
    template: CommodityTemplate
    bill_of_lading_number: str
    issuer: str
    registrar: str
    storage_location: str
    public_attributes: tuple
    bill_terms: str
    original_document_mapping: str
    controlled_access_mapping: str
    registration_deadline: int
    registration_comparison: str
    voucher_format: RegistrationFormat

    def __post_init__(self):
        if not (isinstance(self.receipt, WarehouseReceipt)
                and isinstance(self.template, CommodityTemplate)
                and isinstance(self.voucher_format, RegistrationFormat)):
            raise MintSpecificationRefused('typed receipt, template and voucher declaration required')
        for value in (self.bill_of_lading_number, self.issuer, self.registrar,
                      self.storage_location, self.bill_terms):
            _text(value)
        _identifier(self.original_document_mapping)
        _identifier(self.controlled_access_mapping)
        _time(self.registration_deadline)
        if self.registration_deadline <= self.receipt.minted_at:
            raise MintSpecificationRefused('registration deadline must follow mint')
        if self.registration_comparison not in ('LT', 'LTE'):
            raise MintSpecificationRefused('explicit registration equality semantics required')
        if self.voucher_format.path != self.receipt.registration_path:
            raise MintSpecificationRefused('voucher format path differs from mint path')
        if type(self.public_attributes) is not tuple:
            raise MintSpecificationRefused('immutable public attributes required')
        names = set()
        for pair in self.public_attributes:
            if type(pair) is not tuple or len(pair) != 2:
                raise MintSpecificationRefused('public attribute name/value pairs required')
            name, value = pair
            _identifier(name)
            _text(value)
            if name in names or name not in self.template.applicable_fields:
                raise MintSpecificationRefused('duplicate or inapplicable commodity field')
            names.add(name)
        if not set(self.template.required_fields) <= names:
            raise MintSpecificationRefused('required commodity template field missing')

    def trade_eligible_at(self, timestamp):
        return self.receipt.minted_at <= _time(timestamp) < self.receipt.trade_stop_at

    def registration_time_eligible(self, effective_at):
        timestamp = _time(effective_at)
        if timestamp < self.receipt.minted_at or timestamp > self.receipt.trade_stop_at:
            return False
        return (timestamp < self.registration_deadline if self.registration_comparison == 'LT'
                else timestamp <= self.registration_deadline)

    def metadata(self, verify):
        """Return only an explicitly verified non-secret declaration candidate."""
        if not callable(verify):
            raise MintSpecificationRefused('existing schema, mapping and privacy verifiers required')
        candidate = {'schema': '8415ex-mint-declaration/1', 'receipt': asdict(self.receipt),
            'wholeReceiptUnits': 1, 'template': asdict(self.template),
            'billOfLadingNumber': self.bill_of_lading_number, 'issuer': self.issuer,
            'registrar': self.registrar, 'storageLocation': self.storage_location,
            'commodityAttributes': dict(self.public_attributes), 'billTerms': self.bill_terms,
            'originalDocumentMapping': self.original_document_mapping,
            'controlledAccessMapping': self.controlled_access_mapping,
            'time': {'unit': 'unix-second', 'timezone': 'UTC', 'precision': 'integer',
                'tradeStopAt': self.receipt.trade_stop_at, 'tradeComparison': 'LT',
                'registrationDeadline': self.registration_deadline,
                'registrationComparison': self.registration_comparison,
                'registrationAlsoMustNotExceedTradeStop': True},
            'voucherFormat': asdict(self.voucher_format),
            'registrationAuthority': 'existing Oracle record only',
            'scope': 'bill-of-lading-transfer-only',
            'legalOrInstitutionalEndorsementClaimed': False}
        for kind, evidence in (('existing-nft0-currency-schema', candidate),
                ('existing-asset-template-schema', candidate),
                ('controlled-encrypted-access-mapping', {
                    'receiptId': self.receipt.receipt_id,
                    'asset': asdict(self.receipt.asset),
                    'mappingId': self.controlled_access_mapping,
                    'originalDocumentMapping': self.original_document_mapping}),
                ('non-secret-metadata-scan', candidate)):
            encoded = json.dumps(candidate, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
            try:
                verified = verify(kind, evidence)
            except Exception:
                raise MintSpecificationRefused('external declaration verification failed') from None
            if verified is not True:
                raise MintSpecificationRefused('required external declaration evidence refused')
            if json.dumps(candidate, sort_keys=True, separators=(',', ':'), ensure_ascii=False) != encoded:
                raise MintSpecificationRefused('verification callback mutated declaration')
        return candidate


class MintDeclarationBook:
    """Single-writer in-memory uniqueness projection, not an NFT mint API."""
    def __init__(self, verify):
        if not callable(verify):
            raise MintSpecificationRefused('existing declaration verifier required')
        self.verify = verify
        self._assets = {}
        self._receipts = {}
        self._documents = {}

    def admit(self, specification):
        if not isinstance(specification, MintSpecification):
            raise MintSpecificationRefused('typed mint declaration required')
        payload = specification.metadata(self.verify)
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        digest = sha256(encoded.encode('utf-8')).hexdigest()
        asset = specification.receipt.asset.key
        receipt_id = specification.receipt.receipt_id
        document = (specification.issuer, specification.receipt.receipt_number)
        identity = (asset, receipt_id, document, digest)
        for index, key in ((self._assets, asset), (self._receipts, receipt_id),
                           (self._documents, document)):
            old = index.get(key)
            if old is not None and old != identity:
                raise MintSpecificationRefused('duplicate asset/receipt/document or changed mint declaration')
        self._assets[asset] = identity
        self._receipts[receipt_id] = identity
        self._documents[document] = identity
        return {'receiptId': receipt_id, 'asset': list(asset), 'declarationDigest': digest,
                'mint': 'NOT_RUN', 'assetValidity': 'NOT_ATTESTED',
                'secretStorage': 'external mapping evidence only; no secret read or write',
                'canonicalDeclaration': payload}
