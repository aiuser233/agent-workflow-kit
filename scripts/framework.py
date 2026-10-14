"""Framework packaging/deployment CLI. Python 3.10+, standard library only."""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCK_START = "<!-- agent-workflow-kit:begin -->"
BLOCK_END = "<!-- agent-workflow-kit:end -->"


def split_agents(raw):
    """Decode without normalizing BOM/newlines; outside block round-trips exactly."""
    if raw.startswith(b"\xff\xfe"):
        encoding, bom = "utf-16-le", b"\xff\xfe"
    elif raw.startswith(b"\xfe\xff"):
        encoding, bom = "utf-16-be", b"\xfe\xff"
    else:
        encoding = "utf-8"
        bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    try:
        text = raw[len(bom):].decode(encoding)
    except UnicodeError as exc:
        raise ValueError("AGENTS encoding must be UTF-8 or BOM-marked UTF-16; preserve original and convert explicitly") from exc
    starts, ends = text.count(BLOCK_START), text.count(BLOCK_END)
    if starts != ends or starts > 1:
        raise ValueError("Malformed/duplicate framework markers; manual review required")
    span = None
    if starts:
        start = text.index(BLOCK_START)
        end = text.index(BLOCK_END)
        if end < start:
            raise ValueError("Reversed framework markers; manual review required")
        span = (start, end + len(BLOCK_END))
        # 标记应独占一行，避免替换混入的用户正文。
        for marker in (BLOCK_START, BLOCK_END):
            if not re.search(r"(?m)^" + re.escape(marker) + r"\r?$", text):
                raise ValueError("Framework markers must occupy complete lines")
    return text, encoding, bom, span


def block_hash(raw):
    text, encoding, _, span = split_agents(raw)
    return digest(text[span[0]:span[1]].encode(encoding)) if span else None


def merge_agents(existing, core):
    text, encoding, bom, span = split_agents(existing)
    newline = "\r\n" if "\r\n" in text else "\n"
    body = "本区块是框架默认规则；区块外已有用户要求保留并优先适用。发生实质冲突时说明，不自行删除或改写用户要求。\n\n" + core
    block = BLOCK_START + newline + body.strip().replace("\n", newline) + newline + BLOCK_END
    if span:
        merged = text[:span[0]] + block + text[span[1]:]
    else:
        separator = "" if not text else (newline if text.endswith("\n") else newline * 2)
        merged = text + separator + block + newline
    return bom + merged.encode(encoding)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def absolute(value):
    # 拒绝路径中实际存在的链接，避免 resolve 后丢失链接身份。
    path = Path(value).expanduser().absolute()
    for component in (path, *path.parents):
        if component.is_symlink() or (hasattr(component, "is_junction") and component.is_junction()):
            raise ValueError(f"Refusing linked path: {component}")
    return path.resolve()


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".awk-", delete=False) as tmp:
        tmp.write(data)
        temp_path = Path(tmp.name)
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def write_json(path, value):
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def targets(args):
    adapter = read_json(ROOT / "adapters" / args.harness / "adapter.json")
    configured = os.environ.get(adapter["root_environment"]) if adapter["root_environment"] else None
    root = absolute(args.target_root or configured or Path.home() / adapter["home_directory"])
    result = []
    for flag, key in (("agents_path", "agents_relative_path"), ("skills_dir", "skills_relative_path")):
        supplied = getattr(args, flag)
        default = adapter[key]
        if not supplied and not default:
            raise ValueError(f"{args.harness} requires explicit --{flag.replace('_', '-')} (loader path unverified)")
        result.append(absolute(supplied or root / default))
    agents, skills = result
    if skills == agents or skills in agents.parents:
        raise ValueError("AGENTS path must not be inside the skills directory")
    for path in (root, agents, skills):
        if path == ROOT or ROOT in path.parents:
            raise ValueError(f"Install destination overlaps source package: {path}")
    if agents.exists() and not agents.is_file():
        raise ValueError("AGENTS destination must be a file")
    if skills.exists() and not skills.is_dir():
        raise ValueError("Skills destination must be a directory")
    return root, agents, skills


def desired(args):
    root, agents, skills = targets(args)
    manifest = read_json(ROOT / "manifest.json")
    try:
        relative = os.path.relpath(skills, agents.parent).replace(os.sep, "/")
    except ValueError:
        relative = skills.as_posix()
    core = (ROOT / manifest["core"]).read_text(encoding="utf-8").rstrip()
    core += f"\n\n## 本机部署映射\n\n当前 harness：`{args.harness}`。技能目录相对于本文件：`{relative}`。若未发现技能，从此目录读取对应 `SKILL.md`。残留清理仅使用对应 harness 的参考规则。\n"
    if agents.exists() and not agents.is_file():
        raise ValueError("AGENTS destination must be a regular file")
    files = {agents: merge_agents(agents.read_bytes() if agents.exists() else b"", core)}
    for name in manifest["skills"]:
        for source in sorted((ROOT / "skills" / name).rglob("*")):
            if source.is_file():
                target = absolute(skills / name / source.relative_to(ROOT / "skills" / name))
                if ROOT == target or ROOT in target.parents:
                    raise ValueError("Skill target overlaps source")
                files[target] = source.read_bytes()
    # 安装环境元数据仅生成到目标，源码保留跨 harness 性质。
    files[skills / "cleanup-local-residue" / "harness.json"] = (
        json.dumps({"harness": args.harness}, indent=2) + "\n").encode("utf-8")
    return root, files


