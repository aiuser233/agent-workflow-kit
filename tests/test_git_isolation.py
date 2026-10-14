"""Verify the documented isolated-index mechanism, not autonomous skill behavior."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("git"), "Git required")
class IsolatedCommitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        self.git("init", "-q")
        self.git("config", "user.name", "Isolated Test")
        self.git("config", "user.email", "isolated@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.autocrlf", "false")
        self.file = self.repo / "mixed.txt"
        self.baseline = "".join(f"row {i:02d}\n" for i in range(30))
        self.file.write_text(self.baseline, encoding="utf-8", newline="\n")
        self.git("add", "mixed.txt")
        self.git("commit", "-qm", "baseline")
        self.head = self.git("rev-parse", "HEAD").stdout
        staged = self.baseline.replace("row 02", "user staged")
        self.file.write_text(staged, encoding="utf-8", newline="\n")
        self.git("add", "mixed.txt")
        self.working = staged.replace("row 15", "user unstaged").replace("row 28", "task change")
        self.file.write_text(self.working, encoding="utf-8", newline="\n")
        self.user_patch = self.git("diff", "--cached", "--binary").stdout
        self.original_index = (self.repo / ".git/index").read_bytes()

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args, index=None, data=None, check=True):
        env = self.env.copy()
        if index:
            env["GIT_INDEX_FILE"] = str(index)
        result = subprocess.run(["git", *args], cwd=self.repo, env=env,
                                input=data, capture_output=True)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        return result

    def task_index(self):
        index = self.repo / "task-index"
        self.git("read-tree", "HEAD", index=index)
        desired = self.baseline.replace("row 28", "task change").encode()
        blob = self.git("hash-object", "-w", "--stdin", data=desired).stdout.decode().strip()
        self.git("update-index", "--cacheinfo", f"100644,{blob},mixed.txt", index=index)
        return index, desired

    def test_mixed_file_preserves_user_staging_and_worktree(self):
        task_index, desired = self.task_index()
        tree = self.git("write-tree", index=task_index).stdout.decode().strip()
        reconciled = self.repo / "reconciled-index"
        self.git("read-tree", tree, index=reconciled)
        self.git("apply", "--cached", "-", index=reconciled, data=self.user_patch)
        self.git("commit", "-qm", "task only", index=task_index)
        self.assertEqual(self.git("show", "HEAD:mixed.txt").stdout, desired)
        self.assertEqual(self.git("diff", "HEAD^", "HEAD", "--name-only").stdout, b"mixed.txt\n")
        self.assertEqual((self.repo / ".git/index").read_bytes(), self.original_index)
        os.replace(reconciled, self.repo / ".git/index")
        self.assertEqual(self.git("show", ":mixed.txt").stdout,
                         desired.replace(b"row 02", b"user staged"))
        cached = self.git("diff", "--cached", "--unified=0").stdout
        self.assertIn(b"+user staged", cached)
        self.assertNotIn(b"task change", cached)
        self.assertNotIn(b"user unstaged", cached)
        unstaged = self.git("diff", "--unified=0").stdout
        self.assertIn(b"+user unstaged", unstaged)
        self.assertNotIn(b"task change", unstaged)
        self.assertNotIn(b"user staged", unstaged)
        self.assertEqual(self.file.read_text(encoding="utf-8"), self.working)

    def test_failed_hook_preserves_head_index_and_user_file(self):
        task_index, _ = self.task_index()
        hook = self.repo / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8", newline="\n")
        hook.chmod(0o755)
        result = self.git("commit", "-qm", "blocked task", index=task_index, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, self.head)
        self.assertEqual((self.repo / ".git/index").read_bytes(), self.original_index)
        self.assertEqual(self.git("diff", "--cached", "--binary").stdout, self.user_patch)
        self.assertEqual(self.file.read_text(encoding="utf-8"), self.working)


if __name__ == "__main__":
    unittest.main()
