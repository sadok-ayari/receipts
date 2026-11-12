import os
import subprocess
import tempfile
import unittest

from receipts import audit, report
from receipts.claims import extract

GOOD_README = """# tool

Python 3.9+. No dependencies. 3 tests, offline. CI is green.
Licensed MIT. Shipped.
"""

BAD_README = """# tool

Python 3.9+. No dependencies. 40 tests. Licensed Apache-2.0. CI is green. Shipped.
"""


def write(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(body)


def git_init(root):
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.org",
                    "commit", "-qm", "init"], cwd=root, check=True)


def good_repo(root):
    write(os.path.join(root, "README.md"), GOOD_README)
    write(os.path.join(root, "LICENSE"), "MIT License\n\nCopyright (c) 2026\n")
    write(os.path.join(root, "pyproject.toml"),
          '[project]\nname = "tool"\nrequires-python = ">=3.9"\ndependencies = []\n')
    write(os.path.join(root, ".github", "workflows", "ci.yml"), "name: ci\non: push\n")
    write(os.path.join(root, "tool", "__init__.py"), "")
    write(os.path.join(root, "tool", "core.py"),
          "import json\nimport urllib.request\nfrom dataclasses import dataclass\n")
    write(os.path.join(root, "tests", "test_core.py"),
          "def test_a():\n    assert True\n\ndef test_b():\n    assert True\n\n"
          "def test_c():\n    assert True\n")
    git_init(root)


def bad_repo(root):
    write(os.path.join(root, "README.md"), BAD_README)
    write(os.path.join(root, "LICENSE"), "Apache License\nVersion 2.0\n")
    write(os.path.join(root, "pyproject.toml"),
          '[project]\nname = "tool"\nrequires-python = ">=3.8"\ndependencies = ["requests"]\n')
    write(os.path.join(root, "tool", "__init__.py"), "")
    write(os.path.join(root, "tool", "core.py"), "import requests\n")
    write(os.path.join(root, "tests", "test_core.py"),
          "def test_a():\n    assert True\n\ndef test_b():\n    assert True\n")


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name

    def tearDown(self):
        self.dir.cleanup()

    def by_kind(self, findings):
        return {finding.claim.kind: finding for finding in findings}

    def test_good_repo_passes_every_claim(self):
        good_repo(self.root)
        findings = audit.audit(self.root, extract(GOOD_README))
        verdicts = {f.claim.kind: f.verdict for f in findings}
        self.assertEqual(verdicts["tests"], "supported")
        self.assertEqual(verdicts["licence"], "supported")
        self.assertEqual(verdicts["stdlib"], "supported")
        self.assertEqual(verdicts["python"], "supported")
        self.assertEqual(verdicts["ci"], "supported")
        self.assertEqual(verdicts["shipped"], "supported")

    def test_bad_repo_fails_the_claims_it_cannot_meet(self):
        bad_repo(self.root)
        findings = self.by_kind(audit.audit(self.root, extract(BAD_README)))
        self.assertEqual(findings["tests"].verdict, "unsupported")
        self.assertIn("2 test functions", findings["tests"].found)
        self.assertEqual(findings["stdlib"].verdict, "unsupported")
        self.assertIn("requests", findings["stdlib"].found)
        self.assertEqual(findings["python"].verdict, "unsupported")
        self.assertEqual(findings["ci"].verdict, "unsupported")
        self.assertEqual(findings["shipped"].verdict, "unverifiable")

    def test_licence_mismatch_is_caught(self):
        good_repo(self.root)
        write(os.path.join(self.root, "LICENSE"), "MIT License\n")
        findings = self.by_kind(audit.audit(self.root, extract("Licensed Apache-2.0.\n")))
        self.assertEqual(findings["licence"].verdict, "unsupported")

    def test_missing_pyproject_makes_the_floor_unverifiable(self):
        write(os.path.join(self.root, "README.md"), "Python 3.9+.\n")
        findings = audit.audit(self.root, extract("Python 3.9+.\n"))
        self.assertEqual(findings[0].verdict, "unverifiable")

    def test_test_count_walks_nested_directories(self):
        write(os.path.join(self.root, "tests", "deep", "test_x.py"),
              "def test_one():\n    pass\n\nclass TestThing:\n    def test_two(self):\n        pass\n")
        self.assertEqual(audit.count_tests(self.root), 2)

    def test_syntax_error_in_a_test_file_does_not_crash(self):
        write(os.path.join(self.root, "tests", "test_broken.py"), "def test_(:\n")
        self.assertEqual(audit.count_tests(self.root), 0)


class ReportTests(unittest.TestCase):
    def test_render_lists_every_claim(self):
        with tempfile.TemporaryDirectory() as root:
            bad_repo(root)
            findings = audit.audit(root, extract(BAD_README))
            markdown = report.render(findings, "tool")
        self.assertIn("# Receipts — tool", markdown)
        self.assertIn("UNSUPPORTED", markdown)
        self.assertIn("Fix or withdraw", markdown)
        self.assertIn("Could not check", markdown)

    def test_counts_add_up(self):
        with tempfile.TemporaryDirectory() as root:
            good_repo(root)
            findings = audit.audit(root, extract(GOOD_README))
            tally = report.counts(findings)
        self.assertEqual(tally["total"], sum(tally[k] for k in ("supported", "unsupported", "unverifiable")))


if __name__ == "__main__":
    unittest.main()
