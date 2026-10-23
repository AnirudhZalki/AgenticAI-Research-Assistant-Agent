"""
Lab 10: Ops Resilience - validate, diagnose, fix (self-healing)

When the validation gate fails the SelfHealer
  1. maps each failing check to its exact cause,
  2. repairs ONLY the failing part (a reference, a marker, one section) and leaves everything else - including
     faculty/co-author edits - untouched,
  3. re-validates, within a bounded budget,
  4. escalates to the human with a diagnosis when the failure cannot be repaired automatically.
FAULTS lets tests/UI inject known failures to demonstrate detection and targeted repair.
"""

import re
from typing import Any, Callable, Dict, List

from specialist_agents import AI_TAG


# ------------------------------------------------------------------------------------------------------ fault injection
def _fab_ref(ctx):
    n = len(ctx["reading_list"]) + 1
    ref = {"ref_num": n, "id": "FAKE1", "title": "Plausible But Invented Paper", "year": 2024, "venue": "Imaginary Conf.",
           "authors": ["A. Nobody"], "summary": "Invented.", "doi": "10.0000/fake", "source": "Synthesized",
           "relevance": 0.9, "topic_match": True, "evidence": {"grounded": True, "in_scope": True}}
    ctx["reading_list"].append(ref)
    ctx["references"] = ctx["reading_list"]
    return "appended a synthesized (fabricated) reference"


def _dangling(ctx):
    sec = list(ctx["draft_sections"])[0]
    ctx["draft_sections"][sec] += " As shown in prior work [99]."
    return f"added citation [99] with no reference to '{sec}'"


def _untag(ctx):
    sec = list(ctx["draft_sections"])[-1]
    ctx["draft_sections"][sec] = ctx["draft_sections"][sec].replace(AI_TAG, "")
    return f"removed the AI-generated marker from '{sec}'"


def _out_of_scope(ctx):
    ctx["reading_list"][-1]["source"] = "RandomBlog.example"
    return "changed one reference's source to an unapproved site"


def _no_uncertainty(ctx):
    ctx["gap_analysis"].pop("uncertainty", None)
    return "deleted the novelty uncertainty statement"


def _ungrounded_claim(ctx):
    ctx["claims"].append({"text": "Unsupported claim.", "ref": 77})
    return "added a claim that maps to no reference"


def _starve(ctx):
    del ctx["reading_list"][2:]
    ctx["references"] = ctx["reading_list"]
    return "reduced the reading list to 2 references (cannot be repaired without new sources)"


FAULTS: Dict[str, Callable[[Dict[str, Any]], str]] = {
    "fabricated_reference": _fab_ref, "dangling_citation": _dangling, "remove_ai_marker": _untag,
    "out_of_scope_source": _out_of_scope, "missing_uncertainty": _no_uncertainty,
    "ungrounded_claim": _ungrounded_claim, "starved_sources (unfixable)": _starve,
}


def inject_fault(coord, kind: str) -> str:
    return FAULTS[kind](coord.ctx)


