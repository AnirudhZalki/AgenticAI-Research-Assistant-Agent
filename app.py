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

from access import ROLES, AccessControl, Actor, redact_view
from clarify import RequestClarifier
from coordinator import REQUIRED, ResearchCoordinator
from domain import PACKS, CitationFormatter, detect_domain, get_pack, parse_venue
from governance import RISK_REGISTER, AuditLedger
from healing import FAULTS, inject_fault
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


def fill_demo():
    st.session_state.in_topic, st.session_state.in_venue = DEMO["topic"], DEMO["venue"]
    st.session_state.in_collab, st.session_state.in_deadline = DEMO["collaborators"], DEMO["deadline"]


def reset(live: bool = None):
    live = st.session_state.get("live", False) if live is None else live
    st.session_state.live = live
    st.session_state.coord = new_coordinator(live)
    st.session_state.stage = 0
    clear_topic_state(["params", "in_topic", "in_venue", "in_collab", "in_deadline", "clarify_qs"])


if "coord" not in st.session_state:
    reset(internet_ok())
S = st.session_state
C: ResearchCoordinator = S.coord


STAGE_OF = {"plan": 1, "outline": 2, "draft": 3, "review": 4, "export": 4}


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
    st.markdown("**Signed in as**")
    S.user = st.text_input("Name", S.get("user", "Faculty Examiner"), label_visibility="collapsed")
    S.role = st.selectbox("Role", list(ROLES), index=list(ROLES).index(S.get("role", "faculty")),
                          format_func=lambda r: ROLES[r]["label"])
    ACTOR = Actor(S.user, S.role)
    st.caption("Classification: **" + C.classification() + "**" if C.ctx.get("topic") else "No active run")
    st.markdown("**Workflow progress**")
    for i, name in enumerate(STAGES):
        st.write(f"{'✅' if i < S.stage else ('▶️' if i == S.stage else '⚪')} {name}")
    st.progress(min(S.stage, len(STAGES)) / len(STAGES))
    st.divider()
    st.metric("Runtime steps", f"{C.runtime.current_step}/{C.runtime.max_budget_steps}")
    st.metric("MCP calls logged", len(C.connector.get_audit_trail()))
    st.metric("Tracked versions", len(C.tracker.versions))
    if st.button("♻️ Resume last run", width="stretch", help="Restore the last checkpoint after a crash or restart"):
        where = C.resume()
        if where:
            S.stage, S.drafted = STAGE_OF.get(where, 1), where in ("review", "export")
            S.outline_draft = list(C.ctx.get("plan_sections", []))
            S.decision = "approved" if where == "export" else None
            st.rerun()
        else:
            st.warning("No checkpoint to resume.")
    if st.button("🔄 Start over", width="stretch"):
        reset()
        st.rerun()

st.title("Research Assistant Agent")
st.caption("Discover → Analyze → Draft → Check → Track · always pausing at faculty review before anything leaves the system")

tabs = st.tabs(["🧭 Workflow", "📊 Dashboard L14", "🛠 Tools L2", "🧠 Memory L4", "🔌 MCP L5", "⚙️ Runtime L6", "📚 Deep research L9",
                "📡 Ops L10", "🏭 SDLC L11", "🛡 Governance L12", "🎓 Domain L13", "🏁 Capstone L14"])
