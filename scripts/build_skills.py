"""从保留的双源文件重建业务技能；不修改核心、适配器或安装目标。"""
import hashlib
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {name: ROOT / f"AGENTS（{name}）.md" for name in ("codex", "zcode")}
SKILLS = [
    (2, "clarify-requirements", "用户明确要求苏格拉底式提问、厘清真正需求或先澄清再执行时使用；普通行动请求只澄清必要缺口。"),
    (3, "project-workflow", "持续维护或需要复现的代码、数据、文档项目，或用户明确启用项目框架时，维护目录、README 和复现记录。"),
    (4, "source-data-research", "检索、下载或核验外部统计数据，或整理已有数据文件时，处理来源档案、口径、清洗和追溯；内部材料保留原身份。"),
    (5, "source-backed-report", "用户要求正式数据报告、带来源报告或可复现 HTML 报告时，生成有来源批注的报告和入口脚本。"),
    (6, "exe-delivery", "用户要求独立 Windows exe 或让无 Python 的人运行程序时，制作 GUI、模板、构建入口和交付说明。"),
    (7, "local-git-commit", "明确要求本地提交或帮我 git 一下，或符合用户默认里程碑提交条件时使用；只处理当前任务改动。"),
    (8, "cleanup-local-residue", "仅在明确请求清理已删除项目或对话的本地残留时执行，按 Codex 或 ZCode 存储核实归属；讨论、归档和规则安装不触发清理。"),
]


def sections(text):
    heads = list(re.finditer(r"^## (\d+)\. .+$", text, re.M))
    return {int(m[1]): text[m.start():heads[i + 1].start() if i + 1 < len(heads) else len(text)].strip()
            for i, m in enumerate(heads)}


def normalize(text):
    # 旧章节引用在独立技能中没有含义，转换为明确技能/核心名称。
    replacements = {
        "按第 1、2 节处理必要澄清": "按核心原则处理必要澄清；仅在用户明确要求时启用 clarify-requirements 完整流程",
        "澄清按第 2 节的适用条件执行": "澄清遵循 clarify-requirements 的适用条件",
        "提交统一按第 7 节执行": "提交按 local-git-commit 的适用条件执行",
        "统一遵循第 7 节": "统一遵循 local-git-commit 的适用条件",
        "路径遵循第 3 节": "路径相对于脚本或项目目录，沿用 project-workflow 的适用约定",
        "按第 3 节维护项目入口": "按 project-workflow 的适用约定维护项目入口",
        "遵循第 1 节开关": "遵循核心可视化开关，仅在用户明确要求时生成",
        "图表仍遵循第 1 节开关": "图表仍只在用户明确要求时生成",
        "数据处理遵循第 4 节适用部分": "数据处理时读取 source-data-research 的适用规则",
        "组合第 6 节": "组合 exe-delivery",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"^(#{2,3}) \d+(?:\.\d+)?\.?( )", r"\1\2", text, flags=re.M)
    return text


