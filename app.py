"""
Research Assistant Agent - Streamlit Interface (Labs 1 through 8)

Run with:  streamlit run app.py

Stages (each one maps to a lab):
  1. Clarify   (Lab 1)  - RequestClarifier parameters, missing-field detection
  2. Plan      (Lab 1/3) - ResearchPlanSkill blueprint, revise sections, lock
  3. Discover  (Lab 8)  - parallel swarm fan-out / fan-in over MCP tools
  4. Pipeline  (Lab 7)  - LangChain runnable sequence + validation gate + bounded retry
  5. Review    (Lab 6)  - OpenClaw human approval gate, export, checkpoint
  Inspect tabs: Lab 2 typed tools, Lab 4 memory, Lab 5 MCP connector, Lab 6 runtime audit.
"""

import json
import os
import time

import pandas as pd
import streamlit as st

from clarify import RequestClarifier
from connector import ResearchDataConnector
from langchain_orchestrator import LangChainOrchestrator
from mcp_server import MCPServer
from memory import MemoryStore
from openclaw_runtime import OpenClawAgentRuntime
from search import SearchTools
from skills import FormattingSkill, ResearchPlanSkill
from swarm import ParallelSwarm
from verify import ValidationAgent

st.set_page_config(page_title="Research Assistant Agent", page_icon="🔬", layout="wide")

STAGES = ["1 · Clarify", "2 · Plan", "3 · Discover", "4 · Pipeline", "5 · Review"]
REQUIRED = RequestClarifier().required_fields
APP_CHECKPOINT = "checkpoint_app.json"  # keep app runs separate from the CLI checkpoint


# ----------------------------------------------------------------------------
# Session-state bootstrap
# ----------------------------------------------------------------------------
def build_stack(use_live_apis: bool):
    """Create the tool layer (MCP), memory, runtime (OpenClaw) and orchestrator (LangChain)."""
    tools = SearchTools()
    if not use_live_apis:
        tools.search_online = lambda query, max_results=6: []  # forces local-corpus fallback
    connector = ResearchDataConnector(tools)
    mcp = MCPServer(connector)
    st.session_state.tools = tools
    st.session_state.connector = connector
    st.session_state.mcp = mcp
    st.session_state.memory = MemoryStore(corpus=tools.corpus, library=tools.library)
    st.session_state.runtime = OpenClawAgentRuntime(checkpoint_file=APP_CHECKPOINT)
    st.session_state.orchestrator = LangChainOrchestrator(mcp_server=mcp)
    st.session_state.live = use_live_apis


def reset_workflow():
    for k in ["clarified", "blueprint", "swarm", "ctx", "val_report", "attempts",
              "gate", "formatted", "final", "params"]:
        st.session_state.pop(k, None)
    st.session_state.stage = 0
    build_stack(st.session_state.get("live", False))


def init_state():
    if "tools" not in st.session_state:
        build_stack(use_live_apis=False)
        st.session_state.stage = 0


def go(stage: int):
    st.session_state.stage = stage
    st.rerun()


init_state()
S = st.session_state

# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
with st.sidebar:
    st.title("🔬 Research Assistant")
    st.caption("Agents draft and flag; a named human (Faculty Examiner) approves.")
    live = st.toggle("Use live academic APIs", value=S.live,
                     help="Semantic Scholar / CrossRef / OpenAlex. Off = local corpus only (fast, offline).")
    if live != S.live:
        build_stack(live)
        st.rerun()

    st.markdown("**Workflow progress**")
    for i, name in enumerate(STAGES):
        icon = "✅" if i < S.stage else ("▶️" if i == S.stage else "⚪")
        st.write(f"{icon} {name}")
    st.progress(min(S.stage, len(STAGES)) / len(STAGES))

    st.divider()
    st.markdown("**Layers**")
    st.caption("OpenClaw runtime · LangChain orchestration · MCP tool layer")
    st.metric("Runtime steps", f"{S.runtime.current_step}/{S.runtime.max_budget_steps}")
    st.metric("MCP calls logged", len(S.connector.get_audit_trail()))
    if st.button("🔄 Start over", width="stretch"):
        reset_workflow()
        st.rerun()

st.title("Research Assistant Agent")
st.caption("Clarify → Plan → Discover → Draft & Validate → Faculty Approval → Export")

