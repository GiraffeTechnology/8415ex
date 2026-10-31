"""Scoped original collateral direction forms; no financing or signing."""
from html.parser import HTMLParser
import unittest
from exchange.collateral_scenario import render_collateral, WORDS
from exchange.nft_directory import NftDirectory
from integration import test_collateral_selection as original_selection

class Forms(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.forms=[]; self.current=None; self.select=None; self.feed(html)
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=="form":
            self.current={"attrs":a,"hidden":{},"options":{},"images":[]};self.forms.append(self.current)
        if self.current is None:return
        if tag=="input":self.current["hidden"][a.get("name")]=a.get("value")
        if tag=="select":self.select=a.get("name");self.current["options"][self.select]=[]
        if tag=="option":self.current["options"][self.select].append(a.get("value"))
        if tag=="img":self.current["images"].append(a.get("src"))
    def handle_endtag(self, tag):
        if tag=="form":self.current=None
        if tag=="select":self.select=None

class CollateralDirectionForms(unittest.TestCase):
    def test_empty_directory_has_separate_crypto_and_receipt_forms_without_invented_assets(self):
        d=NftDirectory((),allow_empty=True)
        for locale in WORDS:
            forms=Forms(render_collateral(d,locale)).forms
            self.assertEqual(len(forms),2)
            self.assertEqual(forms[0]["hidden"],{"lang":locale,"kind":"crypto"})
            self.assertEqual(forms[1]["hidden"],{"lang":locale,"kind":"warehouse-nft"})
            self.assertEqual(forms[0]["options"]["asset"],["","BTC","ETH"])
            self.assertEqual(forms[1]["options"]["asset"],[""])
            for f in forms:
                self.assertEqual(f["attrs"]["method"],"get")
                self.assertEqual(f["options"]["target"],[""])
            self.assertEqual(forms[0]["images"],["/assets/collateral-swap-crypto.svg","/assets/collateral-arrow.svg"])
            self.assertEqual(forms[1]["images"],["/assets/collateral-swap-receipt.svg","/assets/collateral-arrow.svg"])
    def test_original_directory_keys_are_only_in_receipt_and_target_choices(self):
        original=original_selection.CollateralSelectionTests("runTest");original.setUp()
        try:
            keys=list(original.keys); forms=Forms(render_collateral(original.server.nft_directory,
                "en",kind="warehouse-nft",asset=keys[0],target=keys[1])).forms
            self.assertEqual(forms[0]["options"]["asset"],["","BTC","ETH"])
            self.assertEqual(forms[1]["options"]["asset"],[""]+keys)
            for f in forms:self.assertEqual(f["options"]["target"],[""]+keys)
            self.assertEqual(original.original.calls,[])
        finally:original.doCleanups()

    def test_collateral_success_csp_allows_only_same_origin_images_and_no_script(self):
        original=original_selection.CollateralSelectionTests("runTest");original.setUp()
        try:
            import http.client, threading
            worker=threading.Thread(target=original.server.serve_forever,
                kwargs={"poll_interval":0.02},daemon=True);worker.start()
            c=http.client.HTTPConnection(*original.server.server_address,timeout=3)
            try:
                c.request("GET","/collateral?lang=en");r=c.getresponse();r.read()
                self.assertEqual(r.status,200);csp=r.getheader("Content-Security-Policy")
                self.assertIn("img-src 'self'",csp);self.assertIn("default-src 'none'",csp)
                self.assertNotIn("script-src",csp);self.assertNotIn("https:",csp)
            finally:c.close();original.server.shutdown();worker.join(3)
            self.assertEqual(original.original.calls,[])
        finally:original.doCleanups()
