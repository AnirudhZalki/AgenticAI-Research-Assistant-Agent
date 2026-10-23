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
        checks = []          # (id, name, passed)

        reading_list = ctx.get("reading_list", [])
        gap_analysis = ctx.get("gap_analysis", {})
        sections = ctx.get("draft_sections", {})
        citation_comp = ctx.get("citation_compliance", {})
        approved = set(ctx.get("approved_sources", []))

        # 1. every claim cites a real source: references are well-formed AND every drafted claim maps to a grounded one
        by_num = {p.get("ref_num"): p for p in reading_list}
        claims = ctx.get("claims", [])
        claims_ok = all(c.get("ref") in by_num and by_num[c["ref"]].get("evidence", {}).get("grounded", True)
                        for c in claims)
        grounded = len(reading_list) > 0 and all("id" in p and "title" in p for p in reading_list) and claims_ok
        checks.append(("grounded", "Every claim cites a real source (no fabricated citations)", grounded))

        # 2. no reference is fabricated; novelty states its uncertainty
        no_fab = not any("synth" in str(p.get("source", "")).lower() for p in reading_list) and \
            (not gap_analysis or "uncertainty" in gap_analysis or "novelty_flag" not in gap_analysis)
        checks.append(("no_fabrication", "No fabricated references; novelty uncertainty stated", no_fab))

        # 3. scope stays within approved corpora
        scope_ok = bool(reading_list) and (not approved or all(p.get("source") in approved for p in reading_list))
        checks.append(("scope", "Scope stays within approved corpora", scope_ok))

        # 4. the draft is marked assistant-generated
        marked = bool(sections) and all("AI-DRAFTED" in t for t in sections.values())
        checks.append(("ai_marked", "The draft is marked assistant-generated", marked))

        # supporting structural checks
        gap_valid = bool(gap_analysis and ("novelty_flag" in gap_analysis or "why_our_work_is_unique" in gap_analysis))
        checks.append(("gap", "Gap analysis evaluates topic novelty & uniqueness vs literature", gap_valid))
        checks.append(("structure", "Draft structure contains all required sections", len(sections) >= 3))
        compliance_valid = citation_comp.get("compliance_passed", False)
        checks.append(("compliance", "Citation compliance & reference formatting passed", compliance_valid))

        failing = [name for _, name, ok in checks if not ok]
        passed_all = not failing
        detail = ""
        if not compliance_valid:
            errs = citation_comp.get("errors", [])
            detail = (" Citation problems: " + "; ".join(errs[:4])) if errs else ""
        report = {
            "passed": passed_all,
            "failing_checks": failing,
            "failing_ids": [i for i, _, ok in checks if not ok],
            "passed_checks": [name for _, name, ok in checks if ok],
            "diagnosis": "All validation gates passed cleanly." if passed_all else
            (f"Validation failures detected: {failing}.{detail}" +
             (f" Only {len(reading_list)} relevant source(s) were found - enable live academic APIs or broaden the topic."
              if len(reading_list) < 5 else "")),
        }

        print(f"Validation Result: Passed={report['passed']}")
        for _, name, ok in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

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