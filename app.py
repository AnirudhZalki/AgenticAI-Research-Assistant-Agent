"""
Research Assistant Agent - Streamlit Interface (Labs 1 through 14)

Run with:  python -m streamlit run app.py

Guided workflow (Workflow tab):
  1 Intake (Gate 1, Lab 1) -> 2 Plan & outline (Lab 3) -> 3 Discover (Labs 8/9, parallel literature || radar)
  -> 4 Draft & checks (Labs 7/13, parallel citation || collaboration, validation gate)
  -> 5 Faculty review & export (Labs 6/12, approval gate, tracker, rollback)

Inspection tabs: Tools (L2) · Memory (L4) · MCP (L5) · Runtime (L6) · Deep Research (L9) · Ops (L10)
                 SDLC (L11) · Governance (L12) · Domain (L13) · Capstone demo (L14)
"""

import importlib.util
import json
import sys

import streamlit as st

# Preflight: give a clear fix instead of a raw ImportError traceback.
_DEPS = {"langchain_core": "langchain-core", "mcp": "mcp", "openclaw": "openclaw", "pandas": "pandas"}
_missing = [pkg for mod, pkg in _DEPS.items() if importlib.util.find_spec(mod) is None]
if _missing:
    st.set_page_config(page_title="Research Assistant Agent", page_icon="🔬")
    st.error(f"Missing Python packages: {', '.join(_missing)}")
    st.write("Install them into the **same Python that runs Streamlit**, then restart the app:")
    st.code(f'"{sys.executable}" -m pip install -r requirements.txt', language="bash")
    st.caption("Start the app with:  python -m streamlit run app.py")
    st.stop()

import pandas as pd

from coordinator import REQUIRED, ResearchCoordinator
from domain import CitationFormatter, parse_venue
from governance import RISK_REGISTER, AuditLedger
from sdlc import SDLCFactory

st.set_page_config(page_title="Research Assistant Agent", page_icon="🔬", layout="wide")

STAGES = ["1 · Intake", "2 · Plan & outline", "3 · Discover", "4 · Draft & checks", "5 · Faculty review"]
DEMO = dict(topic="edge AI hardware porting frameworks", venue="IEEE conference, IMRAD, 6-page limit",
            collaborators="Faculty Author, Co-Author A", deadline="2026-11-15")
TRACKER_FILE = "research_tracker.json"


@st.cache_resource(ttl=300, show_spinner=False)
def internet_ok() -> bool:
    """Quick reachability probe so live academic APIs are the default whenever they can actually be used."""
    import urllib.request
    try:
        urllib.request.urlopen("https://api.openalex.org/works?per-page=1", timeout=4).close()
        return True
    except Exception:
        return False


def df(rows, **kw):
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, **kw)


def new_coordinator(live: bool):
    return ResearchCoordinator(use_live=live, tracker_path=TRACKER_FILE, checkpoint_file="checkpoint_app.json")


def clear_topic_state(extra=()):
    """Everything derived from a topic must be dropped when the topic changes (sub-queries, draft widgets, decision)."""
    for k in ["outline_draft", "drafted", "decision", "subq", *extra]:
        st.session_state.pop(k, None)
    st.session_state.draft_ver = st.session_state.get("draft_ver", 0) + 1


def reset(live: bool = None):
    live = st.session_state.get("live", False) if live is None else live
    st.session_state.live = live
    st.session_state.coord = new_coordinator(live)
    st.session_state.stage = 0
    clear_topic_state(["params"])


if "coord" not in st.session_state:
    reset(internet_ok())
S = st.session_state
C: ResearchCoordinator = S.coord


def go(stage: int):
    S.stage = stage
    st.rerun()