def owned_hashes(root):
    owned = {}
    receipts = sorted((root / ".framework-install").glob("*/receipt.json"))
    for path in receipts:
        receipt = read_json(path)
        if receipt.get("status") != "installed":
            continue
        for item in receipt["files"]:
            owned[item["target"]] = item
    return owned


def plan(args):
    _, agents, _ = targets(args)
    agents_snapshot = agents.read_bytes() if agents.exists() else None
    root, files = desired(args)
    owned = owned_hashes(root)
    rows = []
    for path, incoming in files.items():
        if path.exists() and not path.is_file():
            raise ValueError(f"File destination is not a regular file: {path}")
        before = path.read_bytes() if path.exists() else None
        if path == agents and before != agents_snapshot:
            raise ValueError("AGENTS changed during merge planning; retry after concurrent writer stops")
        current_hash = digest(before) if before is not None else None
        if before == incoming:
            action = "unchanged"
        elif before is None:
            action = "create"
        elif path == agents and block_hash(before) is None:
            action = "append-framework"
        elif path == agents and owned.get(str(path), {}).get("installed_block_sha256") == block_hash(before):
            action = "update-framework-block"
        elif owned.get(str(path), {}).get("installed_sha256") == current_hash:
            action = "update-managed"
        else:
            action = "conflict"
        row = {"target": str(path), "action": action, "before_sha256": current_hash,
               "installed_sha256": digest(incoming)}
        if path == agents:
            row["installed_block_sha256"] = block_hash(incoming)
        rows.append(row)
    return root, files, rows


def install(args):
    root, incoming, rows = plan(args)
    conflicts = [row for row in rows if row["action"] == "conflict"]
    if conflicts and not args.replace_conflicts:
        raise ValueError("Existing content conflicts; inspect plan and authorize --replace-conflicts")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    state = root / ".framework-install" / stamp
    state.mkdir(parents=True, exist_ok=False)
    receipt_path = state / "receipt.json"
    receipt = {"schema_version": 1, "kit_version": read_json(ROOT / "manifest.json")["version"],
               "harness": args.harness, "status": "preparing", "files": [], "created_directories": []}
    # 在任何写入前保存全部前版本；收据不含文件正文。
    for i, row in enumerate(rows):
        if row["action"] == "unchanged":
            continue
        path = absolute(row["target"])
        before = path.read_bytes() if path.exists() else None
        if (digest(before) if before is not None else None) != row["before_sha256"]:
            raise ValueError(f"Concurrent change before backup: {path}")
        item = dict(row, applied=False, backup=None)
        if before is not None:
            item["backup"] = f"backups/{i:04d}.bin"
            atomic_write(state / item["backup"], before)
        receipt["files"].append(item)
    write_json(receipt_path, receipt)
    try:
        for item in receipt["files"]:
            path = absolute(item["target"])
            before = path.read_bytes() if path.exists() else None
            if (digest(before) if before is not None else None) != item["before_sha256"]:
                raise ValueError(f"Concurrent change before write: {path}")
            missing = []
            parent = path.parent
            while not parent.exists():
                missing.append(str(parent))
                parent = parent.parent
            receipt["created_directories"].extend(x for x in reversed(missing) if x not in receipt["created_directories"])
            # 记录预期写入，进程异常时可以依据 hash 定向恢复。
            item["applied"] = True
            write_json(receipt_path, receipt)
            atomic_write(path, incoming[path])
            if digest(path.read_bytes()) != item["installed_sha256"]:
                raise ValueError(f"Post-write verification failed: {path}")
        receipt["status"] = "installed"
        write_json(receipt_path, receipt)
    except Exception:
        receipt["status"] = "incomplete"
        write_json(receipt_path, receipt)
        print(f"Incomplete install receipt: {receipt_path}", file=sys.stderr)
        raise
    return {"receipt": str(receipt_path), "backup_directory": str(state / "backups"),
            "changed_files": len(receipt["files"]), "unchanged_files": len(rows) - len(receipt["files"])}


