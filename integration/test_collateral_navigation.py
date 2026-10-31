"""Source-only product navigation to original mounted collateral routes."""
from html.parser import HTMLParser
import unittest
from urllib.parse import parse_qs,urlsplit
from exchange.collateral_scenario import WORDS
from exchange.market_page import render_market,render_terminal
from integration import test_simulation_collateral_continuation as mounted

class ProductNav(HTMLParser):
    def __init__(self,html):
        super().__init__();self.links=[];self.feed(html)
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="a" and a.get("class")=="collateral-entry":self.links.append(a["href"])

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
        status,_,raw=original.request("/terminal?lang=fr&nft="+key+"&currency=local-test-quote&q=context")
        self.assertEqual(status,200);links=ProductNav(raw.decode()).links;self.assertEqual(len(links),1)
        target=parse_qs(urlsplit(links[0]).query)
        self.assertEqual(target,{"lang":["fr"],"target":[key]})
        status,_,body=original.request(links[0]);self.assertEqual(status,200)
        self.assertIn(('value="'+key+'" selected').encode(),body)
        self.assertEqual(original.s.history.recent(),[])
    def test_renderer_does_not_invent_unmounted_collateral_route_or_accept_truthy_flag(self):
        self.assertEqual(ProductNav(render_market([],{"status":"not-connected"},"en")).links,[])
        self.assertEqual(ProductNav(render_market([],{"status":"not-connected"},"en",collateral_available=True)).links,["/collateral?lang=en"])
        for bad in ("yes",1,None):
            with self.assertRaises(ValueError):render_market([],{"status":"not-connected"},"en",collateral_available=bad)
            with self.assertRaises(ValueError):render_terminal({},[],None,None,"en",nft_key="0"*64,collateral_available=bad)
