"""Source-only product navigation to original mounted collateral routes."""
from html.parser import HTMLParser
import unittest
from urllib.parse import parse_qs,urlsplit
from exchange.collateral_scenario import WORDS
from exchange.market_page import render_market,render_terminal
from integration import test_simulation_collateral_continuation as mounted

class ProductNav(HTMLParser):
    def __init__(self,html):
        super().__init__();self.links=[];self.collateral=[];self.all_links=[];self.feed(html)
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="a":
            self.all_links.append(a.get("href", ""))
            if urlsplit(a.get("href", "")).path=="/collateral":self.collateral.append(a["href"])
            if a.get("class")=="collateral-entry":self.links.append(a["href"])

class CollateralProductNavigation(unittest.TestCase):
    def setUp(self):
        self.original=mounted.MountedCollateralSimulation("runTest");self.original.setUp();self.addCleanup(self.original.doCleanups)
    def test_six_locale_market_header_links_only_original_mounted_route_without_history_write(self):
        original=self.original;before=original.s.history.recent()
        for lang in WORDS:
            status,_,raw=original.request("/market?lang="+lang)
            self.assertEqual(status,200);links=ProductNav(raw.decode()).links
            self.assertEqual(links,["/collateral?lang="+lang])
            status,_,body=original.request(links[0])
            self.assertEqual(status,200);self.assertIn(b"LOCAL_SIMULATION",body)
        self.assertEqual(original.s.history.recent(),before)
    def test_selected_terminal_header_carries_exact_original_target_and_locale_to_get(self):
        original=self.original;key=original.s.nft_directory.choices()[0]["nftKey"]
        for lang in WORDS:
            with self.subTest(locale=lang):
                status,_,raw=original.request("/terminal?lang="+lang+"&nft="+key+"&currency=local-test-quote&q=context&side=sell")
                self.assertEqual(status,200);nav=ProductNav(raw.decode())
                self.assertEqual(len(nav.links),1)
                self.assertEqual(nav.collateral,nav.links)
                target=parse_qs(urlsplit(nav.links[0]).query)
                self.assertEqual(target,{"lang":[lang],"target":[key]})
                self.assertTrue(any(urlsplit(href).path=="/evidence" for href in nav.all_links))
                evidence=next(href for href in nav.all_links if urlsplit(href).path=="/evidence")
                self.assertEqual(parse_qs(urlsplit(evidence).query),{} if lang=="en" else {"lang":[lang]})
                self.assertTrue(any(urlsplit(href).path=="/nft" for href in nav.all_links))
                status,_,body=original.request(nav.links[0]);self.assertEqual(status,200)
                self.assertIn(('value="'+key+'" selected').encode(),body)
        self.assertEqual(original.s.history.recent(),[])

    def test_native_receipt_keeps_its_only_legacy_collateral_route(self):
        for lang in WORDS:
            with self.subTest(locale=lang):
                status,_,raw=self.original.request("/receipt?lang="+lang)
                self.assertEqual(status,200);nav=ProductNav(raw.decode())
                self.assertEqual(nav.links,[])
                self.assertEqual(nav.collateral,["/collateral?lang="+lang])
                self.assertTrue(any(urlsplit(href).path=="/evidence" for href in nav.all_links))
                evidence=next(href for href in nav.all_links if urlsplit(href).path=="/evidence")
                self.assertEqual(parse_qs(urlsplit(evidence).query),{} if lang=="en" else {"lang":[lang]})
        self.assertEqual(self.original.s.history.recent(),[])

    def test_unmounted_terminal_keeps_no_invented_collateral_entry(self):
        from integration.test_terminal_ui import TerminalUI
        original=TerminalUI("runTest");original.setUp()
        try:
            status,body=original.get("/terminal?lang=en")
            self.assertEqual(status,200)
            self.assertEqual(ProductNav(body).collateral,[])
        finally:
            original.tearDown()

    def test_renderer_does_not_invent_unmounted_collateral_route_or_accept_truthy_flag(self):
        self.assertEqual(ProductNav(render_market([],{"status":"not-connected"},"en")).links,[])
        self.assertEqual(ProductNav(render_market([],{"status":"not-connected"},"en",collateral_available=True)).links,["/collateral?lang=en"])
        for bad in ("yes",1,None):
            with self.assertRaises(ValueError):render_market([],{"status":"not-connected"},"en",collateral_available=bad)
            with self.assertRaises(ValueError):render_terminal({},[],None,None,"en",nft_key="0"*64,collateral_available=bad)
