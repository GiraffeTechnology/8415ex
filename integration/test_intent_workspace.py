"""Initial unsigned UI contracts; authored only, no real signing or provider."""
import io
import unittest
from types import SimpleNamespace
from urllib.parse import urlencode

from exchange import fixtures as F
from exchange.intent_workspace import (IntentWorkbenchHandler, integer_text,
    parse_draft_form, preview_draft, render_form)
from exchange.workbench import RuntimeBinding


def fields(side='sell'):
    return dict(intentId='draft-'+side, side=side, signer=F.A if side=='sell' else F.B,
        counterparty=F.B if side=='sell' else F.A, limitPrice='1000000',
        quoteAsset=F.QUOTE_ASSET, nonce='1', expiresAt='1700800000',
        authorizationId='auth-draft-'+side)


def binding():
    exchange, _ = F.minted()
    return RuntimeBinding(exchange, 'rcpt-8415-0001', run={'runId':'fixture-review'})


class IntentWorkspaceContracts(unittest.TestCase):
    def test_preview_keeps_domain_untouched_and_never_authorizes(self):
        runtime = binding()
        before = runtime.exchange.receipt_view(runtime.receipt_id)
        draft = preview_draft(runtime, fields())
        self.assertEqual(runtime.exchange.receipt_view(runtime.receipt_id), before)
        self.assertEqual(draft['terms']['limitPrice'], '1000000')
        self.assertEqual(draft['terms']['units'], 1)
        self.assertEqual(draft['terms']['contract'], F.CONTRACT)
        self.assertEqual(draft['walletAuthorization'], 'NOT_CHECKED')
        self.assertEqual(draft['signature'], 'NOT_REQUESTED')
        self.assertEqual(draft['execution'], 'NOT_RUN')
        self.assertIsNone(runtime.gateway)

    def test_sides_and_limits_are_not_implicitly_paired(self):
        runtime = binding()
        seller = fields('sell'); buyer = fields('buy'); buyer['limitPrice'] = '1000001'
        sell_review = preview_draft(runtime, seller)
        buy_review = preview_draft(runtime, buyer)
        self.assertEqual(sell_review['terms']['limitPrice'], '1000000')
        self.assertEqual(buy_review['terms']['limitPrice'], '1000001')
        self.assertEqual(buy_review['terms']['side'], 'buy')
        self.assertNotEqual(sell_review['domainDigest'], buy_review['domainDigest'])
        self.assertEqual(buy_review['matching'], 'NOT_RUN')

    def test_integer_input_does_not_round_or_coerce(self):
        for bad in ('1.0','1e6','-1','+1',' 1','1 ','','1'*79,'\u0661',True,1,None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                integer_text(bad)
        self.assertEqual(integer_text('00012'), 12)

    def test_extra_asset_signature_and_duplicate_fields_refused(self):
        runtime = binding()
        for key in ('units','chainId','contract','signature','outcome'):
            invalid = fields(); invalid[key] = 'untrusted'
            with self.subTest(key=key), self.assertRaises(ValueError):
                preview_draft(runtime, invalid)
        raw = urlencode(dict(fields(), csrf='request')).encode()
        self.assertEqual(parse_draft_form(raw)['csrf'], 'request')
        for extra in (b'&side=buy',b'&signature=untrusted',b'&csrf=other'):
            with self.assertRaises(ValueError):
                parse_draft_form(raw+extra)

    def test_render_escapes_source_and_request_token(self):
        draft = preview_draft(binding(), fields())
        draft['source']['label'] = '<script>untrusted</script>'
        html = render_form('\"<unsafe>', draft)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&quot;&lt;unsafe&gt;', html)
        self.assertIn('Preview unsigned terms only', html)
        self.assertIn('not an additional approval gate', html)

    def test_origin_and_csrf_refused_before_preview(self):
        replies = []
        runtime = binding()
        raw = urlencode(dict(fields(), csrf='incorrect')).encode()
        request = SimpleNamespace(path='/intent-preview',
            server=SimpleNamespace(origin='http://127.0.0.1:1234', csrf='correct', binding=runtime),
            headers={'Origin':'http://127.0.0.1:1234','Content-Type':'application/x-www-form-urlencoded',
                     'Content-Length':str(len(raw))}, rfile=io.BytesIO(raw),
            host_ok=lambda: True, send_body=lambda status,body: replies.append((status,body)))
        IntentWorkbenchHandler.do_POST(request)
        self.assertEqual(replies[-1][0],403)
        request.headers['Origin'] = 'http://foreign.invalid'
        IntentWorkbenchHandler.do_POST(request)
        self.assertEqual(replies[-1][0],403)
        self.assertEqual(replies[-1][1],'same-origin request required')


if __name__ == '__main__':
    unittest.main()
