"""
Automated Test Suite for Labs 1 through 8 (Research Assistant Agent)
Runs acceptance tests for each lab deliverable and verifies output criteria.
"""

import sys
import unittest
from clarify import RequestClarifier
from search import SearchTools
from skills import ResearchPlanSkill, FormattingSkill
from memory import MemoryStore
from connector import ResearchDataConnector
from runtime import AgentRuntime
from specialist_agents import LiteratureDiscoveryAgent, GapAnalysisAgent, CitationComplianceAgent
from node_graph import ResearchNodeGraph
from swarm import ParallelSwarm
from verify import ValidationAgent

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

    def test_lab_5_mcp_connector(self):
        """Lab 5: Exposes data sources through one governed connector with audit logging."""
        connector = ResearchDataConnector()
        papers = connector.read_paper_corpus("edge", agent_id="TestAgent")
        deadlines = connector.read_funding_deadlines("edge", agent_id="TestAgent")
        
        trail = connector.get_audit_trail()
        self.assertGreaterEqual(len(trail), 2)
        self.assertEqual(trail[0]["agent_id"], "TestAgent")
        print("  [PASS] Lab 5: Governed MCP data connector handles requests with audit logging.")

    def test_lab_6_governed_runtime(self):
        """Lab 6: Governed runtime with step logging, budgets, and state checkpointing."""
        runtime = AgentRuntime(max_budget_steps=10)
        runtime.log_audit_step("Test Step", "Action", "Result OK")
        runtime.checkpoint()
        
        self.assertTrue(runtime.resume_from_checkpoint())
        self.assertEqual(len(runtime.audit_log), 1)
        print("  [PASS] Lab 6: Runtime logs steps, saves checkpoints, and restores state.")

    def test_lab_7_agentic_node_graph(self):
        """Lab 7: Specialist agents wired into an executable node graph with validation & human gate."""
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
        print("  [PASS] Lab 7: Agentic node graph executes end-to-end specialist pipeline.")

    def test_lab_8_parallel_swarm(self):
        """Lab 8: Parallel Swarm fan-out workers and plan-aligned fan-in merge."""
        swarm = ParallelSwarm()
        subqueries = ["edge AI", "microcontroller", "benchmarking"]
        merged = swarm.run_swarm(subqueries, main_topic="edge AI hardware porting")
        
        self.assertEqual(merged["total_workers_executed"], 3)
        self.assertGreater(merged["total_unique_papers"], 0)
        self.assertIn("consolidated_papers", merged)
        print("  [PASS] Lab 8: Parallel Swarm fan-out and fan-in merge completed.")

def run_all_tests():
    print("==========================================================================")
    print("          RUNNING AUTOMATED VERIFICATION SUITE (LABS 1 - 8)               ")
    print("==========================================================================\n")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestResearchAgentLabs)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
