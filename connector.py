"""
Lab 5: MCP-Style Governed Data Connector (Phase A - Foundations)
Exposes a single, unified, governed surface for all data sources (paper corpus, library, notes, deadlines).
No agent touches data sources directly — all access is routed through this connector interface with audit logging.
"""

import time
from typing import Dict, Any, List
from search import SearchTools

class ResearchDataConnector:
    """Governed Model Context Protocol (MCP) style data connector server."""
    
    def __init__(self, search_tools: SearchTools = None):
        self._tools = search_tools if search_tools is not None else SearchTools()
        self.access_log: List[Dict[str, Any]] = []

    def _log_access(self, endpoint: str, params: Dict[str, Any], agent_id: str):
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "agent_id": agent_id,
            "endpoint": endpoint,
            "params": params
        }
        self.access_log.append(entry)

    def read_paper_corpus(self, keyword: str = "", agent_id: str = "AnonymousAgent") -> List[Dict[str, Any]]:
        """Governed endpoint: Read scholarly paper corpus."""
        self._log_access("read_paper_corpus", {"keyword": keyword}, agent_id)
        return self._tools.read_corpus(keyword)

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
    print(f"Connector endpoint returned {len(papers)} papers.")
    print("Access Log:", connector.get_audit_trail())
