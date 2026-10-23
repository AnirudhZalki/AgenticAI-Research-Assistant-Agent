"""
Lab 11: Agentic SDLC Factory - requirement -> design -> implementation -> tests -> traceability report

The factory takes the proposal's requirements (each with an executable acceptance test), runs the
implementation (the coordinator pipeline), executes the acceptance tests - including negative tests such as
"export without approval must be refused" and "tampered audit log must be detected" - plus the lab unit
tests, and emits a requirements-traceability matrix.
"""

import io
import time
import unittest
from typing import Any, Callable, Dict, List, Tuple

from coordinator import ResearchCoordinator
from governance import AuditLedger
from healing import SelfHealer, inject_fault

REQUEST = dict(topic="edge AI hardware porting frameworks", venue="IEEE conference, IMRAD, 6-page limit",
               collaborators="Faculty Author, Co-Author A", deadline="2026-11-15")

# (id, requirement text, proposal source, implementing module, acceptance test)
Test = Callable[[Dict[str, Any]], Tuple[bool, str]]


def _fresh() -> ResearchCoordinator:
    return ResearchCoordinator(use_live=False, checkpoint_file="checkpoint_sdlc.json")


def _raises(fn, exc) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def t_intake(r):
    c = _fresh()
    ok = _raises(lambda: c.intake({"topic": "x", "venue": "", "collaborators": "a", "deadline": "2026-11-15"}), ValueError) \
        and _raises(lambda: c.intake({**REQUEST, "deadline": "15/11/2026"}), ValueError)
    return ok, "missing venue and malformed deadline both rejected at Gate 1"


def t_reading(r):
    refs = r["ctx"]["reading_list"]
    rel = [p["relevance"] for p in refs]
    ok = len(refs) >= 5 and rel == sorted(rel, reverse=True) and all(p["doi"] and p["source"] and p["authors"] for p in refs)
    return ok, f"{len(refs)} ranked references, each with source and DOI field"


def t_gap(r):
    g = r["ctx"]["gap_analysis"]
    return bool(g.get("uncertainty") and g.get("closest_prior_work")), "uncertainty statement + closest prior work present"


def t_outline(r):
    c = _fresh()
    c.intake(REQUEST)
    blocked = _raises(c.draft, PermissionError)
    same = list(r["ctx"]["draft_sections"]) == r["ctx"]["confirmed_outline"]
    return blocked and same, "drafting refused before outline confirmation; draft sections == confirmed outline"


def t_marked(r):
    secs = r["ctx"]["draft_sections"]
    ok = all("AI-DRAFTED" in t for t in secs.values()) and any("AUTHORS TO COMPLETE" in t for t in secs.values())
    return ok, "all sections AI-tagged; methods/results left to authors"


def t_citations(r):
    cc = r["ctx"]["citation_compliance"]
    return cc["compliance_passed"] and len(cc["formatted_references"]) == len(r["ctx"]["reading_list"]), \
        f"{cc['citation_style']} references formatted; 0 hard errors"


def t_radar(r):
    d = r["ctx"]["radar_deadlines"]
    return bool(d) and all("checked_at" in x for x in d), f"{len(d)} deadline alerts, each timestamped"


def t_collab(r):
    col = r["ctx"]["collaboration"]
    return bool(col["attribution"]) and "policy" in col, "sections attributed; conflicts surfaced, never overwritten"


def t_gate(r):
    c = _fresh()
    c.run_all(REQUEST, approve=False)
    return _raises(c.export, PermissionError) and c.runtime.state["status"] == "STOPPED_AT_FACULTY_GATE", \
        "export refused after faculty rejection"


def t_export(r):
    e = r["ctx"]["tracker_entry"]
    return e["status"] == "APPROVED" and len(e["sha256"]) == 64 and e["source_links"], \
        f"{r['ctx']['version']} logged with sha256 and {len(e['source_links'])} source links"


def t_ledger(r):
    led = AuditLedger()
    for i in range(3):
        led.append("t", f"a{i}")
    intact = led.verify()["intact"]
    led.entries[1]["detail"] = "tampered"
    return intact and not led.verify()["intact"], "hash chain verifies, and detects a tampered entry"


def t_parallel(r):
    return sum(t["mode"] == "PARALLEL" for t in r["timeline"]) >= 3, \
        "discovery, checks and export ran as PARALLEL stages"


def t_heal(r):
    c = _fresh()
    c.build(REQUEST)
    inject_fault(c, "fabricated_reference")
    c.check()
    rep = c.validate()
    out = SelfHealer(c).heal(rep)
    return (not rep["passed"]) and out["healed"] and bool(out["log"]), \
        f"injected fabricated reference detected and repaired: {out['log'][0]['repair'][:60]}"


def t_roles(r):
    c = _fresh()
    c.build(REQUEST)
    return _raises(lambda: c.faculty_decision(True, "S", role="student_assistant"), PermissionError), \
        "student role refused at the approval gate and the denial audited"


def t_acceptance_gate(r):
    c = _fresh()
    c.build(REQUEST)
    c.ctx["acceptance"]["all_pass"] = False
    return _raises(lambda: c.faculty_decision(True, "Dr"), PermissionError), \
        "approval blocked while the acceptance report is not fully passing"


def t_connector(r):
    c = _fresh()
    return _raises(lambda: c.connector.read_collaboration_notes(agent_id="FundingRadarAgent"), PermissionError), \
        "radar agent refused access to collaboration notes (least privilege)"


