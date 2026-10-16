# Review-sheet text for Labs 6–14 (copy into the worklet sheet)

Evidence for every lab: `python run_labs.py` (14 tests) and the Streamlit app tab named in brackets.

## Lab 6 — OpenClaw Runtime  [Runtime tab]
**Concept:** runtime that executes steps with a budget, audit log, checkpoints and a human gate.
**Stack:** Python, `openclaw_runtime.py`, JSON checkpoints.
**Implementation:** `OpenClawAgentRuntime.log_audit_step` enforces a step budget; `checkpoint`/`resume_from_checkpoint` persist run state; `human_approval_gate` blocks export until the Faculty Examiner approves. The coordinator logs every stage here.
**Evidence:** `test_lab_6_openclaw_runtime`, Runtime tab (audit table, checkpoint save/restore).

## Lab 7 — Agentic Node Graph  [Draft & checks stage]
**Concept:** graph orchestration with branching and bounded retry.
**Stack:** LangChain `RunnableSequence/RunnableLambda/RunnableParallel`, specialist agents.
**Implementation:** Literature → Gap → Drafting → Citation ‖ Collaboration → Validation gate → (bounded regenerate) → Faculty gate → Export. Agents never invent references; validation fails on synthesized sources.
**Evidence:** `test_lab_7_*`, workflow tab 4.

## Lab 8 — Parallel Swarm  [Discover stage]
**Concept:** fan-out workers + merge. **Stack:** `ThreadPoolExecutor`, MCP tools.
**Implementation:** one worker per sub-query calls MCP `read_paper_corpus`/`read_funding_deadlines`; `MergeSelector` de-duplicates and ranks by alignment with the topic; results feed the Literature agent.
**Evidence:** `test_lab_8_*`, swarm metrics in tab 3.

## Lab 9 — Deep Research Agent  [Deep research tab]
**Concept:** deep research with evidence synthesis. **Stack:** `deep_research.py`, MCP connector, live APIs or local corpus.
**Implementation:** multi-round retrieval; each round expands the query with frequent keywords of what was found and stops on saturation. Builds an evidence table (claim = sentence copied from the paper abstract, DOI, source, confidence) and a cited briefing with limitations and evidence gaps.
**Evidence:** `test_lab_9_deep_research`; trace + evidence table in the tab.

## Lab 10 — Cloud Operations Agent  [Ops tab]
**Concept:** observability and failure handling. **Stack:** `ops.py` (Tracer, CircuitBreaker, FaultInjector, OpsAgent).
**Implementation:** every connector endpoint is traced (latency, status); the search endpoint has retry with exponential backoff, a circuit breaker and graceful fallback to the local corpus. The tab injects failures (the "failed deployment"), shows the breaker opening, diagnoses the root cause, and remediates.
**Evidence:** `test_lab_10_cloud_ops_observability`; Ops tab drill (inject → probe → diagnose → auto-remediate).

## Lab 11 — Agentic SDLC Factory  [SDLC tab]
**Concept:** requirements → tested implementation. **Stack:** `sdlc.py`, `unittest`.
**Implementation:** 12 requirements derived from the proposal, each with an executable acceptance test (including negative tests: gate refusal, tampered ledger). The factory runs the pipeline, executes the tests plus the lab unit tests, and outputs a requirements-traceability matrix and a release-ready verdict.
**Evidence:** `test_lab_11_agentic_sdlc`; SDLC tab matrix.

## Lab 12 — Safety & Governance  [Governance tab]
**Concept:** approval gates, audit logs, evaluation, rollback. **Stack:** `governance.py`, `tracker.py`, `hashlib`.
**Implementation:** seven executable guardrails (G1–G7); hash-chained tamper-evident ledger (edits are detected); risk register with dynamic escalation (e.g. mock-only sources); per-run scorecard and multi-topic regression; append-only version history with rollback.
**Evidence:** `test_lab_12_safety_governance`; Governance tab (guardrails, tamper demo, regression), version history in Workflow tab.

## Lab 13 — Discipline-Specific Agent (CSE/AI publishing)  [Domain tab]
**Concept:** domain worklet. **Stack:** `domain.py`.
**Implementation:** parses a free-text venue into citation style, structure (IMRAD/survey/grant) and page→word limits; formats IEEE/ACM/APA references and BibTeX without inventing missing fields; screens drafts for 5-gram overlap with known sources.
**Evidence:** `test_lab_13_domain_agent`; Domain tab.

## Lab 14 — Capstone  [Capstone tab + whole Workflow]
**Concept:** integrated system. **Stack:** LangChain + OpenClaw + MCP + Streamlit.
**Implementation:** `ResearchCoordinator` runs Gate 1 → outline → parallel discovery → gap → draft → parallel checks → validation → faculty gate → parallel export, with timeline, guardrails, scorecard and version history. Also available as `research_agent.py start-workflow` (the proposal's prompt command).
**Evidence:** `test_lab_14_capstone_end_to_end`; Capstone tab timeline.
