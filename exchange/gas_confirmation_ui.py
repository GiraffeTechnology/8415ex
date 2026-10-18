"""Server-rendered gas disclosure and existing-wallet confirmation boundary."""
from html import escape
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from .gas_budget import GasQuote, BuyerConfirmation, GasBudgetRefused
from .gas_disclosure_locales import WORDS


def _escape(value):
    return escape(str(value), quote=True)


class GasConfirmationPage:
    """Bind a trusted existing session to a live quote and wallet adapter.

    This controller never accepts buyer, grant, action identity or fee values
    from the form. It does not implement authentication, wallet I/O or sending.
    """
    def __init__(self, current_quote, confirm_with_wallet, buyer, action_digest,
                 wallet_grant, post_path, validate_csrf):
        if not callable(current_quote) or not callable(confirm_with_wallet):
            raise GasBudgetRefused('live quote resolver and existing wallet adapter required')
        for value in (buyer, action_digest, wallet_grant):
            if type(value) is not str or not value.strip():
                raise GasBudgetRefused('trusted existing session binding required')
        if (type(post_path) is not str or not post_path.startswith('/')
                or post_path.startswith('//') or chr(92) in post_path
                or any(ord(c) < 32 for c in post_path)):
            raise GasBudgetRefused('explicit same-origin POST route required')
        if not callable(validate_csrf):
            raise GasBudgetRefused('existing application CSRF verifier required')
        self.validate_csrf = validate_csrf
        self.current_quote = current_quote
        self.confirm_with_wallet = confirm_with_wallet
        self.buyer = buyer
        self.action_digest = action_digest
        self.wallet_grant = wallet_grant
        self.post_path = post_path

    def _quote(self, now):
        if type(now) is not int or now < 0:
            raise GasBudgetRefused('trusted current time required')
        quote = self.current_quote()
        if not isinstance(quote, GasQuote):
            raise GasBudgetRefused('current typed quote unavailable')
        if not quote.quoted_at <= now < quote.valid_until:
            raise GasBudgetRefused('quote expired or not yet valid; refresh before confirming')
        return quote

    def render(self, now, csrf_token, locale="en"):
        if type(locale) is not str or locale not in WORDS:
            raise GasBudgetRefused('supported disclosure locale required')
        words = WORDS[locale]
        quote = self._quote(now)
        if type(csrf_token) is not str or not csrf_token:
            raise GasBudgetRefused('existing application CSRF token required')
        data = quote.disclosure()
        target = self.post_path
        if locale != 'en':
            route = urlsplit(target)
            query = parse_qsl(route.query, keep_blank_values=True)
            if any(key == 'lang' for key, _ in query):
                raise GasBudgetRefused('confirmation locale already bound')
            target = urlunsplit((route.scheme, route.netloc, route.path,
                                urlencode(query + [('lang', locale)]), route.fragment))
        rows = ''.join('<tr><td>' + '</td><td>'.join(_escape(value) for value in (
            sample.sample_id, sample.fee_wei, sample.observed_at, sample.block_number,
            sample.source, sample.raw_sha256)) + '</td></tr>' for sample in quote.samples)
        cap = _escape(data['cap']['ETH']) + ' ETH / $' + _escape(data['cap']['USD']) + ' USD'
        median = _escape(data['median']['ETH']) + ' ETH / $' + _escape(data['median']['USD']) + ' USD'
        values = (
            ('maximum', cap), ('median', median),
            ('quote', _escape(quote.quote_id) + ' / ' + _escape(quote.version)),
            ('actions', _escape(', '.join(quote.actions))), ('chain', _escape(quote.chain_id)),
            ('fxTime', _escape(quote.rate_observed_at)),
            ('fxSource', _escape(quote.rate_source) + ' / ' + _escape(quote.usd_micro_per_eth)),
            ('expires', _escape(quote.valid_until)),
        )
        definitions = ''.join('<dt>' + _escape(words[key]) + '</dt><dd>' + value + '</dd>'
                              for key, value in values)
        headers = ''.join('<th>' + _escape(words[key]) + '</th>'
                          for key in ('sample', 'wei', 'time', 'block', 'source', 'raw'))
        def hidden(name, value):
            return '<input type="hidden" name="' + name + '" value="' + _escape(value) + '">'
        return ('<section lang="' + locale + '" aria-labelledby="gas-quote-heading">'
            '<h2 id="gas-quote-heading">' + _escape(words['heading']) + '</h2><dl>'
            + definitions + '</dl><p>' + _escape(words['explanation']) + '</p>'
            '<details><summary>' + _escape(words['evidence']) + ' ('
            + _escape(len(quote.samples)) + ' ' + _escape(words['samples']) + ')</summary>'
            '<p>sorted-P50-middle-or-two-middle-mean; ' + _escape(words['window']) + ' '
            + _escape(quote.window_start) + ' ' + _escape(words['to']) + ' '
            + _escape(quote.window_end) + '; ' + _escape(words['scope']) + ' '
            + _escape(quote.scope) + '; FX SHA-256 ' + _escape(quote.rate_sha256)
            + '</p><table><thead><tr>' + headers + '</tr></thead><tbody>'
            + rows + '</tbody></table></details>'
            '<form method="post" action="' + _escape(target) + '">'
            + hidden('csrf', csrf_token) + hidden('quoteId', quote.quote_id)
            + hidden('version', quote.version) + hidden('quoteDigest', quote.digest)
            + '<label><input type="checkbox" name="accepted" value="yes" required>'
            + _escape(words['consent']) + '</label><button type="submit">'
            + _escape(words['continue']) + '</button></form></section>')

    def submit(self, fields, now):
        expected = {'csrf', 'quoteId', 'version', 'quoteDigest', 'accepted'}
        if (type(fields) is not dict or set(fields) != expected
                or any(type(value) is not str for value in fields.values())):
            raise GasBudgetRefused('exact scalar form fields required')
        if self.validate_csrf(fields['csrf']) is not True:
            raise GasBudgetRefused('existing application CSRF verification refused')
        quote = self._quote(now)
        if (fields['accepted'] != 'yes' or fields['quoteId'] != quote.quote_id
                or fields['version'] != str(quote.version) or fields['quoteDigest'] != quote.digest):
            raise GasBudgetRefused('current quote and explicit buyer consent required')
        confirmation = self.confirm_with_wallet(quote, self.buyer, self.action_digest,
                                                self.wallet_grant, now)
        if not isinstance(confirmation, BuyerConfirmation):
            raise GasBudgetRefused('verified wallet confirmation unavailable')
        if (confirmation.quote_digest != quote.digest or confirmation.buyer != self.buyer
                or confirmation.action_digest != self.action_digest
                or confirmation.wallet_grant != self.wallet_grant
                or type(confirmation.confirmed_at) is not int
                or not quote.quoted_at <= confirmation.confirmed_at <= now
                or type(confirmation.proof_reference) is not str
                or not confirmation.proof_reference.strip()):
            raise GasBudgetRefused('wallet confirmation does not bind the displayed quote')
        if self._quote(now).digest != quote.digest:
            raise GasBudgetRefused('quote changed during confirmation; do not send')
        return confirmation


