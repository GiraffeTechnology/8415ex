"""Changed original simulation route and failure continuation only."""
from copy import deepcopy
from datetime import timedelta
from html.parser import HTMLParser
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from exchange.persistent_simulation_serve import create_simulation_server
from exchange.eia_wti_spot_reader import SpotSourceDeferred
from integration import test_reference_continuation as original_continuation

class FailedReferenceContinuation(unittest.TestCase):
    def setUp(self):
        self.original=original_continuation.ReferenceContinuation("runTest")
        self.original.setUp()
        self.data=deepcopy(self.original.data)
        o=self.data["observation"]
        o.update(status="unavailable",retainedValue=True,lastAttemptAt="2026-10-17T00:00:30Z")
        o["events"].append({"attemptedAt":o["lastAttemptAt"],"result":"unavailable"})
        o["transportObservation"]["value"]={"status":"unavailable","code":"SPOT_SOURCE_READ_UNAVAILABLE","retainedSource":True}
        self.data["capturedAt"]="2026-10-17T00:00:35Z"
        self.original.time+=timedelta(seconds=35)
    def test_failure_value_events_transport_and_full_capture_backoff_survive_without_fetch(self):
        r,f,result=self.original.resume(self.data)
        try:
            restored=f.snapshot()
            for key in ("status","retainedValue","lastAttemptAt","lastSuccessful","fetchedAt","price","events","transportObservation"):
                self.assertEqual(restored[key],self.data["observation"][key])
            self.assertEqual(result["firstRefreshNotBefore"],"2026-10-17T00:00:55Z")
            with self.assertRaises(SpotSourceDeferred):r(self.original.policy)
            f.start();f.close()
            self.assertEqual(len(self.original.calls),1)
            self.assertEqual(f.snapshot()["events"],self.data["observation"]["events"])
        finally:f.close()
    def test_failed_continuation_rejects_inconsistent_or_unbound_failure_before_network(self):
        variants=[]
        for key,value in (("retainedValue",False),("lastSuccessful","2026-10-17T00:00:30Z"),("lastAttemptAt","2026-10-16T23:59:00Z"),("price","900")):
            row=deepcopy(self.data);row["observation"][key]=value;variants.append(row)
        row=deepcopy(self.data);row["observation"]["transportObservation"]["value"]["retainedSource"]=False;variants.append(row)
        row=deepcopy(self.data);row["observation"]["events"][-1]["result"]="read";variants.append(row)
        row=deepcopy(self.data);row["observation"]["sourceEvidence"]["rawResponseSHA256"]="0"*64;variants.append(row)
        for row in variants:
            with self.subTest(row=row),self.assertRaises(ValueError):self.original.resume(row)
        self.assertEqual(len(self.original.calls),1)
    def test_failure_backoff_larger_than_poll_is_not_shortened(self):
        self.original.ports_original=self.original.ports
        def ports():
            r,f=self.original.ports_original();r._failure=70;return r,f
        self.original.ports=ports
        r,f,result=self.original.resume(self.data)
        try:self.assertEqual(result["firstRefreshNotBefore"],"2026-10-17T00:01:45Z")
        finally:f.close()

class MountedCollateralSimulation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.s=create_simulation_server(state_path=Path(self.temp.name)/"history.sqlite",port=0,commit="a"*40,tree="b"*40,registration_path="REG_DIRECT")
        self.thread=threading.Thread(target=self.s.serve_forever,kwargs={"poll_interval":0.02},daemon=True);self.thread.start()
        def close():
            self.s.shutdown();self.thread.join(3);self.s.server_close();self.s.history.close()
        self.addCleanup(close)
    def request(self,path,method="GET",headers=None):
        c=http.client.HTTPConnection(*self.s.server_address,timeout=3)
        try:
            c.request(method,path,headers=headers or {});r=c.getresponse()
            return r.status,dict(r.getheaders()),r.read()
        finally:c.close()
    def test_original_simulation_mounts_get_selection_svg_and_retains_mode_history_and_gateway(self):
        before=self.s.history.recent()
        status,headers,body=self.request("/collateral?lang=zh-Hans&kind=crypto&asset=ETH")
        self.assertEqual(status,200);self.assertIn(b"LOCAL_SIMULATION",body);self.assertIn(b'data-direction="crypto"',body)
        self.assertIn("img-src 'self'",headers["Content-Security-Policy"])
        self.assertEqual(headers["X-EX-Runtime-Mode"],"LOCAL_SIMULATION")
        for asset in ("collateral-swap-crypto.svg","collateral-swap-receipt.svg","collateral-arrow.svg"):
            status,_,raw=self.request("/assets/"+asset);self.assertEqual(status,200);self.assertIn(b"<svg",raw)
        status,_,raw=self.request("/healthz");self.assertEqual(status,200)
        self.assertFalse(json.loads(raw)["configuredComponents"]["commandGateway"])
        self.assertEqual(self.s.history.recent(),before)
    def test_mounted_collateral_retains_strict_query_host_and_post_refusal_without_history_write(self):
        before=self.s.history.recent()
        for path in ("/collateral?kind=crypto&asset=DOGE","/collateral?kind=crypto&asset=ETH&ltv=50","/collateral?kind=crypto&kind=crypto&asset=ETH"):
            self.assertEqual(self.request(path)[0],400)
        self.assertEqual(self.request("/collateral?lang=en","POST")[0],405)
        self.assertEqual(self.request("/collateral?lang=en",headers={"Host":"different.invalid"})[0],421)
        self.assertEqual(self.s.history.recent(),before)
