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
                _, _, skills = fw.targets(args)
                for name in fw.read_json(ROOT / "manifest.json")["skills"]:
                    self.assertEqual((skills / name / "agents/openai.yaml").exists(), harness == "codex")
                core = next(iter(expected)).read_text(encoding="utf-8")
                self.assertIn(f"`{harness}`", core)
                reinstalled = fw.install(args)
                self.assertEqual(reinstalled["changed_files"], 0)
                self.assertIsNone(reinstalled["backup_directory"])
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
        result = fw.install(args)
        self.assertTrue(agents.read_bytes().startswith(original))
        self.assertEqual(agents.read_text(encoding="utf-8").count(fw.BLOCK_START), 1)
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
        # 用户完整移除框架后，重新安装只能追加，不能替换其新正文。
        fw.install(args)
        self.assertTrue(agents.read_bytes().startswith(b"new user edit"))

    def test_replace_modified_install_can_restore_user_edit(self):
        args = self.args()
        fw.install(args)
        _, agents, _ = fw.targets(args)
        agents.write_bytes(b"user customization")
        args.replace_conflicts = True
        replacement = fw.install(args)
        fw.rollback(replacement["receipt"])
        self.assertEqual(agents.read_bytes(), b"user customization")

    def test_zcode_default_loader_and_source_overlap_refused(self):
        args = self.args("zcode")
        args.agents_path = None
        _, agents, _ = fw.targets(args)
        self.assertEqual(agents, (self.base / "zcode" / "AGENTS.md").resolve())
        args.skills_dir = None
        _, _, skills = fw.targets(args)
        self.assertEqual(skills, (self.base / "zcode" / "skills").resolve())
        _, files = fw.desired(args)
        self.assertFalse(any(path.as_posix().endswith("agents/openai.yaml") for path in files))
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
        result = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/framework.py"), "inspect"],
                                cwd=self.base, text=True, capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        zcode = next(item for item in json.loads(result.stdout)["candidates"] if item["harness"] == "zcode")
        self.assertFalse(zcode["explicit_skills_path_required"])

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
        expected[agents] = expected[agents].replace(b"# Agent ", b"# Upgraded Agent ")
        with patch.object(fw, "desired", return_value=(root, expected)):
            _, _, rows = fw.plan(args)
            self.assertEqual(next(r for r in rows if r["target"] == str(agents))["action"], "update-framework-block")
            second = fw.install(args)
        fw.rollback(second["receipt"])
        self.assertEqual(agents.read_bytes(), original)
        fw.rollback(first["receipt"])
        self.assertFalse(agents.exists())

    def test_merge_preserves_encoding_bom_newlines_and_user_paths(self):
        text = "# User settings\r\nPython: C:\\tools\\Python312\\python.exe\r\n中文要求，不增加图表。"
        for encoding, bom in (("utf-8", b""), ("utf-8", b"\xef\xbb\xbf"),
                              ("utf-16-le", b"\xff\xfe"), ("utf-16-be", b"\xfe\xff")):
            with self.subTest(encoding=encoding, bom=bom):
                original = bom + text.encode(encoding)
                merged = fw.merge_agents(original, "# Framework\nRules")
                self.assertTrue(merged.startswith(original))
                self.assertEqual(fw.merge_agents(merged, "# Framework\nRules"), merged)
                prefix, _, _, span = fw.split_agents(merged)
                suffix = "\r\n# User additions\r\n"
                with_suffix = bom + (prefix + suffix).encode(encoding)
                upgraded = fw.merge_agents(with_suffix, "# New framework")
                self.assertTrue(upgraded.startswith(original))
                self.assertTrue(upgraded.endswith(suffix.encode(encoding)))
                self.assertEqual(upgraded.count(fw.BLOCK_START.encode(encoding)), 1)

    def test_external_user_edits_survive_managed_upgrade(self):
        args = self.args()
        fw.install(args)
        _, agents, _ = fw.targets(args)
        agents.write_bytes(b"Python: custom-python\n\n" + agents.read_bytes() + b"\nUser suffix\n")
        user_version = agents.read_bytes()
        # simulate new core release using the real merger rather than bypassing it
        original_read_text = Path.read_text
        def new_core(path, *a, **kw):
            value = original_read_text(path, *a, **kw)
            return value + "\nNew release rule\n" if path == ROOT / "AGENTS.md" else value
        with patch.object(Path, "read_text", new_core):
            _, _, rows = fw.plan(args)
            self.assertEqual(next(r for r in rows if r["target"] == str(agents))["action"], "update-framework-block")
            result = fw.install(args)
        self.assertTrue(agents.read_bytes().startswith(b"Python: custom-python\n\n"))
        self.assertTrue(agents.read_bytes().endswith(b"\nUser suffix\n"))
        fw.rollback(result["receipt"])
        self.assertEqual(agents.read_bytes(), user_version)

    def test_modified_framework_block_requires_authorization(self):
        args = self.args()
        fw.install(args)
        _, agents, _ = fw.targets(args)
        agents.write_bytes(b"keep user prefix\n\n" + agents.read_bytes().replace(b"# Agent ", b"# User-modified Agent "))
        before = agents.read_bytes()
        with self.assertRaisesRegex(ValueError, "conflicts"):
            fw.install(args)
        self.assertEqual(agents.read_bytes(), before)
        args.replace_conflicts = True
        fw.install(args)
        self.assertTrue(agents.read_bytes().startswith(b"keep user prefix\n\n"))

    def test_invalid_markers_and_unsupported_encoding_refused(self):
        for raw in (fw.BLOCK_START.encode(), fw.BLOCK_END.encode() + b"\n" + fw.BLOCK_START.encode(),
                    (fw.BLOCK_START + "\n" + fw.BLOCK_END + "\n") .encode() * 2,
                    ("User text " + fw.BLOCK_START + "\n" + fw.BLOCK_END).encode(), b"\x81\xff"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    fw.merge_agents(raw, "rules")

    def test_same_named_user_skill_conflict_blocks_all_writes(self):
        args = self.args()
        _, agents, skills = fw.targets(args)
        agents.parent.mkdir(parents=True)
        agents.write_bytes(b"Python: keep-path")
        skill = skills / "project-workflow" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_bytes(b"User-owned skill")
        with self.assertRaisesRegex(ValueError, "conflicts"):
            fw.install(args)
        self.assertEqual(agents.read_bytes(), b"Python: keep-path")
        self.assertEqual(skill.read_bytes(), b"User-owned skill")

    def test_concurrent_user_edit_during_plan_is_not_overwritten(self):
        args = self.args()
        _, agents, _ = fw.targets(args)
        agents.parent.mkdir(parents=True)
        agents.write_bytes(b"original settings")
        real_desired = fw.desired
        def edited_during_plan(args):
            result = real_desired(args)
            agents.write_bytes(b"concurrent new Python path")
            return result
        with patch.object(fw, "desired", side_effect=edited_during_plan):
            with self.assertRaisesRegex(ValueError, "changed during merge planning"):
                fw.install(args)
        self.assertEqual(agents.read_bytes(), b"concurrent new Python path")

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
            ["install", "--harness", "zcode", "--target-root", str(self.base / "isolated-zcode")],
        ]
        for command in commands:
            completed = subprocess.run([sys.executable, "-X", "utf8", str(script), *command],
                                       cwd=self.base, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            if "receipt" in report:
                recovery_target = ["--harness", command[2], "--target-root",
                                   command[command.index("--target-root") + 1]]
                for recovery_command in (["history", *recovery_target],
                                         ["uninstall", *recovery_target, "--dry-run"],
                                         ["uninstall", *recovery_target]):
                    recovery = subprocess.run([sys.executable, "-X", "utf8", str(script), *recovery_command],
                                              cwd=self.base, capture_output=True, text=True, encoding="utf-8")
                    self.assertEqual(recovery.returncode, 0, recovery.stderr)
                    recovery_report = json.loads(recovery.stdout)
                    if recovery_command[0] == "uninstall" and "--dry-run" not in recovery_command:
                        undo = subprocess.run([sys.executable, "-X", "utf8", str(script), "rollback",
                                               "--receipt", recovery_report["receipt"]], cwd=self.base,
                                              capture_output=True, text=True, encoding="utf-8")
                        self.assertEqual(undo.returncode, 0, undo.stderr)
                rollback = subprocess.run([sys.executable, "-X", "utf8", str(script), "rollback",
                                           "--receipt", report["receipt"]], cwd=self.base,
                                          capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(rollback.returncode, 0, rollback.stderr)


if __name__ == "__main__":
    unittest.main()
