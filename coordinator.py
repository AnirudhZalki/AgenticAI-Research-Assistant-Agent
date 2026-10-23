"""
Lab 14: Capstone - Research Assistant Coordinator (end-to-end, all labs integrated)

Implements the proposal's hybrid execution methodology on top of LangChain runnables, OpenClaw runtime
governance and the MCP tool layer:

  Gate 1  intake            sequential  faculty confirms topic / venue / deadline        (Lab 1)
          plan + outline    sequential  locked blueprint, outline confirmed before draft  (Lab 3)
  Stage 2 discovery         PARALLEL    swarm + Literature Discovery || Funding Radar     (Labs 8, 9, 7)
  Stage 3 gap analysis      sequential  needs the reading list
  Stage 4 drafting          sequential  needs the gap analysis + confirmed outline
  Stage 5 checks            PARALLEL    Citation & Compliance || Collaboration
  Gate 2  validation        sequential  hard acceptance gate with bounded retry           (Lab 7)
  Gate 3  faculty approval  sequential  nothing is exported without it                    (Labs 6, 12)
  Stage 6 export            PARALLEL    Export & tracker version || checkpoint + ledger
"""

import json
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional

from langchain_core.runnables import RunnableLambda, RunnableParallel

from clarify import RequestClarifier
from access import AccessControl, Actor, classification
from connector import ResearchDataConnector
from deep_research import DeepResearchAgent
from domain import detect_domain, get_pack, parse_venue
from healing import SelfHealer
from governance import AuditLedger, Evaluator, GuardrailPolicy, dynamic_risks
from langchain_orchestrator import LangChainOrchestrator
from mcp_server import MCPServer
from memory import MemoryStore
from openclaw_runtime import OpenClawAgentRuntime
from ops import CircuitBreaker, FaultInjector, OpsAgent, Tracer, instrument
from radar import RadarMonitor
from search import SearchTools
from skills import FormattingSkill, ResearchPlanSkill
from specialist_agents import DEFAULT_APPROVED_SOURCES
from swarm import ParallelSwarm
from tracker import ResearchTracker
from verify import ValidationAgent

REQUIRED = ("topic", "venue", "collaborators", "deadline")