def rollback(receipt_value):
    receipt_path = absolute(receipt_value)
    receipt = read_json(receipt_path)
    if receipt.get("schema_version") != 1 or receipt.get("status") not in ("installed", "incomplete", "preparing"):
        raise ValueError("Receipt is not an active installation")
    actions = []
    # 全部核对后再恢复；目标后续改动、损坏备份和路径链接都会阻止回滚。
    for item in receipt["files"]:
        if not item["applied"]:
            continue
        path = absolute(item["target"])
        now = path.read_bytes() if path.is_file() else None
        current = digest(now) if now is not None else None
        if current == item["before_sha256"]:
            continue
        if current != item["installed_sha256"]:
            raise ValueError(f"Modified after install; refusing rollback: {path}")
        old = None
        if item["backup"]:
            backup = absolute(receipt_path.parent / item["backup"])
            if receipt_path.parent not in backup.parents:
                raise ValueError("Backup escapes receipt directory")
            old = backup.read_bytes()
            if digest(old) != item["before_sha256"]:
                raise ValueError("Backup integrity failed")
        actions.append((path, old, current))
    for path, old, expected in reversed(actions):
        if digest(path.read_bytes()) != expected:
            raise ValueError(f"Concurrent change during rollback: {path}")
        if old is None:
            path.unlink()
        else:
            atomic_write(path, old)
    # 仅移除本次创建且为空的目录，不递归删除。
    for directory in reversed(receipt.get("created_directories", [])):
        path = absolute(directory)
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    receipt["status"] = "rolled-back"
    write_json(receipt_path, receipt)
    return {"receipt": str(receipt_path), "restored_files": len(actions), "backups_retained": True}


def validate():
    manifest = read_json(ROOT / "manifest.json")
    errors = []
    paths = [ROOT / "SKILL.md"] + [ROOT / "skills" / name / "SKILL.md" for name in manifest["skills"]]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        match = re.match(r'^---\nname: ([a-z0-9-]{1,64})\ndescription: (.+)\n---\n', text)
        if not match or not match[2].strip() or "[TODO:" in text:
            errors.append(f"Invalid skill frontmatter/placeholder: {path}")
        elif path.parent != ROOT and match[1] != path.parent.name:
            errors.append(f"Skill name/directory mismatch: {path}")
    for source in manifest["sources"]:
        path = ROOT / source["path"]
        # 原件不在独立安装包内，安装包声明保留 provenance 但不强求附带原件。
        if path.exists() and digest(path.read_bytes()) != source["sha256"]:
            errors.append(f"Original source changed: {path.name}")
    for path in ROOT.rglob("*.md"):
        if any(part in (".git", "output") for part in path.relative_to(ROOT).parts):
            continue
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            if target.startswith(("http:", "https:", "#")):
                continue
            if not (path.parent / target.split("#")[0]).exists():
                errors.append(f"Broken link: {path.relative_to(ROOT)} -> {target}")
        if path.name == "SKILL.md" or "references" in path.parts:
            if re.search(r"第 [1-9] 节", text):
                errors.append(f"Stale source section reference: {path}")
    for harness in manifest["harnesses"]:
        adapter = read_json(ROOT / "adapters" / harness / "adapter.json")
        if adapter["harness"] != harness:
            errors.append(f"Adapter mismatch: {harness}")
    if errors:
        raise ValueError("\n".join(errors))
    return {"skills": len(paths), "source_files_present": sum((ROOT / item["path"]).exists() for item in manifest["sources"]),
            "links_valid": True}


def bundle():
    validate()
    manifest = read_json(ROOT / "manifest.json")
    out = ROOT / "output" / f"agent-workflow-kit-{manifest['version']}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    selected = [ROOT / name for name in ("SKILL.md", "AGENTS.md", "README.md", "manifest.json")]
    selected += [p for base in ("skills", "adapters", "docs") for p in (ROOT / base).rglob("*") if p.is_file()]
    selected.append(ROOT / "scripts" / "framework.py")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(selected):
            archive.write(path, Path("agent-workflow-kit") / path.relative_to(ROOT))
    return {"bundle": str(out), "sha256": digest(out.read_bytes()), "files": len(selected)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "install"):
        p = sub.add_parser(command)
        p.add_argument("--harness", choices=("codex", "zcode"), required=True)
        p.add_argument("--target-root")
        p.add_argument("--agents-path")
        p.add_argument("--skills-dir")
        if command == "install":
            p.add_argument("--replace-conflicts", action="store_true")
    sub.add_parser("inspect")
    sub.add_parser("validate")
    sub.add_parser("bundle")
    p = sub.add_parser("rollback")
    p.add_argument("--receipt", required=True)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            result = {"candidates": [], "note": "Presence is not proof of harness or loader compatibility"}
            for name in ("codex", "zcode"):
                adapter = read_json(ROOT / "adapters" / name / "adapter.json")
                configured = os.environ.get(adapter["root_environment"]) if adapter["root_environment"] else None
                root = absolute(configured or Path.home() / adapter["home_directory"])
                result["candidates"].append({"harness": name, "root": str(root), "exists": root.exists(),
                                              "agents_path": str(root / adapter["agents_relative_path"]) if adapter["agents_relative_path"] else None,
                                              "explicit_skills_path_required": adapter["skills_relative_path"] is None})
        elif args.command == "validate":
            result = validate()
        elif args.command == "bundle":
            result = bundle()
        elif args.command == "rollback":
            result = rollback(args.receipt)
        elif args.command == "install":
            validate()
            result = install(args)
        else:
            _, _, result = plan(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
