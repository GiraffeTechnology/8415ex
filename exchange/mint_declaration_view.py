"""Escaped, read-only display of a verified mint declaration candidate."""
from html import escape
from .mint_specification import MintSpecification, MintSpecificationRefused


def render_mint_declaration(specification, verify, now):
    if not isinstance(specification, MintSpecification):
        raise MintSpecificationRefused('typed declared receipt required')
    if type(now) is not int or now < 0:
        raise MintSpecificationRefused('trusted UTC epoch-second observation required')
    meta = specification.metadata(verify)
    receipt = meta['receipt']
    asset = receipt['asset']
    def esc(value):
        return escape(str(value), quote=True)
    def row(label, value):
        return '<dt>' + esc(label) + '</dt><dd>' + esc(value) + '</dd>'
    fields = [
        ('Receipt ID', receipt['receipt_id']),
        ('Warehouse receipt number', receipt['receipt_number']),
        ('Bill of lading number', meta['billOfLadingNumber']),
        ('Commodity', receipt['commodity_name']),
        ('Goods quantity', str(receipt['commodity_quantity']) + ' ' + receipt['commodity_unit']),
        ('Tradeable NFT units', meta['wholeReceiptUnits']),
        ('Chain ID', asset['chain_id']), ('NFT contract', asset['contract']),
        ('NFT token ID', asset['token_id']), ('Initial account at mint', receipt['origin_account']),
        ('Issuer', meta['issuer']), ('Registrar', meta['registrar']),
        ('Storage or location', meta['storageLocation']),
        ('Template and version', meta['template']['template_id'] + ' / ' + meta['template']['version']),
        ('Commodity scope', meta['template']['commodity_scope']),
        ('Referenced standard', meta['template']['standard_reference']),
        ('Original document mapping', meta['originalDocumentMapping']),
        ('Controlled access mapping', meta['controlledAccessMapping']),
        ('Registration source', receipt['registration_path']),
        ('Oracle voucher format and version', meta['voucherFormat']['format_id'] + ' / '
             + meta['voucherFormat']['version']),
        ('Required voucher fields', ', '.join(meta['voucherFormat']['required_fields'])),
        ('Trade deadline (UTC epoch seconds)', meta['time']['tradeStopAt']),
        ('Trade comparison', 'observed time LT trade deadline'),
        ('Registration deadline (UTC epoch seconds)', meta['time']['registrationDeadline']),
        ('Registration comparison', meta['time']['registrationComparison']),
        ('Registration trade-stop condition', 'effective time must also be <= trade deadline'),
        ('Observation (UTC epoch seconds)', now),
        ('Declared-time trade eligibility only', specification.trade_eligible_at(now)),
    ]
    attribute_rows = ''.join(row(name, value) for name, value in meta['commodityAttributes'].items())
    return ('<section aria-labelledby="mint-declaration-title">'
        '<h2 id="mint-declaration-title">Whole receipt and bill of lading declaration</h2>'
        '<p role="status">Declaration candidate only. Mint and asset validity are not attested. '
        'Time eligibility alone is not permission to trade.</p><dl>'
        + ''.join(row(label, value) for label, value in fields) + '</dl>'
        '<h3>Applicable commodity attributes</h3><dl>' + attribute_rows + '</dl>'
        '<h3>Bill of lading terms</h3><pre>' + esc(meta['billTerms']) + '</pre>'
        '<p>EX transfers the bill of lading. Pickup, transport, warehouse-out and NFT burning '
        'are not EX completion steps. Oracle consumes the declared voucher and records the '
        'single authoritative registration fact. This declaration view is not a second receipt.</p>'
        '<p>No legal or institutional endorsement is asserted. Only opaque non-secret mappings '
        'are displayed; controlled encrypted storage remains outside this view.</p></section>')
