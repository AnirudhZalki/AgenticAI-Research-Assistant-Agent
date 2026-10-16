"""
Lab 10: Cloud Operations Agent - observability and failure handling

  * Tracer          - span per tool call (latency, status, error) => traces, p50/p95, error rate
  * CircuitBreaker  - stops hammering a failing dependency, half-opens after a cool-down
  * FaultInjector   - deterministic failures/latency for chaos drills (the "failed deployment")
  * instrument()    - wraps ResearchDataConnector endpoints with tracing + retry/backoff + breaker + fallback
  * OpsAgent        - reads the traces, diagnoses the failure and recommends/executes remediation
"""

import statistics
import threading
import time
from typing import Any, Callable, Dict, List, Optional


class Tracer:
    def __init__(self):
        self.spans: List[Dict[str, Any]] = []
        self.baseline = 0            # spans before this index are "history" (set by mark_recovered)
        self._lock = threading.Lock()

    def mark_recovered(self):
        self.baseline = len(self.spans)

    def record(self, name: str, started: float, status: str, error: str = "", attempt: int = 1, note: str = ""):
        span = {"time": time.strftime("%H:%M:%S"), "name": name, "status": status, "attempt": attempt,
                "latency_ms": round((time.time() - started) * 1000, 2), "error": error, "note": note}
        with self._lock:
            self.spans.append(span)

    def summary(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for s in list(self.spans)[self.baseline:]:
            o = out.setdefault(s["name"], {"calls": 0, "errors": 0, "lat": []})
            o["calls"] += 1
            o["errors"] += s["status"] != "OK"
            o["lat"].append(s["latency_ms"])
        for o in out.values():
            lat = sorted(o.pop("lat"))
            o["error_rate"] = round(o["errors"] / o["calls"], 3)
            o["p50_ms"] = round(statistics.median(lat), 2)
            o["p95_ms"] = round(lat[min(len(lat) - 1, int(len(lat) * 0.95))], 2)
        return out


class CircuitBreaker:
    """CLOSED -> (threshold failures) -> OPEN -> (cool-down) -> HALF_OPEN -> success => CLOSED."""

    def __init__(self, threshold: int = 3, cooldown_s: float = 5.0):
        self.threshold, self.cooldown_s = threshold, cooldown_s
        self.failures, self.opened_at, self.state = 0, 0.0, "CLOSED"

    def allow(self) -> bool:
        if self.state == "OPEN":
            if time.time() - self.opened_at >= self.cooldown_s:
                self.state = "HALF_OPEN"
                return True
            return False
        return True

    def success(self):
        self.failures, self.state = 0, "CLOSED"

    def failure(self):
        self.failures += 1
        if self.state == "HALF_OPEN" or self.failures >= self.threshold:
            self.state, self.opened_at = "OPEN", time.time()


class FaultInjector:
    """Inject N consecutive failures (and/or latency) into a named endpoint."""

    def __init__(self):
        self.plan: Dict[str, Dict[str, Any]] = {}

    def arm(self, endpoint: str, failures: int = 3, latency_s: float = 0.0, message: str = "injected: upstream 503"):
        self.plan[endpoint] = {"failures": failures, "latency_s": latency_s, "message": message}

    def clear(self):
        self.plan.clear()

    def maybe_fail(self, endpoint: str):
        f = self.plan.get(endpoint)
        if not f:
            return
        if f["latency_s"]:
            time.sleep(f["latency_s"])
        if f["failures"] > 0:
            f["failures"] -= 1
            raise ConnectionError(f["message"])


def instrument(connector, tracer: Tracer, faults: Optional[FaultInjector] = None,
               retries: int = 2, backoff_s: float = 0.05, breaker: Optional[CircuitBreaker] = None):
    """
    Wrap the connector's endpoints in place. search_online_papers additionally gets retry+backoff,
    a circuit breaker, and a graceful fallback to the local corpus (degraded mode, never fabricated data).
    """
    faults = faults or FaultInjector()
    breaker = breaker or CircuitBreaker()
    connector.breaker, connector.faults, connector.tracer = breaker, faults, tracer
    connector.degraded_calls = 0

    def wrap(name: str, fn: Callable, resilient: bool, fallback: Optional[Callable] = None):
        def inner(*args, **kwargs):
            started = time.time()
            if not resilient:
                try:
                    faults.maybe_fail(name)
                    res = fn(*args, **kwargs)
                    tracer.record(name, started, "OK")
                    return res
                except Exception as exc:
                    tracer.record(name, started, "ERROR", str(exc))
                    raise
            if not breaker.allow():
                tracer.record(name, started, "SHORT_CIRCUITED", "circuit OPEN", note="served from fallback")
                connector.degraded_calls += 1
                return fallback(*args, **kwargs)
            last = ""
            for attempt in range(1, retries + 2):
                t0 = time.time()
                try:
                    faults.maybe_fail(name)
                    res = fn(*args, **kwargs)
                    breaker.success()
                    tracer.record(name, t0, "OK", attempt=attempt)
                    return res
                except Exception as exc:
                    last = str(exc)
                    breaker.failure()
                    tracer.record(name, t0, "ERROR", last, attempt=attempt)
                    if attempt <= retries and breaker.state != "OPEN":
                        time.sleep(backoff_s * (2 ** (attempt - 1)))
                    else:
                        break
            connector.degraded_calls += 1
            tracer.record(name, started, "FALLBACK", last, note="local corpus used (degraded mode)")
            return fallback(*args, **kwargs)
        inner.__wrapped__ = fn
        return inner

    local_fb = lambda query="", max_results=6, agent_id="Fallback": connector._tools.read_corpus("")[:max_results]
    connector.search_online_papers = wrap("search_online_papers", connector.search_online_papers, True, local_fb)
    for ep in ("read_paper_corpus", "read_researcher_library", "read_funding_deadlines", "read_collaboration_notes"):
        setattr(connector, ep, wrap(ep, getattr(connector, ep), False))
    return connector


class OpsAgent:
    """Diagnose from telemetry and propose (or perform) remediation."""

    def diagnose(self, tracer: Tracer, connector=None) -> Dict[str, Any]:
        summ = tracer.summary()
        findings, actions = [], []
        for name, s in summ.items():
            if s["error_rate"] >= 0.5:
                findings.append(f"CRITICAL: {name} failing {int(s['error_rate'] * 100)}% of calls "
                                f"({s['errors']}/{s['calls']}).")
            elif s["errors"]:
                findings.append(f"WARN: {name} had {s['errors']} failed attempt(s) (recovered by retry/fallback).")
            if s["p95_ms"] > 2000:
                findings.append(f"WARN: {name} p95 latency {s['p95_ms']} ms exceeds 2000 ms SLO.")
        state = getattr(connector, "breaker", None)
        if state and state.state != "CLOSED":
            findings.append(f"Circuit breaker is {state.state}: dependency treated as down.")
            actions.append("Wait for cool-down, then probe (half-open); or disable live APIs in the sidebar.")
        degraded = getattr(connector, "degraded_calls", 0)
        if degraded:
            findings.append(f"{degraded} call(s) served in DEGRADED mode from the local corpus.")
            actions.append("Verify references against live sources before submission (degraded results are mock data).")
        if not findings:
            findings.append("All endpoints healthy; no anomalies in traces.")
        root = next((sp["error"] for sp in tracer.spans[tracer.baseline:] if sp["error"]), "")
        return {"healthy": not any(f.startswith("CRITICAL") for f in findings),
                "findings": findings, "root_cause_hint": root or "n/a",
                "recommended_actions": actions or ["No action required."], "endpoints": summ}

    def remediate(self, connector) -> str:
        if getattr(connector, "faults", None):
            connector.faults.clear()
        if getattr(connector, "breaker", None):
            connector.breaker.success()
        connector.degraded_calls = 0
        if getattr(connector, "tracer", None):
            connector.tracer.mark_recovered()
        return "Cleared injected faults and reset the circuit breaker."
