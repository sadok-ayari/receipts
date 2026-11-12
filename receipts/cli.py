from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__, audit, report
from .claims import extract


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="receipts",
                                     description="Check a README's claims against the repository.")
    parser.add_argument("--version", action="version", version=f"receipts {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("audit", help="audit a repository in place")
    run.add_argument("path", nargs="?", default=".")
    run.add_argument("--out", default=None, help="write the markdown report here")
    run.add_argument("--json", action="store_true")
    run.add_argument("--strict", action="store_true", help="exit 1 on unverifiable claims too")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    root = os.path.abspath(args.path)
    readme_path = os.path.join(root, "README.md")
    if not os.path.isfile(readme_path):
        print(f"error: no README.md in {root}", file=sys.stderr)
        return 2

    with open(readme_path, encoding="utf-8") as handle:
        claims = extract(handle.read())
    findings = audit.audit(root, claims)
    markdown = report.render(findings, os.path.basename(root.rstrip("/")) or root)

    if args.out:
        directory = os.path.dirname(os.path.abspath(args.out))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(markdown)

    tally = report.counts(findings)
    if args.json:
        print(json.dumps({"repo": root, "counts": tally,
                          "findings": [{"line": f.claim.line, "kind": f.claim.kind,
                                        "claim": f.claim.text, "found": f.found,
                                        "verdict": f.verdict, "note": f.note} for f in findings]},
                         indent=2))
    else:
        print(f"{tally['total']} claims · {tally['supported']} supported · "
              f"{tally['unsupported']} unsupported · {tally['unverifiable']} unverifiable")
        for finding in findings:
            if finding.verdict != "supported":
                print(f"  line {finding.claim.line}: {finding.claim.text!r} — {finding.found}")

    if tally["unsupported"]:
        return 1
    if args.strict and tally["unverifiable"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
