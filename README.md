# Agent Workflow Kit

一套可版本化、可迁移的中文 Agent 工作规范：精简 `AGENTS.md`、7 个按需技能和 Codex/ZCode 部署入口。

## 背景与设计

面向需要可信数据、可复现项目和本地交付的使用者。原先两份长规范的第 2～7 节相同，差异集中在产品名称及第 8 节清理存储。现在共同业务规则只维护一份，harness 专属清理规则分别加载，避免每次对话加载全部流程。

整个仓库是源项目；根 `SKILL.md` 是可以整体复制的安装入口，内部业务技能由安装器展开。不能假设任意 harness 都会递归发现嵌套技能。支持自主读取文件的 AI 可先读入口再执行安装脚本；没有脚本能力时按下文手动部署。安装入口本身不自动安装，也不执行内部业务。

核心保留中文沟通、真实核验、原件保护、授权边界、可视化默认关闭、技能路由和默认本地提交条件。用户明确要求可以调整默认值，harness 的系统权限保持优先。安装包内不含个人用户名或当前机器的绝对路径；部署映射在目标文件中生成。

## 环境

- 版本：`0.1.0`；日期：2026-10-14（Asia/Shanghai）。
- 构建/安装/核验：Python 3.10+，全部运行脚本仅使用标准库；开发备份使用 Git。
- 使用规则和手动复制无需 Python。打包技能涉及的 Python/PyInstaller 仅在实际 exe 任务使用，不是框架依赖。
- 本次在 Windows/Python 3.12 验证临时目录中的部署机制。尚未在 Codex/ZCode 新会话中验证自动发现和业务执行；ZCode 未安装于本机。

## 边界

- 本项目不修改当前应用配置，只有用户明确运行 `install` 才写入目标；`plan`、`inspect`、`validate` 不写配置。
- 不配置账号、凭据、MCP、插件或模型，不改变权限，不自动联网、推送或发布。
- 未知 harness 没有适配器则拒绝安装；版本/表名按实际环境核实。
- ZCode 源文件未提供全局 AGENTS 和 skills 加载位置，须显式指定。`.zcode/cli` 和 `.zcode/v2` 是用户提供的数据存储线索，不能等同技能目录。
- 当前交付是通用 skill 文件布局与可指定路径的 ZCode 部署，不能宣称已验证 ZCode 原生技能发现。
- Git 是本地版本历史；防磁盘故障的异地备份/远程仓库需要另行配置，目前没有 push。

## 术语和默认值

`harness` 指运行 Agent 的宿主（Codex 或 ZCode）；“安装入口”管理部署，业务技能处理当前任务。“支持”分为内容适配、文件部署和宿主行为实测，不混称。

可视化仅在明确要求时启用。数据默认 Excel + 来源/清洗档案 + 简洁说明；正式报告默认离线 HTML + 单入口脚本；exe 默认 tkinter/PyInstaller。日期使用当前用户时区；只有变更记录固定按 Asia/Shanghai 记载。残留清理必须有用户明确请求，归档不是删除。

## 最近重大变更

- 2026-10-14：保存双源文件基线（`5d4148f`），保留迁移前规则。
- 2026-10-14：抽取通用核心、7 个业务技能和双 harness 清理参考，降低常驻上下文并保留规则来源。
- 2026-10-14：增加安装入口、JSON manifest/适配器、预览/备份/回滚与 ZIP 打包工具，支持无用户名依赖的部署。

## 当前状态与下一步

规则和部署工具已编写，安装、冲突、回滚与路径保护通过自动测试。原件哈希和文档链接通过检查。当前应用配置未改动。

待办：在使用者明确指定的 ZCode 版本中核实两个加载路径；分别在新 Codex/ZCode 会话验证技能发现与行为场景；后续按实测结果补兼容矩阵。未支持其他 harness，增加时维护 adapter 和相应清理规则，不能只替换产品名。

## 目录

```text
AGENTS（codex）.md / AGENTS（zcode）.md  原始材料，不覆盖
AGENTS.md                            通用核心
SKILL.md                             总安装入口
manifest.json                        版本、组件、原件哈希与章节映射
skills/                              7 个业务技能（入口、参考和 Codex UI 元数据）
adapters/{codex,zcode}/adapter.json   目标路径规则及实测状态
scripts/build_skills.py              重放原始 0.1.0 迁移（已有衍生文件默认保护）
scripts/framework.py                 检测、预览、安装、回滚、核验、打包
tests/test_framework.py              临时目录部署契约测试
docs/                                兼容性、原规则迁移和行为验收场景
output/                              本地生成 ZIP，Git 忽略；运行 bundle 时创建
```