# ----------------------------------------------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------------------------------------------
with st.sidebar:
    st.title("🔬 Research Assistant")
    st.caption("Agents draft and flag; a named human (Faculty Examiner) approves.")
    live = st.toggle("Use live academic APIs", value=S.live,
                     help="Semantic Scholar / CrossRef / OpenAlex (no API key). Off = local MOCK corpus, fully offline.")
    if live != S.live:
        reset(live)
        st.rerun()
    if not S.live:
        st.warning("Offline mode: only the small MOCK corpus (a few demo topics) is searched. Other topics will find "
                   "nothing; turn on live APIs for real papers.", icon="⚠️")
    else:
        st.success("Live mode: Semantic Scholar → CrossRef → OpenAlex", icon="🌐")
    st.markdown("**Workflow progress**")
    for i, name in enumerate(STAGES):
        st.write(f"{'✅' if i < S.stage else ('▶️' if i == S.stage else '⚪')} {name}")
    st.progress(min(S.stage, len(STAGES)) / len(STAGES))
    st.divider()
    st.metric("Runtime steps", f"{C.runtime.current_step}/{C.runtime.max_budget_steps}")
    st.metric("MCP calls logged", len(C.connector.get_audit_trail()))
    st.metric("Tracked versions", len(C.tracker.versions))
    if st.button("🔄 Start over", width="stretch"):
        reset()
        st.rerun()

st.title("Research Assistant Agent")
st.caption("Discover → Analyze → Draft → Check → Track · always pausing at faculty review before anything leaves the system")

tabs = st.tabs(["🧭 Workflow", "🛠 Tools L2", "🧠 Memory L4", "🔌 MCP L5", "⚙️ Runtime L6", "📚 Deep research L9",
                "📡 Ops L10", "🏭 SDLC L11", "🛡 Governance L12", "🎓 Domain L13", "🏁 Capstone L14"])
(t_flow, t_tools, t_mem, t_mcp, t_rt, t_deep, t_ops, t_sdlc, t_gov, t_dom, t_cap) = tabs