main_tab, tools_tab, memory_tab, mcp_tab, runtime_tab = st.tabs(
    ["🧭 Workflow", "🛠 Tools (Lab 2)", "🧠 Memory (Lab 4)", "🔌 MCP (Lab 5)", "⚙️ Runtime (Lab 6)"]
)

# ----------------------------------------------------------------------------
# Workflow
# ----------------------------------------------------------------------------
with main_tab:
    stage = S.stage

    # ---- Stage 1: Clarify (Lab 1) -------------------------------------------
    if stage == 0:
        st.subheader("Lab 1 · Clarify the research request")
        st.write("The agent refuses to plan until all four required parameters are supplied.")
        defaults = S.get("params", {})
        with st.form("clarify_form"):
            topic = st.text_input("Research topic / question", defaults.get("topic", ""),
                                  placeholder="e.g. edge AI hardware porting frameworks")
            venue = st.text_input("Target venue", defaults.get("venue", ""),
                                  placeholder="e.g. IEEE Conference, IMRAD, 6-page limit")
            collaborators = st.text_input("Collaborators (comma separated)", defaults.get("collaborators", ""),
                                          placeholder="e.g. Faculty Author, Co-Author A")
            deadline = st.text_input("Submission deadline", defaults.get("deadline", ""),
                                     placeholder="YYYY-MM-DD")
            submitted = st.form_submit_button("Clarify request", type="primary")
        if submitted:
            S.params = dict(topic=topic, venue=venue, collaborators=collaborators, deadline=deadline)
            missing = [f for f in REQUIRED if not S.params[f].strip()]
            if missing:
                st.warning("Assistant: I still need → " + ", ".join(f"**{m}**" for m in missing))
            else:
                clarifier = RequestClarifier()
                # interactive=False + all fields supplied => no defaults and no input() calls
                state = clarifier.clarify(initial_inputs=S.params, interactive=False)
                S.clarified = state
                S.memory.update_session("clarified_state", state)
                S.runtime.log_audit_step("Clarify", "RequestClarifier", state)
                go(1)
        if st.button("Fill with demo values"):
            S.params = dict(topic="edge AI hardware porting frameworks",
                            venue="IEEE conference, IMRAD, 6-page limit",
                            collaborators="Faculty Author, Co-Author A", deadline="2026-11-15")
            st.rerun()

    # ---- Stage 2: Plan (Lab 1 revise loop + Lab 3 skill) ---------------------
    elif stage == 1:
        st.subheader("Lab 3 · Research plan blueprint (revise, then lock)")
        if "blueprint" not in S:
            S.blueprint = ResearchPlanSkill().execute(S.clarified)
        bp = S.blueprint
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"**Title:** {bp.title}")
            st.markdown(f"**Venue:** {bp.venue}  ·  **Citation style:** {bp.citation_style}")
            st.markdown(f"**Deadline:** {bp.deadline}  ·  **Word limit:** {bp.word_limit}")
            st.markdown(f"**Collaborators:** {', '.join(bp.collaborators)}")
        with c2:
            st.info("Blueprint is generated by `ResearchPlanSkill`. Revise the outline below; "
                    "approving locks it.")
        st.markdown("**Sections**")
        for i, sec in enumerate(bp.sections):
            col_a, col_b = st.columns([10, 1])
            col_a.write(sec)
            if col_b.button("✖", key=f"rm_{i}", help="Remove section"):
                bp.sections.pop(i)
                st.rerun()
        with st.form("add_section", clear_on_submit=True):
            new_sec = st.text_input("Revise plan: add a section")
            if st.form_submit_button("Add section") and new_sec.strip():
                bp.sections.append(f"{len(bp.sections) + 1}. {new_sec.strip()}")
                st.rerun()
        if st.button("✅ Approve & lock plan", type="primary"):
            bp.locked = True
            S.memory.update_session("active_plan", bp)
            S.runtime.log_audit_step("Plan", "ResearchPlanSkill locked", bp.title)
            go(2)
        if st.button("← Back"):
            go(0)

    # ---- Stage 3: Discover swarm (Lab 8) -------------------------------------
    elif stage == 2:
        st.subheader("Lab 8 · Parallel swarm discovery (fan-out → fan-in)")
        topic = S.clarified["topic"]
        default_qs = [topic.split()[0], "hardware porting", "microcontrollers", "benchmarking"]
        qs_text = st.text_area("Sub-queries (one per line) — each is handled by its own worker",
                               S.get("subq_text", "\n".join(default_qs)), height=110)
        S.subq_text = qs_text
        subqueries = [q.strip() for q in qs_text.splitlines() if q.strip()]
        if st.button("🚀 Dispatch swarm", type="primary", disabled=not subqueries):
            with st.spinner(f"Running {len(subqueries)} workers in parallel via MCP tools..."):
                S.swarm = ParallelSwarm(mcp_server=S.mcp).run_swarm(subqueries, main_topic=topic)
                S.memory.update_session("swarm_discovery", S.swarm)
                S.runtime.log_audit_step("Swarm", f"{len(subqueries)} workers", S.swarm["total_unique_papers"])
        if "swarm" in S:
            sw = S.swarm
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Workers", sw["total_workers_executed"])
            m2.metric("Unique papers", sw["total_unique_papers"])
            m3.metric("Deadlines", sw["total_unique_deadlines"])
            m4.metric("Wall clock (s)", sw["swarm_wall_clock_time_sec"])
            best = sw.get("best_aligned_paper")
            if best:
                st.success(f"Best-aligned paper: **{best['title']}** ({best.get('year', '')})")
            if sw["consolidated_papers"]:
                st.dataframe(pd.DataFrame(sw["consolidated_papers"])[
                    [c for c in ["id", "title", "year", "venue", "keywords"]
                     if c in sw["consolidated_papers"][0]]], width="stretch", hide_index=True)
            else:
                st.info("No corpus matches for these sub-queries; the pipeline will still discover papers.")
        cb, cn = st.columns(2)
        if cb.button("← Back"):
            go(1)
        if cn.button("Continue to pipeline →", type="primary", disabled="swarm" not in S):
            go(3)

    # ---- Stage 4: Pipeline (Lab 7) --------------------------------------------
    elif stage == 3:
        st.subheader("Lab 7 · Specialist agent node graph (LangChain + OpenClaw)")
        max_retry = st.slider("Bounded retry attempts (validation back-edge)", 1, 5, 3)
        if st.button("▶️ Run pipeline", type="primary"):
            runtime, orch, validator = S.runtime, S.orchestrator, ValidationAgent()
            bp = S.blueprint
            base_ctx = {
                "topic": S.clarified["topic"], "venue": S.clarified["venue"],
                "collaborators": S.clarified["collaborators"], "deadline": S.clarified["deadline"],
                "swarm_results": S.swarm,
            }
            runtime.state["status"] = "PIPELINE_RUNNING"
            runtime.log_audit_step("Graph Init", "Initializing OpenClaw context", {"topic": base_ctx["topic"]})
            steps_view = st.status("Running specialist agents...", expanded=True)
            ctx, report, attempts = dict(base_ctx), {"passed": False}, 0
            while attempts < max_retry:
                attempts += 1
                steps_view.write(f"LangChain pass #{attempts}")
                ctx = orch.execute_sequence(ctx)
                runtime.log_audit_step("Literature Discovery", "Search & rank via MCP", len(ctx.get("reading_list", [])))
                runtime.log_audit_step("Gap Analysis", "Novelty vs overlap", ctx.get("gap_analysis", {}).get("novelty_flag"))
                runtime.log_audit_step("Drafting", "Outline & sections", len(ctx.get("draft_sections", {})))
                runtime.log_audit_step("Citation Compliance", "Validate references", ctx.get("citation_compliance"))
                runtime.log_audit_step("Radar", "Deadlines & CFPs", len(ctx.get("radar_deadlines", [])))
                runtime.log_audit_step("Collaboration", "Section ownership", ctx.get("collaboration"))
                report = validator.validate(ctx)
                runtime.log_audit_step("Validation", "Acceptance gate", report,
                                       status="PASS" if report["passed"] else "FAIL")
                steps_view.write(f"Validation: {'✅ passed' if report['passed'] else '❌ ' + report['diagnosis']}")
                if report["passed"]:
                    break
                ctx["retry_count"] = attempts
            S.val_report, S.attempts, S.ctx = report, attempts, ctx
            if report["passed"]:
                S.formatted = FormattingSkill().execute({
                    "title": f"Research on {ctx.get('topic', '').title()}",
                    "collaborators": [ctx.get("collaborators", "Faculty Author")],
                    "abstract": ctx.get("gap_analysis", {}).get("novelty_summary", ""),
                    "sections": ctx.get("draft_sections", {}),
                    "references": ctx.get("reading_list", []),
                }, venue_spec=bp.citation_style)
                ctx["formatted_paper"] = S.formatted
                S.memory.update_session("current_draft", S.formatted)
                runtime.checkpoint(session_state=ctx)
                steps_view.update(label="Pipeline complete — awaiting faculty review", state="complete")
            else:
                steps_view.update(label="Validation failed after retries", state="error")

        if "ctx" in S:
            ctx, rep = S.ctx, S.val_report
            (st.success if rep["passed"] else st.error)(
                f"Validation gate {'PASSED' if rep['passed'] else 'FAILED'} after {S.attempts} attempt(s)")
            for name in rep["passed_checks"]:
                st.write(f"✅ {name}")
            for name in rep["failing_checks"]:
                st.write(f"❌ {name}")
            t1, t2, t3, t4, t5, t6 = st.tabs(["Reading list", "Gap analysis", "Draft", "Citations",
                                              "Deadline radar", "Collaboration"])
            with t1:
                rl = ctx.get("reading_list", [])
                for p in rl:
                    st.markdown(f"**{p.get('title')}** — {p.get('venue', '')}, {p.get('year', '')}  \n"
                                f"`{p.get('doi', 'N/A')}`  ·  source: {p.get('source', 'local')}")
            with t2:
                st.json(ctx.get("gap_analysis", {}))
            with t3:
                for sec, txt in ctx.get("draft_sections", {}).items():
                    with st.expander(sec):
                        st.write(txt)
            with t4:
                st.json(ctx.get("citation_compliance", {}))
            with t5:
                rd = ctx.get("radar_deadlines", [])
                if rd:
                    st.dataframe(pd.DataFrame(rd), width="stretch", hide_index=True)
                else:
                    st.info("No matching deadlines.")
            with t6:
                st.json(ctx.get("collaboration", {}))
        cb, cn = st.columns(2)
        if cb.button("← Back"):
            go(2)
        if cn.button("Continue to faculty review →", type="primary",
                     disabled="formatted" not in S):
            go(4)

    # ---- Stage 5: Review gate (Lab 6) ------------------------------------------
    elif stage == 4:
        st.subheader("Lab 6 · Faculty Examiner approval gate")
        st.warning("Hard stop: nothing is exported or published without explicit human approval.")
        st.code(S.formatted, language="text")
        if S.get("gate") is None:
            approver = st.text_input("Approver name", "Faculty Examiner")
            ca, cr = st.columns(2)
            if ca.button("✅ Approve & export", type="primary"):
                S.runtime.log_audit_step("Human Gate: Publish Formatted Research Paper",
                                         "Faculty Review", f"APPROVED by {approver}", status="APPROVED")
                S.final = S.orchestrator._run_export(dict(S.ctx))
                S.runtime.log_audit_step("Export", "Archive approved document", S.final.get("version"))
                S.runtime.state["status"] = "PUBLISHED"
                S.runtime.checkpoint(session_state=S.final)
                S.memory.archive_task({"topic": S.clarified["topic"], "version": S.final.get("version"),
                                       "approved_by": approver})
                S.gate = "approved"
                st.rerun()
            if cr.button("❌ Reject / request revision"):
                S.runtime.log_audit_step("Human Gate: Publish Formatted Research Paper",
                                         "Faculty Review", f"REJECTED by {approver}", status="REJECTED")
                S.runtime.state["status"] = "STOPPED_AT_FACULTY_GATE"
                S.gate = "rejected"
                st.rerun()
        elif S.gate == "approved":
            st.success(f"Approved and archived as version **{S.final.get('version')}** "
                       f"(status: {S.final.get('export_status')})")
            st.download_button("⬇️ Download paper draft", S.formatted, file_name="research_draft.txt")
            st.download_button("⬇️ Download audit log (JSON)",
                               json.dumps(S.runtime.audit_log, indent=2), file_name="audit_log.json")
        else:
            st.error("Rejected by Faculty Examiner. Go back to the pipeline to regenerate.")
            if st.button("← Return to pipeline"):
                S.gate = None
                S.runtime.state["status"] = "PIPELINE_RUNNING"
                go(3)

