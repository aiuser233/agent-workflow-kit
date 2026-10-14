"""Verify deployment side effects in isolated temporary user homes."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("framework", ROOT / "scripts/framework.py")
fw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fw)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def args(self, harness="codex", replace=False):
        root = self.base / harness
        return Namespace(harness=harness, target_root=str(root),
                         agents_path=str(self.base / "custom" / "rules.md") if harness == "zcode" else None,
                         skills_dir=str(self.base / "custom" / "business-skills") if harness == "zcode" else None,
                         replace_conflicts=replace)

    def test_both_harnesses_install_idempotency_and_rollback(self):
        for harness in ("codex", "zcode"):
            with self.subTest(harness=harness):
                args = self.args(harness)
                _, expected = fw.desired(args)
                result = fw.install(args)
                for path, data in expected.items():
                    self.assertEqual(path.read_bytes(), data)
                core = next(iter(expected)).read_text(encoding="utf-8")
                self.assertIn(f"`{harness}`", core)
                self.assertEqual(fw.install(args)["changed_files"], 0)
                self.assertEqual(fw.rollback(result["receipt"])["restored_files"], len(expected))
                self.assertTrue(all(not p.exists() for p in expected))

    def test_original_backup_conflict_and_unrelated_preservation(self):
        args = self.args()
        root, agents, skills = fw.targets(args)
        agents.parent.mkdir(parents=True)
        original = b"original user rules\r\n"
        agents.write_bytes(original)
        unrelated = skills / "other-skill" / "SKILL.md"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_bytes(b"keep")
        with self.assertRaisesRegex(ValueError, "conflicts"):
            fw.install(args)
        self.assertEqual(agents.read_bytes(), original)
        args.replace_conflicts = True
        result = fw.install(args)
        receipt = fw.read_json(Path(result["receipt"]))
        item = next(x for x in receipt["files"] if x["target"] == str(agents))
        self.assertEqual((Path(result["receipt"]).parent / item["backup"]).read_bytes(), original)
        fw.rollback(result["receipt"])
        self.assertEqual(agents.read_bytes(), original)
        self.assertEqual(unrelated.read_bytes(), b"keep")

    def test_user_edit_blocks_rollback_and_reinstall(self):
        args = self.args()
        result = fw.install(args)
        _, agents, _ = fw.targets(args)
        agents.write_bytes(b"new user edit")
        with self.assertRaisesRegex(ValueError, "Modified after install"):
            fw.rollback(result["receipt"])
        self.assertEqual(agents.read_bytes(), b"new user edit")
        with self.assertRaisesRegex(ValueError, "conflicts"):
            fw.install(args)

    def test_replace_modified_install_can_restore_user_edit(self):
        args = self.args()
        fw.install(args)
        _, agents, _ = fw.targets(args)
        agents.write_bytes(b"user customization")
        args.replace_conflicts = True
        replacement = fw.install(args)
        fw.rollback(replacement["receipt"])
        self.assertEqual(agents.read_bytes(), b"user customization")

    def test_missing_zcode_loader_and_source_overlap_refused(self):
        args = self.args("zcode")
        args.agents_path = None
        with self.assertRaisesRegex(ValueError, "explicit --agents-path"):
            fw.plan(args)
        args = self.args()
        args.target_root = str(ROOT)
        with self.assertRaisesRegex(ValueError, "overlaps source"):
            fw.plan(args)

    def test_file_destination_type_and_backup_integrity(self):
        args = self.args(replace=True)
        _, agents, _ = fw.targets(args)
        agents.parent.mkdir(parents=True)
        agents.write_bytes(b"old")
        result = fw.install(args)
        receipt_path = Path(result["receipt"])
        receipt = fw.read_json(receipt_path)
        item = next(x for x in receipt["files"] if x["backup"])
        (receipt_path.parent / item["backup"]).write_bytes(b"corrupted")
        before = agents.read_bytes()
        with self.assertRaisesRegex(ValueError, "integrity"):
            fw.rollback(receipt_path)
        self.assertEqual(agents.read_bytes(), before)

    def test_validate_and_cli_runs_from_other_cwd(self):
        self.assertEqual(fw.validate()["skills"], 8)
        result = subprocess.run([sys.executable, str(ROOT / "scripts/framework.py"), "validate"],
                                cwd=self.base, text=True, capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["links_valid"])

    def test_link_destination_refused_when_available(self):
        outside = self.base / "outside"
        outside.mkdir()
        link = self.base / "linked"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Host does not permit test symlinks")
        args = self.args()
        args.target_root = str(link)
        with self.assertRaisesRegex(ValueError, "linked path"):
            fw.plan(args)

    def test_managed_upgrade_and_reverse_rollback(self):
        args = self.args()
        first = fw.install(args)
        root, expected = fw.desired(args)
        _, agents, _ = fw.targets(args)
        original = expected[agents]
        expected[agents] += b"\nupgraded rules\n"
        with patch.object(fw, "desired", return_value=(root, expected)):
            _, _, rows = fw.plan(args)
            self.assertEqual(next(r for r in rows if r["target"] == str(agents))["action"], "update-managed")
            second = fw.install(args)
        fw.rollback(second["receipt"])
        self.assertEqual(agents.read_bytes(), original)
        fw.rollback(first["receipt"])
        self.assertFalse(agents.exists())

    def test_partial_write_has_recoverable_receipt(self):
        args = self.args()
        real_write = fw.atomic_write
        count = 0

        def fail_on_second_file(path, data):
            nonlocal count
            if path.name != "receipt.json":
                count += 1
                if count == 2:
                    raise OSError("simulated interrupted write")
            return real_write(path, data)

        with patch.object(fw, "atomic_write", side_effect=fail_on_second_file):
            with self.assertRaisesRegex(OSError, "interrupted"):
                fw.install(args)
        root, expected = fw.desired(args)
        receipt_path = next((root / ".framework-install").glob("*/receipt.json"))
        self.assertEqual(fw.read_json(receipt_path)["status"], "incomplete")
        fw.rollback(receipt_path)
        self.assertTrue(all(not p.exists() for p in expected))

    def test_standalone_bundle_from_unicode_path(self):
        result = fw.bundle()
        unpacked = self.base / "迁移 测试"
        with zipfile.ZipFile(result["bundle"]) as archive:
            self.assertTrue(all(not Path(name).is_absolute() and ".." not in Path(name).parts
                                for name in archive.namelist()))
            archive.extractall(unpacked)
        script = unpacked / "agent-workflow-kit" / "scripts" / "framework.py"
        commands = [
            ["validate"],
            ["install", "--harness", "codex", "--target-root", str(self.base / "isolated-codex")],
            ["install", "--harness", "zcode", "--target-root", str(self.base / "isolated-zcode"),
             "--agents-path", str(self.base / "规则" / "AGENTS.md"),
             "--skills-dir", str(self.base / "技能")],
        ]
        for command in commands:
            completed = subprocess.run([sys.executable, "-X", "utf8", str(script), *command],
                                       cwd=self.base, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            if "receipt" in report:
                rollback = subprocess.run([sys.executable, "-X", "utf8", str(script), "rollback",
                                           "--receipt", report["receipt"]], cwd=self.base,
                                          capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(rollback.returncode, 0, rollback.stderr)


if __name__ == "__main__":
    unittest.main()