# ----------------------------------------------------------------------------------------------------------------
# Workflow
# ----------------------------------------------------------------------------------------------------------------
with t_flow:
    stage = S.stage

    # ---- 1 Intake -------------------------------------------------------------------------------------------
    if stage == 0:
        st.subheader("Gate 1 · Confirm intent and venue (Lab 1)")
        st.write("Nothing starts until topic, venue, collaborators and deadline are all confirmed.")
        d = S.get("params", {})
        with st.form("intake"):
            topic = st.text_input("Research question / topic", d.get("topic", ""), placeholder="edge AI hardware porting frameworks")
            venue = st.text_input("Target venue", d.get("venue", ""), placeholder="IEEE conference, IMRAD, 6-page limit")
            collab = st.text_input("Collaborators (comma separated)", d.get("collaborators", ""), placeholder="Faculty Author, Co-Author A")
            deadline = st.text_input("Deadline (YYYY-MM-DD)", d.get("deadline", ""), placeholder="2026-11-15")
            ok = st.form_submit_button("Confirm & continue", type="primary")
        if ok:
            S.params = dict(topic=topic, venue=venue, collaborators=collab, deadline=deadline)
            missing = [f for f in REQUIRED if not S.params[f].strip()]
            if missing:
                st.warning("Assistant: I still need → " + ", ".join(f"**{m}**" for m in missing))
            else:
                try:
                    C.intake(S.params)          # starts a fresh context for this topic
                    clear_topic_state()
                    C.plan()
                    S.outline_draft = list(C.blueprint.sections)
                    go(1)
                except ValueError as exc:
                    st.error(str(exc))
        if st.button("Fill with demo values"):
            S.params = dict(DEMO)
            st.rerun()
        if d.get("venue"):
            spec = parse_venue(d["venue"])
            st.caption(f"Parsed venue → style **{spec.citation_style}**, structure **{spec.structure}**, "
                       f"{spec.page_limit} pages ≈ {spec.word_limit} words")

    # ---- 2 Plan & outline ------------------------------------------------------------------------------------
    elif stage == 1:
        st.subheader("Plan & outline-first (Lab 3)")
        bp = C.blueprint
        if C.ctx.get("prior_tasks"):
            st.info(f"Similar earlier task found in memory: {C.ctx['prior_tasks']}")
        st.markdown(f"**{bp.title}**  \n{bp.venue} · **{bp.citation_style}** · ≤ {bp.word_limit} words · due {bp.deadline}  \n"
                    f"Collaborators: {', '.join(bp.collaborators)}")
        st.markdown("**Outline** — edit it; the draft is only written after you confirm it.")
        ol = S.outline_draft
        for i, sec in enumerate(list(ol)):
            c1, c2, c3, c4 = st.columns([12, 1, 1, 1])
            c1.write(sec)
            if c2.button("↑", key=f"up{i}", disabled=i == 0):
                ol[i - 1], ol[i] = ol[i], ol[i - 1]; st.rerun()
            if c3.button("↓", key=f"dn{i}", disabled=i == len(ol) - 1):
                ol[i + 1], ol[i] = ol[i], ol[i + 1]; st.rerun()
            if c4.button("✖", key=f"rm{i}"):
                ol.pop(i); st.rerun()
        with st.form("add_sec", clear_on_submit=True):
            new = st.text_input("Add a section")
            if st.form_submit_button("Add") and new.strip():
                ol.append(new.strip()); st.rerun()
        if st.button("✅ Confirm outline", type="primary", disabled=not ol):
            C.confirm_outline([f"{i}. {s.split('. ', 1)[1] if s.split('.')[0].isdigit() else s}" for i, s in enumerate(ol, 1)])
            go(2)
        if st.button("← Back"):
            go(0)

    # ---- 3 Discover ------------------------------------------------------------------------------------------
    elif stage == 2:
        st.subheader("Parallel discovery · literature swarm ‖ funding radar (Labs 8, 7)")
        topic = C.ctx["topic"]
        default_q = "\n".join([topic] + [w for w in topic.split() if len(w) > 4][:3])
        qs = st.text_area("Sub-queries (one per line; each runs in its own worker)", S.get("subq", default_q), height=110)
        S.subq = qs
        if st.button("🚀 Run discovery", type="primary"):
            with st.spinner("Swarm workers and the radar are running in parallel..."):
                C.discover([q.strip() for q in qs.splitlines() if q.strip()])
        if "reading_list" in C.ctx:
            sw = C.ctx.get("swarm_results", {})
            a, b, c_, d_ = st.columns(4)
            a.metric("Swarm workers", sw.get("total_workers_executed", 0))
            b.metric("Reading list", len(C.ctx["reading_list"]))
            c_.metric("Radar alerts", len(C.ctx["radar_deadlines"]))
            d_.metric("Swarm wall clock (s)", sw.get("swarm_wall_clock_time_sec", 0))
            for w in C.ctx.get("literature_warnings", []):
                (st.error if w.startswith("NO relevant") else st.warning)(w)
            st.markdown("**Ranked reading list**")
            df([{"#": p["ref_num"], "title": p["title"], "year": p["year"], "venue": p["venue"],
                 "relevance": p["relevance"], "doi": p["doi"], "source": p["source"]} for p in C.ctx["reading_list"]])
            st.markdown("**Funding / journal radar** (timestamped)")
            df([{k: d.get(k) for k in ("title", "type", "deadline", "days_remaining", "status",
                                       "before_your_deadline", "checked_at", "url")} for d in C.ctx["radar_deadlines"]])
        cb, cn = st.columns(2)
        if cb.button("← Back"):
            go(1)
        if cn.button("Continue → draft", type="primary", disabled=not C.ctx.get("reading_list")):
            go(3)

    # ---- 4 Draft & checks ------------------------------------------------------------------------------------
    elif stage == 3:
        st.subheader("Gap analysis → draft → parallel checks → validation gate (Labs 7, 13)")
        retries = st.slider("Bounded regenerate attempts", 1, 4, 2)
        if st.button("▶️ Analyze, draft & check", type="primary"):
            with st.spinner("Running gap analysis, drafting, citation ‖ collaboration checks..."):
                C.analyze_gap()
                S.draft_ver += 1
                C.generate_and_validate(retries)
                if C.ctx["validation"]["passed"]:
                    C.assemble()
                S.drafted = True
        if S.get("drafted") and "validation" in C.ctx:
            rep = C.ctx["validation"]
            (st.success if rep["passed"] else st.error)(f"Validation gate {'PASSED' if rep['passed'] else 'FAILED'}")
            for n in rep["passed_checks"]:
                st.write(f"✅ {n}")
            for n in rep["failing_checks"]:
                st.write(f"❌ {n}")
            if not rep["passed"]:
                st.info(rep["diagnosis"])
                if rep.get("stopped_early"):
                    st.caption(rep["stopped_early"])
            g = C.ctx["gap_analysis"]
            with st.expander(f"Gap analysis — {g['novelty_flag']}", expanded=True):
                st.write(g["novelty_positioning_statement"])
                st.markdown("**Closest prior work**\n" + "\n".join(f"- {x}" for x in g["closest_prior_work"]))
                st.markdown("**Candidate angles**\n" + "\n".join(f"- {x}" for x in g["why_our_work_is_unique"]))
                st.caption("⚠ " + g["uncertainty"])
            cc = C.ctx["citation_compliance"]
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Citation & compliance ({cc['citation_style']})** — {cc['word_count']}/{cc['word_limit']} words")
                for e in cc["errors"]:
                    st.error(e)
                for w in cc["warnings"]:
                    st.warning(w)
                if not cc["errors"] and not cc["warnings"]:
                    st.success("No issues.")
            with c2:
                st.markdown("**Collaboration (attribution)**")
                df([{"section": a["section"], "owner": a["owner"], "edits": len(a["edits"]), "status": a["status"]}
                    for a in C.ctx["collaboration"]["attribution"]])
            st.markdown("**Draft sections** (editable — authors own every claim)")
            edited = {}
            for sec, txt in C.ctx["draft_sections"].items():
                with st.expander(sec):
                    edited[sec] = st.text_area("text", txt, key=f"ed_{S.draft_ver}_{sec}", height=200, label_visibility="collapsed")
            if st.button("💾 Save edits & re-check"):
                C.ctx["draft_sections"] = edited
                S.draft_ver += 1
                C.check()
                C.validate()
                if C.ctx["validation"]["passed"]:
                    C.assemble()
                st.rerun()
        cb, cn = st.columns(2)
        if cb.button("← Back"):
            go(2)
        if cn.button("Continue → faculty review", type="primary",
                     disabled=not (S.get("drafted") and C.ctx.get("validation", {}).get("passed"))):
            go(4)

    # ---- 5 Faculty review ------------------------------------------------------------------------------------
    elif stage == 4:
        st.subheader("Faculty review gate → export (Labs 6, 12)")
        gov = C.governance_report()
        cols = st.columns(len(gov["guardrails"]))
        for col, g in zip(cols, gov["guardrails"]):
            col.metric(g["guardrail"].split(" ")[0], "✅" if g["passed"] else "❌", help=f"{g['guardrail']} — {g['evidence']}")
        for r in gov["dynamic_risks"]:
            st.warning(r)
        st.code(C.ctx["formatted_paper"], language="text")
        if S.get("decision") is None:
            approver = st.text_input("Approver (named human)", "Faculty Examiner")
            comments = st.text_area("Comments / corrections requested", "")
            a, r = st.columns(2)
            if a.button("✅ Approve & export", type="primary"):
                C.faculty_decision(True, approver, comments)
                C.export()
                S.decision = "approved"
                st.rerun()
            if r.button("❌ Reject / request revision"):
                C.faculty_decision(False, approver, comments or "Revision requested")
                S.decision = "rejected"
                st.rerun()
        elif S.decision == "approved":
            st.success(f"Approved and archived as **{C.ctx['version']}** — status {C.ctx['export_status']}")
            e = C.ctx["tracker_entry"]
            st.caption(f"sha256 {e['sha256'][:16]}… · {len(e['source_links'])} source links · approved by {e['approved_by']}")
            d1, d2, d3, d4 = st.columns(4)
            d1.download_button("⬇ Paper (txt)", C.ctx["formatted_paper"], "research_draft.txt")
            d2.download_button("⬇ References (BibTeX)", CitationFormatter().to_bibtex(C.ctx["references"]), "references.bib")
            d3.download_button("⬇ Audit ledger (JSON)", json.dumps(C.ledger.entries, indent=2), "audit_ledger.json")
            d4.download_button("⬇ Evidence briefing (md)", C.ctx.get("deep_research", {}).get("briefing_markdown", "(run Deep research tab)"), "briefing.md")
        else:
            st.error(f"Rejected. Feedback recorded: {C.ctx.get('faculty_feedback')}")
            if st.button("← Return to drafting"):
                C.approved = False
                C.runtime.state["status"] = "PIPELINE_RUNNING"
                S.decision = None
                go(3)

    if C.tracker.versions:
        with st.expander("📜 Version history & rollback (append-only)"):
            df(C.tracker.history())
            ver = st.selectbox("Version", [v["version"] for v in C.tracker.versions])
            c1, c2 = st.columns(2)
            if c1.button("Show text"):
                st.code(C.tracker.get(ver)["text"][:3000], language="text")
            if c2.button("⏪ Roll back to this version"):
                rb = C.tracker.rollback(ver, "manual rollback from UI")
                C.ledger.append("Faculty", "Rollback", f"{ver} -> {rb['version']}")
                st.success(f"Restored as new entry {rb['version']} (history kept).")