# ----------------------------------------------------------------------------
# Inspection tabs
# ----------------------------------------------------------------------------
with tools_tab:
    st.subheader("Lab 2 · Typed tools (no hallucinated data)")
    kw = st.text_input("Corpus keyword", "edge", key="tool_kw")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**read_corpus**")
        res = S.tools.read_corpus(kw)
        st.caption(f"{len(res)} matching papers")
        if res:
            st.dataframe(pd.DataFrame(res), width="stretch", hide_index=True)
    with c2:
        st.markdown("**read_deadlines**")
        dl = S.tools.read_deadlines(kw)
        st.caption(f"{len(dl)} matching deadlines")
        if dl:
            st.dataframe(pd.DataFrame(dl), width="stretch", hide_index=True)
    with st.expander("read_library"):
        st.dataframe(pd.DataFrame(S.tools.read_library()), width="stretch", hide_index=True)
    with st.expander("read_notes"):
        st.json(S.tools.read_notes())

with memory_tab:
    st.subheader("Lab 4 · Short-term session state vs long-term retrieval")
    l, r = st.columns(2)
    with l:
        st.markdown("**Session state (short-term)**")
        st.json(json.loads(json.dumps(S.memory.session_state, default=lambda o: getattr(o, "__dict__", str(o)))),
                expanded=1)
    with r:
        st.markdown("**Long-term retrieval**")
        q = st.text_input("Similarity query", S.get("clarified", {}).get("topic", "edge ai"), key="mem_q")
        mode = st.radio("Mode", ["Similarity", "Tags"], horizontal=True)
        hits = (S.memory.retrieve_by_similarity(q) if mode == "Similarity"
                else S.memory.retrieve_by_tags([t.strip() for t in q.split(",") if t.strip()]))
        st.caption(f"{len(hits)} results")
        for p in hits:
            st.markdown(f"- **{p['title']}** ({p.get('year', '')})")
        st.markdown("**Prior tasks**")
        st.write(S.memory.prior_task_history or "None archived yet.")

