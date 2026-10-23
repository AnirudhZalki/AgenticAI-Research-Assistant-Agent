# Agentic AI: Research Assistant Agent (Labs 1 – 14)
## Multi-Framework Architecture: LangChain + MCP + OpenClaw

This repository contains the complete implementation of the **Research Assistant Agent** up to **Lab 8**, refactored into a modern tri-layer agentic architecture using **LangChain**, **MCP (Model Context Protocol)**, and **OpenClaw**.

> **Guiding Principle:** Agents draft and flag; a named human (Faculty Examiner) approves. No consequential action (e.g. publication or submission) is taken autonomously.

---

## Tri-Layer System Architecture

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

## Lab Milestone Summary (Labs 1 – 14)

| Lab | Capability | Module / File |
|---|---|---|
| 1 | Clarify → plan → revise loop; Gate 1 refuses to start without topic/venue/collaborators/deadline | `clarify.py`, `coordinator.intake` |
| 2 | Typed tools instead of recalled data | `search.py` |
| 3 | Reusable skills (venue-aware plan blueprint, formatting) | `skills.py`, `domain.py` |
| 4 | Session state vs long-term retrieval | `memory.py` |
| 5 | MCP server + governed connector with access audit | `mcp_server.py`, `connector.py` |
| 6 | OpenClaw runtime: step budget, audit log, checkpoints, human gate | `openclaw_runtime.py` |
| 7 | Specialist agent graph on LangChain runnables + validation gate + bounded retry | `specialist_agents.py`, `langchain_orchestrator.py`, `node_graph.py`, `verify.py` |
| 8 | Parallel swarm fan-out / fan-in merge | `swarm.py` |
| 9 | Deep research: iterative retrieval, evidence table, cited briefing | `deep_research.py` |
| 10 | Self-healing validation (targeted repair, bounded retries, escalation) + API resilience (traces, retry, circuit breaker) | `healing.py`, `ops.py` |
| 11 | Agentic SDLC: 17 requirements → acceptance tests → traceability matrix; acceptance report gates human review | `sdlc.py`, `coordinator.acceptance_suite` |
| 12 | Governance: roles & confidentiality, 7 guardrails, hash-chained audit ledger, risk register, evaluation, rollback | `access.py`, `governance.py`, `tracker.py` |
| 13 | Pluggable domain packs (CS/AI, Biosciences, Materials) with checkable rules; venue parser, IEEE/ACM/APA/BibTeX, originality screen | `domain.py` |
| 14 | Capstone coordinator with the proposal's hybrid sequential/parallel methodology, dashboard, continuous radar | `coordinator.py`, `radar.py`, `research_agent.py`, `app.py` |

### Proposal guardrails and where they are enforced
| Guardrail | Enforcement |
|---|---|
| Never fabricate a citation/abstract/result | No synthesized papers; validation gate fails on them; draft leaves methods/results as `[AUTHORS TO COMPLETE]` |
| Flag novelty uncertainty | `GapAnalysisAgent` reports lexical overlap + explicit uncertainty statement |
| No submission without faculty approval | `coordinator.export()` raises `PermissionError` unless the gate was approved |
| Preserve co-author attribution | `CollaborationAgent` attributes edits, surfaces conflicts, overwrites nothing |
| Source links + version history | `tracker.ResearchTracker` (sha256, source links, append-only, rollback) |
| Audit log | OpenClaw runtime log + tamper-evident `AuditLedger` |

> **Data note:** `data/corpus.json` is a *mock* dataset (labelled `LocalCorpus (mock dataset)` everywhere). For real citations enable
> "Use live academic APIs" (Semantic Scholar → CrossRef → OpenAlex, no API key needed).

---

## Repository Structure

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
├── app.py                   # Streamlit web interface (Labs 1-14)
├── coordinator.py           # Lab 14: capstone Research Assistant Coordinator
├── research_agent.py        # CLI: python research_agent.py start-workflow ...
├── deep_research.py         # Lab 9
├── ops.py                   # Lab 10
├── sdlc.py                  # Lab 11
├── governance.py            # Lab 12
├── domain.py                # Lab 13
├── tracker.py               # Version history / repository
├── healing.py               # Lab 10: self-healing + fault injection
├── access.py                # Lab 12: roles & confidentiality
├── radar.py                 # Continuous funding/journal radar monitor
├── docs/LAB_EVIDENCE_6-14.md# Review-sheet text aligned to Chapter 12
├── main.py                  # End-to-End Multi-Framework Orchestrator
├── run_labs.py              # Automated test runner for Labs 1 through 8
└── README.md                # System documentation & execution guide
```

---

## How to Execute

### Prerequisites
- Python 3.8+
- Installed packages: `langchain`, `langchain_core`, `mcp`, `openclaw`

---

### Option 0: Streamlit Web Interface (recommended)
```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```
Guided workflow: **Intake → Plan & outline → Discover (swarm ‖ radar) → Draft & checks → Faculty review & export**, plus one tab per lab (tools, memory, MCP, runtime, deep research, ops/chaos drill, SDLC factory, governance, domain, one-click capstone demo). The sidebar toggle switches between the offline local corpus and live academic APIs.

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
test_lab_9_deep_research ... ok
test_lab_10_cloud_ops_observability ... ok
test_lab_11_agentic_sdlc ... ok
test_lab_12_safety_governance ... ok
test_lab_13_domain_agent ... ok
test_lab_14_capstone_end_to_end ... ok
----------------------------------------------------------------------
Ran 25 tests

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


### Option D: Proposal-style command
```bash
python research_agent.py start-workflow --topic "edge AI hardware porting frameworks" \
  --venue "IEEE conference, IMRAD, 6-page limit" --collaborators "self, co-author" --deadline 2026-11-15
```
Add `--live` for real academic APIs and `--auto-approve` to skip the terminal approval prompt (testing only).
