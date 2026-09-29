"""
Research Assistant Agent - Main Orchestrator (Labs 1 through 8)
Multi-Framework Architecture:
- OpenClaw: Agent Runtime Layer (State, Audit Logs, Checkpoints, Human Gates)
- LangChain: Orchestration Layer (Runnable Sequence & RunnableLambda)
- MCP (Model Context Protocol): Tool & Data Access Layer (Typed Tool Server)
"""

import sys
import argparse
from clarify import RequestClarifier
from search import SearchTools
from skills import ResearchPlanSkill
from memory import MemoryStore
from connector import ResearchDataConnector
from mcp_server import MCPServer
from openclaw_runtime import OpenClawAgentRuntime
from langchain_orchestrator import LangChainOrchestrator
from swarm import ParallelSwarm
from node_graph import ResearchNodeGraph

def run_research_assistant_pipeline(interactive: bool = True, auto_approve: bool = False):
    print("==========================================================================")
    print("        RESEARCH ASSISTANT AGENT (LANGCHAIN + OPENCLAW + MCP PIPELINE)   ")
    print("        Guiding Principle: Agents draft and flag; faculty approves.       ")
    print("==========================================================================\n")

    # 1. Initialize Tool / Data Layer (MCP Standard)
    search_tools = SearchTools()
    connector = ResearchDataConnector(search_tools)
    mcp_server = MCPServer(connector)
    memory = MemoryStore(corpus=search_tools.corpus, library=search_tools.library)

    # 2. Initialize OpenClaw Agent Runtime & LangChain Orchestrator
    runtime = OpenClawAgentRuntime()
    orchestrator = LangChainOrchestrator(mcp_server=mcp_server)

    print(f"Agent Runtime Engine: {runtime.state['runtime_engine']}")
    print(f"MCP Server Tools Loaded: {len(mcp_server.list_tools())} tools registered.")

    # 3. Lab 1: Clarify Intent & Parameters
    clarifier = RequestClarifier()
    clarified_state = clarifier.clarify(interactive=interactive)
    memory.update_session("clarified_state", clarified_state)

    # 4. Lab 3: Plan Skill - Generate & Lock Blueprint
    plan_skill = ResearchPlanSkill()
    blueprint = plan_skill.execute(clarified_state)
    memory.update_session("active_plan", blueprint)
    
    print("\n--- PHASE 2 (LAB 3): LOCKED PLAN BLUEPRINT ---")
    print(f"Title: {blueprint.title}")
    print(f"Venue Target: {blueprint.venue} (Style: {blueprint.citation_style})")
    print(f"Deadline: {blueprint.deadline}")
    print(f"Collaborators: {', '.join(blueprint.collaborators)}")
    print("Sections Blueprint:")
    for sec in blueprint.sections:
        print(f"  - {sec}")
    print("--------------------------------------------------------------------------\n")

    # 5. Lab 8: Parallel Swarm Discovery via MCP & LangChain
    swarm = ParallelSwarm(mcp_server=mcp_server)
    subqueries = [
        clarified_state["topic"].split()[0],
        "hardware porting",
        "microcontrollers",
        "benchmarking"
    ]
    swarm_merged = swarm.run_swarm(subqueries, main_topic=clarified_state["topic"])
    memory.update_session("swarm_discovery", swarm_merged)

    # 6. Lab 7: Multi-Framework Agentic Node Graph Execution
    graph = ResearchNodeGraph(runtime=runtime, orchestrator=orchestrator)
    final_ctx = graph.run_graph(
        initial_request={
            "topic": clarified_state["topic"],
            "venue": clarified_state["venue"],
            "collaborators": clarified_state["collaborators"],
            "deadline": clarified_state["deadline"],
            "swarm_results": swarm_merged
        },
        auto_approve_gate=auto_approve
    )

    # 7. Output Final Published Brief & Audit Summary
    if runtime.state.get("status") == "PUBLISHED":
        print("\n==========================================================================")
        print("          FINAL PUBLISHED & ARCHIVED RESEARCH BRIEF (LAB 1-8)             ")
        print("==========================================================================")
        print(final_ctx.get("formatted_paper", "No formatted draft generated."))
        print("\nRadar Surfaced Upcoming Deadlines:")
        for dl in final_ctx.get("radar_deadlines", []):
            print(f"  - [{dl.get('type')}] {dl.get('title')} (Deadline: {dl.get('deadline')}) -> {dl.get('url')}")
            
        print("\nMCP Connector Access Log Entries:", len(connector.get_audit_trail()))
        print("OpenClaw Runtime Audit Log Step Count:", len(runtime.audit_log))
        print("==========================================================================\n")
        print("Pipeline finished successfully!")
    else:
        print("\nPipeline halted prior to final export.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Research Assistant Agent CLI")
    parser.add_argument("--non-interactive", action="store_true", help="Run in automated non-interactive mode")
    parser.add_argument("--auto-approve", action="store_true", help="Auto-approve faculty human gates (for testing)")
    args = parser.parse_args()

    is_interactive = not args.non_interactive
    run_research_assistant_pipeline(interactive=is_interactive, auto_approve=args.auto_approve)