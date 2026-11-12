from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .claims import Claim

# Enough of the stdlib to check import hygiene on interpreters without
# sys.stdlib_module_names (3.9). Not exhaustive; a miss is reported as
# unverifiable rather than as a failure.
FALLBACK_STDLIB = frozenset("""
abc argparse ast asyncio base64 bisect calendar collections concurrent contextlib copy
csv dataclasses datetime decimal difflib email enum fnmatch fractions functools getpass
glob gzip hashlib heapq hmac html http importlib inspect io ipaddress itertools json
logging math mimetypes multiprocessing operator os pathlib pickle platform pprint queue
random re shutil signal socket sqlite3 ssl stat statistics string struct subprocess sys
sysconfig tarfile tempfile textwrap threading time timeit traceback types typing unicodedata
unittest urllib uuid warnings weakref xml zipfile zlib
""".split())


@dataclass
class Finding:
    claim: Claim
    found: str
    verdict: str          # supported | unsupported | unverifiable
    note: str = ""


def count_tests(root: str) -> int:
    count = 0
    for base, _dirs, files in os.walk(root):
        if any(part in base for part in (".git", "__pycache__", ".venv", "venv")):
            continue
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            try:
                with open(path, encoding="utf-8") as handle:
                    tree = ast.parse(handle.read())
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                    count += 1
    return count


def check_tests(root: str, claim: Claim) -> Finding:
    claimed = int(claim.value or 0)
    found = count_tests(root)
    if found >= claimed:
        return Finding(claim, f"{found} test functions", "supported")
    return Finding(claim, f"{found} test functions", "unsupported", f"{claimed - found} fewer than claimed")


def check_licence(root: str, claim: Claim) -> Finding:
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"):
        path = os.path.join(root, name)
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="ignore") as handle:
                body = handle.read(400)
            wanted = (claim.value or "").lower().replace("-", " ")
            if wanted.split()[0] in body.lower():
                return Finding(claim, f"{name}: {claim.value}", "supported")
            return Finding(claim, f"{name}: does not mention {claim.value}", "unsupported")
    return Finding(claim, "no licence file", "unsupported")


def declared_requirements(root: str) -> Tuple[Optional[str], List[str]]:
    """Return (requires-python, runtime dependencies) from pyproject.toml, read without a TOML lib."""
    path = os.path.join(root, "pyproject.toml")
    if not os.path.isfile(path):
        return None, []
    with open(path, encoding="utf-8") as handle:
        body = handle.read()
    python = None
    match = re.search(r'requires-python\s*=\s*"([^"]+)"', body)
    if match:
        python = re.search(r"(\d\.\d+)", match.group(1)).group(1) if re.search(r"(\d\.\d+)", match.group(1)) else None
    deps: List[str] = []
    block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", body, re.S | re.M)
    if block:
        deps = re.findall(r'"([^"]+)"', block.group(1))
    return python, deps


def imported_top_level(root: str) -> Dict[str, str]:
    """Top-level imports across the package, skipping tests and local modules."""
    local = {name[:-3] for name in os.listdir(root) if name.endswith(".py")}
    for entry in os.listdir(root):
        if os.path.isdir(os.path.join(root, entry)) and os.path.isfile(os.path.join(root, entry, "__init__.py")):
            local.add(entry)
    found: Dict[str, str] = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".venv", "venv", "tests", ".github"}]
        for name in files:
            if not name.endswith(".py"):
                continue
            try:
                with open(os.path.join(base, name), encoding="utf-8") as handle:
                    tree = ast.parse(handle.read())
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        found.setdefault(alias.name.split(".")[0], os.path.relpath(os.path.join(base, name), root))
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    found.setdefault(node.module.split(".")[0], os.path.relpath(os.path.join(base, name), root))
    return {name: where for name, where in found.items() if name not in local}


def stdlib_names() -> frozenset:
    return frozenset(getattr(sys, "stdlib_module_names", FALLBACK_STDLIB))


def check_stdlib(root: str, claim: Claim) -> Finding:
    imports = imported_top_level(root)
    third_party = {name: where for name, where in imports.items() if name not in stdlib_names()}
    if not third_party:
        return Finding(claim, f"{len(imports)} imports, all stdlib", "supported")
    listed = ", ".join(f"{name} ({where})" for name, where in sorted(third_party.items())[:4])
    return Finding(claim, listed, "unsupported", "third-party import found")


def check_python(root: str, claim: Claim) -> Finding:
    declared, _deps = declared_requirements(root)
    if not declared:
        return Finding(claim, "no requires-python", "unverifiable", "nothing to compare against")
    if declared == claim.value:
        return Finding(claim, f"requires-python {declared}", "supported")
    return Finding(claim, f"requires-python {declared}", "unsupported", "floor differs from the claim")


def has_ci(root: str) -> bool:
    workflows = os.path.join(root, ".github", "workflows")
    if not os.path.isdir(workflows):
        return False
    return any(name.endswith((".yml", ".yaml")) for name in os.listdir(workflows))


def check_ci(root: str, claim: Claim) -> Finding:
    if has_ci(root):
        return Finding(claim, ".github/workflows present", "supported", "run status needs the network; not checked")
    return Finding(claim, "no workflow file", "unsupported")


def commit_count(root: str) -> Optional[int]:
    try:
        out = subprocess.run(["git", "-C", root, "rev-list", "--count", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return int(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def check_shipped(root: str, claim: Claim) -> Finding:
    commits = commit_count(root)
    tests = count_tests(root)
    if commits is None:
        return Finding(claim, "not a git repository", "unverifiable", "history needed to check")
    if commits >= 1 and tests >= 1 and has_ci(root):
        return Finding(claim, f"{commits} commits, {tests} tests, CI workflow", "supported")
    parts = [f"{commits} commits", f"{tests} tests", "CI workflow" if has_ci(root) else "no CI workflow"]
    return Finding(claim, ", ".join(parts), "unsupported", "shipped needs history, tests and CI")


CHECKS = {
    "tests": check_tests,
    "licence": check_licence,
    "stdlib": check_stdlib,
    "python": check_python,
    "ci": check_ci,
    "shipped": check_shipped,
}


def audit(root: str, claims: List[Claim]) -> List[Finding]:
    findings = []
    for claim in claims:
        check = CHECKS.get(claim.kind)
        findings.append(check(root, claim) if check else Finding(claim, "", "unverifiable", "no check"))
    return findings
