"""Presentation for the Stage 1 status pages.

Each page renders only from the state machine's own report functions, so the UI
cannot become a second source of truth. The wording rules are part of the
requirement, not decoration:

* ``owner`` and ``holder`` are always labelled and never merged into one
  unexplained "holder";
* a filed hop reads "submitted, awaiting registrar", never "delivered";
* a confirmed prefix stays visible even while a later hop is open;
* every registration line says it is simulated;
* nothing on these pages can mark an outcome by hand.
"""
from html import escape
import re

from .model import REGISTRATION_PATHS

#: Wording for each registration status. "pending" must never read as complete.
REGISTRATION_WORDING = {
    "not-submitted": "not filed yet",
    "pending": "submitted, awaiting registrar",
    "confirmed": "registration confirmed",
    "rejected": "registrar refused this hop",
}

#: Wording for each funding status. An unsettled payment never reads as paid.
FUNDING_WORDING = {
    "not-modelled": "not modelled in this stage",
    "locked": "this leg's buyer funded its own escrow",
    "released": "released to this leg's seller",
    "refunded": "refunded to this leg's buyer",
    "release-failed": "release attempted, payment failed - still held, not refunded",
    "release-outcome-unknown": "release attempted, payment outcome unknown - being enquired, "
                              "no second payment sent",
}

PAGES = ("receipt", "authorization", "timeline", "rollback", "queue", "evidence")


def _row(label, value):
    return f"<tr><th>{escape(str(label))}</th><td>{escape(str(value))}</td></tr>"


def _table(rows):
    return "<table>" + "".join(rows) + "</table>"


def receipt_page(exchange, receipt_id, now=None, *, read_details=None, verify_details=None, verify_signature=None):
    """A complete HTML document from original-verified privacy-safe detail only.

    Direct library callers have the same boundary as the native HTTP entry.
    An absent original reader stays explicitly unavailable; raw mint declarations
    must never become a fallback for missing verified business clauses.
    """
    from .nft_detail import receipt_detail
    from .nft_detail_page import render_detail
    return render_detail(receipt_detail(exchange, receipt_id, read_details=read_details,
                         verify_details=verify_details, verify_signature=verify_signature))


def authorization_page(exchange, receipt_id, authorization_ids, now=None):
    """What each wallet actually granted. Connecting is not authorizing."""
    view = exchange.receipt_view(receipt_id, now)
    blocks = ["<h2>Authorization and trade</h2>",
              "<p>Connecting a wallet authorizes nothing by itself. Each action below is "
              "checked against the constraints that wallet signed.</p>"]
    for ordinal, authorization_id in enumerate(authorization_ids, 1):
        state = exchange.authorization_state(authorization_id, now)
        grant = exchange.authorization(authorization_id)
        blocks.append(_table([
            _row("Authorization", f"scope {ordinal}"),
            _row("Applies right now", "yes" if state["applies"] else
                 "no - original authorization checks did not pass"),
            _row("Allowed actions", ", ".join(grant.allowed_actions)),
            _row("Counterparty scope", "restricted by original grant" if grant.counterparties else "unrestricted by this grant"),
            _row("Amount bound", f"{grant.max_amount} (smallest units of {grant.quote_asset})"),
            _row("Asset", f"chain {grant.chain_id} / token {grant.asset.token_id} "
                          f"(one whole receipt)"),
            _row("Validity", f"{grant.not_before} to {grant.expires_at} (unix seconds)"),
            _row("Revoked", "yes" if grant.revoked else "no"),
        ]))
    blocks.append(_table([
        _row("Network", f"chain id {view['asset']['chainId']} - test network; no mainnet "
                        f"or real-value transaction is performed"),
        _row("Price basis", "a reproducible fixture price, not a commercial quotation"),
        _row("Gas responsibility", "each leg's buyer bears that leg's gas, including the "
                                   "rollback gas it is due to bear"),
        _row("Signed content", "the signed terms are the intent fields themselves; "
                               "changing any of them changes the digest"),
    ]))
    return "".join(blocks)


def timeline_page(exchange, receipt_id, now=None):
    """Each hop with its registration and funding state, never collapsed."""
    view = exchange.receipt_view(receipt_id, now)
    header = ("<tr><th>Leg</th><th>From</th><th>To</th><th>Price</th><th>Execution</th>"
              "<th>Registration</th><th>Funding</th><th>Rollback</th></tr>")
    rows = [header]
    for leg in view["legs"]:
        rows.append("<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in (
            leg["legIndex"], f"position {leg['legIndex']}", f"position {leg['legIndex'] + 1}",
            f"{leg['price']} {leg['quoteAsset']}",
            "trade submitted and observed locally",
            REGISTRATION_WORDING[leg["registrationStatus"]] + " (simulated)",
            FUNDING_WORDING[leg["fundingStatus"]], leg["rollbackStatus"])) + "</tr>")
    if not view["legs"]:
        rows.append("<tr><td colspan='8'>no trade yet; the origin account is "
                    "both owner and holder</td></tr>")
    note = ("<p>Registration is serial: each hop is recorded one at a time, so the "
            "holder position trails the owner position. A result for a later hop waits "
            "for the gap and is not a refusal.</p>")
    deadline = exchange.evaluate_deadline(receipt_id, now)
    stop = (f"<p>Trading window: {'open' if view['tradingOpen'] else 'closed'}; "
            f"stop-trading instant {view['tradeStopAt']}. "
            + ("New trades are refused from that instant; registration, settlement and "
               "rollback already in flight continue under their own rules. "
               if deadline["pastDeadline"] else "")
            + (f"Unfinished segments would return to position {view['holder']['position']}, "
               f"the last confirmed holder. "
               if deadline["pastDeadline"] and deadline["unfinishedSuffixReturnsTo"] else "")
            + "</p>"
            + ("".join(f"<p>Undefined ordering: {escape(entry)}</p>"
                       for entry in deadline["undefinedOrdering"])))
    return "<h2>Continuous trade timeline</h2>" + note + stop + "<table>" + "".join(rows) + "</table>"


