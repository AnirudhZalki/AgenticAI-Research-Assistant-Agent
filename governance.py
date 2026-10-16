"""
Lab 12: Safety & Governance - approval gates, audit logs, evaluation, rollback

  * GuardrailPolicy - the proposal's guardrails as executable checks over a finished run
  * AuditLedger     - hash-chained, tamper-evident audit trail (verify() detects edits/deletions)
  * RISK_REGISTER   - risks, likelihood/impact, mitigation, owner (+ dynamic escalation from the run)
  * Evaluator       - per-run scorecard and a multi-topic regression suite
  * rollback        - delegated to tracker.ResearchTracker.rollback (append-only history)
"""

import hashlib
import json
import time
from typing import Any, Callable, Dict, List

from specialist_agents import AI_TAG


class AuditLedger:
    def __init__(self):
        self.entries: List[Dict[str, Any]] = []

    @staticmethod
    def _hash(prev: str, body: Dict[str, Any]) -> str:
        return hashlib.sha256((prev + json.dumps(body, sort_keys=True, default=str)).encode()).hexdigest()

    def append(self, actor: str, action: str, detail: Any = "", status: str = "OK") -> Dict[str, Any]:
        prev = self.entries[-1]["hash"] if self.entries else "GENESIS"
        body = {"seq": len(self.entries) + 1, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "actor": actor, "action": action, "status": status, "detail": str(detail)[:300]}
        entry = {**body, "prev_hash": prev, "hash": self._hash(prev, body)}
        self.entries.append(entry)
        return entry

    def verify(self) -> Dict[str, Any]:
        prev = "GENESIS"
        for e in self.entries:
            body = {k: e[k] for k in ("seq", "timestamp", "actor", "action", "status", "detail")}
            if e["prev_hash"] != prev or e["hash"] != self._hash(prev, body):
                return {"intact": False, "broken_at_seq": e["seq"], "entries": len(self.entries)}
            prev = e["hash"]
        return {"intact": True, "broken_at_seq": None, "entries": len(self.entries)}

    @classmethod
    def from_runtime(cls, runtime, actor: str = "OpenClawRuntime") -> "AuditLedger":
        led = cls()
        for s in runtime.audit_log:
            led.append(actor, s.get("intent", ""), s.get("result_summary", ""), s.get("status", "OK"))
        return led


class GuardrailPolicy:
    """Each check returns (passed, evidence). Run after the pipeline and again after export."""

    def evaluate(self, ctx: Dict[str, Any], runtime=None, tracker=None) -> List[Dict[str, Any]]:
        refs = ctx.get("references", ctx.get("reading_list", []))
        sections = ctx.get("draft_sections", {})
        gap = ctx.get("gap_analysis", {})
        collab = ctx.get("collaboration", {})
        exported = ctx.get("export_status") == "READY_FOR_PUBLICATION"
        audit = getattr(runtime, "audit_log", []) if runtime else []
        approved = any(s.get("status") == "APPROVED" for s in audit)

        bad = [p.get("ref_num") for p in refs if "synth" in str(p.get("source", "")).lower()
               or not p.get("title") or not p.get("authors")]
        edits_ok = all(e.get("author") for a in collab.get("attribution", []) for e in a.get("edits", []))
        results = [
            ("G1 Never fabricate a citation, abstract or result", not bad and bool(refs),
             f"{len(refs)} references, all from retrieved sources" if not bad else f"suspect refs: {bad}"),
            ("G2 Never submit/share without explicit faculty approval", (not exported) or approved,
             "not exported yet" if not exported else ("faculty gate APPROVED before export" if approved
                                                      else "EXPORTED WITHOUT APPROVAL")),
            ("G3 Preserve co-author attribution; no silent overwrite", edits_ok and "policy" in collab,
             f"{len(collab.get('conflicts', []))} conflict(s) surfaced, all edits attributed"),
            ("G4 Keep source links and version history", bool(refs) and all(p.get("source") for p in refs)
             and ((not exported) or bool(tracker and tracker.versions)),
             f"{len(tracker.versions) if tracker else 0} tracked version(s)"),
            ("G5 Flag novelty uncertainty instead of asserting it", bool(gap.get("uncertainty")),
             gap.get("novelty_flag", "no gap analysis")),
            ("G6 AI-authored text is clearly marked", bool(sections) and all(AI_TAG in t for t in sections.values()),
             f"{sum(AI_TAG in t for t in sections.values())}/{len(sections)} sections tagged"),
            ("G7 Every step is audit-logged", len(audit) > 0, f"{len(audit)} runtime audit steps"),
        ]
        return [{"guardrail": n, "passed": bool(p), "evidence": e} for n, p, e in results]


