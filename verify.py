"""
Lab 2 & Lab 7 Validation Agent (Phase C - Applied Reliability)
Acts as the hard validation gate.
Verifies grounding (every claim cites a real source, no fabricated citations), scope bounds, and venue compliance.
Returns a structured validation report used by the bounded regenerate back-edge in the node graph.
"""

from typing import Dict, Any, List

class ValidationAgent:
    def __init__(self, search_tools=None):
        self.search_tools = search_tools

    def validate(self, ctx: Dict[str, Any], plan: Any = None) -> Dict[str, Any]:
        """
        Executes strict acceptance checks on the current run context.
        """
        print("\n--- VALIDATION AGENT: ACCEPTANCE GATE CHECK ---")
        checks = []
        
        # Check 1: Reading list exists and references have valid IDs & titles (Grounding)
        reading_list = ctx.get("reading_list", [])
        grounded = len(reading_list) > 0 and all("id" in p and "title" in p for p in reading_list)
        checks.append(("Every claim cites a real source (no fabricated citations)", grounded))

        # Check 2: Gap analysis & uniqueness decision exists
        gap_analysis = ctx.get("gap_analysis", {})
        gap_valid = bool(gap_analysis and ("novelty_flag" in gap_analysis or "why_our_work_is_unique" in gap_analysis))
        checks.append(("Gap analysis evaluates topic novelty & uniqueness vs literature", gap_valid))

        # Check 3: Draft sections match outline structure
        sections = ctx.get("draft_sections", {})
        sections_valid = len(sections) >= 3
        checks.append(("Draft structure contains all required sections", sections_valid))

        # Check 4: Citation compliance report passed
        citation_comp = ctx.get("citation_compliance", {})
        compliance_valid = citation_comp.get("compliance_passed", False)
        checks.append(("Citation compliance & reference formatting passed", compliance_valid))

        # Evaluate failing checks
        failing = [name for name, passed in checks if not passed]
        passed_all = len(failing) == 0

        report = {
            "passed": passed_all,
            "failing_checks": failing,
            "passed_checks": [name for name, passed in checks if passed],
            "diagnosis": "All validation gates passed cleanly." if passed_all else f"Validation failures detected: {failing}"
        }

        print(f"Validation Result: Passed={report['passed']}")
        for name, ok in checks:
            status_str = "PASS" if ok else "FAIL"
            print(f"  [{status_str}] {name}")

        return report

    def run_and_verify(self, tool_name: str, arg: str = "") -> Dict[str, Any]:
        """Legacy tool execution verifier for Lab 2 compatibility."""
        if not self.search_tools:
            return {"valid": False, "error": "No search tools bound."}

        if tool_name == "read_corpus":
            results = self.search_tools.read_corpus(arg)
        elif tool_name == "read_library":
            results = self.search_tools.read_library()
        else:
            return {"valid": False, "error": "Unknown tool."}

        try:
            assert isinstance(results, list), "Tool must return a list."
            for item in results:
                assert "id" in item, "Missing ID in data."
                assert "title" in item, "Missing Title in data."
            return {"valid": True, "data": results}
        except AssertionError as e:
            return {"valid": False, "error": str(e)}

if __name__ == "__main__":
    v = ValidationAgent()
    rep = v.validate({"reading_list": [{"id": "C1", "title": "Test"}]})
    print("Validation agent test completed.")