(t_flow, t_dash, t_tools, t_mem, t_mcp, t_rt, t_deep, t_ops, t_sdlc, t_gov, t_dom, t_cap) = tabs

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
        for k in ("in_topic", "in_venue", "in_collab", "in_deadline"):
            S.setdefault(k, "")                         # stable widget keys: typed values survive reruns
        with st.form("intake"):
            topic = st.text_input("Research question / topic", key="in_topic", placeholder="edge AI hardware porting frameworks")
            venue = st.text_input("Target venue", key="in_venue", placeholder="IEEE conference, IMRAD, 6-page limit")
            collab = st.text_input("Collaborators (comma separated)", key="in_collab", placeholder="Faculty Author, Co-Author A")
            deadline = st.text_input("Deadline (YYYY-MM-DD)", key="in_deadline", placeholder="2026-11-15")
            discipline = st.selectbox("Discipline pack", ["auto-detect"] + list(PACKS),
                                      format_func=lambda k: k if k == "auto-detect" else PACKS[k].name)
            ok = st.form_submit_button("Confirm & continue", type="primary",
                                       disabled=not AccessControl.can(ACTOR, "run_pipeline"))
        if ok:
            S.params = dict(topic=topic, venue=venue, collaborators=collab, deadline=deadline,
                            domain="" if discipline == "auto-detect" else discipline)
            missing = [f for f in REQUIRED if not S.params[f].strip()]
            questions = RequestClarifier().questions(S.params)
            if missing:
                st.warning("**Assistant asks before planning:**\n" + "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1)))
            else:
                S.clarify_qs = questions
                try:
                    C.intake(S.params)          # starts a fresh context for this topic
                    clear_topic_state()
                    C.plan()
                    S.outline_draft = list(C.blueprint.sections)
                    go(1)
                except ValueError as exc:
                    st.error(str(exc))
        if not AccessControl.can(ACTOR, "run_pipeline"):
            st.warning(f"Role '{ROLES[S.role]['label']}' cannot start a workflow.")
        st.button("Fill with demo values", on_click=fill_demo)
        if S.in_venue:
            spec = parse_venue(S.in_venue)
            st.caption(f"Parsed venue → style **{spec.citation_style}**, structure **{spec.structure}**, "
                       f"{spec.page_limit} pages ≈ {spec.word_limit} words")

    # ---- 2 Plan & outline ------------------------------------------------------------------------------------
    elif stage == 1:
        st.subheader("Plan & outline-first (Lab 3)")
        bp = C.blueprint
        if S.get("clarify_qs"):
            st.info("**The assistant would still like to know:**\n" + "\n".join(f"- {q}" for q in S.clarify_qs) +
                    "\n\nYou can proceed; refine the outline below accordingly.")
        st.caption(f"Discipline pack: **{get_pack(C.ctx.get('domain')).name}** — its required sections are already in the outline.")
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
            st.markdown("**Ranked reading list** (each item carries an evidence record)")
            df([{"#": p["ref_num"], "title": p["title"], "year": p["year"], "venue": p["venue"],
                 "relevance": p["relevance"], "doi": p["doi"], "source": p["source"],
                 "scope": p["evidence"]["scope"], "grounded": p["evidence"]["grounded"]} for p in C.ctx["reading_list"]])
            if C.ctx.get("rejected_references"):
                with st.expander(f"🚫 Grounding step rejected {len(C.ctx['rejected_references'])} candidate(s)"):
                    df(C.ctx["rejected_references"])
            with st.expander("Evidence records"):
                df([{"#": p["ref_num"], "supporting sentence": p["evidence"]["supporting_sentence"],
                     "tags": ", ".join(p["evidence"]["tags"][:4]), "retrieved_at": p["evidence"]["retrieved_at"]}
                    for p in C.ctx["reading_list"]])
            st.markdown("**Funding / journal radar** (timestamped)")
            df([{k: d.get(k) for k in ("title", "type", "deadline", "days_remaining", "status",
                                       "before_your_deadline", "checked_at", "url")} for d in C.ctx["radar_deadlines"]])
        with st.expander("⏱ Lab 8: parallel vs sequential benchmark"):
            lat = st.slider("Simulated per-call network latency (s)", 0.0, 0.2, 0.05, 0.01,
                            help="Offline corpus reads take microseconds; this emulates real API latency.")
            if st.button("Run benchmark"):
                from swarm import ParallelSwarm
                b = ParallelSwarm(mcp_server=C.mcp).benchmark([q for q in qs.splitlines() if q.strip()] or [topic], topic, lat)
                (st.success if b["accepted"] else st.warning)(
                    f"Sequential {b['sequential_s']}s · parallel {b['parallel_s']}s · speed-up ×{b['speedup']} · "
                    f"identical merged result: {b['same_merged_result']}")
        cb, cn = st.columns(2)
        if cb.button("← Back"):
            go(1)
        if cn.button("Continue → draft", type="primary", disabled=not C.ctx.get("reading_list")):
            go(3)

    # ---- 4 Draft & checks ------------------------------------------------------------------------------------
    elif stage == 3:
        st.subheader("Gap analysis → draft → parallel checks → validation gate (Labs 7, 13)")
        retries = st.slider("Bounded regenerate attempts", 1, 4, 2)
        can_see = AccessControl.can(ACTOR, "view_confidential")
        can_edit = AccessControl.can(ACTOR, "edit_draft")
        if not can_see:
            st.warning("🔒 Unpublished drafts are confidential. Your role sees validation status only.")
        if st.button("▶️ Analyze, draft & check", type="primary", disabled=not AccessControl.can(ACTOR, "run_pipeline")):
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
            if C.ctx.get("heal_log"):
                with st.expander(f"🩹 Self-healing log ({len(C.ctx['heal_log'])} targeted repairs)", expanded=True):
                    df([{k: (", ".join(v) if isinstance(v, list) else v) for k, v in e.items()} for e in C.ctx["heal_log"]])
            if "escalation" in C.ctx:
                st.error("**Escalated to the faculty** — " + C.ctx["escalation"]["reason"])
                for a_ in C.ctx["escalation"]["suggested_actions"]:
                    st.write("• " + a_)
            acc = C.ctx.get("acceptance")
            if acc:
                with st.expander(f"✅ Acceptance report — {'ALL PASS' if acc['all_pass'] else 'NOT PASSING'} "
                                 f"(gates the faculty review)", expanded=not acc["all_pass"]):
                    df(acc["checks"])
            g = C.ctx["gap_analysis"] if can_see else {"novelty_flag": "[REDACTED]", "novelty_positioning_statement": "",
                                                        "closest_prior_work": [], "why_our_work_is_unique": [], "uncertainty": ""}
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
                with st.expander("➕ Record a co-author edit (attributed, never overwritten)"):
                    with st.form("coedit", clear_on_submit=True):
                        who = st.text_input("Author", "Co-Author A")
                        sec_pick = st.selectbox("Section", list(C.ctx["draft_sections"]))
                        note = st.text_area("Edit note")
                        if st.form_submit_button("Add edit") and note.strip() and can_edit:
                            C.ctx.setdefault("coauthor_edits", []).append({"author": who, "section": sec_pick, "note": note})
                            C.check(); C.validate(); C.assemble()
                            st.rerun()
            dcs = cc.get("domain_checks", [])
            if dcs:
                with st.expander(f"🎓 Domain pack checks — {get_pack(cc.get('domain')).name}"):
                    df(dcs)
            st.markdown("**Draft sections** (editable — authors own every claim)")
            edited = {}
            for sec, txt in C.ctx["draft_sections"].items():
                with st.expander(sec):
                    edited[sec] = st.text_area("text", txt if can_see else "[REDACTED - confidential unpublished draft]",
                                               key=f"ed_{S.draft_ver}_{sec}", height=200, label_visibility="collapsed",
                                               disabled=not (can_see and can_edit))
            if st.button("💾 Save edits & re-check", disabled=not (can_see and can_edit)):
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
                     disabled=not (S.get("drafted") and C.ctx.get("validation", {}).get("passed")
                                   and C.ctx.get("acceptance", {}).get("all_pass"))):
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
        st.caption("Classification: **" + C.classification() + "**")
        acc = C.ctx.get("acceptance")
        if acc:
            (st.success if acc["all_pass"] else st.error)(
                "Acceptance report: " + ("ALL PASS — eligible for faculty review" if acc["all_pass"] else "NOT PASSING — approval is blocked"))
        view = redact_view(C.ctx, ACTOR)
        st.code(view["formatted_paper"], language="text")
        if S.get("decision") is None:
            st.write(f"Acting as **{S.user}** ({ROLES[S.role]['label']}). Only the faculty role may approve.")
            comments = st.text_area("Comments / corrections requested", "")
            a, r = st.columns(2)
            if a.button("✅ Approve & export", type="primary"):
                try:
                    C.faculty_decision(True, S.user, comments, role=S.role)
                    C.export()
                    S.decision = "approved"
                    st.rerun()
                except PermissionError as exc:
                    st.error(str(exc))
            if r.button("❌ Reject / request revision"):
                try:
                    C.faculty_decision(False, S.user, comments or "Revision requested", role=S.role)
                    S.decision = "rejected"
                    st.rerun()
                except PermissionError as exc:
                    st.error(str(exc))
        elif S.decision == "approved":
            st.success(f"Approved and archived as **{C.ctx['version']}** — status {C.ctx['export_status']}")
            e = C.ctx["tracker_entry"]
            st.caption(f"sha256 {e['sha256'][:16]}… · {len(e['source_links'])} source links · approved by {e['approved_by']}")
            if not AccessControl.can(ACTOR, "export_files"):
                st.info("Your role may not download files.")
            d1, d2, d3, d4 = st.columns(4)
            d1.download_button("⬇ Paper (txt)", C.ctx["formatted_paper"], "research_draft.txt", disabled=not AccessControl.can(ACTOR, "export_files"))
            d2.download_button("⬇ References (BibTeX)", CitationFormatter().to_bibtex(C.ctx["references"]), "references.bib", disabled=not AccessControl.can(ACTOR, "export_files"))
            d3.download_button("⬇ Audit ledger (JSON)", json.dumps(C.ledger.entries, indent=2), "audit_ledger.json", disabled=not AccessControl.can(ACTOR, "export_files"))
            d4.download_button("⬇ Evidence briefing (md)", C.ctx.get("deep_research", {}).get("briefing_markdown", "(run Deep research tab)"), "briefing.md", disabled=not AccessControl.can(ACTOR, "export_files"))
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
                try:
                    rb = C.rollback(ver, S.user, S.role, "manual rollback from UI")
                    st.success(f"Restored as new entry {rb['version']} (history kept).")
                except PermissionError as exc:
                    st.error(str(exc))