# ----------------------------------------------------------------------------------------------------------------
# Lab 2 / 4 / 5 / 6
# ----------------------------------------------------------------------------------------------------------------
with t_tools:
    st.subheader("Lab 2 · Typed tools (no hallucinated data)")
    kw = st.text_input("Corpus keyword", "edge", key="tool_kw")
    c1, c2 = st.columns(2)
    res, dl = C.tools.read_corpus(kw), C.tools.read_deadlines(kw)
    with c1:
        st.markdown(f"**read_corpus** · {len(res)} papers")
        if res:
            df(res)
    with c2:
        st.markdown(f"**read_deadlines** · {len(dl)} entries")
        if dl:
            df(dl)
    with st.expander("read_library"):
        df(C.tools.read_library())
    with st.expander("read_notes"):
        st.json(C.tools.read_notes())

with t_mem:
    st.subheader("Lab 4 · Short-term session state vs long-term retrieval")
    l, r = st.columns(2)
    with l:
        st.markdown("**Session state**")
        st.json(json.loads(json.dumps(C.memory.session_state, default=lambda o: getattr(o, "__dict__", str(o)))), expanded=1)
    with r:
        q = st.text_input("Query", C.ctx.get("topic", "edge ai"), key="mem_q")
        mode = st.radio("Mode", ["Similarity", "Tags"], horizontal=True)
        hits = (C.memory.retrieve_by_similarity(q) if mode == "Similarity"
                else C.memory.retrieve_by_tags([t.strip() for t in q.split(",") if t.strip()]))
        for p in hits:
            st.markdown(f"- **{p['title']}** ({p.get('year', '')})")
        st.markdown("**Prior tasks**")
        st.write(C.memory.prior_task_history or "None archived yet.")