RISK_REGISTER = [
    {"id": "R1", "risk": "Hallucinated / fabricated citation reaches a submission", "likelihood": "Low", "impact": "Critical",
     "mitigation": "Only retrieved records are citable; validation gate fails on synthesized refs; faculty gate.", "owner": "Faculty Author"},
    {"id": "R2", "risk": "False novelty claim (overlooked prior work)", "likelihood": "Medium", "impact": "High",
     "mitigation": "Gap agent states uncertainty and lists closest prior work; authors verify manually.", "owner": "Faculty Author"},
    {"id": "R3", "risk": "Live API outage degrades results to mock data", "likelihood": "Medium", "impact": "Medium",
     "mitigation": "Retry+backoff, circuit breaker, degraded-mode banner, mock sources labelled.", "owner": "Ops (Lab 10)"},
    {"id": "R4", "risk": "Co-author edit overwritten", "likelihood": "Low", "impact": "High",
     "mitigation": "Attributed edits, conflict surfacing, append-only version history, rollback.", "owner": "Collaboration Agent"},
    {"id": "R5", "risk": "Text over-lap / plagiarism from sources", "likelihood": "Low", "impact": "High",
     "mitigation": "5-gram overlap screen; external plagiarism check before submission.", "owner": "Faculty Author"},
    {"id": "R6", "risk": "Missed deadline", "likelihood": "Medium", "impact": "Medium",
     "mitigation": "Radar timestamps alerts and flags whether each fits the stated deadline.", "owner": "Radar Agent"},
]


def dynamic_risks(ctx: Dict[str, Any], connector=None) -> List[str]:
    out = []
    refs = ctx.get("reading_list", [])
    if refs and all("mock" in str(p.get("source", "")) for p in refs):
        out.append("R1/R3 ESCALATED: all references are from the MOCK corpus - not citable in a real paper.")
    if getattr(connector, "degraded_calls", 0):
        out.append(f"R3 ACTIVE: {connector.degraded_calls} degraded-mode call(s).")
    if ctx.get("gap_analysis", {}).get("novelty_level") == "LOW":
        out.append("R2 ESCALATED: literature suggests the topic is well covered.")
    for r in ctx.get("citation_compliance", {}).get("originality", {}).get("flagged_sections", []):
        out.append(f"R5 ACTIVE: high overlap in section '{r}'.")
    if ctx.get("collaboration", {}).get("conflicts"):
        out.append("R4 ACTIVE: unresolved co-author conflicts.")
    return out


class Evaluator:
    def score(self, ctx: Dict[str, Any], guardrails: List[Dict[str, Any]], val_report: Dict[str, Any] = None) -> Dict[str, Any]:
        refs = ctx.get("reading_list", [])
        secs = ctx.get("draft_sections", {})
        n = max(len(refs), 1)
        completed = sum("AUTHORS TO COMPLETE" not in t for t in secs.values())
        m = {
            "reference_count": len(refs),
            "doi_coverage": round(sum(1 for p in refs if p.get("doi") not in (None, "", "N/A")) / n, 2),
            "topic_relevance_mean": round(sum(p.get("relevance", 0) for p in refs) / n, 2),
            "live_source_share": round(sum(1 for p in refs if "mock" not in str(p.get("source", ""))) / n, 2),
            "sections_needing_authors": f"{len(secs) - completed}/{len(secs)}",
            "citation_errors": len(ctx.get("citation_compliance", {}).get("errors", [])),
            "validation_passed": (val_report or {}).get("passed"),
            "guardrails_passed": f"{sum(g['passed'] for g in guardrails)}/{len(guardrails)}",
        }
        grade = (0.25 * (len(refs) >= 5) + 0.15 * m["doi_coverage"] + 0.2 * m["topic_relevance_mean"]
                 + 0.2 * (sum(g["passed"] for g in guardrails) / max(len(guardrails), 1))
                 + 0.2 * bool((val_report or {}).get("passed")))
        m["overall_score"] = round(grade * 100)
        return m

    def regression(self, run_fn: Callable[[str], Dict[str, Any]], topics: List[str]) -> List[Dict[str, Any]]:
        rows = []
        for t in topics:
            try:
                r = run_fn(t)
                rows.append({"topic": t, "refs": r["metrics"]["reference_count"], "score": r["metrics"]["overall_score"],
                             "validation": r["metrics"]["validation_passed"], "guardrails": r["metrics"]["guardrails_passed"],
                             "pass": r["metrics"]["validation_passed"] and r["metrics"]["reference_count"] >= 5})
            except Exception as exc:
                rows.append({"topic": t, "refs": 0, "score": 0, "validation": False, "guardrails": "-",
                             "pass": False, "error": str(exc)})
        return rows