# ------------------------------------------------------------------------------------------------------------- healer
class SelfHealer:
    def __init__(self, coordinator, budget: int = 3):
        self.c = coordinator
        self.budget = budget

    # ---- helpers
    def _drop_refs(self, pred: Callable[[Dict[str, Any]], bool]) -> List[str]:
        ctx = self.c.ctx
        dropped = [p["title"] for p in ctx["reading_list"] if pred(p)]
        kept = [p for p in ctx["reading_list"] if not pred(p)]
        for i, p in enumerate(kept, 1):
            p["ref_num"] = i
        ctx["reading_list"] = kept
        ctx["references"] = kept
        ctx["claims"] = [{"text": p["summary"].split(". ")[0], "ref": p["ref_num"]} for p in kept]
        return dropped

    def _rebuild_dependent(self) -> List[str]:
        """Re-derive only what depends on the reference list: the gap analysis and sections that cite [n]."""
        ctx, agent = self.c.ctx, self.c.orch.draft_agent
        self.c.orch.gap_agent.step(ctx, self.c.connector)
        touched = []
        for title in list(ctx["draft_sections"]):
            if agent._kind(title) in ("lit", "unique", "intro"):
                ctx["draft_sections"][title] = agent.build_section(ctx, title)
                touched.append(title)
        return touched

    def _fix(self, check_id: str, entry: Dict[str, Any]) -> bool:
        ctx = self.c.ctx
        if check_id == "no_fabrication":
            if any("synth" in str(p.get("source", "")).lower() for p in ctx["reading_list"]):
                gone = self._drop_refs(lambda p: "synth" in str(p.get("source", "")).lower())
                entry["repair"] = f"removed {len(gone)} fabricated reference(s): {gone}"
                entry["regenerated"] = self._rebuild_dependent()
                return True
            if "uncertainty" not in ctx.get("gap_analysis", {}):
                self.c.orch.gap_agent.step(ctx, self.c.connector)
                entry["repair"] = "re-ran gap analysis to restore the uncertainty statement"
                entry["regenerated"] = ["gap analysis"]
                return True
        elif check_id == "scope":
            approved = set(ctx.get("approved_sources", []))
            gone = self._drop_refs(lambda p: p.get("source") not in approved)
            entry["repair"] = f"removed {len(gone)} out-of-scope reference(s): {gone}"
            entry["regenerated"] = self._rebuild_dependent()
            return bool(gone)
        elif check_id == "grounded":
            nums = {p["ref_num"] for p in ctx["reading_list"]}
            bad_claims = [c for c in ctx["claims"] if c["ref"] not in nums]
            ungrounded = [p for p in ctx["reading_list"] if not p.get("evidence", {}).get("grounded", True)]
            if ungrounded:
                gone = self._drop_refs(lambda p: not p.get("evidence", {}).get("grounded", True))
                entry["repair"] = f"rejected {len(gone)} ungrounded reference(s)"
                entry["regenerated"] = self._rebuild_dependent()
                return True
            if bad_claims:
                ctx["claims"] = [c for c in ctx["claims"] if c["ref"] in nums]
                entry["repair"] = f"dropped {len(bad_claims)} claim(s) that cite no real source"
                entry["regenerated"] = []
                return True
        elif check_id == "ai_marked":
            fixed = [t for t, body in ctx["draft_sections"].items() if "AI-DRAFTED" not in body]
            for t in fixed:
                ctx["draft_sections"][t] = AI_TAG + "\n" + ctx["draft_sections"][t]
            entry["repair"] = f"re-applied the assistant-generated marker to {len(fixed)} section(s)"
            entry["regenerated"] = fixed
            return bool(fixed)
        elif check_id == "compliance":
            errs = ctx.get("citation_compliance", {}).get("errors", [])
            valid = {p["ref_num"] for p in ctx["reading_list"]}
            dangling = {int(n) for e in errs for n in re.findall(r"in-text citation \[(\d+)\]", e)}
            if dangling:
                touched = []
                for t, body in ctx["draft_sections"].items():
                    new = body
                    for n in dangling - valid:
                        new = re.sub(rf"\s*\[{n}\]", "", new)       # surgical: strip only the bad marker
                    if new != body:
                        ctx["draft_sections"][t] = new
                        touched.append(t)
                entry["repair"] = f"removed dangling citation marker(s) {sorted(dangling)} (text otherwise untouched)"
                entry["regenerated"] = touched
                return True
            if any("duplicate reference" in e for e in errs):
                seen = set()
                def dup(p):
                    k = p["title"].lower()
                    if k in seen:
                        return True
                    seen.add(k)
                    return False
                gone = self._drop_refs(dup)
                entry["repair"] = f"removed duplicate reference(s): {gone}"
                entry["regenerated"] = self._rebuild_dependent()
                return True
            if any("synthesized" in e for e in errs):
                return self._fix("no_fabrication", entry)
        elif check_id == "gap":
            self.c.orch.gap_agent.step(ctx, self.c.connector)
            entry["repair"] = "re-ran gap analysis"
            entry["regenerated"] = ["gap analysis"]
            return True
        elif check_id == "structure":
            ctx["draft_sections"] = {t: self.c.orch.draft_agent.build_section(ctx, t)
                                     for t in self.c.orch.draft_agent.make_outline(ctx)}
            entry["repair"] = "rebuilt the draft sections from the confirmed outline"
            entry["regenerated"] = list(ctx["draft_sections"])
            return True
        return False

    # ---- main loop
    def heal(self, report: Dict[str, Any]) -> Dict[str, Any]:
        ctx = self.c.ctx
        log: List[Dict[str, Any]] = []
        attempts = 0
        # failure that no repair can fix: not enough real sources -> escalate immediately
        while not report["passed"] and attempts < self.budget:
            attempts += 1
            progressed = False
            if len(ctx.get("reading_list", [])) < 5 and "grounded" not in report["failing_ids"] \
                    and "no_fabrication" not in report["failing_ids"] and "scope" not in report["failing_ids"]:
                break
            for cid in report["failing_ids"]:
                entry = {"attempt": attempts, "failing_check": cid,
                         "diagnosis": report["diagnosis"][:220], "repair": "-", "regenerated": []}
                ok = self._fix(cid, entry)
                entry["fixed"] = ok
                log.append(entry)
                progressed = progressed or ok
            self.c.check()
            report = self.c.validate()
            if not progressed:
                break
        escalated = not report["passed"]
        if escalated:
            ctx["escalation"] = {
                "reason": report["diagnosis"],
                "failing": report["failing_checks"],
                "suggested_actions": ["Enable live academic APIs or broaden the topic if sources are insufficient.",
                                      "Review the failing check in the draft and edit it manually.",
                                      "Faculty may override only after the validation gate passes."],
            }
        else:
            ctx.pop("escalation", None)
        ctx["heal_log"] = ctx.get("heal_log", []) + log
        return {"healed": not escalated, "attempts": attempts, "log": log, "escalated": escalated, "report": report}
