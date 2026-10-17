"""Unsigned human review workspace over the existing TradeIntent contract.

Never signs, submits, grants wallet authority, matches, locks funds or trades.
The original wallet integration remains the only signing/execution boundary.
"""
from html import escape
import json
import re
import secrets
from urllib.parse import parse_qs

from .errors import DomainError
from .model import TradeIntent, WHOLE_RECEIPT_UNITS
from .workbench import WorkbenchHandler, WorkbenchServer, MAX_BODY

FIELDS = ('intentId', 'side', 'signer', 'counterparty', 'limitPrice',
          'quoteAsset', 'nonce', 'expiresAt', 'authorizationId')


def integer_text(value):
    if not isinstance(value, str) or re.fullmatch(r'[0-9]{1,78}', value) is None:
        raise ValueError('exact non-negative integer text required')
    return int(value)


def parse_draft_form(raw):
    form = parse_qs(raw.decode('utf-8'), strict_parsing=True, keep_blank_values=True)
    if set(form) != set(FIELDS) | {'csrf'} or any(len(v) != 1 for v in form.values()):
        raise ValueError('exact single draft fields required; signatures and outcomes are not accepted')
    return {key: value[0] for key, value in form.items()}


def preview_draft(binding, fields):
    if type(fields) is not dict or set(fields) != set(FIELDS):
        raise ValueError('exact unsigned draft fields required')
    if any(not isinstance(value, str) or len(value) > 256 for value in fields.values()):
        raise ValueError('bounded text fields required')
    receipt = binding.exchange.receipt(binding.receipt_id)
    intent = TradeIntent(intent_id=fields['intentId'], side=fields['side'],
        signer=fields['signer'], asset=receipt.asset,
        limit_price=integer_text(fields['limitPrice']), quote_asset=fields['quoteAsset'],
        units=WHOLE_RECEIPT_UNITS, nonce=integer_text(fields['nonce']),
        expires_at=integer_text(fields['expiresAt']),
        authorization_id=fields['authorizationId'], counterparty=fields['counterparty'] or None)
    return {'schema': '8415ex-unsigned-intent-review/1', 'receiptId': binding.receipt_id,
            'source': dict(binding.run), 'terms': intent.signed_terms,
            'domainDigest': intent.digest, 'signature': 'NOT_REQUESTED',
            'walletAuthorization': 'NOT_CHECKED', 'expiryNow': 'NOT_CHECKED',
            'matching': 'NOT_RUN', 'funding': 'NOT_RUN', 'execution': 'NOT_RUN',
            'meaning': 'unsigned proposed terms only; digest is the existing local domain digest, not a wallet signing ABI or authorization'}


def render_form(csrf, preview=None):
    controls = []
    for field in FIELDS:
        if field == 'side':
            controls.append('<label>Side <select name="side"><option value="sell">Sell</option>'
                            '<option value="buy">Buy</option></select></label>')
        else:
            optional = field == 'counterparty'
            maximum = '78' if field in ('limitPrice', 'nonce', 'expiresAt') else '128'
            controls.append('<label>' + field + ' <input name="' + field + '" maxlength="' + maximum
                            + '"' + ('' if optional else ' required') + '></label>')
    result = '' if preview is None else '<h3>Unsigned proposed terms</h3><pre>' + escape(
        json.dumps(preview, sort_keys=True, indent=2)) + '</pre>'
    return ('<h2>Review one unsigned intent</h2><p>Seller and buyer enter their own terms separately. '
            'This form does not connect a wallet, request a signature, submit an intent, pair orders, '
            'lock escrow or trade. It is an optional review aid, not an additional approval gate.</p>'
            '<p>The asset and chain are taken from this runtime receipt, and quantity is exactly one '
            'whole receipt. Price uses integer smallest units; expiry uses Unix seconds. No price or '
            'counterparty is chosen automatically. Each segment buyer bears its corresponding gas. '
            'Wallet authority, nonce availability, current expiry and execution conditions are not checked here.</p>'
            '<form method="post" action="/intent-preview" autocomplete="off">'
            '<input type="hidden" name="csrf" value="' + escape(csrf, quote=True) + '">'
            + ''.join(controls) + '<button type="submit">Preview unsigned terms only</button></form>'
            + result)


class IntentWorkbenchHandler(WorkbenchHandler):
    def native_page(self, name):
        body = super().native_page(name)
        if name == 'authorization':
            body = body.replace('<main>', '<main><p><a href="/intent-draft">Review an unsigned buy or sell intent</a></p>', 1)
        return body

    def draft_page(self, preview=None):
        body = super().native_page('authorization')
        return body.replace('</main>', render_form(self.server.csrf, preview) + '</main>', 1)

    def do_GET(self):
        if self.path != '/intent-draft':
            return super().do_GET()
        if not self.host_ok():
            self.send_body(421, 'host refused')
            return
        try:
            self.send_body(200, self.draft_page())
        except (KeyError, DomainError):
            self.send_body(400, 'receipt observation unavailable')

    def do_POST(self):
        if self.path != '/intent-preview':
            return super().do_POST()
        if not self.host_ok() or self.headers.get('Origin') != self.server.origin:
            self.send_body(403, 'same-origin request required')
            return
        try:
            if self.headers.get('Transfer-Encoding') is not None or self.headers.get('Content-Type') != 'application/x-www-form-urlencoded':
                raise ValueError('bounded plain form required')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY:
                raise ValueError('bounded body required')
            raw = self.rfile.read(length)
            if len(raw) != length:
                self.close_connection = True
                raise ValueError('incomplete body')
            fields = parse_draft_form(raw)
            csrf = fields.pop('csrf')
            if not csrf.isascii() or not secrets.compare_digest(csrf, self.server.csrf):
                self.send_body(403, 'request token refused')
                return
            preview = preview_draft(self.server.binding, fields)
            self.send_body(200, self.draft_page(preview))
        except TimeoutError:
            self.close_connection = True
            self.send_body(408, 'draft request timed out; no operation submitted')
        except (ValueError, UnicodeError, KeyError, DomainError):
            self.send_body(400, 'unsigned draft fields refused; no operation submitted')


class IntentWorkbenchServer(WorkbenchServer):
    def __init__(self, binding, port=0, commit=None, tree=None):
        super().__init__(binding, port=port, commit=commit, tree=tree)
        self.RequestHandlerClass = IntentWorkbenchHandler