def write(relative, text):
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild-original", action="store_true",
                        help="明确允许用原始 0.1.0 规则重写衍生技能和 manifest；不是日常升级入口")
    args = parser.parse_args()
    if (ROOT / "manifest.json").exists() and not args.rebuild_original:
        raise ValueError("Derived files already exist; preserve edits. Use --rebuild-original only to replay original migration.")
    contents = {name: p.read_text(encoding="utf-8") for name, p in SOURCES.items()}
    sec = {name: sections(text) for name, text in contents.items()}
    for number in range(2, 8):
        if sec["codex"][number] != sec["zcode"][number]:
            raise ValueError(f"共同模块第 {number} 节存在源文件差异，先人工核实")
    mapping = []
    for number, name, description in SKILLS:
        prefix = f"---\nname: {name}\ndescription: {json.dumps(description, ensure_ascii=False)}\n---\n\n"
        if number == 4:
            source = sec["codex"][4]
            a = source.index("#### A.")
            b = source.index("#### B.")
            f = source.index("#### F.")
            deliver = source.index("### 4.4")
            write(f"skills/{name}/references/external-sources.md", normalize(source[a:b]))
            write(f"skills/{name}/references/data-workflow.md", normalize(source[b:f] + "\n\n" + source[f:deliver] + "\n\n" + source[deliver:]))
            body = """# 数据检索与整理

先识别指标、对象、时期、频率、单位、口径、检索截止时点和交付格式，仅澄清关键缺口。默认 Excel 数据表、来源档案、清洗后数据和简洁说明。

- 检索外部统计数据时，先读 [外部来源规则](references/external-sources.md)，再读 [归档、清洗与核验](references/data-workflow.md)。
- 仅整理用户现有文件时，读 [归档、清洗与核验](references/data-workflow.md)；内部材料按真实身份处理，不替换为官方来源。随后另行检索的外部数据才适用外部来源规则。
- 原件与清洗结果分开；每个最终数值定位到原件或输入公式。缺失不填 0，不自动插值、外推、删异常值。
- 数据不足交付已核验部分并列明缺口，不暗中换指标。普通数据请求不扩展为完整报告或打包；可视化只在用户明确要求时生成。
- 持续项目使用 project-workflow；只有用户要求正式报告才组合 source-backed-report。
"""
        elif number == 8:
            for harness in SOURCES:
                write(f"skills/{name}/references/{harness}/cleanup.md", normalize(sec[harness][8]))
            body = """# 已删除项目/对话的本地残留清理

阅读、安装、讨论本技能不授权清理。只有当前用户明确要求执行一次本地残留清理或等价行动时才开始。保持原有工具确认要求，已明确授权范围内不反复确认。

先确定 harness、真实用户目录、当前/运行会话及保护对象，再完整读取对应参考：

- Codex：[Codex 存储、证据与清理规则](references/codex/cleanup.md)。
- ZCode：[ZCode 存储、证据与清理规则](references/zcode/cleanup.md)。
- 未知 harness 或无法判定：只核实环境，不执行删除，报告缺少适配规则。不会根据相似路径套用另一 harness 的数据库操作。

参考来自用户提供的原始规范，路径/表名是待验证线索，不是当前版本已验证接口。必须实际核实每个存储位置、字段、归属和并发状态。没有交叉删除证据，保留目标；归档不等于删除。保护会话、项目、成果、源码、原件、附件、凭据、登录、配置、技能、长期记忆和运行任务；不退出、强杀或重启应用。

Codex 直接修改 SQLite 需要确认离线且无并发写入；ZCode 原规范允许事务内并发访问，但必须使用一致性数据库备份、busy_timeout、可靠引用关系，处理应用回写冲突，无法证实安全则跳过。不要把 busy_timeout 当作归属或并发安全证明。不自动删除 ZCode 整库备份，位置和去留按用户原规则处理。正文敏感信息不复制到新报告。

交付只报告必要 ID/路径、实际删除与保留数量、跳过原因、备份和剩余项；释放空间实测才报。不承诺云端或底层可恢复字节已清除。
"""
        else:
            body = normalize(sec["codex"][number])
        write(f"skills/{name}/SKILL.md", prefix + body)
        # 产品元数据与通用技能正文分离；默认允许自动发现，正文限定业务授权。
        write(f"skills/{name}/agents/openai.yaml", f'interface:\n  display_name: "{name}"\n  short_description: {json.dumps(description[:64], ensure_ascii=False)}\npolicy:\n  allow_implicit_invocation: true\n')
        mapping.append({"skill": name, "source_section": number,
                        "strategy": "shared" if number < 8 else "harness-specific references"})
    manifest = {
        "name": "agent-workflow-kit", "version": "0.1.0", "schema_version": 1,
        "core": "AGENTS.md", "bootstrap": "SKILL.md", "skills": [x[1] for x in SKILLS],
        "harnesses": ["codex", "zcode"],
        "sources": [{"path": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in SOURCES.values()], "source_mapping": mapping,
    }
    write("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    print("Built 7 skills and source mapping; original files unchanged.")


if __name__ == "__main__":
    main()