def rollback_page(exchange, receipt_id, now=None):
    """Stage 1 states plainly that rollback is not implemented yet."""
    view = exchange.receipt_view(receipt_id, now)
    rows = [
        _row("Finalized prefix", f"{view['registeredPrefixLegs']} legs confirmed and shown, "
                                 f"not hidden"),
        _row("Unresolved suffix", f"{view['outstandingLegs']} legs still open"),
        _row("Legs the registrar refused", ", ".join(str(i) for i in view["rejectedLegs"]) or "none"),
    ]
    state = exchange.rollback_report(receipt_id, now)
    if not state["open"]:
        rows.append(_row("Suffix rollback", "no rollback is open for this receipt"))
    else:
        rows.extend([
            _row("Rollback state", state["state"] + ("" if state["complete"] else
                 " - not complete until every step has its own evidence")),
            _row("Trigger", f"{state['trigger']} (leg {state['refusedLegIndex']})"),
            _row("Affected interval", ", ".join(str(i) for i in state["affectedLegs"])),
            _row("Last finalized position", f"leg {state['lastFinalizedPosition']} - this prefix "
                                            f"is not reopened, reversed or re-collected"),
            _row("Return boundary", f"position {state['lastFinalizedPosition']} - the asset returns here, "
                                    f"in one control operation, without walking the intermediate "
                                    f"wallets or needing their gas"),
            _row("Asset returned", "yes" if state["assetControl"]["returned"] else "not yet"),
            _row("Outstanding steps", ", ".join(
                f"{step['stepId']} ({step['status']})" for step in state["outstandingSteps"])
                or "none"),
            _row("Safe retry", state["safeRetryCondition"]),
            _row("Withdrawn mechanisms not used", ", ".join(state["withdrawnMechanismsNotUsed"])),
            _row("Late conflicting results", len(state["conflicts"])),
        ])
    if not view["fundingModelled"]:
        rows.append(_row("Refund and release", "not modelled in this stage"))
        money = ""
    else:
        report = exchange.reconciliation(receipt_id, now)
        header = ("<tr><th>Leg</th><th>Principal</th><th>Escrow</th><th>Payment</th>"
                  "<th>Net to seller</th><th>Net to buyer</th><th>Gas borne by buyer</th>"
                  "<th>Rollback</th></tr>")
        lines = [header]
        for segment in report["segments"]:
            lines.append("<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in (
                segment["legIndex"], f"{segment['principal']} {segment['quoteAsset']}",
                segment["escrowStatus"], segment["paymentStatus"] or "no attempt yet",
                segment["netToPayee"], segment["netToPayer"],
                f"{segment['gasTotal']} ETH wei (buyer at position {segment['legIndex'] + 1})",
                segment["rollbackStatus"])) + "</tr>")
        money = ("<p>Release and refund are mutually exclusive, and a released segment's "
                 "rollback capability is gone for good. A shared on-chain operation is "
                 "recorded once; its apportionment is still undecided and is not assumed "
                 "here.</p><table>" + "".join(lines) + "</table>")
    return ("<h2>Rollback detail</h2><p>Nothing on this page is zeroed out: a confirmed "
            "prefix stays visible even when a later hop is open or refused.</p>"
            + _table(rows) + money)


def queue_page(exchange, receipt_id, now=None):
    """Work waiting on the registrar, with no way to mark it done by hand."""
    view = exchange.receipt_view(receipt_id, now)
    overdue = {entry["legIndex"]: entry for entry in exchange.overdue_requests(receipt_id, now)}
    rows = ["<tr><th>Leg</th><th>State</th><th>Detail</th></tr>"]
    for leg in view["legs"]:
        index = leg["legIndex"]
        if index in view["deferredLegs"]:
            state, detail = "deferred", "a later result is held until the earlier hop is recorded"
        elif index in view["rejectedLegs"]:
            state, detail = "refused", "the registrar refused this hop; the other hops are unaffected"
        elif leg["registrationStatus"] == "pending" and index in overdue:
            state, detail = "window passed", (
                f"the agreed commitment window ({overdue[index]['commitmentDeadlineAt']}) has "
                f"passed. This is a report, not a conclusion and not advice")
        elif leg["registrationStatus"] == "pending":
            state, detail = "awaiting registrar", "filed and waiting; this is the normal state"
        elif leg["registrationStatus"] == "confirmed":
            state, detail = "confirmed", "inside the registered prefix"
        else:
            state, detail = "not filed", "no registration request has been submitted for this leg"
        rows.append(f"<tr><td>{index}</td><td>{escape(state)}</td><td>{escape(detail)}</td></tr>")
    return ("<h2>Operations queue</h2><p>There is no control on this page that marks an "
            "outcome by hand. A state changes only when a registrar result passes the "
            "binding checks.</p><table>" + "".join(rows) + "</table>")


