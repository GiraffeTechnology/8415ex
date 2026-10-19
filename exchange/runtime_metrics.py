"""Bounded observations of the original workbench gateway, not a new executor."""
from collections import deque
from html import escape
import json
from threading import Lock
from time import perf_counter_ns

from .workbench import RuntimeBinding, WorkbenchHandler, WorkbenchServer


class RuntimeMetrics:
    """Count call outcomes without inspecting arguments, results or exception text.

    Returned means the original call returned, including a pending or unknown
    result. It never means a trade, payment, registration or chain action passed.
    The sample window is bounded; totals describe this process lifetime only.
    """
    def __init__(self, sample_limit=128, clock=perf_counter_ns):
        if type(sample_limit) is not int or not 1 <= sample_limit <= 512:
            raise ValueError("sample limit must be between 1 and 512")
        self._clock = clock
        self._limit = sample_limit
        self._lock = Lock()
        self._active = 0
        self._high_water = 0
        self._calls = {name: {"started": 0, "returned": 0, "raised": 0,
                             "untimed": 0, "durations": deque(maxlen=sample_limit)}
                       for name in ("enquire", "dispatch")}

    def _now(self):
        try:
            value = self._clock()
            return value if type(value) is int and value >= 0 else None
        except Exception:
            return None

    def call(self, name, operation, *args, **kwargs):
        if name not in self._calls:
            raise ValueError("unsupported observation category")
        start = self._now()
        with self._lock:
            self._calls[name]["started"] += 1
            self._active += 1
            self._high_water = max(self._high_water, self._active)
        returned = False
        try:
            result = operation(*args, **kwargs)
            returned = True
            return result
        finally:
            end = self._now()
            with self._lock:
                row = self._calls[name]
                row["returned" if returned else "raised"] += 1
                self._active -= 1
                if start is None or end is None or end < start:
                    row["untimed"] += 1
                else:
                    row["durations"].append(end - start)

    def snapshot(self):
        with self._lock:
            methods = {}
            for name, row in self._calls.items():
                values = sorted(row["durations"])
                completed = row["returned"] + row["raised"]
                methods[name] = {k: row[k] for k in ("started", "returned", "raised", "untimed")}
                methods[name].update({
                    "completedCalls": completed,
                    "raisedRatio": row["raised"] / completed if completed else None,
                    "latencyWindowCount": len(values),
                    "latencyMs": {
                        "min": values[0] / 1000000 if values else None,
                        "max": values[-1] / 1000000 if values else None,
                        "mean": sum(values) / len(values) / 1000000 if values else None,
                        "p95NearestRank": values[(95 * len(values) + 99) // 100 - 1] / 1000000
                                          if values else None,
                    },
                })
            return {"schema": "8415ex-runtime-observations/1",
                    "scope": "this process and the original synchronous gateway calls only",
                    "sampleLimitPerMethod": self._limit,
                    "activeCalls": self._active, "highWaterCalls": self._high_water,
                    "methods": methods,
                    "meaning": "returned is not business success; raised is not a confirmed chain failure",
                    "persistence": "RAM only; reset on restart",
                    "productionSLA": "NOT_ESTABLISHED"}


class MeasuredGateway:
    """Pass through the exact original call; never retry, wrap errors or authorize."""
    def __init__(self, gateway, metrics):
        self.original = gateway
        self.metrics = metrics

    def enquire(self, key, context):
        return self.metrics.call("enquire", self.original.enquire, key, context)

    def dispatch(self, action, payload, context):
        return self.metrics.call("dispatch", self.original.dispatch, action, payload, context)


class ObservedRuntimeBinding(RuntimeBinding):
    """Add observations to the same domain binding without changing its revision.

    Latency and counters must not invalidate a business-state revision or turn
    an outcome-unknown retry into a fresh request. Original gateway checks remain
    authoritative. Configuring this wrapper does not establish provider readiness.
    """
    def __init__(self, exchange, receipt_id, authorization_ids=(), run=None, gateway=None,
                 metrics=None):
        self.metrics = metrics if metrics is not None else RuntimeMetrics()
        original = MeasuredGateway(gateway, self.metrics) if gateway is not None else None
        super().__init__(exchange, receipt_id, authorization_ids, run, original)

    def snapshot(self):
        value = super().snapshot()
        state = value["state"]
        legs = state["receipt"]["legs"]
        value["performance"] = self.metrics.snapshot()
        value["performance"]["source"] = dict(value["source"])
        value["performance"]["domainQueueObservation"] = {
            "pendingRegistrationLegs": sum(leg["registrationStatus"] == "pending" for leg in legs),
            "overdueRegistrationRequests": len(state["overdue"]),
            "meaning": "counts from the current domain view; not a durable worker queue or throughput proof",
        }
        return value


class ObservedWorkbenchHandler(WorkbenchHandler):
    def native_page(self, name):
        body = super().native_page(name)
        if name not in ("queue", "evidence"):
            return body
        observations = self.server.binding.snapshot()["performance"]
        panel = ('<section aria-labelledby="runtime-observations">'
                 '<h3 id="runtime-observations">Measured runtime observations</h3>'
                 '<p>Original gateway call timing and current domain backlog only. '
                 'A returned call may still report pending or unknown. These counters '
                 'do not establish real-chain acceptance or a production SLA.</p><pre>'
                 + escape(json.dumps(observations, sort_keys=True, indent=2))
                 + '</pre></section>')
        return body.replace('</main>', panel + '</main>', 1)


class ObservedWorkbenchServer(WorkbenchServer):
    """Use the existing server, port policy, CSRF and checked command routes."""
    def __init__(self, binding, port=0, commit=None, tree=None):
        if not isinstance(binding, ObservedRuntimeBinding):
            raise TypeError("an observed original runtime binding is required")
        super().__init__(binding, port=port, commit=commit, tree=tree)
        self.RequestHandlerClass = ObservedWorkbenchHandler