with t_mcp:
    st.subheader("Lab 5 · MCP server & governed connector")
    tl = C.mcp.list_tools()
    df([{"name": t.name, "description": t.description} for t in tl])
    tool = st.selectbox("Call a tool", [t.name for t in tl])
    args = st.text_input("Arguments (JSON)", '{"keyword": "edge"}')
    if st.button("Call tool"):
        try:
            st.json(json.loads(C.mcp.call_tool(tool, json.loads(args or "{}"), agent_id="StreamlitUser")[0].text))
        except Exception as exc:
            st.error(f"Tool call failed: {exc}")
    trail = C.connector.get_audit_trail()
    st.markdown(f"**Access audit trail** · {len(trail)} calls")
    if trail:
        df(pd.DataFrame(trail).astype({"params": str}).to_dict("records"))

with t_rt:
    st.subheader("Lab 6 · OpenClaw runtime: budget, audit log, checkpoint")
    rt = C.runtime
    a, b = st.columns(2)
    a.metric("Status", rt.state["status"])
    b.metric("Steps used", f"{rt.current_step}/{rt.max_budget_steps}")
    st.progress(min(rt.current_step / rt.max_budget_steps, 1.0))
    if rt.audit_log:
        df(rt.audit_log)
    k1, k2 = st.columns(2)
    if k1.button("💾 Save checkpoint"):
        rt.checkpoint(session_state={"ctx_keys": list(C.ctx)})
        st.success("Checkpoint saved.")
    if k2.button("♻️ Restore checkpoint"):
        st.success("Restored.") if rt.resume_from_checkpoint() else st.warning("No checkpoint found.")

# ----------------------------------------------------------------------------------------------------------------
# Lab 9 Deep research
# ----------------------------------------------------------------------------------------------------------------
with t_deep:
    st.subheader("Lab 9 · Deep research: iterative retrieval, evidence table, cited synthesis")
    if not C.ctx.get("topic"):
        st.info("Confirm the intake step first (Workflow tab).")
    else:
        if st.button("🔎 Run deep research", type="primary"):
            with st.spinner("Searching, expanding queries, extracting evidence..."):
                C.deep_research()
        dr = C.ctx.get("deep_research")
        if dr:
            st.markdown("**Research trace** (stops on saturation)")
            df(dr["trace"])
            st.markdown("**Evidence table** — every claim is a sentence copied from the cited paper's abstract")
            df(dr["evidence_table"])
            st.markdown(dr["briefing_markdown"])
            for lim in dr["limitations"]:
                st.caption("⚠ " + lim)
            if dr["evidence_gaps"]:
                st.info("Thinly covered terms: " + ", ".join(dr["evidence_gaps"]))

