"""
Lab 6: Governed Agent Runtime (Phase A - Foundations)
Binds skills, connector, and memory behind a controlled execution controller.
Enforces step execution budgets, human approval gates, state checkpointing, and structured audit logs.
"""

import os
import json
import time
from typing import Dict, Any, List, Optional, Callable
from skills import ResearchPlanSkill, FormattingSkill
from memory import MemoryStore
from connector import ResearchDataConnector

class AgentRuntime:
    def __init__(self, 
                 connector: ResearchDataConnector = None, 
                 memory: MemoryStore = None, 
                 max_budget_steps: int = 50,
                 checkpoint_file: str = "checkpoint.json"):
        self.connector = connector if connector is not None else ResearchDataConnector()
        self.memory = memory if memory is not None else MemoryStore()
        self.plan_skill = ResearchPlanSkill()
        self.format_skill = FormattingSkill()
        
        self.max_budget_steps = max_budget_steps
        self.current_step = 0
        self.checkpoint_file = os.path.join(os.path.dirname(__file__), checkpoint_file)
        self.audit_log: List[Dict[str, Any]] = []
        self.state: Dict[str, Any] = {
            "run_id": f"run-{int(time.time())}",
            "status": "INITIALIZED",
            "context": {}
        }

    def log_audit_step(self, intent: str, action: str, result: Any, status: str = "SUCCESS"):
        """Records an audited step in the runtime execution log."""
        self.current_step += 1
        entry = {
            "step_index": self.current_step,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "intent": intent,
            "action": action,
            "status": status,
            "result_summary": str(result)[:300]
        }
        self.audit_log.append(entry)
        print(f"[RUNTIME STEP {self.current_step}/{self.max_budget_steps}] {intent} -> {status}")
        
        if self.current_step >= self.max_budget_steps:
            raise RuntimeError(f"Runtime execution budget exceeded! (Max steps: {self.max_budget_steps})")

    def checkpoint(self):
        """Saves current runtime state to checkpoint file."""
        checkpoint_data = {
            "state": self.state,
            "audit_log": self.audit_log,
            "session_state": self.memory.session_state,
            "current_step": self.current_step
        }
        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2, default=lambda o: o.__dict__ if hasattr(o, '__dict__') else str(o))
        print(f"[RUNTIME CHECKPOINT] Saved state to {os.path.basename(self.checkpoint_file)}")

    def resume_from_checkpoint(self) -> bool:
        """Resumes runtime state from saved checkpoint if available."""
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            self.state = checkpoint_data.get("state", self.state)
            self.audit_log = checkpoint_data.get("audit_log", [])
            self.memory.session_state = checkpoint_data.get("session_state", {})
            self.current_step = checkpoint_data.get("current_step", 0)
            print(f"[RUNTIME RESUME] Successfully restored state from {os.path.basename(self.checkpoint_file)}")
            return True
        return False

    def human_approval_gate(self, action_name: str, draft_summary: str, auto_approve: bool = False) -> bool:
        """
        Enforces a hard stop human gate before consequential actions (such as paper export or publication).
        """
        print("\n==========================================================================")
        print(f"!!! HUMAN APPROVAL GATE REQUIRED: {action_name.upper()} !!!")
        print("==========================================================================")
        print(f"Draft Summary for Review:\n{draft_summary[:500]}...")
        print("==========================================================================")
        
        if auto_approve:
            print("Auto-Approve Enabled: Faculty Examiner Approved Gate.")
            self.log_audit_step(f"Human Gate: {action_name}", "Faculty Review", "APPROVED (auto)", status="APPROVED")
            return True
            
        ans = input("Faculty Examiner: Do you approve this draft to proceed? (yes/no/edit)\n> ").strip().lower()
        if ans in ['y', 'yes', 'approve']:
            print("Faculty Examiner Approved Gate.")
            self.log_audit_step(f"Human Gate: {action_name}", "Faculty Review", "APPROVED", status="APPROVED")
            return True
        else:
            print("Faculty Examiner Rejected or Requested Revision.")
            self.log_audit_step(f"Human Gate: {action_name}", "Faculty Review", "REJECTED", status="REJECTED")
            return False

if __name__ == "__main__":
    rt = AgentRuntime()
    rt.log_audit_step("Test Step", "Initializing runtime test", "OK")
    rt.checkpoint()
    print("Runtime test completed.")
