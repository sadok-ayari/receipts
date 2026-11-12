import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from receipts import cli

GOOD_README = "# tool\n\nPython 3.9+. No dependencies. 2 tests. CI is green.\nLicensed MIT. Shipped.\n"
BAD_README = "# tool\n\n40 tests. No dependencies.\n"


def write(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(body)


def good_repo(root):
    write(os.path.join(root, "README.md"), GOOD_README)
    write(os.path.join(root, "LICENSE"), "MIT License\n")
    write(os.path.join(root, "pyproject.toml"),
          '[project]\nrequires-python = ">=3.9"\ndependencies = []\n')
    write(os.path.join(root, ".github", "workflows", "ci.yml"), "name: ci\n")
    write(os.path.join(root, "tool", "core.py"), "import json\n")
    write(os.path.join(root, "tests", "test_core.py"),
          "def test_a():\n    pass\n\ndef test_b():\n    pass\n")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.org",
                    "commit", "-qm", "init"], cwd=root, check=True)


def bad_repo(root):
    write(os.path.join(root, "README.md"), BAD_README)
    write(os.path.join(root, "tool", "core.py"), "def f():\n    pass\n")
    write(os.path.join(root, "tests", "test_core.py"), "def test_a():\n    pass\n")


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name

    def tearDown(self):
        self.dir.cleanup()

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_good_repo_exits_zero(self):
        good_repo(self.root)
        code, out, _ = self.run_cli("audit", self.root)
        self.assertEqual(code, 0)
        self.assertIn("0 unsupported", out)

    def test_bad_repo_exits_one(self):
        bad_repo(self.root)
        code, out, _ = self.run_cli("audit", self.root)
        self.assertEqual(code, 1)
        self.assertIn("unsupported", out)

    def test_strict_fails_on_unverifiable(self):
        write(os.path.join(self.root, "README.md"), "# tool\n\nPython 3.9+.\n")
        self.assertEqual(self.run_cli("audit", self.root)[0], 0)
        self.assertEqual(self.run_cli("audit", self.root, "--strict")[0], 1)

    def test_json_payload(self):
        bad_repo(self.root)
        code, out, _ = self.run_cli("audit", self.root, "--json")
        payload = json.loads(out)
        self.assertEqual(code, 1)
        self.assertTrue(any(f["verdict"] == "unsupported" for f in payload["findings"]))
        self.assertEqual(payload["counts"]["total"], len(payload["findings"]))

    def test_writes_markdown(self):
        good_repo(self.root)
        target = os.path.join(self.root, "out", "receipts.md")
        code, _, _ = self.run_cli("audit", self.root, "--out", target)
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(target))

    def test_missing_readme_exits_two(self):
        code, _, err = self.run_cli("audit", self.root)
        self.assertEqual(code, 2)
        self.assertIn("no README.md", err)


if __name__ == "__main__":
    unittest.main()
