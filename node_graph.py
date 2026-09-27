"""
Lab 7: Agentic Node Graph (Phase B - Orchestration)
Wires specialist agents into an explicit executable node graph with state, branching, and bounded retry back-edges.
Flow: LiteratureDiscovery -> GapAnalysis -> DraftingWriting -> CitationCompliance -> FundingRadar -> Collaboration -> Validation Gate -> (if fail: Bounded Regenerate Retry) -> Faculty Review Gate -> ExportRepository.
"""

from typing import Dict, Any
from runtime import AgentRuntime
from specialist_agents import (
    LiteratureDiscoveryAgent,
    GapAnalysisAgent,
    DraftingWritingAgent,
    CitationComplianceAgent,
    FundingRadarAgent,
    CollaborationAgent,
    ExportRepositoryAgent
)
from verify import ValidationAgent

class ResearchNodeGraph:
    def __init__(self, runtime: AgentRuntime = None, max_retry_attempts: int = 3):
        self.runtime = runtime if runtime is not None else AgentRuntime()
        self.max_retry_attempts = max_retry_attempts
        
        # Instantiate Specialist Agent Nodes
        self.lit_agent = LiteratureDiscoveryAgent()
        self.gap_agent = GapAnalysisAgent()
        self.draft_agent = DraftingWritingAgent()
        self.comp_agent = CitationComplianceAgent()
        self.radar_agent = FundingRadarAgent()
        self.collab_agent = CollaborationAgent()
        self.export_agent = ExportRepositoryAgent()
        self.validator = ValidationAgent()

    def run_graph(self, initial_request: Dict[str, Any], auto_approve_gate: bool = False) -> Dict[str, Any]:
        """Executes the full agentic node graph pipeline."""
        print("\n==========================================================================")
        print("--- PHASE B (LAB 7): AGENTIC NODE GRAPH PIPELINE EXECUTION ---")
        print("==========================================================================")
        
        # 1. Initialize context & state
        ctx = dict(initial_request)
        self.runtime.state["status"] = "PIPELINE_RUNNING"
        self.runtime.log_audit_step("Graph Init", "Initializing run context", {"topic": ctx.get("topic")})

        # 2. Sequential / Parallel Agent Step Execution
        attempts = 0
        while attempts < self.max_retry_attempts:
            attempts += 1
            print(f"\n---> Node Graph Execution Pass #{attempts}")

            # Node 1: Literature Discovery
            ctx = self.lit_agent.step(ctx, self.runtime.connector)
            self.runtime.log_audit_step("Literature Discovery", "Search & Rank Corpus", len(ctx.get("reading_list", [])))

            # Node 2: Gap & Idea Analysis
            ctx = self.gap_agent.step(ctx, self.runtime.connector)
            self.runtime.log_audit_step("Gap Analysis", "Analyze Novelty vs Overlap", ctx.get("gap_analysis", {}).get("novelty_flag"))

            # Node 3: Drafting & Writing
            ctx = self.draft_agent.step(ctx, self.runtime.connector)
            self.runtime.log_audit_step("Drafting", "Generate Outline & Draft Sections", len(ctx.get("draft_sections", {})))

            # Node 4: Citation & Compliance
            ctx = self.comp_agent.step(ctx, self.runtime.connector)
            self.runtime.log_audit_step("Citation Compliance", "Validate References & Guidelines", ctx.get("citation_compliance"))

            # Node 5: Funding / Journal Radar
            ctx = self.radar_agent.step(ctx, self.runtime.connector)
            self.runtime.log_audit_step("Radar Agent", "Scan Deadlines & CFPs", len(ctx.get("radar_deadlines", [])))

            # Node 6: Collaboration Tracking
            ctx = self.collab_agent.step(ctx, self.runtime.connector)
            self.runtime.log_audit_step("Collaboration", "Sync Co-Author Ownership", ctx.get("collaboration"))

            # Hard Gate: Validation Agent Check
            val_report = self.validator.validate(ctx)
            self.runtime.log_audit_step("Validation Check", "Acceptance Gate Evaluation", val_report, status="PASS" if val_report["passed"] else "FAIL")

            if val_report["passed"]:
                print("\n[Node Graph] Validation Gate Passed!")
                break
            else:
                print(f"\n[Node Graph Retry Edge] Validation Failed (Attempt {attempts}/{self.max_retry_attempts}). Regenerating failing nodes...")
                # Bounded back-edge regeneration trigger
                ctx["retry_count"] = attempts

        if not val_report["passed"]:
            raise RuntimeError(f"Node graph pipeline failed after {self.max_retry_attempts} attempts. Diagnosis: {val_report['diagnosis']}")

        # 3. Assemble Formatted Draft Document
        formatted_paper = self.runtime.format_skill.execute({
            "title": f"Research on {ctx.get('topic', '').title()}",
            "collaborators": [ctx.get("collaborators", "Faculty Author")],
            "abstract": ctx.get("gap_analysis", {}).get("novelty_summary", ""),
            "sections": ctx.get("draft_sections", {}),
            "references": ctx.get("reading_list", [])
        }, venue_spec=ctx.get("venue", "IEEE"))
        
        ctx["formatted_paper"] = formatted_paper

        # 4. Amber Node: Human Review Gate (Hard Stop before Publish)
        approved = self.runtime.human_approval_gate(
            action_name="Publish Formatted Research Paper",
            draft_summary=formatted_paper,
            auto_approve=auto_approve_gate
        )

        if not approved:
            print("\nPipeline stopped at Human Review Gate by Faculty Examiner.")
            self.runtime.state["status"] = "STOPPED_AT_FACULTY_GATE"
            return ctx

        # 5. Node 8: Export & Repository Logging
        ctx = self.export_agent.step(ctx, self.runtime.connector)
        self.runtime.log_audit_step("Export", "Archive Approved Document", ctx.get("version"))
        self.runtime.checkpoint()
        
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
    print("Node graph execution test passed.")
