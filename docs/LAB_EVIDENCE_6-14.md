# Review-sheet text, aligned to Chapter 12 of the Build Book (Research Assistant Agent)

Run `python run_labs.py` (25 tests) and open the Streamlit tab named in brackets. Each entry lists the chapter's acceptance
criterion and how it is met.

## Lab 1 — Agent vs Chatbot  [Workflow · Intake]
**Accept:** a vague request yields ≥ 2 clarifying questions and an editable plan.
`RequestClarifier.questions()` asks per missing field and probes vague topics ("GRU" → 5 questions); the outline can be edited (add/remove/reorder) before confirmation. Test: `test_lab_1_asks_clarifying_questions`.

## Lab 4 — Memory & Retrieval  [Memory tab]
**Accept:** retrieval returns tagged candidates and similar prior items. Session state vs long-term store; tag retrieval, keyword similarity, and **vector retrieval (TF-IDF cosine)** (`retrieve_by_vector`); prior tasks archived and surfaced at intake. Test: `test_lab_4_vector_retrieval`.

## Lab 5 — Connector  [MCP tab]
**Accept:** all data access goes through the connector, typed endpoints **and auth**. `ResearchDataConnector(auth_required=True)` enforces least-privilege scopes per agent (e.g. the radar cannot read collaboration notes); every ALLOWED/DENIED call is audited. Tools are exposed with `mcp.types.Tool`. Test: `test_lab_5_connector_enforces_scopes`.

## Lab 6 — Runtime  [Runtime tab]
**Accept:** every action logged with inputs/outputs; a crashed run resumes from its last checkpoint. The coordinator checkpoints after every stage; `coordinator.resume()` / sidebar "Resume last run" restores the context and stage. Test: `test_lab_6_resume_after_crash`.

## Lab 7 — Agentic Node Graph  [Workflow]
**Accept:** one command yields a validated draft end to end; retry edge bounded. Literature ‖ Radar → Gap → Draft → Citation ‖ Collaboration → Validation (7 checks) → self-healing back-edge (bounded) → faculty gate → export. `python research_agent.py start-workflow …`.

## Lab 8 — Parallel Swarm  [Discover stage]
**Accept:** parallel matches sequential quality at lower wall-clock time. `ParallelSwarm.benchmark()` runs both and compares merged results and time (button in the Discover stage; per-call latency can be simulated offline). Test: `test_lab_8_parallel_beats_sequential`.

## Lab 9 — Deep Research: ground & evidence  [Discover stage, Deep research tab]
**Accept:** every output maps to an in-scope source; ungrounded candidates are rejected. Each reference carries an **evidence record** (source, scope, tags, retrieved_at, supporting sentence). The grounding step rejects out-of-scope or record-less candidates (logged with the reason). Validation also requires every drafted claim to map to a grounded reference. Iterative deep research builds the paper-level evidence table. Test: `test_lab_9_grounding_rejects_ungrounded`.

## Lab 10 — Ops Resilience: validate, diagnose, fix  [Workflow · Draft, Ops tab]
**Accept:** injected faults are detected and fixed within the retry budget; regenerate only the failing part; escalate to the human when exhausted. `healing.SelfHealer` maps each failing check to a targeted repair (drop a fabricated reference and rebuild only dependent sections; strip one dangling marker; re-tag only untagged sections …) and logs a diagnosis per repair. Six faults can be injected from the Ops tab; an unfixable one (too few sources) escalates with suggested actions. API-level resilience (retry, circuit breaker, tracing) is in `ops.py`. Test: `test_lab_10_self_healing_targeted_repair`.

## Lab 11 — SDLC Factory: spec → tested output  [Draft stage, SDLC tab]
**Accept:** no brief advances to the researcher without a fully passing acceptance report. `coordinator.build()` = plan → brief + acceptance report (8 criteria AC1–AC8); `faculty_decision(approve)` raises `PermissionError` unless every criterion passes. The SDLC tab runs 17 requirement-level acceptance tests plus all unit tests and prints a traceability matrix. Tests: `test_lab_11_acceptance_gates_human_review`, `test_lab_11_agentic_sdlc`.

## Lab 12 — Safety & Governance  [Review stage, Governance tab]
**Accept:** only researcher-approved results publish; any release rolls back cleanly; confidentiality controls. `access.py`: roles (faculty, co-author, student assistant, research office) decide who can approve / roll back / export / view confidential drafts; unpublished drafts are classified CONFIDENTIAL and **redacted** for roles without access; denials are audited in the hash-chained ledger. Plus 7 guardrails, risk register, scorecard, metrics history, append-only versions with one-click rollback. Test: `test_lab_12_roles_and_confidentiality`.

## Lab 13 — Discipline-Specific Agents  [Domain tab]
**Accept:** specialist outputs use valid domain patterns and produce checkable results. Pluggable **domain packs** (CS/AI, Biosciences, Materials) selected by auto-detection or manually; each adds required sections to the plan, domain guidance for the authors, acronym expansions for search, and **checkable rules** (e.g. ethics/consent statement present, characterization methods and units stated). Venue/citation formatting (IEEE/ACM/APA/BibTeX) and originality screen in `domain.py`. Test: `test_lab_13_domain_packs`.

## Lab 14 — Capstone  [Dashboard, Capstone tab]
**Accept:** request → approved, published brief in one session, with dashboard + audit trail. The researcher dashboard shows the four chapter panels (reading list & gap · draft & compliance · deadline radar with a **continuous background monitor** · collaboration & versions), metrics, acceptance report and audit trail. Test: `test_lab_14_capstone_end_to_end`, `test_radar_monitor_continuous`.
