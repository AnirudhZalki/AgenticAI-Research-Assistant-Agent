"""
Automated Test Suite for Labs 1 through 8 (LangChain + OpenClaw + MCP Frameworks)
Runs acceptance tests for each lab deliverable and verifies output criteria across framework layers.
"""

import sys
import json
import unittest
from clarify import RequestClarifier
from search import SearchTools
from skills import ResearchPlanSkill, FormattingSkill
from memory import MemoryStore
from connector import ResearchDataConnector
from mcp_server import MCPServer
from openclaw_runtime import OpenClawAgentRuntime
from langchain_orchestrator import LangChainOrchestrator
from node_graph import ResearchNodeGraph
from swarm import ParallelSwarm
from verify import ValidationAgent
from deep_research import DeepResearchAgent
from ops import Tracer, FaultInjector, CircuitBreaker, OpsAgent, instrument
from sdlc import SDLCFactory
from governance import AuditLedger, GuardrailPolicy, Evaluator
from domain import parse_venue, CitationFormatter, OriginalityChecker
from coordinator import ResearchCoordinator
from tracker import ResearchTracker
from healing import FAULTS, SelfHealer, inject_fault
from access import AccessControl, Actor, redact_view
from radar import RadarMonitor
from domain import detect_domain, get_pack
from swarm import ParallelSwarm

REQUEST = {"topic": "edge AI hardware porting frameworks", "venue": "IEEE conference, IMRAD, 6-page limit",
           "collaborators": "Faculty Author, Co-Author A", "deadline": "2026-11-15"}

