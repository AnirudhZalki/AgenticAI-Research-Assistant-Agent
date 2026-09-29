"""
MCP (Model Context Protocol) Data Access & Tool Layer
Exposes scholarly database and research tools according to Model Context Protocol (MCP) standards.
Uses mcp.types.Tool definitions and schema-validated tool invocation wrappers.
"""

import json
from typing import Dict, Any, List
from mcp.types import Tool, TextContent
from connector import ResearchDataConnector

class MCPServer:
    """Model Context Protocol (MCP) standard tool server."""
    
    def __init__(self, connector: ResearchDataConnector = None):
        self.connector = connector if connector is not None else ResearchDataConnector()
        self.tools = self._register_mcp_tools()

    def _register_mcp_tools(self) -> Dict[str, Tool]:
        """Registers MCP typed tools with JSON schema parameter definitions."""
        return {
            "read_paper_corpus": Tool(
                name="read_paper_corpus",
                description="Searches mock scholarly database for papers matching keyword in title, abstract, or keywords.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string", "description": "Search keyword or topic query"}
                    }
                }
            ),
            "read_researcher_library": Tool(
                name="read_researcher_library",
                description="Returns the researcher's personal prior papers library for self-citation checking.",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            "read_funding_deadlines": Tool(
                name="read_funding_deadlines",
                description="Returns upcoming journal calls for papers and grant funding deadlines.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "topic_keyword": {"type": "string", "description": "Topic keyword filter"}
                    }
                }
            ),
            "read_collaboration_notes": Tool(
                name="read_collaboration_notes",
                description="Returns collaborator notes and section ownership assignments.",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        }

    def list_tools(self) -> List[Tool]:
        """MCP Protocol: Returns list of available tools."""
        return list(self.tools.values())

    def call_tool(self, name: str, arguments: Dict[str, Any] = None, agent_id: str = "LangChainAgent") -> List[TextContent]:
        """MCP Protocol: Executes an MCP tool and returns TextContent results."""
        if arguments is None:
            arguments = {}

        if name not in self.tools:
            raise ValueError(f"MCP Error: Tool '{name}' not found on MCP Server.")

        if name == "read_paper_corpus":
            kw = arguments.get("keyword", "")
            data = self.connector.read_paper_corpus(kw, agent_id=agent_id)
        elif name == "read_researcher_library":
            data = self.connector.read_researcher_library(agent_id=agent_id)
        elif name == "read_funding_deadlines":
            kw = arguments.get("topic_keyword", "")
            data = self.connector.read_funding_deadlines(kw, agent_id=agent_id)
        elif name == "read_collaboration_notes":
            data = self.connector.read_collaboration_notes(agent_id=agent_id)
        else:
            data = {}

        return [TextContent(type="text", text=json.dumps(data, indent=2))]

if __name__ == "__main__":
    mcp_server = MCPServer()
    print("MCP Server Tools Registered:")
    for t in mcp_server.list_tools():
        print(f" - {t.name}: {t.description}")
        
    res = mcp_server.call_tool("read_paper_corpus", {"keyword": "edge"})
    print("MCP Call Tool Output Sample:", res[0].text[:150])