# ----------------------------------------------------------------------------------------------------------------
# Lab 14 dashboard (what the researcher sees to review, approve and monitor)
# ----------------------------------------------------------------------------------------------------------------
with t_dash:
    st.subheader("Researcher dashboard")
    if not AccessControl.can(ACTOR, "view_dashboard"):
        st.warning("Your role cannot open the dashboard.")
    elif not C.ctx.get("topic"):
        st.info("Start a workflow (Workflow tab) to populate the dashboard.")
    else:
        V = redact_view(C.ctx, ACTOR)
        st.caption(f"**{C.ctx['topic']}** · {C.ctx['venue']} · due {C.ctx['deadline']} · "
                   f"discipline: {get_pack(C.ctx.get('domain')).name} · **{C.classification()}**")
        acc = C.ctx.get("acceptance")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Run status", C.runtime.state["status"])
        k2.metric("Validation", "—" if "validation" not in C.ctx else ("PASS" if C.ctx["validation"]["passed"] else "FAIL"))
        k3.metric("Acceptance", "—" if not acc else ("ALL PASS" if acc["all_pass"] else "BLOCKED"))
        k4.metric("Version", C.ctx.get("version", "draft"))
        left, right = st.columns(2)
        with left:
            st.markdown("#### 📚 Reading list & gap")
            if C.ctx.get("reading_list"):
                df([{"#": p["ref_num"], "title": p["title"], "year": p["year"], "relevance": p["relevance"],
                     "source": p["source"]} for p in C.ctx["reading_list"]])
                st.write("**Novelty:** " + V.get("gap_analysis", {}).get("novelty_flag", "not analysed yet"))
            else:
                st.caption("Run discovery first.")
            st.markdown("#### ✍️ Draft & compliance")
            cc = C.ctx.get("citation_compliance")
            if cc:
                st.write(f"{len(V.get('draft_sections', {}))} sections · {cc['word_count']}/{cc['word_limit']} words · "
                         f"{len(cc['errors'])} errors · {len(cc['warnings'])} warnings")
                if cc.get("domain_checks"):
                    df(cc["domain_checks"])
            else:
                st.caption("No draft yet.")
        with right:
            st.markdown("#### 📡 Deadline radar")
            if C.ctx.get("radar_deadlines"):
                df([{k: d.get(k) for k in ("title", "deadline", "days_remaining", "status", "before_your_deadline", "checked_at")}
                    for d in C.ctx["radar_deadlines"]])
            iv = st.number_input("Continuous monitor interval (seconds)", 1, 86400, 3600)
            r1, r2, r3 = st.columns(3)
            if r1.button("▶ Start monitor"):
                C.start_radar(float(iv))
            if r2.button("⏹ Stop monitor") and C.radar_monitor:
                C.radar_monitor.stop()
            if r3.button("🔎 Check now"):
                (C.radar_monitor or C.start_radar(float(iv))).check_now()
            if C.radar_monitor:
                st.caption(f"Monitor {'RUNNING' if C.radar_monitor.running else 'stopped'} · "
                           f"{len(C.radar_monitor.digest)} checks")
                if C.radar_monitor.digest:
                    last = C.radar_monitor.digest[-1]
                    st.write(f"Last check {last['checked_at']}: {last['alerts']} alerts · new {last['new'] or 'none'} · "
                             f"urgent {last['urgent'] or 'none'}")
            st.markdown("#### 🤝 Collaboration & versions")
            col = V.get("collaboration", {})
            if col.get("attribution"):
                df([{"section": a["section"], "owner": a["owner"], "edits": len(a["edits"]), "status": a["status"]}
                    for a in col["attribution"]])
            if C.tracker.versions:
                df(C.tracker.history(C.ctx["topic"]))
        if acc:
            with st.expander("Acceptance report"):
                df(acc["checks"])
        with st.expander("Audit trail (last 15 ledger entries)"):
            if AccessControl.can(ACTOR, "view_audit"):
                df(C.ledger.entries[-15:])
            else:
                st.caption("Your role cannot view the audit trail.")

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
        mode = st.radio("Mode", ["Similarity (keyword overlap)", "Vector (TF-IDF cosine)", "Tags"], horizontal=True)
        hits = (C.memory.retrieve_by_similarity(q) if mode.startswith("Similarity")
                else C.memory.retrieve_by_vector(q) if mode.startswith("Vector")
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
    st.divider()
    st.markdown("### 🩹 Validation failure drill: diagnose → targeted repair → escalate")
    if not C.ctx.get("draft_sections"):
        st.info("Build a draft first (Workflow → Draft & checks), then inject a fault here.")
    else:
        kind = st.selectbox("Fault to inject into the current draft", list(FAULTS))
        if st.button("💉 Inject, detect & heal"):
            snapshot = {k: v for k, v in C.ctx["draft_sections"].items()}
            what = inject_fault(C, kind)
            C.check()
            before = C.validate()
            st.error(f"Injected: {what}")
            st.write("**Detected:** " + "; ".join(before["failing_checks"]))
            out = C.healer.heal(before)
            C.ctx["validation"] = out["report"]
            if out["healed"]:
                st.success(f"Healed in {out['attempts']} attempt(s). Untouched sections: "
                           f"{sum(1 for t in snapshot if C.ctx['draft_sections'].get(t) == snapshot[t])}/{len(snapshot)}")
                C.assemble()
            else:
                st.error("Could not be repaired automatically → escalated to the faculty with a diagnosis.")
                st.write(C.ctx.get("escalation"))
            df([{k: (", ".join(v) if isinstance(v, list) else v) for k, v in e.items()} for e in out["log"]])
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
    st.markdown("**Access control (who may do what)**")
    df(AccessControl.matrix())
    denied = [e for e in C.ledger.entries if e["status"] == "DENIED"]
    denied_conn = [e for e in C.connector.get_audit_trail() if e.get("decision") == "DENIED"]
    st.caption(f"{len(denied)} denied human action(s) · {len(denied_conn)} denied connector call(s)")
    if denied or denied_conn:
        df(denied + denied_conn)
    if C.metrics_history:
        st.markdown("**Run metrics history**")
        df(C.metrics_history)
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
    st.subheader("Lab 13 · Discipline-specific agents (domain packs)")
    topic_probe = st.text_input("Topic to classify", C.ctx.get("topic", DEMO["topic"]), key="dom_topic")
    detected = detect_domain(topic_probe)
    pick = st.selectbox("Pack", list(PACKS), index=list(PACKS).index(detected), format_func=lambda k: PACKS[k].name,
                        help=f"Auto-detected: {PACKS[detected].name}")
    pk = PACKS[pick]
    st.write(f"**Extra sections plugged into the outline:** {', '.join(pk.extra_sections)}")
    st.write("**Authors must state:** " + "; ".join(pk.method_guidance))
    st.write("**Checkable rules:**")
    df([{"rule": r["name"], "looks in sections": ", ".join(r["section_keywords"]), "needs one of": ", ".join(r["must_contain"])}
        for r in pk.required_checks])
    st.divider()
    st.markdown("**Venue & citation tools**")
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
