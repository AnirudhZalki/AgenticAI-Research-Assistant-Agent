"""
Lab 7: Agentic Node Graph (Phase B - Orchestration)
Wires specialist agents into an explicit executable node graph with state, branching, and bounded retry back-edges.
Uses LangChain for Runnable Sequence orchestration and OpenClaw for Agent Runtime execution governance.
Flow: LiteratureDiscovery -> GapAnalysis -> DraftingWriting -> CitationCompliance -> FundingRadar -> Collaboration -> Validation Gate -> (if fail: Bounded Regenerate Retry) -> Faculty Review Gate -> ExportRepository.
"""

from typing import Dict, Any
from openclaw_runtime import OpenClawAgentRuntime
from langchain_orchestrator import LangChainOrchestrator
from verify import ValidationAgent
from skills import FormattingSkill

class ResearchNodeGraph:
    def __init__(self, 
                 runtime: OpenClawAgentRuntime = None, 
                 orchestrator: LangChainOrchestrator = None,
                 max_retry_attempts: int = 3):
        self.runtime = runtime if runtime is not None else OpenClawAgentRuntime()
        self.orchestrator = orchestrator if orchestrator is not None else LangChainOrchestrator()
        self.max_retry_attempts = max_retry_attempts
        self.validator = ValidationAgent()
        self.format_skill = FormattingSkill()

    def run_graph(self, initial_request: Dict[str, Any], auto_approve_gate: bool = False) -> Dict[str, Any]:
        """Executes the full multi-framework agentic node graph pipeline."""
        print("\n==========================================================================")
        print("--- PHASE B (LAB 7): LANGCHAIN + OPENCLAW + MCP NODE GRAPH EXECUTION ---")
        print("==========================================================================")
        
        # 1. Initialize context & state in OpenClaw Runtime
        ctx = dict(initial_request)
        self.runtime.state["status"] = "PIPELINE_RUNNING"
        self.runtime.log_audit_step("Graph Init", "Initializing OpenClaw context", {"topic": ctx.get("topic")})

        # 2. Sequential LangChain Runnable Execution with OpenClaw Auditing
        attempts = 0
        val_report = {"passed": False}
        
        while attempts < self.max_retry_attempts:
            attempts += 1
            print(f"\n---> LangChain Orchestrator Pass #{attempts}")

            # Execute LangChain Runnable Sequence
            ctx = self.orchestrator.execute_sequence(ctx)
            
            # Record OpenClaw Audit Steps
            self.runtime.log_audit_step("Literature Discovery", "Search & Rank via MCP", len(ctx.get("reading_list", [])))
            self.runtime.log_audit_step("Gap Analysis", "Analyze Novelty vs Overlap", ctx.get("gap_analysis", {}).get("novelty_flag"))
            self.runtime.log_audit_step("Drafting", "Generate Outline & Draft Sections", len(ctx.get("draft_sections", {})))
            self.runtime.log_audit_step("Citation Compliance", "Validate References via MCP", ctx.get("citation_compliance"))
            self.runtime.log_audit_step("Radar Agent", "Scan Deadlines & CFPs via MCP", len(ctx.get("radar_deadlines", [])))
            self.runtime.log_audit_step("Collaboration", "Sync Ownership via MCP", ctx.get("collaboration"))

            # Hard Gate: Validation Agent Check
            val_report = self.validator.validate(ctx)
            self.runtime.log_audit_step("Validation Check", "Acceptance Gate Evaluation", val_report, status="PASS" if val_report["passed"] else "FAIL")

            if val_report["passed"]:
                print("\n[LangChain Node Graph] Validation Gate Passed!")
                break
            else:
                print(f"\n[Retry Edge] Validation Failed (Attempt {attempts}/{self.max_retry_attempts}). Regenerating...")
                ctx["retry_count"] = attempts

        if not val_report["passed"]:
            raise RuntimeError(f"Node graph pipeline failed after {self.max_retry_attempts} attempts. Diagnosis: {val_report['diagnosis']}")

        # 3. Assemble Formatted Draft Document
        formatted_paper = self.format_skill.execute({
            "title": f"Research on {ctx.get('topic', '').title()}",
            "collaborators": [ctx.get("collaborators", "Faculty Author")],
            "abstract": ctx.get("gap_analysis", {}).get("novelty_summary", ""),
            "sections": ctx.get("draft_sections", {}),
            "references": ctx.get("reading_list", [])
        }, venue_spec=ctx.get("venue", "IEEE"))
        
        ctx["formatted_paper"] = formatted_paper

        # 4. OpenClaw Amber Node: Human Review Gate (Hard Stop before Publish)
        approved = self.runtime.human_approval_gate(
            action_name="Publish Formatted Research Paper",
            draft_summary=formatted_paper,
            auto_approve=auto_approve_gate
        )

        if not approved:
            print("\nPipeline stopped at Human Review Gate by Faculty Examiner.")
            self.runtime.state["status"] = "STOPPED_AT_FACULTY_GATE"
            return ctx

        # 5. Export & Archiving Node via LangChain Runnable
        ctx = self.orchestrator._run_export(ctx)
        self.runtime.log_audit_step("Export", "Archive Approved Document", ctx.get("version"))
        self.runtime.checkpoint(session_state=ctx)
        
        self.runtime.state["status"] = "PUBLISHED"
        return ctx

if __name__ == "__main__":
    graph = ResearchNodeGraph()
    test_req = {
        "topic": "edge AI hardware porting frameworks",
        "venue": "IEEE Conference",
        "collaborators": "Faculty Author, Co-Author A",
        "deadline": "2026-11-15"
    }
    result = graph.run_graph(test_req, auto_approve_gate=True)
    print("Multi-framework node graph execution test passed.")
