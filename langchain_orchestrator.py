"""
LangChain Orchestration Layer
Uses LangChain RunnableSequence and RunnableLambda to orchestrate specialist research agent pipelines.
Connects specialist nodes to the MCP Tool Server and executes governed pipeline steps.
"""

from typing import Dict, Any
from langchain_core.runnables import RunnableLambda, RunnableSequence
from mcp_server import MCPServer
from specialist_agents import (
    LiteratureDiscoveryAgent,
    GapAnalysisAgent,
    DraftingWritingAgent,
    CitationComplianceAgent,
    FundingRadarAgent,
    CollaborationAgent,
    ExportRepositoryAgent
)

class LangChainOrchestrator:
    """LangChain Orchestration Engine for Research Assistant Agent."""
    
    def __init__(self, mcp_server: MCPServer = None):
        self.mcp_server = mcp_server if mcp_server is not None else MCPServer()
        
        # Instantiate Specialist Agent Nodes
        self.lit_agent = LiteratureDiscoveryAgent()
        self.gap_agent = GapAnalysisAgent()
        self.draft_agent = DraftingWritingAgent()
        self.comp_agent = CitationComplianceAgent()
        self.radar_agent = FundingRadarAgent()
        self.collab_agent = CollaborationAgent()
        self.export_agent = ExportRepositoryAgent()

        # Build LangChain Runnables
        self.lit_runnable = RunnableLambda(self._run_lit_discovery)
        self.gap_runnable = RunnableLambda(self._run_gap_analysis)
        self.draft_runnable = RunnableLambda(self._run_drafting)
        self.comp_runnable = RunnableLambda(self._run_citation_compliance)
        self.radar_runnable = RunnableLambda(self._run_funding_radar)
        self.collab_runnable = RunnableLambda(self._run_collaboration)
        self.export_runnable = RunnableLambda(self._run_export)

        # Build LangChain Orchestration Sequence using Pipe | Operator
        self.orchestration_sequence: RunnableSequence = (
            self.lit_runnable
            | self.gap_runnable
            | self.draft_runnable
            | self.comp_runnable
            | self.radar_runnable
            | self.collab_runnable
        )

    def _run_lit_discovery(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """LangChain Runnable Node: Literature Discovery via MCP Tool."""
        return self.lit_agent.step(ctx, self.mcp_server.connector)

    def _run_gap_analysis(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """LangChain Runnable Node: Gap Analysis."""
        return self.gap_agent.step(ctx, self.mcp_server.connector)

    def _run_drafting(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """LangChain Runnable Node: Drafting & Writing."""
        return self.draft_agent.step(ctx, self.mcp_server.connector)

    def _run_citation_compliance(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """LangChain Runnable Node: Citation Compliance via MCP Tool."""
        return self.comp_agent.step(ctx, self.mcp_server.connector)

    def _run_funding_radar(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """LangChain Runnable Node: Funding Radar via MCP Tool."""
        return self.radar_agent.step(ctx, self.mcp_server.connector)

    def _run_collaboration(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """LangChain Runnable Node: Collaboration Tracking via MCP Tool."""
        return self.collab_agent.step(ctx, self.mcp_server.connector)

    def _run_export(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """LangChain Runnable Node: Export & Archiving."""
        return self.export_agent.step(ctx, self.mcp_server.connector)

    def execute_sequence(self, initial_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the complete LangChain Runnable Sequence."""
        print("\n--- LANGCHAIN ORCHESTRATOR: EXECUTING RUNNABLE SEQUENCE ---")
        return self.orchestration_sequence.invoke(initial_ctx)

if __name__ == "__main__":
    lc_orchestrator = LangChainOrchestrator()
    test_req = {
        "topic": "edge AI hardware porting frameworks",
        "venue": "IEEE Conference",
        "collaborators": "Faculty Author",
        "deadline": "2026-11-15"
    }
    out = lc_orchestrator.execute_sequence(test_req)
    print("LangChain Runnable Sequence executed successfully. Keys:", list(out.keys()))
