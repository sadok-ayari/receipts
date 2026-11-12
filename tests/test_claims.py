import unittest

from receipts.claims import extract


README = """# example

Collects coverage and writes a brief. No dependencies, no model in the loop.

Python 3.9+. 38 tests, all offline. CI is green.

Licensed under the MIT licence. Shipped and used weekly.
"""


def kinds(text=README):
    return {claim.kind: claim for claim in extract(text)}


class ExtractTests(unittest.TestCase):
    def test_finds_test_count(self):
        self.assertEqual(kinds()["tests"].value, "38")

    def test_finds_licence(self):
        self.assertEqual(kinds()["licence"].value, "MIT")

    def test_finds_stdlib_claim(self):
        self.assertIn("stdlib", kinds())

    def test_finds_python_floor(self):
        self.assertEqual(kinds()["python"].value, "3.9")

    def test_finds_ci_claim(self):
        self.assertIn("ci", kinds())

    def test_finds_shipped_claim(self):
        self.assertIn("shipped", kinds())

    def test_ignores_quoted_blockquote(self):
        self.assertNotIn("tests", kinds("> 999 tests in the quoted demo output\n"))

    def test_ignores_headings_and_blank_lines(self):
        self.assertEqual(extract("# 4 things\n\n"), [])

    def test_dedupes_the_same_claim(self):
        claims = extract("38 tests here.\n38 tests there.\n")
        self.assertEqual(len([c for c in claims if c.kind == "tests"]), 1)

    def test_records_the_line_number(self):
        claims = extract("intro\n\n50 tests, offline\n")
        self.assertEqual(claims[0].line, 3)

    def test_skips_fenced_code_blocks(self):
        text = "Demo:\n\n```\n68 tests\n```\n\nReal: 12 tests.\n"
        claims = [c for c in extract(text) if c.kind == "tests"]
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].value, "12")

    def test_skips_inline_code_and_quoted_claims(self):
        text = "It checks claims like `68 tests` and the \u201cshipped\u201d label. We have 12 tests.\n"
        claims = [c for c in extract(text) if c.kind == "tests"]
        self.assertEqual([c.value for c in claims], ["12"])

    def test_still_reads_a_real_assertion_after_code(self):
        text = "```bash\nmake test\n```\n\n24 tests, all offline. No dependencies.\n"
        kinds = {c.kind for c in extract(text)}
        self.assertEqual(kinds, {"tests", "stdlib"})


if __name__ == "__main__":
    unittest.main()