def evidence_page(exchange, receipt_id, run, now=None):
    """Run identity for this page load. It never presents an older run as this one."""
    view = exchange.receipt_view(receipt_id, now)
    def source_identity(name):
        value = run.get(name)
        return value if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) else "not supplied"
    scenario = run.get("scenario")
    scenario = scenario if isinstance(scenario, str) and re.fullmatch(r"DEMO-0[1-6]", scenario) else "native domain observation"
    run_id = run.get("runId")
    run_id = run_id if isinstance(run_id, str) and re.fullmatch(r"demo-[0-9a-f]{32}", run_id) else "private run reference"
    hashes = run.get("transactionHashes", ())
    hashes = [hashes] if isinstance(hashes, str) else hashes
    hashes = [item for item in hashes if isinstance(item, str) and re.fullmatch(r"0x[0-9a-fA-F]{64}", item)] if isinstance(hashes, (tuple, list)) else []
    rows = [
        _row("Scenario", scenario),
        _row("Run id", run_id),
        _row("Source commit", source_identity("commit")),
        _row("Source tree", source_identity("tree")),
        _row("Network", f"chain id {view['asset']['chainId']} (test network)"),
        _row("Transaction hashes", ", ".join(hashes) or "no verified transaction hash supplied"),
        _row("Registration evidence", "simulated adapter results only"),
        _row("Final assertion", f"owner position {view['owner']['position']}, "
                                f"holder position {view['holder']['position']}, "
                                f"registered prefix {view['registeredPrefixLegs']}"),
        _row("Observed at", view["observedAt"]),
        _row("Scope", "local Stage 1 state; this is not a deployment, a chain result or an "
                      "acceptance record, and no earlier run's output is reused here"),
    ]
    return "<h2>Demonstration and evidence</h2>" + _table(rows)


STYLE = """
body{font:14px/1.5 system-ui,sans-serif;margin:0;background:#f7f7f8;color:#16181d}
header{background:#1d2330;color:#fff;padding:12px 20px}
header b{font-weight:600}
nav{display:flex;gap:4px;flex-wrap:wrap;padding:10px 20px;background:#fff;border-bottom:1px solid #e3e5ea}
nav a{padding:6px 12px;border-radius:6px;text-decoration:none;color:#1d2330;background:#eef0f4}
nav a.on{background:#1d2330;color:#fff}
main{padding:20px;max-width:1100px}
h2{margin:0 0 12px;font-size:17px}
table{border-collapse:collapse;background:#fff;width:100%;margin:0 0 16px;
      box-shadow:0 1px 2px rgba(0,0,0,.06)}
th,td{border:1px solid #e3e5ea;padding:7px 10px;text-align:left;vertical-align:top}
th{background:#f2f4f7;font-weight:600;width:260px}
tr>td{width:auto}
p{margin:0 0 14px;color:#404551}
.banner{background:#fff4d6;border:1px solid #e6cf86;padding:8px 12px;margin:0 20px 16px;
        border-radius:6px}
@media (max-width:700px){th{width:auto}main{padding:12px}}
"""


def page(exchange, receipt_id, name, authorization_ids=(), run=None, now=None):
    """Render one named page as a complete HTML document."""
    if name not in PAGES:
        raise KeyError(name)
    if name == "receipt":
        return receipt_page(exchange, receipt_id, now)
    body = {
        "authorization": lambda: authorization_page(exchange, receipt_id, authorization_ids, now),
        "timeline": lambda: timeline_page(exchange, receipt_id, now),
        "rollback": lambda: rollback_page(exchange, receipt_id, now),
        "queue": lambda: queue_page(exchange, receipt_id, now),
        "evidence": lambda: evidence_page(exchange, receipt_id, run or {}, now),
    }[name]()
    tabs = "".join(
        f"<a class=\"{'on' if other == name else ''}\" href=\"/{other}\">{other}</a>"
        for other in PAGES)
    funded = exchange.receipt_view(receipt_id, now)["fundingModelled"]
    banner = ("Local state. Registration is simulated and no transaction is sent. "
              + ("Payments are simulated through the optional adapter; no real value moves. "
                 if funded else "No payment is modelled at this stage. ")
              + "Not a deployment or an acceptance record.")
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>8415ex - {escape(name)}</title><style>{STYLE}</style></head><body>"
            f"<header><b>8415ex</b> status console</header><nav>{tabs}</nav>"
            f"<div class=\"banner\">{escape(banner)}</div>"
            f"<main>{body}</main></body></html>")



