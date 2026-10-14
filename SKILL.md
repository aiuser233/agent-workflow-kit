---
name: agent-workflow-kit
description: 安装、迁移、升级或检查 Agent Workflow Kit 工作规范框架，用于 Codex 与 ZCode 的规则和技能配置；普通业务任务不调用此安装入口。
---

# 框架安装入口

本目录是一个可整体复制的安装 skill 包，内部 `skills/` 是待安装的独立技能，不能假设 harness 会递归发现它们。

1. 先读 [README.md](README.md) 的安装说明，以及 [manifest.json](manifest.json) 和相应 `adapters/<harness>/adapter.json`。
2. 识别 harness 和当前用户目录：使用运行环境、用户明确选择和存在的配置证据，不依靠文件名猜测。执行 `python scripts/framework.py inspect` 只报告候选路径。未知 harness 停止安装并报告缺少适配器。
3. 默认先运行 `plan`，显示实际目标路径和冲突。ZCode 全局规则按当前用户 `~/.zcode/AGENTS.md` 解析，技能目录仍须用户指定或从目标版本可信配置核实，通过 `--skills-dir` 传入；自定义规则路径用 `--agents-path`。不写死提供示例路径的用户名。
4. 读取现有用户级 AGENTS.md，识别 Python 路径、环境与其他要求。安装保留原文，追加 `agent-workflow-kit:begin/end` 标记区块；重装不重复追加，升级只替换该区块。区块外要求优先于框架默认；有实质冲突则列出具体冲突，请用户选择，不修改或删除原规则。保持原编码/BOM和区块外换行；非支持编码/破损标记停止合并。
5. 用户已要求安装且目标明确后运行 `install`，先备份、记录收据、验证内容。首次追加不需要覆盖授权；用户修改过的框架区块或同名技能默认报冲突，明确授权后才能用 `--replace-conflicts`，该参数也不覆盖区块外正文。不批量替换个人路径。
6. 报告收据、备份、实际追加/更新文件和加载限制；新对话中验证技能发现。需要回滚时使用 `rollback --receipt ...`，有后续修改的文件停止恢复，保护用户改动。

安装时只展开 manifest 中的业务技能和核心规则。本安装入口不自动执行数据、提交、打包或残留清理。运行脚本的路径相对于本目录；支持手动部署见 README。本框架不更改 harness 的权限、登录、MCP 或插件配置。