# ----------------------------------------------------------------------------------------------------------------
# Lab 10 Ops
# ----------------------------------------------------------------------------------------------------------------
with t_ops:
    st.subheader("Lab 10 · Operations: traces, failure injection, diagnosis, recovery")
    c1, c2, c3 = st.columns(3)
    n = c1.number_input("Failures to inject", 1, 20, 4)
    if c2.button("💥 Inject failure into search_online_papers"):
        C.faults.arm("search_online_papers", failures=int(n))
        st.warning(f"Armed: next {int(n)} calls will fail with a simulated upstream 503.")
    if c3.button("📡 Probe search endpoint"):
        got = C.connector.search_online_papers("edge AI", max_results=3, agent_id="OpsProbe")
        st.write(f"Probe returned {len(got)} papers · circuit breaker: **{C.connector.breaker.state}** · "
                 f"degraded calls: {C.connector.degraded_calls}")
    diag = C.ops.diagnose(C.tracer, C.connector)
    (st.success if diag["healthy"] else st.error)("HEALTHY" if diag["healthy"] else "DEGRADED / FAILING")
    for f in diag["findings"]:
        st.write("• " + f)
    st.write("**Root-cause hint:** " + diag["root_cause_hint"])
    st.write("**Recommended:** " + " ".join(diag["recommended_actions"]))
    if st.button("🛠 Auto-remediate"):
        st.success(C.ops.remediate(C.connector))
    if diag["endpoints"]:
        df([{"endpoint": k, **v} for k, v in diag["endpoints"].items()])
    with st.expander("Raw traces"):
        if C.tracer.spans:
            df(C.tracer.spans[-200:])

# ----------------------------------------------------------------------------------------------------------------
# Lab 11 SDLC
# ----------------------------------------------------------------------------------------------------------------
with t_sdlc:
    st.subheader("Lab 11 · Agentic SDLC: requirement → design → implementation → tests → traceability")
    if st.button("🏭 Run SDLC factory", type="primary"):
        with st.spinner("Building, running acceptance tests and unit tests..."):
            S.sdlc = SDLCFactory().run()
    if "sdlc" in S:
        r = S.sdlc
        (st.success if r["release_ready"] else st.error)(
            f"{'RELEASE READY' if r['release_ready'] else 'NOT READY'} · acceptance {int(r['acceptance_pass_rate'] * 100)}% · "
            f"unit tests {r['unit_tests']['ran']} run / {r['unit_tests']['failures'] + r['unit_tests']['errors']} failed · {r['seconds']}s")
        st.markdown("**Design**")
        df([{"layer": a, "implemented by": b} for a, b in r["design"]])
        st.markdown("**Requirements traceability matrix**")
        df(r["traceability"])