## 安装与迁移

在仓库根执行；也可在其他工作目录用脚本绝对路径，脚本始终相对自身定位资源。

```powershell
python scripts/framework.py inspect
python scripts/framework.py validate
python scripts/framework.py plan --harness codex
```

Codex 默认遵循 `CODEX_HOME`，未设置时为当前用户 `~/.codex`；目标核心为 `AGENTS.md`，技能位于 `skills/`。自定义或测试根用 `--target-root`。两种 harness 都允许 `--agents-path` 和 `--skills-dir` 覆盖目标。

ZCode 必须填入通过目标版本界面/可信配置核实的加载路径，示例参数中的路径由使用者提供，不表示 ZCode 官方默认位置：

```powershell
python scripts/framework.py plan --harness zcode --target-root <ZCode数据根> --agents-path <全局规范文件> --skills-dir <技能目录>
```

确认路径和计划后，用相同参数将 `plan` 改为 `install`。这一步才修改目标。已有不同内容默认报冲突；只有用户明确选择覆盖时追加 `--replace-conflicts`。不删除目标技能目录中本框架未管理的文件。更新使用同样命令，未被用户修改的旧版框架文件可升级；被修改的文件仍报冲突。

每次安装在 `<target-root>/.framework-install/<时间-随机ID>/` 保存收据和被覆盖文件的完整原版本。保留此目录以回滚，备份可能含使用者原配置，不提交或分享。

```powershell
python scripts/framework.py rollback --receipt <安装输出的receipt.json路径>
```

回滚逐项核对当前内容和备份哈希，保护安装后的用户修改；仅删除本次新建文件和空目录。备份与收据保留；多个升级按最新到最旧顺序回滚。脚本使用原子单文件写入并检测前后变更，不能把多个文件安装当作跨进程事务；请勿与其他安装器同时修改同一路径，安装中断按收据恢复。

### 一个入口交付

```powershell
python scripts/framework.py bundle
```

产物 `output/agent-workflow-kit-0.1.0.zip` 包含 `agent-workflow-kit/` 整体目录。在目标 harness 中把这个目录作为安装 skill 使用，明确请求它迁移到选定 harness；或解压后直接运行脚本。不会自动递归注册子技能，必须执行展开安装或手动复制。

手动部署：备份实际加载的全局规则；复制核心内容到该文件，将 `skills/` 下每个业务技能目录复制到已核实的技能目录。在核心末尾写明实际 skills 相对路径和当前 harness。不要把源文件中的第 8 节同时粘贴到全局核心。新会话验证发现失败时，可要求 AI 按实际路径读取相应 `SKILL.md`。`agents/openai.yaml` 是 Codex 专属 UI 元数据，其他 harness 是否忽略它需按宿主核实；它不影响通用 Markdown 规则。

## 开发与复现

原始双文件保持不改，业务技能、核心和 adapter 是今后维护的源，版本更新写入 manifest。`build_skills.py` 仅用于重放首次迁移，已有 manifest 时默认拒绝运行；明确使用 `--rebuild-original` 会以原始规则重写业务技能和 0.1.0 manifest，应在独立副本中使用或先保留已提交的改动，不作为日常构建入口。

```powershell
python scripts/framework.py validate
python -m unittest discover -s tests -v
python scripts/framework.py bundle
git diff --check
```

上述日常核验与打包从当前本地框架源复现，不联网。重放首次提取可在完整仓库的独立副本中执行 `python scripts/build_skills.py --rebuild-original`。ZIP 不附带原始长规范、提取工具和开发测试，完整仓库保留它们。提交前检查完整 diff，只暂存本任务文件。本仓库已初始化并有本地基线，开发里程碑核验后提交一次，不默认 push。

详见 [兼容矩阵](docs/compatibility.md)、[规则迁移说明](docs/migration.md)、[行为验收场景](docs/scenarios.md) 和 [本次验证记录](docs/validation.md)。
