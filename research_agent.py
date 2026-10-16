"""
Command-line entry point matching the proposal's prompt command:

  python research_agent.py start-workflow \
      --topic "edge AI hardware porting frameworks" \
      --venue "IEEE conference, IMRAD, 6-page limit" \
      --collaborators "self, co-author" --deadline "2026-11-15" \
      --constraints "faculty approval before submission, no fabricated citations, audit log"

Faculty approval is asked on the terminal unless --auto-approve is given (testing only).
"""

import argparse
import json
import sys

from coordinator import ResearchCoordinator


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="research_agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("start-workflow", help="run the full Research Assistant workflow")
    for f in ("topic", "venue", "collaborators", "deadline"):
        w.add_argument(f"--{f}", required=True)
    w.add_argument("--outputs", default="ranked reading list, gap summary, outline, draft, citation check")
    w.add_argument("--constraints", default="faculty approval before submission, no fabricated citations, audit log")
    w.add_argument("--live", action="store_true", help="use live academic APIs (Semantic Scholar/CrossRef/OpenAlex)")
    w.add_argument("--auto-approve", action="store_true", help="skip the interactive faculty gate (testing only)")
    w.add_argument("--tracker", default="research_tracker.json")
    args = ap.parse_args(argv)

    c = ResearchCoordinator(use_live=args.live, tracker_path=args.tracker, checkpoint_file="checkpoint_cli.json")
    req = {k: getattr(args, k) for k in ("topic", "venue", "collaborators", "deadline")}
    try:
        c.intake(req)
    except ValueError as exc:
        print(exc)
        return 2
    bp = c.plan()
    print("\nProposed outline:")
    for s in bp.sections:
        print("  ", s)
    if not args.auto_approve and input("Confirm outline? [Y/n] ").strip().lower() in ("n", "no"):
        print("Outline not confirmed; stopping before drafting.")
        return 1
    c.confirm_outline(bp.sections)
    c.discover()
    c.analyze_gap()
    c.draft()
    c.check()
    if not c.validate()["passed"]:
        print("Validation gate failed:", c.ctx["validation"]["diagnosis"])
        return 1
    print(c.assemble())
    ok = args.auto_approve or input("Faculty Examiner - approve and export? [y/N] ").strip().lower() in ("y", "yes")
    c.faculty_decision(ok, "Faculty Examiner", "" if ok else "Declined at CLI")
    if not ok:
        print("Not approved. Nothing exported.")
        return 1
    c.export()
    gov = c.governance_report()
    print(f"\nExported {c.ctx['version']}  |  score {gov['metrics']['overall_score']}  |  guardrails {gov['metrics']['guardrails_passed']}")
    print(json.dumps({"ledger": gov["ledger"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
