from __future__ import annotations

from typing import List

from .audit import Finding

MARK = {"supported": "supported", "unsupported": "UNSUPPORTED", "unverifiable": "unverifiable"}


def counts(findings: List[Finding]) -> dict:
    out = {key: 0 for key in MARK}
    for finding in findings:
        out[finding.verdict] += 1
    out["total"] = len(findings)
    return out


def render(findings: List[Finding], name: str) -> str:
    tally = counts(findings)
    out = [f"# Receipts — {name}", ""]
    out.append(f"**{tally['total']} claims · {tally['supported']} supported · "
               f"{tally['unsupported']} unsupported · {tally['unverifiable']} unverifiable**")
    out += ["", "| line | claim | found | verdict |", "|---|---|---|---|"]
    for finding in findings:
        claim = finding.claim.text.replace("|", "/")
        found = finding.found.replace("|", "/")
        out.append(f"| {finding.claim.line} | {claim} | {found} | {MARK[finding.verdict]} |")

    broken = [f for f in findings if f.verdict == "unsupported"]
    if broken:
        out += ["", "## Fix or withdraw", "",
                "_Each line is either a number that is wrong or a claim that is ahead of the code._"]
        for finding in broken:
            out.append(f"- **line {finding.claim.line}:** \"{finding.claim.text}\" — {finding.found}"
                       + (f" ({finding.note})" if finding.note else ""))

    unverifiable = [f for f in findings if f.verdict == "unverifiable"]
    if unverifiable:
        out += ["", "## Could not check", ""]
        for finding in unverifiable:
            out.append(f"- line {finding.claim.line}: \"{finding.claim.text}\" — {finding.note or 'no rule'}")

    out += ["", "---", "",
            "_Claims are read from the README, checks run against the working tree. "
            "A claim with no check is reported, not assumed true._"]
    return "\n".join(out) + "\n"
