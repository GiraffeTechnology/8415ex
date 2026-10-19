"""Child fixture for synthetic crash windows; never a deployed controller."""
import json
import os
from pathlib import Path
import sqlite3
import sys

from exchange import fixtures as F
from exchange.aggregate_checkpoint import AggregateCheckpointStore
from exchange.checkpoint_runtime_load import load_exchange_checkpoint
from exchange.direct_return_checkpoint import DirectReturnCheckpoint
from exchange.exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint
from exchange.ledger import Exchange
from exchange.rollback import SimulatedAssetControl
from exchange.settlement import SimulatedPaymentAdapter


RECEIPT = "rcpt-8415-0001"
SCOPE = "synthetic-crash-window"
MARKER = "synthetic direct-return process test only"


class SyntheticJournal:
    def __init__(self, root, clock, mode):
        self.db = sqlite3.connect(root / "synthetic-native.db")
        self.db.execute("PRAGMA synchronous=FULL")
        self.clock = clock
        self.mode = mode

    def lookup(self, kind, key):
        row = self.db.execute("SELECT payload FROM effects WHERE kind=? AND operation_key=?",
                              (kind, key)).fetchone()
        return json.loads(row[0]) if row is not None else None

    def record(self, kind, key, value):
        self.db.execute("INSERT INTO effects(kind,operation_key,payload) VALUES(?,?,?)",
                        (kind, key, json.dumps(value, sort_keys=True)))
        self.db.commit()
        # Abruptly terminate after the synthetic external effect is durable,
        # before its result can update EX or reach its following checkpoint.
        if self.mode == "crash-" + kind:
            os._exit(71)
        return value


class SyntheticPayments:
    def __init__(self, journal):
        self.journal = journal

    def lookup(self, key):
        return self.journal.lookup("payment", key)

    def pay(self, key, payer, payee, currency, principal):
        if self.lookup(key) is not None:
            raise AssertionError("original refund key was submitted twice")
        original = SimulatedPaymentAdapter(self.journal.clock)
        return self.journal.record("payment", key,
            original.pay(key, payer, payee, currency, principal))


class SyntheticAssets:
    def __init__(self, journal):
        self.journal = journal

    def lookup(self, key):
        return self.journal.lookup("asset", key)

    def return_asset(self, key, source, destination, asset):
        if self.lookup(key) is not None:
            raise AssertionError("original return key was submitted twice")
        outcomes = {key: "unknown"} if self.journal.mode == "unknown-asset" else None
        original = SimulatedAssetControl(self.journal.clock, outcomes=outcomes)
        return self.journal.record("asset", key,
            original.return_asset(key, source, destination, asset))


def advance(root, mode):
    root = Path(root)
    if (root / "TEST-ONLY.txt").read_text(encoding="utf-8") != MARKER:
        raise ValueError("explicit synthetic temporary fixture directory required")
    if mode not in ("advance", "crash-payment", "crash-asset", "unknown-asset"):
        raise ValueError("synthetic test mode required")
    clock = F.ManualClock()
    journal = SyntheticJournal(root, clock, mode)
    db = sqlite3.connect(root / "checkpoint.db")
    db.execute("PRAGMA synchronous=FULL")
    checkpoint = ExchangeSnapshotCheckpoint(AggregateCheckpointStore(db,
        components=("owned-facts",), source_commit="a" * 40, source_tree="b" * 40))
    runtime = Exchange(clock, payment_adapter=SyntheticPayments(journal),
        release_sources=(F.RELEASE_SOURCE,), funding_required=True,
        asset_control=SyntheticAssets(journal), rollback_sources=(F.ROLLBACK_SOURCE,),
        mint_verifier=F.verify_fixture_mint, eth_gas_gate=F.fixture_eth_gas_gate(),
        price_balance_gate=F.fixture_price_balance_gate())
    loaded = load_exchange_checkpoint(checkpoint, SCOPE, runtime)
    if loaded is None:
        raise AssertionError("synthetic initial checkpoint missing")
    bridge = DirectReturnCheckpoint(loaded.access, checkpoint, SCOPE)
    result = bridge.advance(RECEIPT, expected_generation=loaded.generation)
    counts = {kind: count for kind, count in journal.db.execute(
        "SELECT kind,COUNT(*) FROM effects GROUP BY kind")}
    report = result["report"]
    print(json.dumps({"complete": report["complete"],
        "owner": loaded.access.owner_of(RECEIPT), "counts": counts,
        "generation": result["afterCheckpoint"]["generation"]}))
    db.close()
    journal.db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("synthetic directory and mode required")
    advance(sys.argv[1], sys.argv[2])