class TestResearchAgentLabs(unittest.TestCase):

    def test_lab_1_clarifier_planner_loop(self):
        """Lab 1: Request Clarifier asks for parameters and establishes state."""
        clarifier = RequestClarifier()
        state = clarifier.clarify(initial_inputs={"topic": "Edge AI"}, interactive=False)
        self.assertIn("topic", state)
        self.assertIn("venue", state)
        self.assertIn("collaborators", state)
        self.assertIn("deadline", state)
        print("  [PASS] Lab 1: Clarification loop gathers missing constraints.")

    def test_lab_2_typed_tools(self):
        """Lab 2: Typed data tools replace LLM memory hallucination."""
        tools = SearchTools()
        papers = tools.read_corpus("edge")
        self.assertIsInstance(papers, list)
        self.assertGreater(len(papers), 0)
        self.assertIn("title", papers[0])
        print("  [PASS] Lab 2: Tool execution reads from verified data files.")

    def test_lab_3_reusable_skills(self):
        """Lab 3: Reusable plan and formatting skills with schemas."""
        plan_skill = ResearchPlanSkill()
        fmt_skill = FormattingSkill()
        
        bp = plan_skill.execute({"topic": "Healthcare AI", "venue": "ACM Journal"})
        self.assertTrue(bp.locked)
        self.assertEqual(bp.citation_style, "ACM")

        doc = fmt_skill.execute({"title": bp.title, "abstract": "Test abstract", "sections": {"1. Intro": "Text"}}, venue_spec="ACM")
        self.assertIn("ACM FORMATTED PAPER DRAFT", doc)
        print("  [PASS] Lab 3: Schema-typed skills generate blueprints and formatted drafts.")

    def test_lab_4_memory_and_retrieval(self):
        """Lab 4: Separates short-term session state from long-term stored reference memory."""
        corpus = [
            {"id": "P1", "title": "Microcontroller Quantisation", "keywords": ["quantisation", "embedded"]},
            {"id": "P2", "title": "Transformer Diagnostics", "keywords": ["transformer", "healthcare"]}
        ]
        mem = MemoryStore(corpus=corpus)
        mem.update_session("current_draft", "Draft v1")
        self.assertEqual(mem.get_session("current_draft"), "Draft v1")

        tag_hits = mem.retrieve_by_tags(["embedded"])
        self.assertEqual(len(tag_hits), 1)
        self.assertEqual(tag_hits[0]["id"], "P1")

        sim_hits = mem.retrieve_by_similarity("microcontroller embedded")
        self.assertEqual(len(sim_hits), 1)
        print("  [PASS] Lab 4: Memory store cleanly manages session state and retrieval.")

    def test_lab_5_mcp_server_connector(self):
        """Lab 5: Model Context Protocol (MCP) Server exposes data tools according to MCP standard."""
        mcp_server = MCPServer()
        tools = mcp_server.list_tools()
        self.assertGreaterEqual(len(tools), 4)
        
        res = mcp_server.call_tool("read_paper_corpus", {"keyword": "edge"}, agent_id="TestAgent")
        papers = json.loads(res[0].text)
        self.assertIsInstance(papers, list)
        self.assertGreater(len(papers), 0)
        
        trail = mcp_server.connector.get_audit_trail()
        self.assertGreaterEqual(len(trail), 1)
        self.assertEqual(trail[0]["agent_id"], "TestAgent")
        print("  [PASS] Lab 5: Governed MCP Tool Server executes protocol tool requests.")

    def test_lab_6_openclaw_runtime(self):
        """Lab 6: OpenClaw Agent Runtime with step audit logging, budget limits, and checkpoints."""
        runtime = OpenClawAgentRuntime(max_budget_steps=10)
        runtime.log_audit_step("Test Step", "Action", "Result OK")
        runtime.checkpoint()
        
        self.assertTrue(runtime.resume_from_checkpoint())
        self.assertEqual(len(runtime.audit_log), 1)
        self.assertIn("OpenClaw", runtime.state["runtime_engine"])
        print("  [PASS] Lab 6: OpenClaw Runtime logs steps, saves checkpoints, and restores state.")

    def test_lab_7_langchain_agentic_node_graph(self):
        """Lab 7: LangChain Runnable Sequence wired into OpenClaw Runtime node graph."""
        graph = ResearchNodeGraph()
        req = {
            "topic": "edge AI hardware porting frameworks",
            "venue": "IEEE Conference",
            "collaborators": "Faculty Author",
            "deadline": "2026-11-15"
        }
        res = graph.run_graph(req, auto_approve_gate=True)
        self.assertIn("formatted_paper", res)
        self.assertEqual(res.get("export_status"), "READY_FOR_PUBLICATION")
        print("  [PASS] Lab 7: LangChain + OpenClaw agentic node graph executes end-to-end pipeline.")

    def test_lab_8_parallel_swarm_mcp(self):
        """Lab 8: Parallel Swarm fan-out workers using MCP Tool Server."""
        swarm = ParallelSwarm()
        subqueries = ["edge AI", "microcontroller", "benchmarking"]
        merged = swarm.run_swarm(subqueries, main_topic="edge AI hardware porting")
        
        self.assertEqual(merged["total_workers_executed"], 3)
        self.assertGreater(merged["total_unique_papers"], 0)
        self.assertIn("consolidated_papers", merged)
        print("  [PASS] Lab 8: Parallel Swarm fan-out via MCP tools and fan-in merge completed.")

    def test_lab_9_deep_research(self):
        """Lab 9: iterative retrieval with a cited evidence table; stops on saturation."""
        conn = MCPServer().connector
        out = DeepResearchAgent(conn).run("edge AI hardware porting", use_online=False)
        self.assertGreater(len(out["evidence_table"]), 0)
        self.assertTrue(all(e["doi"] and e["confidence"] in ("HIGH", "MEDIUM", "LOW") for e in out["evidence_table"]))
        self.assertTrue(out["stopped_because"])
        self.assertIn("[1]", out["briefing_markdown"])
        print("  [PASS] Lab 9: Deep research builds a traceable evidence table.")

    def test_lab_10_cloud_ops_observability(self):
        """Lab 10: tracing, retry/backoff, circuit breaker, fault injection and diagnosis."""
        conn = MCPServer().connector
        tracer, faults = Tracer(), FaultInjector()
        instrument(conn, tracer, faults, retries=1, backoff_s=0.001, breaker=CircuitBreaker(threshold=2, cooldown_s=60))
        faults.arm("search_online_papers", failures=10)
        papers = conn.search_online_papers("edge", agent_id="t")        # fails -> degraded fallback
        self.assertGreater(len(papers), 0)
        self.assertEqual(conn.breaker.state, "OPEN")
        conn.search_online_papers("edge", agent_id="t")                  # short-circuited
        diag = OpsAgent().diagnose(tracer, conn)
        self.assertFalse(diag["healthy"])
        self.assertIn("injected", diag["root_cause_hint"])
        OpsAgent().remediate(conn)
        self.assertEqual(conn.breaker.state, "CLOSED")
        print("  [PASS] Lab 10: Failure injected, diagnosed, degraded gracefully and remediated.")

    def test_lab_11_agentic_sdlc(self):
        """Lab 11: requirements -> pipeline -> acceptance tests -> traceability matrix."""
        rep = SDLCFactory().run(with_unit_tests=False)
        failed = [r["id"] for r in rep["traceability"] if r["result"] != "PASS"]
        self.assertEqual(failed, [])
        self.assertTrue(rep["release_ready"])
        print("  [PASS] Lab 11: All requirement acceptance tests pass with traceability.")

    def test_lab_12_safety_governance(self):
        """Lab 12: guardrails, tamper-evident audit, approval gate, evaluation, rollback."""
        c = ResearchCoordinator(checkpoint_file="checkpoint_app.json")
        res = c.run_all(REQUEST, approve=True)
        self.assertTrue(all(g["passed"] for g in res["governance"]["guardrails"]))
        self.assertTrue(res["governance"]["ledger"]["intact"])
        self.assertGreater(res["metrics"]["overall_score"], 50)
        c.ledger.entries[0]["detail"] = "tampered"
        self.assertFalse(c.ledger.verify()["intact"])
        v1 = c.ctx["version"]
        c.tracker.log_version("t", "v", "newer text", [], status="DRAFT")
        rb = c.tracker.rollback(v1, "test")
        self.assertEqual(rb["sha256"], c.tracker.get(v1)["sha256"])
        c2 = ResearchCoordinator(checkpoint_file="checkpoint_app.json")
        c2.run_all(REQUEST, approve=False)
        with self.assertRaises(PermissionError):
            c2.export()
        print("  [PASS] Lab 12: Guardrails, ledger integrity, gate refusal and rollback verified.")

    def test_lab_13_domain_agent(self):
        """Lab 13: venue parsing, citation styles, BibTeX and originality screening."""
        spec = parse_venue("ACM journal, 10-page limit")
        self.assertEqual((spec.citation_style, spec.kind, spec.page_limit), ("ACM", "journal", 10))
        self.assertEqual(parse_venue("IEEE conference, IMRAD, 6-page limit").sections[1], "Related Work")
        ref = {"authors": ["A. Sharma", "B. Patel"], "title": "T", "venue": "V", "year": 2024, "doi": "10.1/x"}
        self.assertIn("A. Sharma", CitationFormatter().format(ref, "IEEE", 1))
        self.assertIn("@inproceedings", CitationFormatter().to_bibtex([ref]))
        src = [{"id": "S", "title": "t", "abstract": "we review lightweight compilation operator fusion and quantisation pipelines for porting"}]
        copied = {"1. Intro": "we review lightweight compilation operator fusion and quantisation pipelines for porting"}
        self.assertTrue(OriginalityChecker().check(copied, src)["flagged_sections"])
        print("  [PASS] Lab 13: Domain venue/citation/originality agent works.")

    def test_lab_14_capstone_end_to_end(self):
        """Lab 14: full coordinator run with parallel stages, gates and tracker."""
        c = ResearchCoordinator(checkpoint_file="checkpoint_app.json")
        with self.assertRaises(ValueError):
            c.intake({"topic": "x"})
        res = c.run_all(REQUEST, approve=True)
        self.assertTrue(res["validation"]["passed"])
        self.assertEqual(res["ctx"]["export_status"], "READY_FOR_PUBLICATION")
        self.assertGreaterEqual(sum(t["mode"] == "PARALLEL" for t in res["timeline"]), 3)
        self.assertEqual(len(c.tracker.history()), 1)
        print("  [PASS] Lab 14: Capstone coordinator runs end-to-end with all gates.")

    # ---------------------------------------------------------------- chapter-12 acceptance additions
    def _built(self, req=None):
        c = ResearchCoordinator(checkpoint_file="checkpoint_app.json")
        c.build(req or REQUEST)
        return c

    def test_lab_1_asks_clarifying_questions(self):
        """Lab 1 acceptance: a vague request yields at least two clarifying questions."""
        qs = RequestClarifier().questions({"topic": "GRU"})
        self.assertGreaterEqual(len(qs), 2)
        self.assertEqual(RequestClarifier().questions(REQUEST), [])
        print("  [PASS] Lab 1: vague request triggers clarifying questions.")

    def test_lab_4_vector_retrieval(self):
        """Lab 4: vector (TF-IDF cosine) retrieval returns the closest paper."""
        mem = MemoryStore(corpus=SearchTools().corpus)
        hits = mem.retrieve_by_vector("quantisation for microcontrollers")
        self.assertIn("Edge AI", hits[0]["title"])
        self.assertGreater(hits[0]["similarity"], 0)
        print("  [PASS] Lab 4: vector similarity retrieval works.")

    def test_lab_5_connector_enforces_scopes(self):
        """Lab 5: typed endpoints with auth - agents only reach endpoints in their scope."""
        c = ResearchCoordinator(checkpoint_file="checkpoint_app.json")
        c.connector.read_funding_deadlines("edge", agent_id="FundingRadarAgent")
        with self.assertRaises(PermissionError):
            c.connector.read_collaboration_notes(agent_id="FundingRadarAgent")
        with self.assertRaises(PermissionError):
            c.connector.read_paper_corpus("x", agent_id="UnknownAgent")
        self.assertTrue(any(e["decision"] == "DENIED" for e in c.connector.get_audit_trail()))
        print("  [PASS] Lab 5: connector scopes enforced and denials audited.")

    def test_lab_6_resume_after_crash(self):
        """Lab 6: a crashed run resumes from its last checkpoint."""
        c = ResearchCoordinator(checkpoint_file="checkpoint_resume.json")
        c.intake(REQUEST); c.plan(); c.confirm_outline(c.blueprint.sections); c.discover(); c.analyze_gap()
        refs = len(c.ctx["reading_list"])
        del c                                                   # "crash"
        c2 = ResearchCoordinator(checkpoint_file="checkpoint_resume.json")
        self.assertEqual(c2.resume(), "draft")
        self.assertEqual(len(c2.ctx["reading_list"]), refs)
        rep = c2.generate_and_validate()
        self.assertTrue(rep["passed"])
        import os
        os.remove(c2.checkpoint_path)
        print("  [PASS] Lab 6: run resumed from checkpoint and finished.")

    def test_lab_8_parallel_beats_sequential(self):
        """Lab 8 acceptance: parallel matches sequential quality at lower wall-clock time."""
        b = ParallelSwarm().benchmark(["edge AI", "microcontroller", "benchmarking", "hardware"], "edge AI",
                                      simulated_latency_s=0.03)
        self.assertTrue(b["same_merged_result"])
        self.assertLess(b["parallel_s"], b["sequential_s"])
        print("  [PASS] Lab 8: parallel faster with identical merged result.")

    def test_lab_9_grounding_rejects_ungrounded(self):
        """Lab 9: ungrounded / out-of-scope candidates are rejected; every kept item has an evidence record."""
        c = ResearchCoordinator(checkpoint_file="checkpoint_app.json")
        c.intake(REQUEST)
        pool = c.tools.corpus + [
            {"id": "X1", "title": "Edge AI blog post", "authors": ["Anon"], "abstract": "edge ai hardware porting rumours",
             "keywords": ["edge ai"], "doi": "N/A", "source": "RandomBlog.example"},
            {"id": "X2", "title": "Edge AI hardware porting stub", "authors": ["Anon"], "abstract": "", "keywords": [],
             "doi": "N/A", "source": "OpenAlex"}]
        c.tools.read_corpus = lambda kw="": pool
        c.discover()
        titles = [p["title"] for p in c.ctx["reading_list"]]
        self.assertNotIn("Edge AI blog post", titles)
        self.assertNotIn("Edge AI hardware porting stub", titles)
        reasons = {r["title"]: r["reason"] for r in c.ctx["rejected_references"]}
        self.assertIn("out of approved scope", reasons["Edge AI blog post"])
        self.assertIn("no abstract", reasons["Edge AI hardware porting stub"])
        self.assertTrue(all(p["evidence"]["grounded"] and p["evidence"]["supporting_sentence"] for p in c.ctx["reading_list"]))
        print("  [PASS] Lab 9: ungrounded candidates rejected; evidence records attached.")

    def test_lab_10_self_healing_targeted_repair(self):
        """Lab 10: injected validation faults are diagnosed and repaired in the retry budget; only the failing part changes."""
        for kind in [k for k in FAULTS if "unfixable" not in k]:
            c = self._built()
            sections_before = dict(c.ctx["draft_sections"])
            inject_fault(c, kind)
            c.check()
            rep = c.validate()
            self.assertFalse(rep["passed"], kind)
            out = SelfHealer(c, budget=3).heal(rep)
            self.assertTrue(out["healed"], f"{kind}: {out['report']['diagnosis']}")
            self.assertLessEqual(out["attempts"], 3)
            self.assertTrue(all(e["repair"] != "-" for e in out["log"] if e["fixed"]))
            if kind in ("remove_ai_marker", "dangling_citation"):
                unchanged = [t for t in sections_before if c.ctx["draft_sections"][t] == sections_before[t]]
                self.assertGreaterEqual(len(unchanged), len(sections_before) - 2, f"{kind} rebuilt too much")
        c = self._built()                                       # unfixable -> escalate to the human
        inject_fault(c, "starved_sources (unfixable)")
        c.check()
        out = SelfHealer(c).heal(c.validate())
        self.assertTrue(out["escalated"])
        self.assertIn("escalation", c.ctx)
        print("  [PASS] Lab 10: faults detected, repaired in-budget; unfixable case escalated.")

    def test_lab_11_acceptance_gates_human_review(self):
        """Lab 11: no brief advances to approval without a fully passing acceptance report."""
        c = self._built()
        self.assertTrue(c.ctx["acceptance"]["all_pass"])
        c.ctx["acceptance"]["all_pass"] = False
        c.ctx["acceptance"]["checks"][0]["result"] = "FAIL"
        with self.assertRaises(PermissionError):
            c.faculty_decision(True, "Dr X")
        c.ctx["acceptance"] = c.acceptance_suite()
        c.faculty_decision(True, "Dr X")
        c.export()
        print("  [PASS] Lab 11: acceptance report gates the faculty approval.")

    def test_lab_12_roles_and_confidentiality(self):
        """Lab 12: only authorised roles approve/rollback; unpublished drafts are redacted for others."""
        c = self._built()
        for role in ("student_assistant", "research_office", "coauthor"):
            with self.assertRaises(PermissionError):
                c.faculty_decision(True, "Someone", role=role)
        self.assertTrue(any(e["status"] == "DENIED" for e in c.ledger.entries))
        view = redact_view(c.ctx, Actor("Office", "research_office"))
        self.assertTrue(all("REDACTED" in t for t in view["draft_sections"].values()))
        self.assertEqual(redact_view(c.ctx, Actor("Dr X", "faculty"))["draft_sections"], c.ctx["draft_sections"])
        self.assertIn("CONFIDENTIAL", c.classification())
        c.faculty_decision(True, "Dr X", role="faculty")
        c.export()
        with self.assertRaises(PermissionError):
            c.rollback(c.ctx["version"], "Student", role="student_assistant")
        self.assertIn("INTERNAL", c.classification())
        self.assertFalse(Actor("S", "student_assistant").can_approve)
        print("  [PASS] Lab 12: role checks and confidentiality enforced.")

    def test_lab_13_domain_packs(self):
        """Lab 13: pluggable packs - detection, extra sections and checkable schemes per discipline."""
        self.assertEqual(detect_domain("CRISPR gene editing in cancer cells"), "biosciences")
        self.assertEqual(detect_domain("perovskite thin film XRD characterization"), "materials")
        self.assertEqual(detect_domain("GRU neural network"), "cs")
        c = ResearchCoordinator(checkpoint_file="checkpoint_app.json")
        c.intake({**REQUEST, "topic": "perovskite thin film XRD characterization", "domain": ""})
        c.plan()
        self.assertTrue(any("Synthesis & Characterization" in s for s in c.ctx["plan_sections"]))
        checks = get_pack("materials").checks({"3. Methods": "We used XRD at 40 kV and ASTM E8 tensile tests at 25 °C."})
        self.assertTrue(all(ch["status"] == "PASS" for ch in checks))
        pending = get_pack("biosciences").checks({"2. Ethics": "[AUTHORS TO COMPLETE: ethics, consent]"})
        self.assertEqual(pending[0]["status"], "PENDING_AUTHORS")
        print("  [PASS] Lab 13: domain packs plug in sections and checkable rules.")

    def test_radar_monitor_continuous(self):
        """Proposal: the radar runs continuously in the background and flags new/urgent alerts."""
        c = ResearchCoordinator(checkpoint_file="checkpoint_app.json")
        m = RadarMonitor(c.connector, "edge AI hardware porting", "2026-12-01", interval_s=0.05)
        m.start()
        import time
        time.sleep(0.3)
        m.stop()
        self.assertGreaterEqual(len(m.digest), 2)
        self.assertTrue(m.digest[0]["new"])
        self.assertFalse(m.digest[1]["new"])
        self.assertFalse(m.running)
        print("  [PASS] Radar monitor: background checks, new-alert detection.")

    def test_paper_fits_venue_page_range(self):
        """Paper length: typeset IEEE-style PDF lands in the venue's page range; thin evidence is reported, not padded."""
        import random
        random.seed(3)
        topics = ["quantization", "pruning", "compilation", "memory scheduling", "energy efficiency", "benchmarking"]
        papers = [{"id": f"OA_{i}", "title": f"{topics[i % 6].title()} for Edge AI Hardware Porting Frameworks {i}",
                   "authors": [f"A{i} X", f"B{i} Y"], "year": 2019 + i % 6, "venue": "IEEE Micro",
                   "abstract": f"We study {topics[i % 6]} for edge AI hardware porting on microcontrollers. Latency and memory "
                               f"are measured across frameworks. Results indicate improved deployment efficiency.",
                   "keywords": [], "doi": f"10.1000/e.{i}", "source": "OpenAlex"} for i in range(24)]
        c = ResearchCoordinator(use_live=True, checkpoint_file="checkpoint_app.json")
        c.tools.search_online = lambda q, n=6: papers
        res = c.run_all(REQUEST)
        info = c.ctx["paper_info"]
        self.assertTrue(res["validation"]["passed"])
        self.assertTrue(c.paper_pdf.startswith(b"%PDF"))
        self.assertGreaterEqual(info["pages"], 6)
        self.assertLessEqual(info["pages"], 8)
        self.assertEqual(info["status"], "IN RANGE")
        self.assertGreaterEqual(len(c.ctx["reading_list"]), 15)
        # placeholders are never filled with invented content
        self.assertIn("AUTHORS TO", " ".join(c.ctx["draft_sections"].values()))
        # offline mock corpus: fits only by reserving labelled space for the authors, and says how much
        c2 = ResearchCoordinator(checkpoint_file="checkpoint_app.json")
        c2.run_all(REQUEST)
        i2 = c2.ctx["paper_info"]
        self.assertGreater(i2["reserved_pages"], 0)
        self.assertLessEqual(i2["pages"], 8)
        print("  [PASS] Paper length: typeset PDF fits the venue page range with transparent reserved space.")

    def test_bibtex_and_formatting_survive_messy_records(self):
        """Real API records can have blank authors, None years or missing venues; formatting must not crash."""
        messy = [{"title": "T1", "authors": [""], "year": None, "venue": None, "doi": None},
                 {"title": "T2", "authors": ["  ", None, "A. B"], "year": "n.d.", "doi": "N/A"},
                 {"title": "T3", "authors": [], "year": 2023, "venue": "V"},
                 {"title": "T4", "authors": "Single Author", "year": "2021"}]
        f = CitationFormatter()
        bib = f.to_bibtex(messy)
        self.assertEqual(bib.count("@inproceedings"), 4)
        for style in ("IEEE", "ACM", "APA"):
            self.assertEqual(len(f.format_all(messy, style)), 4)
        print("  [PASS] Citation formatting and BibTeX tolerate messy API records.")

def run_all_tests():
    print("==========================================================================")
    print("      AUTOMATED VERIFICATION SUITE (LANGCHAIN + OPENCLAW + MCP LABS 1 - 14)")
    print("==========================================================================\n")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestResearchAgentLabs)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
