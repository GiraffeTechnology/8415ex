"""Actual loopback HTTP journeys for the synthetic demo, not real provider UI acceptance."""
from contextlib import contextmanager
import copy
import http.client
import json
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from exchange import demo_ui
from scenarios.harness import Scenario

@contextmanager
def running():
    server = demo_ui.DemoServer(commit="a" * 40, tree="b" * 40)
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    worker.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        worker.join(2)

def request(server, method, path, body=None, **extra):
    headers = {"Host": server.origin.removeprefix("http://")}
    if method == "POST":
        headers.update({"Origin": server.origin, "Content-Type": "application/x-www-form-urlencoded"})
    headers.update(extra)
    connection = http.client.HTTPConnection(*server.server_address[:2], timeout=3)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read().decode()
    finally:
        connection.close()

def post(server, scenario="DEMO-01", **extra):
    return request(server, "POST", "/simulate",
                   urlencode({"csrf": server.csrf, "scenario": scenario}), **extra)

class InteractiveDemoJourney(unittest.TestCase):
    def test_six_scenarios_have_executed_facts_and_matching_html_and_json(self):
        with running() as server:
            self.assertEqual(len(server.runs), 0)
            status, _, home = request(server, "GET", "/")
            self.assertEqual(status, 200)
            self.assertIn("Run simulation", home)
            self.assertIn("no real wallet signing", home)
            for scenario in demo_ui.DEMOS:
                with self.subTest(scenario=scenario.scenario_id, path=scenario.main_path):
                    status, headers, _ = post(server, scenario.scenario_id)
                    self.assertEqual(status, 303)
                    location = headers["Location"]
                    key = location.split("id=")[1]
                    stored = server.runs[key]
                    status, _, raw = request(server, "GET", "/evidence?id=" + key)
                    self.assertEqual(status, 200)
                    record = json.loads(raw)
                    self.assertEqual(record, demo_ui.run_record(stored))
                    self.assertEqual(record["evidenceKind"], "SIMULATION_PUBLIC_PROJECTION")
                    self.assertEqual(record["schema"], "8415ex-public-demo/2")
                    self.assertNotIn("accounts", record["report"]["scenarios"][0]["setup"])
                    self.assertTrue(stored["report"]["scenarios"][0]["setup"]["accounts"])
                    result = record["report"]["scenarios"][0]
                    self.assertEqual(result["scenarioId"], scenario.scenario_id)
                    self.assertEqual(result["mainPath"], scenario.main_path)
                    self.assertTrue(result["passed"], result)
                    self.assertTrue(result["steps"])
                    self.assertTrue(result["setup"]["prices"])
                    self.assertTrue(result["setup"]["gasConditions"])
                    self.assertGreater(result["counts"]["passed"], 0)
                    self.assertGreater(result["counts"]["not-run"], 0)
                    self.assertEqual(set(record["realEvidence"].values()), {"NOT_RUN"})
                    before = copy.deepcopy(stored)
                    for index in range(len(result["steps"]) + 1):
                        status, _, page = request(server, "GET", location + "&step=" + str(index))
                        self.assertEqual(status, 200)
                        self.assertIn("Expected and observed assertions", page)
                        self.assertIn("NOT_RUN", page)
                        self.assertIn("synthetic", page)
                        self.assertIn("LOCAL SIMULATION", page)
                        self.assertIn(key, page)
                    self.assertEqual(before, server.runs[key])
            self.assertEqual(len(server.runs), 6)

    def test_cross_origin_host_and_token_cannot_execute(self):
        with running() as server:
            self.assertEqual(post(server, Origin="http://attacker.invalid")[0], 403)
            self.assertEqual(post(server, Host="attacker.invalid")[0], 403)
            body = urlencode({"csrf": "wrong", "scenario": "DEMO-01"})
            self.assertEqual(request(server, "POST", "/simulate", body)[0], 403)
            self.assertEqual(request(server, "GET", "/", Host="attacker.invalid")[0], 421)
            self.assertEqual(len(server.runs), 0)

    def test_outcome_injection_unknown_scenario_and_bad_observation_refused(self):
        with running() as server:
            injected = urlencode({"csrf": server.csrf, "scenario": "DEMO-01", "passed": "true"})
            self.assertEqual(request(server, "POST", "/simulate", injected)[0], 400)
            self.assertEqual(post(server, "UNKNOWN")[0], 400)
            self.assertEqual(request(server, "POST", "/simulate", "x" * 2049)[0], 400)
            self.assertEqual(len(server.runs), 0)
            _, headers, _ = post(server)
            self.assertEqual(request(server, "GET", headers["Location"] + "&step=-1")[0], 400)
            self.assertEqual(request(server, "GET", headers["Location"] + "&step=99999")[0], 400)
            self.assertEqual(request(server, "GET", "/evidence?id=missing")[0], 404)
            self.assertEqual(len(server.runs), 1)

    def test_failure_is_visible_and_html_escaped_without_becoming_pass(self):
        def broken(recorder):
            recorder.step("<script>unsafe</script>", observed="<img src=x>")
            recorder.expect("injected mismatch", ("T-36",), "expected", "actual")
            raise RuntimeError("synthetic failure")
        scenario = Scenario("DEMO-01", "<script>title</script>", ("T-36",), "REG_DIRECT", broken, prd_version="1.5")
        with patch.object(demo_ui, "DEMOS", (scenario,)), running() as server:
            _, headers, _ = post(server)
            key = headers["Location"].split("id=")[1]
            result = server.runs[key]["report"]["scenarios"][0]
            self.assertFalse(result["passed"])
            self.assertIn("synthetic failure", result["error"])
            _, _, page = request(server, "GET", headers["Location"] + "&step=1")
            self.assertIn("LOCAL FAILURE", page)
            self.assertNotIn("&lt;script&gt;", page)
            self.assertNotIn("<script>", page)
            self.assertNotIn("<img src=x>", page)
            self.assertIn("Original run error retained privately", page)
            self.assertNotIn("synthetic failure", page)

    def test_history_is_bounded_and_old_run_does_not_reexecute(self):
        with running() as server:
            # Exercise eviction without rerunning an unchanged domain scenario 17 times.
            report = {"allPassed": True, "scenarios": [{"scenarioId": "DEMO-01"}]}
            with patch.object(demo_ui, "run_all", return_value=report) as execute:
                keys = [server.simulate("DEMO-01")["runId"] for _ in range(17)]
                self.assertEqual(execute.call_count, 17)
            self.assertEqual(len(server.runs), 16)
            self.assertNotIn(keys[0], server.runs)
            self.assertEqual(request(server, "GET", "/evidence?id=" + keys[0])[0], 404)

    def test_non_loopback_and_incomplete_source_identity_refused(self):
        with self.assertRaises(ValueError):
            demo_ui.DemoServer(host="0.0.0.0")
        with self.assertRaises(ValueError):
            demo_ui.DemoServer(commit="short")

    def test_non_ascii_csrf_returns_stable_refusal_without_run(self):
        with running() as server:
            body = urlencode({"csrf": "\u4e2d\u6587", "scenario": "DEMO-01"})
            self.assertEqual(request(server, "POST", "/simulate", body)[0], 403)
            self.assertEqual(len(server.runs), 0)

    def test_incomplete_body_times_out_without_executing(self):
        import socket
        with running() as server:
            connection = socket.create_connection(server.server_address[:2], timeout=4)
            try:
                request_bytes = ("POST /simulate HTTP/1.1\r\nHost: "
                                 + server.origin.removeprefix("http://")
                                 + "\r\nOrigin: " + server.origin
                                 + "\r\nContent-Type: application/x-www-form-urlencoded"
                                 + "\r\nContent-Length: 100\r\n\r\nx=1").encode()
                connection.sendall(request_bytes)
                response = http.client.HTTPResponse(connection)
                response.begin()
                self.assertEqual(response.status, 408)
                response.read()
                self.assertEqual(len(server.runs), 0)
            finally:
                connection.close()

    def test_early_eof_refuses_short_body_before_parsing_or_simulation(self):
        import socket
        with running() as server:
            bodies = (urlencode({"csrf": server.csrf, "scenario": "DEMO-01"}).encode(),
                      json.dumps({"csrf": server.csrf, "scenario": "DEMO-01"}).encode())
            for body in bodies:
                with self.subTest(body=body), patch.object(server, "simulate", wraps=server.simulate) as execute, patch.object(demo_ui, "parse_qs", wraps=demo_ui.parse_qs) as parse:
                    connection = socket.create_connection(server.server_address[:2], timeout=3)
                    try:
                        headers = ("POST /simulate HTTP/1.1\r\nHost: "
                                   + server.origin.removeprefix("http://")
                                   + "\r\nOrigin: " + server.origin
                                   + "\r\nContent-Type: application/x-www-form-urlencoded"
                                   + "\r\nContent-Length: " + str(len(body) + 10) + "\r\n\r\n").encode()
                        connection.sendall(headers + body)
                        connection.shutdown(socket.SHUT_WR)
                        response = http.client.HTTPResponse(connection)
                        response.begin()
                        response_body = response.read().decode()
                        self.assertEqual(response.status, 400)
                        self.assertEqual(response_body,
                            "simulation request refused; original diagnostic remains private")
                        self.assertNotIn("incomplete request body", response_body)
                        self.assertNotIn(server.csrf, response_body)
                        self.assertEqual(response.getheader("Cache-Control"), "no-store")
                        parse.assert_not_called()
                        execute.assert_not_called()
                        self.assertEqual(len(server.runs), 0)
                    finally:
                        connection.close()
