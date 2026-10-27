"""
Lab 12: access control & confidentiality

  * ROLES / AccessControl : who may approve, roll back, export, view confidential drafts, edit
  * Actor                 : a named person with a role ("actor.can_approve" in the chapter's pseudocode)
  * classification / redact_view : unpublished drafts are CONFIDENTIAL; roles without view_confidential see a
                                   redacted view (outline and status only) until the approved version is published
Every refusal is written to the audit ledger by the caller.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

ROLES: Dict[str, Dict[str, Any]] = {
    "faculty": {"label": "Faculty / Researcher", "can": {"approve", "reject", "rollback", "export_files",
                "view_confidential", "edit_draft", "run_pipeline", "view_audit", "view_dashboard"}},
    "coauthor": {"label": "Co-author", "can": {"edit_draft", "export_files", "view_confidential", "run_pipeline",
                 "view_audit", "view_dashboard"}},
    "student_assistant": {"label": "Student research assistant", "can": {"run_pipeline", "edit_draft", "view_dashboard"}},
    "research_office": {"label": "Research office (read-only)", "can": {"view_audit", "view_dashboard"}},
}


@dataclass
class Actor:
    name: str
    role: str = "faculty"

    @property
    def can_approve(self) -> bool:
        return AccessControl.can(self, "approve")


class AccessControl:
    @staticmethod
    def can(actor: Actor, action: str) -> bool:
        return action in ROLES.get(actor.role, {}).get("can", set())

    @staticmethod
    def require(actor: Actor, action: str):
        if not AccessControl.can(actor, action):
            raise PermissionError(f"Access denied: role '{actor.role}' ({actor.name}) may not '{action}'.")

    @staticmethod
    def matrix() -> List[Dict[str, Any]]:
        actions = sorted({a for r in ROLES.values() for a in r["can"]})
        return [{"action": a, **{r: ("yes" if a in v["can"] else "-") for r, v in ROLES.items()}} for a in actions]


def classification(ctx: Dict[str, Any]) -> str:
    return ("INTERNAL - APPROVED & PUBLISHED" if ctx.get("export_status") == "READY_FOR_PUBLICATION"
            else "CONFIDENTIAL - UNPUBLISHED DRAFT")


def redact_view(ctx: Dict[str, Any], actor: Actor) -> Dict[str, Any]:
    """What an actor is allowed to see of the current run."""
    if AccessControl.can(actor, "view_confidential") or ctx.get("export_status") == "READY_FOR_PUBLICATION":
        return ctx
    out = dict(ctx)
    out["draft_sections"] = {t: "[REDACTED - confidential unpublished draft]" for t in ctx.get("draft_sections", {})}
    out["formatted_paper"] = "[REDACTED - confidential unpublished draft]"
    out["gap_analysis"] = {"novelty_flag": "[REDACTED]"}
    out["collaboration"] = {"policy": ctx.get("collaboration", {}).get("policy", ""),
                            "attribution": [], "conflicts": []}
    out["coauthor_edits"] = []
    return out
