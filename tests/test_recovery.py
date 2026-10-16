"""Recovery checks operate only on temporary user homes, never live settings."""
from argparse import Namespace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_framework import fw, ROOT


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.args = Namespace(harness="codex", target_root=str(self.base / "host"),
                              agents_path=None, skills_dir=None, backup_dir=None,
                              replace_conflicts=False, dry_run=False, remove_modified_block=False)
        self.root, self.agents, self.skills = fw.targets(self.args)
        self.agents.parent.mkdir(parents=True)
        self.original = b"Python: custom-python\r\nPersonal rules\r\n"
        self.agents.write_bytes(self.original)

    def tearDown(self):
        self.tmp.cleanup()

    def test_corrupt_backup_stops_before_any_target_write(self):
        real = fw.atomic_write
        def corrupt(path, data):
            real(path, b"bad backup" if path.suffix == ".bin" else data)
        with patch.object(fw, "atomic_write", side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, "integrity"):
                fw.install(self.args)
        self.assertEqual(self.agents.read_bytes(), self.original)
        self.assertFalse(self.skills.exists())

    def test_backup_write_failure_leaves_targets_untouched(self):
        real = fw.atomic_write
        def fail(path, data):
            if path.suffix == ".bin":
                raise OSError("backup disk full")
            real(path, data)
        with patch.object(fw, "atomic_write", side_effect=fail):
            with self.assertRaisesRegex(OSError, "disk full"):
                fw.install(self.args)
        self.assertEqual(self.agents.read_bytes(), self.original)
        self.assertFalse(self.skills.exists())

    def test_custom_backup_is_discovered_and_survives_uninstall(self):
        self.args.backup_dir = str(self.base / "independent backups")
        result = fw.install(self.args)
        self.assertTrue(Path(result["receipt"]).resolve().is_relative_to(Path(self.args.backup_dir).resolve()))
        self.args.backup_dir = None
        records = fw.history(self.args)["records"]
        self.assertEqual(records[0]["receipt"], result["receipt"])
        self.assertEqual(fw.install(self.args)["changed_files"], 0)
        fw.uninstall(self.args)
        self.assertEqual(self.agents.read_bytes(), self.original)
        self.assertTrue(Path(result["receipt"]).exists())

    def test_backup_only_and_explicit_restore_without_git(self):
        env = os.environ.copy()
        env["PATH"] = ""
        command = [sys.executable, "-X", "utf8", str(ROOT / "scripts/framework.py"), "backup",
                   "--harness", "codex", "--target-root", str(self.root)]
        completed = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["target_files_changed"], 0)
        self.assertEqual(self.agents.read_bytes(), self.original)
        self.assertFalse(self.skills.exists())
        self.agents.write_bytes(b"new setting")
        with self.assertRaisesRegex(ValueError, "Modified after"):
            fw.rollback(result["receipt"])
        restored = fw.rollback(result["receipt"], restore_modified=True)
        self.assertEqual(self.agents.read_bytes(), self.original)
        fw.rollback(restored["safety_receipt"])
        self.assertEqual(self.agents.read_bytes(), b"new setting")

    def test_zcode_install_and_uninstall_cli_do_not_require_git(self):
        env = os.environ.copy()
        env["PATH"] = ""
        root = self.base / "zcode"
        agents = self.base / "user rules/AGENTS.md"
        skills = self.base / "user skills"
        agents.parent.mkdir()
        agents.write_bytes(self.original)
        script = [sys.executable, "-X", "utf8", str(ROOT / "scripts/framework.py")]
        commands = [
            ["install", "--harness", "zcode", "--target-root", str(root),
             "--agents-path", str(agents), "--skills-dir", str(skills)],
            ["history", "--harness", "zcode", "--target-root", str(root)],
            ["uninstall", "--harness", "zcode", "--target-root", str(root)],
        ]
        for command in commands:
            result = subprocess.run(script + command, env=env, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
        self.assertEqual(report["status"], "uninstalled")
        self.assertEqual(agents.read_bytes(), self.original)
        self.assertFalse(skills.exists())

    def test_zcode_default_install_without_preexisting_files_can_uninstall(self):
        args = Namespace(harness="zcode", target_root=str(self.base / "zcode-default"),
                         agents_path=None, skills_dir=None, backup_dir=None,
                         replace_conflicts=False, dry_run=False, remove_modified_block=False)
        root, agents, skills = fw.targets(args)
        self.assertEqual(skills, (root / "skills").resolve())
        result = fw.install(args)
        self.assertFalse((skills / "clarify-requirements" / "agents" / "openai.yaml").exists())
        self.assertIsNone(result["backup_directory"])
        self.assertEqual(fw.uninstall(args)["status"], "uninstalled")

    def test_empty_backup_records_absent_paths_without_fake_directory(self):
        self.args.target_root = str(self.base / "empty-user-home")
        result = fw.backup(self.args)
        self.assertIsNone(result["backup_directory"])
        self.assertEqual(result["existing_files_backed_up"], 0)
        self.assertGreater(result["absent_paths_recorded"], 0)
        self.assertFalse((Path(result["receipt"]).parent / "backups").exists())

    def test_zcode_upgrade_keeps_old_metadata_until_receipt_based_uninstall(self):
        self.args.harness = "zcode"
        root, incoming = fw.desired(self.args)
        _, _, skills = fw.targets(self.args)
        metadata = skills / "clarify-requirements/agents/openai.yaml"
        incoming[metadata] = b"old Codex UI metadata"
        with patch.object(fw, "desired", return_value=(root, incoming)):
            fw.install(self.args)
        fw.install(self.args)
        self.assertEqual(metadata.read_bytes(), b"old Codex UI metadata")
        self.assertEqual(fw.uninstall(self.args)["status"], "uninstalled")
        self.assertFalse(metadata.exists())

    def test_uninstall_preserves_outside_user_bytes_and_modified_skill(self):
        for encoding, bom in (("utf-8", b""), ("utf-8", b"\xef\xbb\xbf"),
                              ("utf-16-le", b"\xff\xfe"), ("utf-16-be", b"\xfe\xff")):
            with self.subTest(encoding=encoding, bom=bom):
                self.args.target_root = str(self.base / encoding / str(len(bom)))
                _, agents, skills = fw.targets(self.args)
                agents.parent.mkdir(parents=True)
                agents.write_bytes(bom + "original\r\n".encode(encoding))
                fw.install(self.args)
                text, _, _, span = fw.split_agents(agents.read_bytes())
                text = "new prefix\r\n" + text + "new suffix\r\n"
                agents.write_bytes(bom + text.encode(encoding))
                _, _, _, span = fw.split_agents(agents.read_bytes())
                expected = bom + (text[:span[0]] + text[span[1]:]).encode(encoding)
                skill = skills / "project-workflow/SKILL.md"
                skill.write_bytes(b"user edited skill")
                unrelated = skills / "my-own/notes.txt"
                unrelated.parent.mkdir()
                unrelated.write_bytes(b"keep")
                self.args.dry_run = True
                preview = fw.uninstall(self.args)
                self.assertTrue(preview["dry_run"])
                self.assertIn(fw.BLOCK_START.encode(encoding), agents.read_bytes())
                self.args.dry_run = False
                result = fw.uninstall(self.args)
                self.assertEqual(result["status"], "partially-uninstalled")
                self.assertEqual(agents.read_bytes(), expected)
                self.assertEqual(skill.read_bytes(), b"user edited skill")
                self.assertEqual(unrelated.read_bytes(), b"keep")
                self.assertEqual(len(result["preserved_modified_files"]), 1)
                self.assertEqual(fw.uninstall(self.args)["changed_files"], 0)

    def test_modified_block_requires_explicit_removal_and_is_backed_up(self):
        fw.install(self.args)
        self.agents.write_bytes(self.agents.read_bytes().replace(b"# Agent ", b"# User edited Agent "))
        edited = self.agents.read_bytes()
        result = fw.uninstall(self.args)
        self.assertEqual(result["status"], "partially-uninstalled")
        self.assertEqual(self.agents.read_bytes(), edited)
        self.args.remove_modified_block = True
        result = fw.uninstall(self.args)
        self.assertEqual(self.agents.read_bytes(), self.original)
        fw.rollback(result["receipt"])
        self.assertEqual(self.agents.read_bytes(), edited)

    def test_uninstall_after_upgrade_restores_prior_same_named_skill(self):
        prior = self.skills / "project-workflow/SKILL.md"
        prior.parent.mkdir(parents=True)
        prior.write_bytes(b"preexisting user skill")
        self.args.replace_conflicts = True
        fw.install(self.args)
        root, incoming = fw.desired(self.args)
        incoming[self.agents] = incoming[self.agents].replace(b"# Agent ", b"# Upgraded Agent ")
        incoming[prior] += b"\nupgrade\n"
        with patch.object(fw, "desired", return_value=(root, incoming)):
            fw.install(self.args)
        result = fw.uninstall(self.args)
        self.assertEqual(result["status"], "uninstalled")
        self.assertEqual(prior.read_bytes(), b"preexisting user skill")
        self.assertEqual(self.agents.read_bytes(), self.original)
        # Reinstall is a new lifecycle; undo-uninstall restores ownership too.
        fw.rollback(result["receipt"])
        self.assertEqual(prior.read_bytes(), incoming[prior])
        self.assertEqual(fw.install(self.args)["changed_files"], 2)

    def test_uninstall_interruption_can_restore_configuration_and_receipts(self):
        installed = fw.install(self.args)
        installed_bytes = self.agents.read_bytes()
        receipt_bytes = Path(installed["receipt"]).read_bytes()
        real = fw.atomic_write
        def fail(path, data):
            if path == Path(installed["receipt"]):
                raise OSError("uninstall interrupted")
            return real(path, data)
        with patch.object(fw, "atomic_write", side_effect=fail):
            with self.assertRaisesRegex(OSError, "interrupted"):
                fw.uninstall(self.args)
        journal = next(r for r in fw.history(self.args)["records"] if r["kind"] == "uninstall")
        self.assertEqual(journal["status"], "incomplete")
        with self.assertRaisesRegex(ValueError, "rollback first"):
            fw.uninstall(self.args)
        with self.assertRaisesRegex(ValueError, "rollback first"):
            fw.install(self.args)
        fw.rollback(journal["receipt"])
        self.assertEqual(self.agents.read_bytes(), installed_bytes)
        self.assertEqual(Path(installed["receipt"]).read_bytes(), receipt_bytes)

    def test_uninstall_backup_corruption_changes_no_targets(self):
        fw.install(self.args)
        installed = self.agents.read_bytes()
        skill = self.skills / "project-workflow/SKILL.md"
        expected_skill = skill.read_bytes()
        real = fw.atomic_write
        def corrupt(path, data):
            return real(path, b"corrupted" if path.suffix == ".bin" else data)
        with patch.object(fw, "atomic_write", side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, "integrity"):
                fw.uninstall(self.args)
        self.assertEqual(self.agents.read_bytes(), installed)
        self.assertEqual(skill.read_bytes(), expected_skill)

    def test_reinstall_after_uninstall_uses_a_new_baseline(self):
        fw.install(self.args)
        fw.uninstall(self.args)
        new_baseline = b"brand new settings\n"
        self.agents.write_bytes(new_baseline)
        fw.install(self.args)
        fw.uninstall(self.args)
        self.assertEqual(self.agents.read_bytes(), new_baseline)

    def test_preexisting_framework_block_is_restored_with_new_outside_settings(self):
        previous = fw.merge_agents(self.original, "previous independently managed framework")
        self.agents.write_bytes(previous)
        self.args.replace_conflicts = True
        fw.install(self.args)
        self.agents.write_bytes(self.agents.read_bytes() + b"new outside setting\r\n")
        fw.uninstall(self.args)
        self.assertEqual(self.agents.read_bytes(), previous + b"new outside setting\r\n")

    def test_forced_rollback_saves_new_user_changes(self):
        result = fw.install(self.args)
        self.agents.write_bytes(self.agents.read_bytes() + b"new personal setting\n")
        edited = self.agents.read_bytes()
        preview = fw.rollback(result["receipt"], restore_modified=True, dry_run=True)
        self.assertTrue(preview["dry_run"])
        self.assertEqual(self.agents.read_bytes(), edited)
        restored = fw.rollback(result["receipt"], restore_modified=True)
        self.assertEqual(self.agents.read_bytes(), self.original)
        fw.rollback(restored["safety_receipt"])
        self.assertEqual(self.agents.read_bytes(), edited)
        self.assertEqual(fw.read_json(Path(result["receipt"]))["status"], "installed")

    def test_backup_in_skill_directory_is_refused(self):
        self.args.backup_dir = str(self.skills / "backups")
        with self.assertRaisesRegex(ValueError, "outside the skills"):
            fw.install(self.args)
        self.assertEqual(self.agents.read_bytes(), self.original)

    def test_latest_cli_and_legacy_receipt_uninstall(self):
        result = fw.install(self.args)
        path = Path(result["receipt"])
        receipt = fw.read_json(path)
        for field in ("kind", "target_root", "created_at", "agents_path", "skills_dir"):
            receipt.pop(field)
        fw.write_json(path, receipt)
        lookup = Namespace(harness="codex", target_root=str(self.root), backup_dir=None, receipt=None)
        self.assertEqual(fw.select_receipt(lookup), path)
        completed = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/framework.py"),
                                    "rollback", "--latest", "--harness", "codex", "--target-root",
                                    str(self.root), "--dry-run"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["dry_run"])
        self.assertEqual(fw.uninstall(self.args)["status"], "uninstalled")
        self.assertEqual(self.agents.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
