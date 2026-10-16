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

import re
import time
from typing import Any, Callable, Dict, List, Optional

from langchain_core.runnables import RunnableLambda, RunnableParallel

from clarify import RequestClarifier
from connector import ResearchDataConnector
from deep_research import DeepResearchAgent
from domain import parse_venue
from governance import AuditLedger, Evaluator, GuardrailPolicy, dynamic_risks
from langchain_orchestrator import LangChainOrchestrator
from mcp_server import MCPServer
from memory import MemoryStore
from openclaw_runtime import OpenClawAgentRuntime
from ops import CircuitBreaker, FaultInjector, OpsAgent, Tracer, instrument
from search import SearchTools
from skills import FormattingSkill, ResearchPlanSkill
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
        self.connector = ResearchDataConnector(tools)
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

    # ---------------------------------------------------------------- helpers
    def _log(self, intent: str, action: str, result: Any = "", status: str = "SUCCESS"):
        self.runtime.log_audit_step(intent, action, result, status=status)
        self.ledger.append("Coordinator", intent, result, status)

    def _stage(self, name: str, mode: str, fn: Callable[[], Any]):
        t0 = time.time()
        out = fn()
        self.timeline.append({"stage": name, "mode": mode, "seconds": round(time.time() - t0, 3)})
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
        state = RequestClarifier().clarify(initial_inputs=request, interactive=False)
        self.ctx = dict(state)
        self.ctx["prior_tasks"] = self.memory.retrieve_prior_tasks(state["topic"])
        self.memory.update_session("clarified_state", state)
        self._log("Gate 1: Intake", "RequestClarifier", state)
        return self.ctx

    # ------------------------------------------------------------------- plan
    def plan(self) -> Any:
        self.blueprint = ResearchPlanSkill().execute(self.ctx)
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
                self.ctx, {"lit": ["reading_list", "literature_warnings"], "radar": ["radar_deadlines"]})
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
        return text

    # --------------------------------------------------- Gate 3: faculty review
    def faculty_decision(self, approve: bool, approver: str = "Faculty Examiner", comments: str = ""):
        if not self.ctx.get("formatted_paper"):
            raise RuntimeError("Nothing to review yet.")
        if approve and not self.ctx.get("validation", {}).get("passed"):
            raise PermissionError("Cannot approve a draft that failed the validation gate.")
        self.approved = approve
        status = "APPROVED" if approve else "REJECTED"
        self.runtime.log_audit_step("Human Gate: Publish Formatted Research Paper", "Faculty Review",
                                    f"{status} by {approver}. {comments}".strip(), status=status)
        self.ledger.append(approver, "Faculty Review", comments or status, status)
        if approve:
            self.ctx["approved_by"] = approver
        else:
            self.ctx["faculty_feedback"] = comments
            self.runtime.state["status"] = "STOPPED_AT_FACULTY_GATE"

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
                outline: Optional[List[str]] = None, max_retries: int = 2) -> Dict[str, Any]:
        self.intake(request)
        bp = self.plan()
        self.confirm_outline(outline or bp.sections)
        self.discover()
        self.deep_research()
        self.analyze_gap()
        rep = {"passed": False}
        for attempt in range(1, max_retries + 2):
            self.draft()
            self.check()
            rep = self.validate()
            if rep["passed"]:
                break
            self.ctx["retry_count"] = attempt
        result = {"ctx": self.ctx, "validation": rep}
        if rep["passed"]:
            self.assemble()
            self.faculty_decision(approve, approver, "" if approve else "Rejected in automated run")
            if approve:
                self.export()
        result["governance"] = self.governance_report()
        result["metrics"] = result["governance"]["metrics"]
        result["timeline"] = self.timeline
        return result