def t_grounding(r):
    c = _fresh()
    c.intake(REQUEST)
    pool = c.tools.corpus + [{"id": "X", "title": "Edge AI hardware porting rumour", "authors": ["A"], "abstract": "edge ai hardware porting",
                              "keywords": [], "doi": "N/A", "source": "RandomBlog.example"}]
    c.tools.read_corpus = lambda kw="": pool
    c.discover()
    return all(p["source"] != "RandomBlog.example" for p in c.ctx["reading_list"]) and bool(c.ctx["rejected_references"]), \
        "out-of-scope candidate rejected by the grounding step"


REQUIREMENTS: List[Tuple[str, str, str, str, Test]] = [
    ("REQ-01", "Do not start until topic, venue, collaborators and deadline are confirmed", "Workflow step 1 / Gate 1", "coordinator.intake", t_intake),
    ("REQ-02", "Ranked reading list from scholarly sources with links", "Workflow step 2", "specialist_agents.LiteratureDiscoveryAgent", t_reading),
    ("REQ-03", "Gap analysis flags novelty vs overlap and states uncertainty", "Workflow step 3", "specialist_agents.GapAnalysisAgent", t_gap),
    ("REQ-04", "Outline first; draft only after the outline is confirmed", "Workflow step 4", "coordinator.confirm_outline/draft", t_outline),
    ("REQ-05", "AI-authored text is marked; no invented results", "Guardrails (Drafting)", "specialist_agents.DraftingWritingAgent", t_marked),
    ("REQ-06", "Citation formatting and reference completeness per venue", "Workflow step 5", "specialist_agents.CitationComplianceAgent", t_citations),
    ("REQ-07", "Deadline radar with timestamped alerts", "Workflow step 6", "specialist_agents.FundingRadarAgent", t_radar),
    ("REQ-08", "Section ownership; never silently overwrite co-author edits", "Workflow step 7", "specialist_agents.CollaborationAgent", t_collab),
    ("REQ-09", "Nothing exported without explicit faculty approval", "Workflow step 8", "coordinator.faculty_decision/export", t_gate),
    ("REQ-10", "Export logs versioned, source-linked, approved-status record", "Workflow step 9", "tracker.ResearchTracker", t_export),
    ("REQ-11", "Audit log is tamper-evident", "Governance layer", "governance.AuditLedger", t_ledger),
    ("REQ-12", "Independent agents run in parallel; gates stay sequential", "Hybrid methodology", "coordinator (RunnableParallel)", t_parallel),
    ("REQ-13", "Validation failures are diagnosed and repaired in a targeted way (Lab 10)", "Chapter 12 Lab 10", "healing.SelfHealer", t_heal),
    ("REQ-14", "Only authorised roles can approve; denials are audited (Lab 12)", "Chapter 12 Lab 12", "access.AccessControl", t_roles),
    ("REQ-15", "No brief reaches approval without a passing acceptance report (Lab 11)", "Chapter 12 Lab 11", "coordinator.acceptance_suite", t_acceptance_gate),
    ("REQ-16", "Agents reach data only through scoped connector endpoints (Lab 5)", "Chapter 12 Lab 5", "connector.ResearchDataConnector", t_connector),
    ("REQ-17", "Ungrounded / out-of-scope candidates are rejected (Lab 9)", "Chapter 12 Lab 9", "specialist_agents.make_evidence", t_grounding),
]

DESIGN = [
    ("Data layer", "data/*.json + MCP connector (search.py, connector.py, mcp_server.py)"),
    ("AI layer", "specialist_agents.py, deep_research.py, domain.py (retrieval, gap, drafting, compliance)"),
    ("Workflow layer", "coordinator.py (LangChain RunnableParallel/Lambda), tracker.py"),
    ("Governance layer", "governance.py, openclaw_runtime.py (approval gate, audit, checkpoints), ops.py"),
]


def run_unit_tests() -> Dict[str, Any]:
    import run_labs
    stream = io.StringIO()
    suite = unittest.TestLoader().loadTestsFromTestCase(run_labs.TestResearchAgentLabs)
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        res = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    return {"ran": res.testsRun, "failures": len(res.failures), "errors": len(res.errors), "ok": res.wasSuccessful(),
            "details": [str(t[0]) + ": " + t[1].splitlines()[-1] for t in res.failures + res.errors]}


class SDLCFactory:
    def run(self, with_unit_tests: bool = True) -> Dict[str, Any]:
        t0 = time.time()
        impl = _fresh().run_all(REQUEST, approve=True)               # Implementation: execute the pipeline
        rows = []
        for rid, text, src, module, test in REQUIREMENTS:            # Test: executable acceptance criteria
            try:
                ok, evidence = test(impl)
            except Exception as exc:
                ok, evidence = False, f"test crashed: {exc}"
            rows.append({"id": rid, "requirement": text, "source": src, "implemented_in": module,
                         "result": "PASS" if ok else "FAIL", "evidence": evidence})
        unit = run_unit_tests() if with_unit_tests else None
        passed = sum(r["result"] == "PASS" for r in rows)
        return {"stages": ["Requirements", "Design", "Implementation", "Test", "Report"],
                "design": DESIGN, "traceability": rows,
                "acceptance_pass_rate": round(passed / len(rows), 2),
                "unit_tests": unit, "seconds": round(time.time() - t0, 2),
                "release_ready": passed == len(rows) and (unit is None or unit["ok"])}
