"""
Lab 5: MCP-Style Governed Data Connector (Phase A - Foundations)
Exposes a single, unified, governed surface for all data sources (paper corpus, library, notes, deadlines).
No agent touches data sources directly — all access is routed through this connector interface with audit logging.
"""

import time
from typing import Dict, Any, List
from search import SearchTools

# Least-privilege scopes (agent-id prefix -> endpoints it may call). Used when auth_required=True.
DEFAULT_SCOPES: Dict[str, List[str]] = {
    "LiteratureDiscoveryAgent": ["read_paper_corpus", "search_online_papers"],
    "DeepResearchAgent": ["read_paper_corpus", "search_online_papers"],
    "SwarmWorker": ["read_paper_corpus", "read_funding_deadlines"],
    "GapAnalysisAgent": ["read_researcher_library"],
    "CitationComplianceAgent": ["read_researcher_library", "read_paper_corpus"],
    "FundingRadarAgent": ["read_funding_deadlines"],
    "RadarMonitor": ["read_funding_deadlines"],
    "CollaborationAgent": ["read_collaboration_notes"],
    "OpsProbe": ["search_online_papers"],
    "StreamlitUser": ["*"],
    "Coordinator": ["*"],
}


class ResearchDataConnector:
    """Governed Model Context Protocol (MCP) style data connector server.

    When auth_required is True every endpoint call must come from a registered agent whose scope includes the
    endpoint; anything else is refused (PermissionError) and the denial is written to the access log.
    """

    def __init__(self, search_tools: SearchTools = None, auth_required: bool = False,
                 scopes: Dict[str, List[str]] = None):
        self._tools = search_tools if search_tools is not None else SearchTools()
        self.access_log: List[Dict[str, Any]] = []
        self.auth_required = auth_required
        self.scopes = dict(scopes if scopes is not None else DEFAULT_SCOPES)

    def grant(self, agent_prefix: str, endpoints: List[str]):
        self.scopes[agent_prefix] = list(endpoints)

    def _authorized(self, agent_id: str, endpoint: str) -> bool:
        if not self.auth_required:
            return True
        for prefix, eps in self.scopes.items():
            if agent_id.startswith(prefix):
                return "*" in eps or endpoint in eps
        return False

    def _log_access(self, endpoint: str, params: Dict[str, Any], agent_id: str):
        allowed = self._authorized(agent_id, endpoint)
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "agent_id": agent_id,
            "endpoint": endpoint,
            "params": params,
            "decision": "ALLOWED" if allowed else "DENIED",
        }
        self.access_log.append(entry)
        if not allowed:
            raise PermissionError(f"Connector denied: '{agent_id}' has no scope for '{endpoint}'")

    def read_paper_corpus(self, keyword: str = "", agent_id: str = "AnonymousAgent") -> List[Dict[str, Any]]:
        """Governed endpoint: Read scholarly paper corpus (local JSON store)."""
        self._log_access("read_paper_corpus", {"keyword": keyword}, agent_id)
        return self._tools.read_corpus(keyword)

    def search_online_papers(self, query: str, max_results: int = 6, agent_id: str = "AnonymousAgent") -> List[Dict[str, Any]]:
        """Governed endpoint: Fetch real scholarly papers from live academic APIs (Semantic Scholar → CrossRef → OpenAlex → local fallback)."""
        self._log_access("search_online_papers", {"query": query, "max_results": max_results}, agent_id)
        return self._tools.search_online(query, max_results)

    def read_researcher_library(self, agent_id: str = "AnonymousAgent") -> List[Dict[str, Any]]:
        """Governed endpoint: Read researcher's personal prior papers library."""
        self._log_access("read_researcher_library", {}, agent_id)
        return self._tools.read_library()

    def read_funding_deadlines(self, topic_keyword: str = "", agent_id: str = "AnonymousAgent") -> List[Dict[str, Any]]:
        """Governed endpoint: Read upcoming journal calls for papers and grant deadlines."""
        self._log_access("read_funding_deadlines", {"topic_keyword": topic_keyword}, agent_id)
        return self._tools.read_deadlines(topic_keyword)

    def read_collaboration_notes(self, agent_id: str = "AnonymousAgent") -> Dict[str, Any]:
        """Governed endpoint: Read collaborator notes and section ownership assignments."""
        self._log_access("read_collaboration_notes", {}, agent_id)
        return self._tools.read_notes()

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Returns log of all data connector interactions."""
        return self.access_log

if __name__ == "__main__":
    connector = ResearchDataConnector()
    papers = connector.read_paper_corpus("edge", agent_id="LiteratureDiscoveryAgent")
    print(f"[Local] Connector returned {len(papers)} papers.")
    print("\n[Online] Fetching live papers for 'federated learning healthcare'...")
    live = connector.search_online_papers("federated learning healthcare", max_results=3, agent_id="TestAgent")
    for p in live:
        print(f"  - [{p.get('source','local')}] {p['title']} ({p['year']}) — {p['venue']}")
    print("Access Log:", connector.get_audit_trail())