with mcp_tab:
    st.subheader("Lab 5 · MCP server & governed connector")
    st.markdown("**Registered tools**")
    st.dataframe(pd.DataFrame([{"name": t.name, "description": t.description}
                               for t in S.mcp.list_tools()]), width="stretch", hide_index=True)
    names = [t.name for t in S.mcp.list_tools()]
    tool = st.selectbox("Call a tool", names)
    args_text = st.text_input("Arguments (JSON)", '{"keyword": "edge"}')
    if st.button("Call tool"):
        try:
            out = S.mcp.call_tool(tool, json.loads(args_text or "{}"), agent_id="StreamlitUser")
            st.json(json.loads(out[0].text))
        except Exception as exc:
            st.error(f"Tool call failed: {exc}")
    st.markdown("**Connector audit trail**")
    trail = S.connector.get_audit_trail()
    if trail:
        st.dataframe(pd.DataFrame(trail).astype({"params": str}), width="stretch", hide_index=True)
    else:
        st.caption("No connector calls yet.")

with runtime_tab:
    st.subheader("Lab 6 · OpenClaw runtime: budget, audit log, checkpoint")
    rt = S.runtime
    a, b, c = st.columns(3)
    a.metric("Status", rt.state["status"])
    b.metric("Steps used", f"{rt.current_step}/{rt.max_budget_steps}")
    c.metric("Run ID", rt.state["run_id"].split("-")[-1])
    st.progress(min(rt.current_step / rt.max_budget_steps, 1.0))
    if rt.audit_log:
        st.dataframe(pd.DataFrame(rt.audit_log), width="stretch", hide_index=True)
    else:
        st.caption("No steps logged yet.")
    k1, k2 = st.columns(2)
    if k1.button("💾 Save checkpoint"):
        rt.checkpoint(session_state={"clarified": S.get("clarified", {})})
        st.success("Checkpoint saved.")
    if k2.button("♻️ Restore checkpoint"):
        st.success("Restored.") if rt.resume_from_checkpoint() else st.warning("No checkpoint found.")
        st.rerun()