# ----------------------------------------------------------------------------------------------------------------
# Lab 12 Governance
# ----------------------------------------------------------------------------------------------------------------
with t_gov:
    st.subheader("Lab 12 · Safety & governance")
    if "formatted_paper" in C.ctx or "reading_list" in C.ctx:
        gov = C.governance_report()
        st.markdown("**Guardrails (live check on the current run)**")
        df(gov["guardrails"])
        st.markdown("**Evaluation scorecard**")
        st.json(gov["metrics"])
        for r in gov["dynamic_risks"]:
            st.warning(r)
    else:
        st.info("Run the workflow (or the Capstone demo) to evaluate a run.")
    st.markdown("**Risk register**")
    df(RISK_REGISTER)
    st.markdown("**Tamper-evident audit ledger**")
    v = C.ledger.verify()
    (st.success if v["intact"] else st.error)(f"Hash chain {'intact' if v['intact'] else 'BROKEN at #' + str(v['broken_at_seq'])} · {v['entries']} entries")
    if C.ledger.entries:
        df(C.ledger.entries)
    if st.button("🧪 Demo: tamper with a copy of the ledger"):
        import copy
        led = AuditLedger()
        if C.ledger.entries:
            led.entries = copy.deepcopy(C.ledger.entries)
        else:
            led.append("demo", "step one"); led.append("demo", "step two")
        led.entries[0]["detail"] = "edited after the fact"
        st.error(f"Verification of tampered copy → {led.verify()}")
    st.markdown("**Evaluation regression** — runs the whole pipeline once per topic and scores each run")
    default_topics = "\n".join(dict.fromkeys([C.ctx.get("topic", DEMO["topic"]), "federated learning healthcare",
                                              "quantum machine learning"]))
    topics_text = st.text_area("Topics to evaluate (one per line)", default_topics, key=f"reg_topics_{C.ctx.get('topic', '')}", height=100)
    if st.button("📊 Run evaluation regression"):
        topics = [t.strip() for t in topics_text.splitlines() if t.strip()]
        def run_topic(t):
            return ResearchCoordinator(use_live=S.live, checkpoint_file="checkpoint_eval.json").run_all({**DEMO, "topic": t})
        with st.spinner("Running pipeline on each topic..."):
            df(C.evaluator.regression(run_topic, topics))

# ----------------------------------------------------------------------------------------------------------------
# Lab 13 Domain
# ----------------------------------------------------------------------------------------------------------------
with t_dom:
    st.subheader("Lab 13 · CSE/AI publishing domain agent")
    v = st.text_input("Venue description", C.ctx.get("venue", DEMO["venue"]), key="dom_venue")
    spec = parse_venue(v)
    a, b, c_, d_ = st.columns(4)
    a.metric("Style", spec.citation_style); b.metric("Kind", spec.kind)
    c_.metric("Pages", spec.page_limit); d_.metric("Word limit", spec.word_limit)
    st.write("**Required structure:** " + " → ".join(spec.sections))
    refs = C.ctx.get("reading_list") or C.tools.corpus[:3]
    style = st.radio("Reference style", ["IEEE", "ACM", "APA"], horizontal=True, index=["IEEE", "ACM", "APA"].index(spec.citation_style) if spec.citation_style in ("IEEE", "ACM", "APA") else 0)
    st.code("\n".join(CitationFormatter().format_all(refs, style)), language="text")
    with st.expander("BibTeX"):
        st.code(CitationFormatter().to_bibtex(refs), language="text")
    orig = C.ctx.get("citation_compliance", {}).get("originality")
    if orig:
        st.markdown("**Originality screen (5-gram overlap)**")
        df(orig["sections"])
        st.caption(orig["disclaimer"])

# ----------------------------------------------------------------------------------------------------------------
# Lab 14 Capstone
# ----------------------------------------------------------------------------------------------------------------
with t_cap:
    st.subheader("Lab 14 · Capstone: complete run in one click")
    st.write("Runs every stage with hybrid parallel/sequential execution and auto-approves the faculty gate "
             "(demo only — use the Workflow tab for the real human gate).")
    c1, c2 = st.columns(2)
    cap_topic = c1.text_input("Topic", DEMO["topic"], key="cap_topic")
    cap_venue = c2.text_input("Venue", DEMO["venue"], key="cap_venue")
    if st.button("🏁 Run full demo", type="primary"):
        demo = ResearchCoordinator(use_live=S.live, checkpoint_file="checkpoint_demo.json")
        with st.spinner("Running end-to-end..."):
            try:
                S.cap = demo.run_all({**DEMO, "topic": cap_topic, "venue": cap_venue}, approve=True, approver="Demo Examiner")
                S.cap_coord = demo
            except Exception as exc:
                st.error(f"Run failed: {exc}")
    if "cap" in S:
        r = S.cap
        m = r["metrics"]
        a, b, c_, d_ = st.columns(4)
        a.metric("Overall score", m["overall_score"]); b.metric("References", m["reference_count"])
        c_.metric("Guardrails", m["guardrails_passed"]); d_.metric("Version", r["ctx"].get("version", "-"))
        st.markdown("**Execution timeline** (mode shows hybrid methodology)")
        df(r["timeline"])
        st.markdown("**Guardrails**")
        df(r["governance"]["guardrails"])
        with st.expander("Final paper"):
            st.code(r["ctx"].get("formatted_paper", "not exported"), language="text")
