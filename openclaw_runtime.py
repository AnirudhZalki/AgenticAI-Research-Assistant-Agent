"""
OpenClaw Agent Runtime Layer
Wraps execution context inside the OpenClaw Agent Runtime environment.
Manages step budget governance, checkpoint persistence, structured audit logs, and faculty human review gates.
"""

import os
import json
import time
from typing import Dict, Any, List
import openclaw

class OpenClawAgentRuntime:
    """OpenClaw Agent Runtime Controller."""
    
    def __init__(self, 
                 max_budget_steps: int = 50, 
                 checkpoint_file: str = "checkpoint.json"):
        self.openclaw_version = getattr(openclaw, "__version__", "2.0.2")
        self.max_budget_steps = max_budget_steps
        self.current_step = 0
        self.checkpoint_file = os.path.join(os.path.dirname(__file__), checkpoint_file)
        self.audit_log: List[Dict[str, Any]] = []
        self.state: Dict[str, Any] = {
            "runtime_engine": f"OpenClaw-{self.openclaw_version}",
            "run_id": f"openclaw-run-{int(time.time())}",
            "status": "INITIALIZED",
            "context": {}
        }

    def log_audit_step(self, intent: str, action: str, result: Any, status: str = "SUCCESS"):
        """OpenClaw Runtime: Logs an audited execution step."""
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
        print(f"[OPENCLAW RUNTIME STEP {self.current_step}/{self.max_budget_steps}] {intent} -> {status}")
        
        if self.current_step >= self.max_budget_steps:
            raise RuntimeError(f"OpenClaw Runtime execution budget exceeded! (Max steps: {self.max_budget_steps})")

    def checkpoint(self, session_state: Dict[str, Any] = None):
        """OpenClaw Runtime: Saves current execution state to checkpoint file."""
        checkpoint_data = {
            "state": self.state,
            "audit_log": self.audit_log,
            "session_state": session_state if session_state is not None else {},
            "current_step": self.current_step
        }
        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2, default=lambda o: o.__dict__ if hasattr(o, '__dict__') else str(o))
        print(f"[OPENCLAW CHECKPOINT] Saved state to {os.path.basename(self.checkpoint_file)}")

    def resume_from_checkpoint(self) -> bool:
        """OpenClaw Runtime: Restores execution state from saved checkpoint."""
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            self.state = checkpoint_data.get("state", self.state)
            self.audit_log = checkpoint_data.get("audit_log", [])
            self.current_step = checkpoint_data.get("current_step", 0)
            print(f"[OPENCLAW RESUME] Restored state from {os.path.basename(self.checkpoint_file)}")
            return True
        return False

    def human_approval_gate(self, action_name: str, draft_summary: str, auto_approve: bool = False) -> bool:
        """OpenClaw Runtime: Enforces a hard stop human approval gate."""
        print("\n==========================================================================")
        print(f"!!! OPENCLAW HUMAN APPROVAL GATE: {action_name.upper()} !!!")
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
    oc_runtime = OpenClawAgentRuntime()
    print("OpenClaw Runtime initialized. Version:", oc_runtime.openclaw_version)
    oc_runtime.log_audit_step("Test Step", "OpenClaw Test Action", "SUCCESS")
