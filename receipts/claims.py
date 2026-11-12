from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

TEST_CLAIM = re.compile(r"(\d{1,4})\s+(?:[A-Za-z-]+\s+){0,3}tests?\b")
LICENSE_CLAIM = re.compile(r"\b(MIT|Apache[- ]2(?:\.0)?|GPLv?3|BSD|ISC|MPL[- ]2(?:\.0)?)\b")
STDLIB_CLAIM = re.compile(
    r"\b(?:no dependencies|zero dependencies|no runtime dependencies|"
    r"standard library only|stdlib[- ]only|no third[- ]party (?:dependencies|packages))\b", re.I)
PYTHON_CLAIM = re.compile(r"[Pp]ython\s*(\d\.\d{1,2})\s*\+")
CI_CLAIM = re.compile(r"\b(?:CI (?:is )?green|tests? pass|build passing|all checks pass)\b", re.I)
SHIPPED_CLAIM = re.compile(r"\b(?:shipped|production[- ]ready|battle[- ]tested|stable|v\d+\.\d+\.\d+ released)\b", re.I)


@dataclass
class Claim:
    kind: str                     # tests | licence | stdlib | python | ci | shipped
    text: str
    value: Optional[str] = None
    line: int = 0


INLINE_CODE = re.compile(r"`[^`]*`")
QUOTED = re.compile(r"\"[^\"]*\"|'[^']*'|\u201c[^\u201d]*\u201d")


def _asserted(text: str) -> str:
    """Strip what the README is quoting or demonstrating. A claim counts when it is asserted."""
    return QUOTED.sub(" ", INLINE_CODE.sub(" ", text))


def extract(readme: str) -> List[Claim]:
    """Pull the checkable claims. Only claims a machine can check are returned."""
    claims: List[Claim] = []
    seen = set()
    in_fence = False
    for number, line in enumerate(readme.splitlines(), start=1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line.strip() or line.strip().startswith(">"):
            continue
        line = _asserted(line)
        for match in TEST_CLAIM.finditer(line):
            key = ("tests", match.group(1))
            if key not in seen:
                seen.add(key)
                claims.append(Claim("tests", match.group(0).strip(), match.group(1), number))
        for match in LICENSE_CLAIM.finditer(line):
            key = ("licence", match.group(1).lower())
            if key not in seen:
                seen.add(key)
                claims.append(Claim("licence", match.group(0), match.group(1), number))
        if STDLIB_CLAIM.search(line):
            key = ("stdlib", "")
            if key not in seen:
                seen.add(key)
                claims.append(Claim("stdlib", STDLIB_CLAIM.search(line).group(0), None, number))
        for match in PYTHON_CLAIM.finditer(line):
            key = ("python", match.group(1))
            if key not in seen:
                seen.add(key)
                claims.append(Claim("python", match.group(0), match.group(1), number))
        if CI_CLAIM.search(line):
            key = ("ci", "")
            if key not in seen:
                seen.add(key)
                claims.append(Claim("ci", CI_CLAIM.search(line).group(0), None, number))
        if SHIPPED_CLAIM.search(line):
            key = ("shipped", "")
            if key not in seen:
                seen.add(key)
                claims.append(Claim("shipped", SHIPPED_CLAIM.search(line).group(0), None, number))
    return claims