class ResearchCoordinator:
    def __init__(self, use_live: bool = False, tracker_path: Optional[str] = None,
                 checkpoint_file: str = "checkpoint_app.json", max_budget_steps: int = 300,
                 retries: int = 2, backoff_s: float = 0.05):
        self.use_live = use_live
        tools = SearchTools()
        if not use_live:
            tools.search_online = lambda query, max_results=6: []      # offline: corpus only
        self.tools = tools
        self.connector = ResearchDataConnector(tools, auth_required=True)   # least-privilege scopes (Lab 5)
        self.tracer, self.faults = Tracer(), FaultInjector()
        instrument(self.connector, self.tracer, self.faults, retries=retries, backoff_s=backoff_s,
                   breaker=CircuitBreaker(threshold=3, cooldown_s=5))
        self.mcp = MCPServer(self.connector)
        self.memory = MemoryStore(corpus=tools.corpus, library=tools.library)
        self.runtime = OpenClawAgentRuntime(max_budget_steps=max_budget_steps, checkpoint_file=checkpoint_file)
        self.orch = LangChainOrchestrator(mcp_server=self.mcp)
        self.tracker = ResearchTracker(tracker_path)
        self.orch.export_agent.tracker = self.tracker
        self.ledger = AuditLedger()
        self.policy, self.evaluator, self.ops = GuardrailPolicy(), Evaluator(), OpsAgent()
        self.validator = ValidationAgent()
        self.timeline: List[Dict[str, Any]] = []
        self.approved = False
        self.ctx: Dict[str, Any] = {}
        self.blueprint = None
        self.healer = SelfHealer(self)
        self.metrics_history: List[Dict[str, Any]] = []
        self.radar_monitor: Optional[RadarMonitor] = None
        self.checkpoint_path = self.runtime.checkpoint_file

    # ---------------------------------------------------------------- helpers
    def _log(self, intent: str, action: str, result: Any = "", status: str = "SUCCESS"):
        self.runtime.log_audit_step(intent, action, result, status=status)
        self.ledger.append("Coordinator", intent, result, status)

    def _stage(self, name: str, mode: str, fn: Callable[[], Any]):
        t0 = time.time()
        out = fn()
        self.timeline.append({"stage": name, "mode": mode, "seconds": round(time.time() - t0, 3)})
        self.ctx.setdefault("stages_done", []).append(name)
        self.runtime.checkpoint(session_state=self.ctx)        # checkpoint after every stage (resume point)
        return out

    def _parallel(self, branches: Dict[str, Callable], ctx: Dict[str, Any], take: Dict[str, List[str]]) -> Dict[str, Any]:
        """Run branches concurrently on copies of ctx and merge only the keys each branch owns."""
        res = RunnableParallel(**{k: RunnableLambda(f) for k, f in branches.items()}).invoke(dict(ctx))
        for branch, keys in take.items():
            for k in keys:
                if k in res[branch]:
                    ctx[k] = res[branch][k]
        return ctx

    # --------------------------------------------------------- Gate 1: intake
    def intake(self, request: Dict[str, str]) -> Dict[str, Any]:
        missing = [f for f in REQUIRED if not str(request.get(f, "")).strip()]
        if missing:
            raise ValueError(f"Gate 1 blocked: faculty must confirm {missing} before any work starts.")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", request["deadline"].strip()):
            raise ValueError("Gate 1 blocked: deadline must be YYYY-MM-DD.")
        state = RequestClarifier().clarify(initial_inputs={k: request[k] for k in REQUIRED}, interactive=False)
        self.ctx = dict(state)
        self.ctx["approved_sources"] = list(DEFAULT_APPROVED_SOURCES)
        self.ctx["domain"] = request.get("domain") or detect_domain(state["topic"])
        self.ctx["stages_done"] = []
        self.ctx["prior_tasks"] = self.memory.retrieve_prior_tasks(state["topic"])
        self.memory.update_session("clarified_state", state)
        self._log("Gate 1: Intake", "RequestClarifier", state)
        return self.ctx

    # ------------------------------------------------------------------- plan
    def plan(self) -> Any:
        self.blueprint = ResearchPlanSkill().execute(self.ctx)
        pack = get_pack(self.ctx.get("domain"))
        names = [x.split(". ", 1)[-1] for x in self.blueprint.sections]
        for extra in pack.extra_sections:                       # domain pack plugs its required sections into the plan
            if extra not in names:
                names.insert(max(len(names) - 1, 0), extra)
        self.blueprint.sections = [f"{i}. {n}" for i, n in enumerate(names, 1)]
        self.ctx["plan_sections"] = list(self.blueprint.sections)
        self.memory.update_session("active_plan", self.blueprint)
        self._log("Plan", "ResearchPlanSkill", self.blueprint.title)
        return self.blueprint

    def confirm_outline(self, sections: List[str]):
        if not sections:
            raise ValueError("Outline cannot be empty.")
        self.ctx["confirmed_outline"] = list(sections)
        self.ctx["plan_sections"] = list(sections)
        if self.blueprint:
            self.blueprint.sections, self.blueprint.locked = list(sections), True
        self._log("Outline confirmed", "Faculty", f"{len(sections)} sections")

    # ------------------------------------------------- Stage 2: parallel discovery
    def discover(self, subqueries: Optional[List[str]] = None) -> Dict[str, Any]:
        topic = self.ctx["topic"]
        subqueries = subqueries or [topic] + [w for w in topic.split() if len(w) > 4][:3]

        def run():
            swarm = ParallelSwarm(mcp_server=self.mcp).run_swarm(subqueries, main_topic=topic)
            self.ctx["swarm_results"] = swarm
            self.memory.update_session("swarm_discovery", swarm)
            self._parallel(
                {"lit": lambda c: self.orch.lit_agent.step(c, self.connector),
                 "radar": lambda c: self.orch.radar_agent.step(c, self.connector)},
                self.ctx, {"lit": ["reading_list", "literature_warnings", "rejected_references"], "radar": ["radar_deadlines"]})
        self._stage("Discovery (swarm + literature || radar)", "PARALLEL", run)
        self._log("Literature Discovery", "Swarm + ranked reading list (MCP)", len(self.ctx.get("reading_list", [])))
        self._log("Funding Radar", "Deadlines & CFPs (MCP)", len(self.ctx.get("radar_deadlines", [])))
        return self.ctx

    def deep_research(self) -> Dict[str, Any]:
        out = self._stage("Deep research (evidence table)", "SEQUENTIAL",
                          lambda: DeepResearchAgent(self.connector).run(self.ctx["topic"], use_online=self.use_live))
        self.ctx["deep_research"] = out
        self._log("Deep Research", "Iterative retrieval + evidence table", f"{len(out['evidence_table'])} rows")
        return out

    # ------------------------------------------------------- Stages 3 & 4
    def analyze_gap(self):
        self._stage("Gap & idea analysis", "SEQUENTIAL", lambda: self.orch.gap_agent.step(self.ctx, self.connector))
        self._log("Gap Analysis", "Novelty vs overlap", self.ctx["gap_analysis"]["novelty_flag"])

    def draft(self):
        if "confirmed_outline" not in self.ctx:
            raise PermissionError("Drafting blocked: the outline must be confirmed first (outline-first rule).")
        self._stage("Drafting & writing", "SEQUENTIAL", lambda: self.orch.draft_agent.step(self.ctx, self.connector))
        self._log("Drafting", "Outline-first draft", len(self.ctx["draft_sections"]))

    # ------------------------------------------------- Stage 5: parallel checks
    def check(self) -> Dict[str, Any]:
        def run():
            self._parallel(
                {"cite": lambda c: self.orch.comp_agent.step(c, self.connector),
                 "collab": lambda c: self.orch.collab_agent.step(c, self.connector)},
                self.ctx, {"cite": ["citation_compliance", "formatted_references"],
                           "collab": ["collaboration", "collab_annotations"]})
        self._stage("Checks (citation || collaboration)", "PARALLEL", run)
        cc = self.ctx["citation_compliance"]
        self._log("Citation Compliance", "Format + completeness", f"errors={len(cc['errors'])} warnings={len(cc['warnings'])}")
        self._log("Collaboration", "Attribution", f"conflicts={len(self.ctx['collaboration']['conflicts'])}")
        return self.ctx

    # ----------------------------------------------------- Gate 2: validation
    def validate(self) -> Dict[str, Any]:
        rep = self._stage("Validation gate", "SEQUENTIAL", lambda: self.validator.validate(self.ctx))
        self.ctx["validation"] = rep
        self._log("Validation", "Acceptance gate", rep["diagnosis"], "PASS" if rep["passed"] else "FAIL")
        return rep

    def generate_and_validate(self, max_attempts: int = 3) -> Dict[str, Any]:
        """Draft once, check, validate; on failure SELF-HEAL (repair only the failing part) within a bounded budget,
        and escalate to the human with a diagnosis if it cannot be repaired."""
        self.ctx.pop("escalation", None)
        self.draft()
        self.check()
        rep = self.validate()
        rep["attempts"] = 1
        if not rep["passed"]:
            out = self.healer.heal(rep)
            rep = out["report"]
            rep["attempts"] = 1 + out["attempts"]
            rep["heal_log"] = out["log"]
            self._log("Self-healing", f"{len(out['log'])} targeted repair(s)",
                      "healed" if out["healed"] else "ESCALATED to faculty", "SUCCESS" if out["healed"] else "ESCALATED")
            if out["escalated"]:
                rep["stopped_early"] = "Could not be repaired automatically - escalated to the faculty with a diagnosis."
            self.ctx["validation"] = rep
        return rep

    def assemble(self) -> str:
        """Format the validated draft (with attributed co-author notes) for faculty review."""
        sections = dict(self.ctx.get("draft_sections", {}))
        for sec, notes in self.ctx.get("collab_annotations", {}).items():
            sections[sec] = sections[sec] + "\n" + "\n".join(notes)
        refs = [re.sub(r"^\[\d+\]\s*", "", r) for r in self.ctx.get("formatted_references", [])]
        spec = parse_venue(self.ctx["venue"])
        text = FormattingSkill().execute({
            "title": self.blueprint.title if self.blueprint else f"Research on {self.ctx['topic'].title()}",
            "collaborators": [c.strip() for c in str(self.ctx["collaborators"]).split(",")],
            "abstract": self.ctx.get("gap_analysis", {}).get("novelty_summary", ""),
            "sections": sections, "references": refs}, venue_spec=spec.citation_style)
        self.ctx["formatted_paper"] = text
        self.memory.update_session("current_draft", text)
        self.ctx["acceptance"] = self.acceptance_suite()
        return text

    # ----------------------------------------------- Lab 11: acceptance suite gates the human review
    def acceptance_suite(self) -> Dict[str, Any]:
        ctx = self.ctx
        refs = ctx.get("reading_list", [])
        gr = {g["guardrail"].split(" ")[0]: g for g in self.policy.evaluate(ctx, self.runtime, self.tracker)}
        cc = ctx.get("citation_compliance", {})
        checks = [
            ("AC1", "Validation gate passed", bool(ctx.get("validation", {}).get("passed")), ctx.get("validation", {}).get("diagnosis", "")),
            ("AC2", ">=5 references, each with a grounded, in-scope evidence record",
             len(refs) >= 5 and all(p.get("evidence", {}).get("grounded") for p in refs), f"{len(refs)} references"),
            ("AC3", "Guardrails G1, G3, G5, G6, G7 hold",
             all(gr[k]["passed"] for k in ("G1", "G3", "G5", "G6", "G7")), "; ".join(f"{k}:{gr[k]['passed']}" for k in ("G1", "G3", "G5", "G6", "G7"))),
            ("AC4", "Draft sections equal the confirmed outline",
             list(ctx.get("draft_sections", {})) == list(ctx.get("confirmed_outline", [])), "outline-first"),
            ("AC5", "Every radar alert is timestamped", bool(ctx.get("radar_deadlines")) and all("checked_at" in d for d in ctx["radar_deadlines"]), f"{len(ctx.get('radar_deadlines', []))} alerts"),
            ("AC6", "No unresolved escalation", "escalation" not in ctx, "none" if "escalation" not in ctx else ctx["escalation"]["reason"][:120]),
            ("AC7", "Domain pack sections present (" + get_pack(ctx.get("domain")).name + ")",
             all(d["status"] != "MISSING_SECTION" for d in cc.get("domain_checks", [])), f"{len(cc.get('domain_checks', []))} domain rule(s)"),
            ("AC8", "Zero citation errors", not cc.get("errors"), f"{len(cc.get('errors', []))} error(s)"),
        ]
        rows = [{"id": i, "criterion": n, "result": "PASS" if ok else "FAIL", "evidence": e} for i, n, ok, e in checks]
        return {"checks": rows, "all_pass": all(ok for _, _, ok, _ in checks)}

    def build(self, request: Dict[str, str], outline: Optional[List[str]] = None, max_attempts: int = 3) -> Dict[str, Any]:
        """The chapter's 'build' command: plan -> research brief + acceptance report (never skips straight to the human)."""
        self.intake(request)
        bp = self.plan()
        self.confirm_outline(outline or bp.sections)
        self.discover()
        self.deep_research()
        self.analyze_gap()
        rep = self.generate_and_validate(max_attempts)
        if rep["passed"]:
            self.assemble()
        return {"ctx": self.ctx, "validation": rep, "acceptance": self.ctx.get("acceptance"),
                "ready_for_review": bool(self.ctx.get("acceptance", {}).get("all_pass"))}

    # --------------------------------------------------- Gate 3: faculty review
    def faculty_decision(self, approve: bool, approver: str = "Faculty Examiner", comments: str = "",
                         role: str = "faculty"):
        actor = Actor(approver, role)
        action = "approve" if approve else "reject"
        try:
            AccessControl.require(actor, action)
        except PermissionError as exc:
            self.ledger.append(approver, f"DENIED {action}", str(exc), "DENIED")
            self.runtime.log_audit_step("Human Gate", "Access control", str(exc), status="DENIED")
            raise
        if not self.ctx.get("formatted_paper"):
            raise RuntimeError("Nothing to review yet.")
        if approve:
            acc = self.ctx.get("acceptance") or self.acceptance_suite()
            if not acc["all_pass"]:
                raise PermissionError("No research brief advances without a fully passing acceptance report: "
                                      + ", ".join(c["id"] for c in acc["checks"] if c["result"] == "FAIL"))
        self.approved = approve
        status = "APPROVED" if approve else "REJECTED"
        self.runtime.log_audit_step("Human Gate: Publish Formatted Research Paper", "Faculty Review",
                                    f"{status} by {approver} ({role}). {comments}".strip(), status=status)
        self.ledger.append(approver, "Faculty Review", comments or status, status)
        if approve:
            self.ctx["approved_by"] = approver
        else:
            self.ctx["faculty_feedback"] = comments
            self.runtime.state["status"] = "STOPPED_AT_FACULTY_GATE"

    def rollback(self, version: str, approver: str = "Faculty Examiner", role: str = "faculty", reason: str = ""):
        actor = Actor(approver, role)
        try:
            AccessControl.require(actor, "rollback")
        except PermissionError as exc:
            self.ledger.append(approver, "DENIED rollback", str(exc), "DENIED")
            raise
        rb = self.tracker.rollback(version, reason or "rollback")
        if rb:
            self.ledger.append(approver, "Rollback", f"{version} -> {rb['version']}")
        return rb

    def classification(self) -> str:
        return classification(self.ctx)

    # ------------------------------------------------------------- Lab 6: crash recovery
    def resume(self) -> str:
        """Restore the last checkpoint (run state, audit log and the working context) after a crash/restart."""
        if not os.path.exists(self.checkpoint_path):
            return ""
        self.runtime.resume_from_checkpoint()
        with open(self.checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ctx = data.get("session_state") or {}
        if not ctx.get("topic"):
            return ""
        self.ctx = ctx
        self.blueprint = ResearchPlanSkill().execute(ctx)
        self.blueprint.sections = list(ctx.get("plan_sections", self.blueprint.sections))
        self.approved = bool(ctx.get("approved_by"))
        return ("export" if ctx.get("export_status") else "review" if ctx.get("formatted_paper") else
                "draft" if ctx.get("reading_list") else "outline" if ctx.get("confirmed_outline") else "plan")

    # ---------------------------------------------------- continuous radar
    def start_radar(self, interval_s: float = 3600.0) -> RadarMonitor:
        if self.radar_monitor is None:
            self.radar_monitor = RadarMonitor(self.connector, self.ctx.get("topic", ""), self.ctx.get("deadline", ""), interval_s)
        else:
            self.radar_monitor.interval_s = interval_s
        self.radar_monitor.start()
        return self.radar_monitor

    # -------------------------------------------------------- Stage 6: export
    def export(self) -> Dict[str, Any]:
        if not self.approved:
            raise PermissionError("Export blocked: faculty approval is required (guardrail G2).")

        def run():
            self._parallel(
                {"export": lambda c: self.orch.export_agent.step(c, self.connector),
                 "repo": lambda c: dict(c, checkpointed=True)},
                self.ctx, {"export": ["export_status", "version", "tracker_entry"]})
        self._stage("Export (document || repository log)", "PARALLEL", run)
        self.memory.archive_task({"topic": self.ctx["topic"], "version": self.ctx["version"],
                                  "approved_by": self.ctx.get("approved_by")})
        self.runtime.state["status"] = "PUBLISHED"
        self._log("Export", "Archive approved document", self.ctx["version"])
        self.runtime.checkpoint(session_state=self.ctx)
        return self.ctx

    # -------------------------------------------------------- reports
    def governance_report(self) -> Dict[str, Any]:
        guardrails = self.policy.evaluate(self.ctx, self.runtime, self.tracker)
        metrics = self.evaluator.score(self.ctx, guardrails, self.ctx.get("validation"))
        return {"guardrails": guardrails, "metrics": metrics,
                "dynamic_risks": dynamic_risks(self.ctx, self.connector),
                "ledger": self.ledger.verify(), "ops": self.ops.diagnose(self.tracer, self.connector)}

    # ------------------------------------------------------- one-shot run
    def run_all(self, request: Dict[str, str], approve: bool = True, approver: str = "Faculty Examiner",
                outline: Optional[List[str]] = None, max_retries: int = 2, role: str = "faculty") -> Dict[str, Any]:
        built = self.build(request, outline, max_retries + 1)
        rep = built["validation"]
        result = {"ctx": self.ctx, "validation": rep, "acceptance": built["acceptance"]}
        if built["ready_for_review"]:
            self.faculty_decision(approve, approver, "" if approve else "Rejected in automated run", role)
            if approve:
                self.export()
        result["governance"] = self.governance_report()
        result["metrics"] = result["governance"]["metrics"]
        result["timeline"] = self.timeline
        self.metrics_history.append({"time": time.strftime("%H:%M:%S"), "topic": self.ctx["topic"],
                                     "score": result["metrics"]["overall_score"],
                                     "validation": result["metrics"]["validation_passed"],
                                     "guardrails": result["metrics"]["guardrails_passed"]})
        return result
