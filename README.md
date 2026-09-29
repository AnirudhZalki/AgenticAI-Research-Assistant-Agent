# Agentic AI: Research Assistant Agent (Labs 1 – 8)
## Multi-Framework Architecture: LangChain + MCP + OpenClaw

This repository contains the complete implementation of the **Research Assistant Agent** up to **Lab 8**, refactored into a modern tri-layer agentic architecture using **LangChain**, **MCP (Model Context Protocol)**, and **OpenClaw**.

> **Guiding Principle:** Agents draft and flag; a named human (Faculty Examiner) approves. No consequential action (e.g. publication or submission) is taken autonomously.

---

## 🏛️ Tri-Layer System Architecture

```text
+-----------------------------------------------------------------------------------+
|                           AGENT RUNTIME LAYER (OpenClaw)                          |
|  OpenClaw Runtime Controller  |  Step Budget Governance  |  Audit & Checkpointing |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        ORCHESTRATION LAYER (LangChain Core)                       |
|   RunnableSequence  |  RunnableLambda  |  Specialist Node Pipeline Orchestration  |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                     TOOL & DATA ACCESS LAYER (MCP Standard)                       |
|   MCP Server  |  mcp.types.Tool  |  read_corpus | read_library | read_deadlines   |
+-----------------------------------------------------------------------------------+
```

1. **LangChain (Orchestration Layer)**: Uses `langchain_core.runnables` (`RunnableSequence`, `RunnableLambda`) to orchestrate specialist agents in sequence.
2. **MCP Standard (Tool & Data Access Layer)**: Exposes all scholarly data and research tools via an MCP Server using `mcp.types.Tool` definitions.
3. **OpenClaw (Agent Runtime Layer)**: Manages execution step budgets, checkpointing (`checkpoint.json`), structured audit logs, and faculty human review gates using `openclaw` runtime hooks.

---

## 🚀 Lab Milestone Summary (Labs 1 – 8)

| Lab | Capability Implemented | Framework Layer | Module / File |
|---|---|---|---|
| **Lab 1** | Request parameter clarification & editable plan proposal. | OpenClaw / Foundation | `clarify.py` |
| **Lab 2** | Typed tools replacing memory hallucinations. | MCP Tool Layer | `search.py` |
| **Lab 3** | Schema-typed skills: `ResearchPlanSkill` & `FormattingSkill`. | LangChain / Foundation | `skills.py` |
| **Lab 4** | Session run-state vs stored memory store. | OpenClaw Memory | `memory.py` |
| **Lab 5** | Model Context Protocol (MCP) Server endpoints (`read_paper_corpus`, `read_library`, `read_deadlines`, `read_notes`). | MCP Protocol Server | `mcp_server.py`, `connector.py` |
| **Lab 6** | OpenClaw Agent Runtime controller, checkpoints (`checkpoint.json`), audit logs, human gates. | OpenClaw Runtime | `openclaw_runtime.py` |
| **Lab 7** | Specialist agent node graph executed via LangChain Runnable Sequence with OpenClaw governance. | LangChain + OpenClaw | `langchain_orchestrator.py`, `specialist_agents.py`, `node_graph.py`, `verify.py` |
| **Lab 8** | Parallel Swarm fan-out workers (`ThreadPoolExecutor`) invoking MCP tools & fan-in merge. | LangChain + MCP | `swarm.py` |

---

## 📁 Repository Structure

```text
AgenticAI-Research-Assistant-Agent/
├── data/
│   ├── corpus.json          # Mock scholarly paper database with DOIs, keywords, abstracts
│   ├── library.json         # Researcher's personal prior publication library
│   ├── deadlines.json       # Mock upcoming journal CFPs and grant funding deadlines
│   └── notes_drafts.json    # Collaborator section assignments & notes
├── mcp_server.py            # MCP Standard Tool Server (read_corpus, read_library, read_deadlines, read_notes)
├── openclaw_runtime.py      # OpenClaw Agent Runtime layer (step budgets, checkpoints, audit logs, human gate)
├── langchain_orchestrator.py# LangChain Orchestration layer (RunnableSequence & RunnableLambda)
├── clarify.py               # Lab 1: Interactive & automated parameter clarification
├── search.py                # Lab 2: Typed data search tools
├── skills.py                # Lab 3: PlanBlueprint & Formatting skills
├── memory.py                # Lab 4: Short-term run state & retrieval store
├── connector.py             # Lab 5: Governed data connector underneath MCP server
├── specialist_agents.py     # Lab 7: Specialist agents (Lit Discovery, Gap, Draft, Citation, Radar, Collab, Export)
├── verify.py                # Lab 2 & 7: Validation Agent & citation grounding gate
├── node_graph.py            # Lab 7: Node Graph pipeline orchestrator linking LangChain & OpenClaw
├── swarm.py                 # Lab 8: Parallel Swarm fan-out workers calling MCP tools & fan-in selector merge
├── app.py                   # Streamlit web interface for the full Labs 1-8 workflow
├── main.py                  # End-to-End Multi-Framework Orchestrator
├── run_labs.py              # Automated test runner for Labs 1 through 8
└── README.md                # System documentation & execution guide
```

---

## 🛠️ How to Execute

### Prerequisites
- Python 3.8+
- Installed packages: `langchain`, `langchain_core`, `mcp`, `openclaw`

---

### Option 0: Streamlit Web Interface (recommended)
```bash
pip install -r requirements.txt
streamlit run app.py
```
Guided workflow: **Clarify (Lab 1) → Plan (Lab 3) → Discover swarm (Lab 8) → Pipeline (Lab 7) → Faculty approval & export (Lab 6)**, plus inspection tabs for typed tools (Lab 2), memory (Lab 4), the MCP server and audit trail (Lab 5), and the OpenClaw runtime audit log/checkpoints (Lab 6). The sidebar toggle switches between the offline local corpus and live academic APIs.

---

### Option A: Run Automated Verification Suite (Labs 1 to 8)
To run unit tests and acceptance checks for all framework layers and labs:

```bash
python run_labs.py
```

**Expected Output:**
```text
test_lab_1_clarifier_planner_loop ... ok
test_lab_2_typed_tools ... ok
test_lab_3_reusable_skills ... ok
test_lab_4_memory_and_retrieval ... ok
test_lab_5_mcp_server_connector ... ok
test_lab_6_openclaw_runtime ... ok
test_lab_7_langchain_agentic_node_graph ... ok
test_lab_8_parallel_swarm_mcp ... ok
----------------------------------------------------------------------
Ran 8 tests in 0.028s

OK
```

---

### Option B: Interactive Pipeline Run
To run the complete interactive multi-framework pipeline:

```bash
python main.py
```

---

### Option C: Non-Interactive / Automated Execution
To run the end-to-end pipeline automatically (for CI/CD or benchmark evaluation):

```bash
python main.py --non-interactive --auto-approve
```
