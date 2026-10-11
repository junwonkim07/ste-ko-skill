"""스킬 파일과 검사기를 확인한다. `python3 -m unittest discover -s tests` 로 돌린다."""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "ste-ko-lint.py"


def run_lint(*args, stdin=None):
    return subprocess.run([sys.executable, "-I", str(LINT), *args],
                          input=stdin, capture_output=True, text=True)


class SkillFileTest(unittest.TestCase):
    def test_frontmatter(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        self.assertIsNotNone(m, "SKILL.md frontmatter 가 없다")
        front = m.group(1)
        self.assertRegex(front, r"(?m)^name: ste-ko$")
        desc = re.search(r'(?m)^description: "(.*)"$', front)
        self.assertIsNotNone(desc, "description 이 없다")
        self.assertLessEqual(len(desc.group(1)), 1024, "description 이 1024자를 넘는다")

    def test_referenced_files_exist(self):
        for rel in ("references/judgment.md", "references/chat-preferences.md", "references/upstream/SPEC.md",
                    "references/upstream/dictionary.md", "references/upstream/LICENSE",
                    "LICENSE", "NOTICE.md"):
            self.assertTrue((ROOT / rel).is_file(), f"{rel} 가 없다")

    def test_own_docs_have_no_hard_violations(self):
        for rel in ("SKILL.md", "README.md", "references/judgment.md", "references/chat-preferences.md", "NOTICE.md"):
            r = run_lint(str(ROOT / rel))
            self.assertEqual(r.returncode, 0, f"{rel}:\n{r.stdout}")


class LintTest(unittest.TestCase):
    def test_self_test(self):
        r = run_lint("--self-test")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("self-test OK", r.stdout)

    def test_stdin_and_exit_code(self):
        r = run_lint("-", stdin="결과가 보여집니다.\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("3.2", r.stdout)
        r = run_lint("-", stdin="결과가 보입니다.\n")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_info_hidden_by_default(self):
        text = "이슈가 있습니다.\n"
        self.assertNotIn("이슈", run_lint("-", stdin=text).stdout)
        self.assertIn("이슈", run_lint("-", "--all", stdin=text).stdout)

    def test_strict(self):
        text = "이 문제에 대해 설명한다.\n"
        self.assertEqual(run_lint("-", stdin=text).returncode, 0)
        self.assertEqual(run_lint("-", "--strict", stdin=text).returncode, 1)

    def test_json(self):
        import json
        r = run_lint("-", "--json", stdin="항목은 3~5개다.\n")
        rows = json.loads(r.stdout)
        self.assertEqual(rows[0]["rule"], "8.1")
        self.assertEqual(rows[0]["level"], "hard")

    def test_code_is_skipped(self):
        text = "```\n결과가 보여집니다.\n```\n`3~5` 는 코드다.\n"
        self.assertEqual(run_lint("-", stdin=text).returncode, 0)


if __name__ == "__main__":
    unittest.main()
