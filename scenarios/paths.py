"""Per-path contract coverage for the three simulated registrar roles.

The three paths share one state machine and one adapter contract. They differ
only in the hand-off they record. Each path therefore gets its own contract
result: a pass on one path never establishes another, and this module keeps the
three results separate rather than merging them.

Nothing here is a real registration institution, an API or a business licence.
"""
from exchange import fixtures as F
from exchange.model import REGISTRATION_PATHS, Asset
from exchange.registration import RegistrationEvidence

from .harness import Scenario

RECEIPT = "rcpt-8415-0001"

#: Which path each scenario selected as its main route.
from .demos import MAIN_PATHS  # noqa: E402  (kept next to the paths it describes)


def _refusal(action):
    try:
        action()
    except Exception as problem:
        return getattr(problem, "code", type(problem).__name__)
    return "accepted"


def _contract_body(path):
    def body(recorder):
        exchange, _ = F.rollback_chain_to_d(registration_path=path)
        registrar = exchange.registrars[path]
        recorder.describe_setup(
            path=path, label=registrar.label, source=registrar.source,
            simulated=registrar.simulated,
            scenariosUsingThisPathAsMain=sorted(key for key, value in MAIN_PATHS.items()
                                                if value == path),
            accounts={"A": F.A, "B": F.B, "C": F.C, "D": F.D},
            prices={"AB": F.PRICE_AB, "BC": F.PRICE_BC, "CD": F.PRICE_CD})
        recorder.expect("the path is labelled a simulated role", ("T-10",),
                        {"simulated": True, "labelled": True, "path": path},
                        {"simulated": registrar.simulated,
                         "labelled": "simulated" in registrar.label, "path": registrar.path})

        requests = F.submit_all(exchange)
        recorder.step("one request filed per hop",
                      requests=[request.request_id for request in requests],
                      adapters=sorted({request.adapter for request in requests}))
        recorder.expect("every request goes through this one adapter", ("T-10",),
                        [path, path, path], [request.adapter for request in requests])
        acknowledgement = registrar.submit(requests[0])
        recorder.expect("the hand-off record is this path's own", ("T-10",),
                        {"accepted": True, "simulated": True, "repeated": True},
                        {"accepted": acknowledgement["accepted"],
                         "simulated": acknowledgement["simulated"],
                         "repeated": acknowledgement["repeated"]},
                        detail=str(acknowledgement["handover"]))

        _, deferred = F.confirm(exchange, requests[2], f"res-{path}-cd")
        recorder.expect("a later result defers on this path too", ("T-04", "T-10"),
                        {"disposition": "deferred", "holderPosition": 0},
                        {"disposition": deferred["disposition"],
                         "holderPosition": exchange.holder_index(RECEIPT)})
        evidence, advanced = F.confirm(exchange, requests[0], f"res-{path}-ab")
        recorder.expect("the first hop advances the confirmed prefix", ("T-10",),
                        {"disposition": "advanced", "holderPosition": 1},
                        {"disposition": advanced["disposition"],
                         "holderPosition": exchange.holder_index(RECEIPT)})
        again = exchange.apply_registration_result(evidence)
        recorder.expect("an exact repeat is idempotent", ("T-05", "T-10"),
                        {"disposition": "idempotent", "holderPosition": 1},
                        {"disposition": again["disposition"],
                         "holderPosition": exchange.holder_index(RECEIPT)})
        conflict = _refusal(lambda: F.confirm(exchange, requests[1], f"res-{path}-ab",
                                              result_version=2))
        recorder.expect("the same result id with other content conflicts", ("T-05", "T-10"),
                        "EX_REGISTRATION_CONFLICT", conflict)

        base = dict(result_id=f"res-{path}-bad", request_id=requests[1].request_id,
                    receipt_id=RECEIPT, transfer_id=requests[1].transfer_id, leg_index=1,
                    adapter=path, source=registrar.source, outcome="confirmed",
                    asset=exchange.receipt(RECEIPT).asset, observed_at=1_700_000_900)

        def forged(**changes):
            fields = dict(base)
            fields.update(changes)
            return lambda: exchange.apply_registration_result(RegistrationEvidence(**fields))

        other_path = next(name for name in REGISTRATION_PATHS if name != path)
        for name, cases, expected, probe in (
            ("a wrong network advances nothing", ("T-14", "T-10"),
             "EX_REGISTRATION_BINDING_REFUSED",
             forged(asset=Asset(1, F.CONTRACT, F.TOKEN_ID))),
            ("a wrong token advances nothing", ("T-14", "T-10"),
             "EX_REGISTRATION_BINDING_REFUSED",
             forged(asset=Asset(F.CHAIN_ID, F.CONTRACT, 4242))),
            ("an untrusted source advances nothing", ("T-14", "T-10"),
             "EX_REGISTRATION_SOURCE_REFUSED", forged(source="someone-else")),
            ("a result naming another leg advances nothing", ("T-14", "T-10"),
             "EX_REGISTRATION_BINDING_REFUSED", forged(leg_index=2)),
            ("a result from another path advances nothing", ("T-10",),
             "EX_REGISTRATION_BINDING_REFUSED", forged(adapter=other_path)),
        ):
            recorder.expect(name, cases, expected, _refusal(probe))
        recorder.expect("no refusal moved the confirmed prefix", ("T-14",),
                        1, exchange.holder_index(RECEIPT))

        cross = _refusal(lambda: exchange.registrars[other_path].submit(requests[1]))
        recorder.expect("a request filed to another path's adapter is refused", ("T-10",),
                        "EX_REGISTRATION_PATH_REFUSED", cross)
        recorder.note(f"{path} contract result is independent of the other two paths")
        recorder.not_run("real registrar integration", ("T-35", "T-36"),
                         "this path is a simulated business role; no real institution, API or "
                         "licence is involved")
    return body


PATH_CONTRACTS = tuple(
    Scenario(f"PATH-{path}", f"registrar contract coverage for {path}",
             ("T-04", "T-05", "T-10", "T-14"), path, _contract_body(path))
    for path in REGISTRATION_PATHS
)


def coverage_map():
    """Which scenarios ran on which path, and each path's own contract result."""
    return {
        "schema": "8415ex-path-coverage/1",
        "paths": list(REGISTRATION_PATHS),
        "mainPathPerScenario": dict(sorted(MAIN_PATHS.items())),
        "scenariosPerPath": {path: sorted(key for key, value in MAIN_PATHS.items()
                                          if value == path)
                             for path in REGISTRATION_PATHS},
        "contractResultPerPath": [f"PATH-{path}" for path in REGISTRATION_PATHS],
        "note": ("each path carries its own contract result; success on one path does not "
                 "establish another, and the six scenarios are not multiplied into eighteen "
                 "runs because the shared contract is covered once per path"),
    }
