# Agent Workflow Kit

一套可版本化、可迁移的中文 Agent 工作规范：精简 `AGENTS.md`、7 个按需技能和 Codex/ZCode 部署入口。

## 背景与设计

面向需要可信数据、可复现项目和本地交付的使用者。原先两份长规范的第 2～7 节相同，差异集中在产品名称及第 8 节清理存储。现在共同业务规则只维护一份，harness 专属清理规则分别加载，避免每次对话加载全部流程。

整个仓库是源项目；根 `SKILL.md` 是可以整体复制的安装入口，内部业务技能由安装器展开。不能假设任意 harness 都会递归发现嵌套技能。支持自主读取文件的 AI 可先读入口再执行安装脚本；没有脚本能力时按下文手动部署。安装入口本身不自动安装，也不执行内部业务。

核心保留中文沟通、真实核验、原件保护、授权边界、可视化默认关闭、技能路由和默认本地提交条件。用户明确要求可以调整默认值，harness 的系统权限保持优先。安装包内不含个人用户名或当前机器的绝对路径；部署映射在目标文件中生成。

## 环境

- 版本：`0.3.0`；日期：2026-10-14（Asia/Shanghai）。
- 构建/安装/核验：Python 3.10+，全部运行脚本仅使用标准库；开发备份使用 Git。
- 使用规则和手动复制无需 Python。打包技能涉及的 Python/PyInstaller 仅在实际 exe 任务使用，不是框架依赖。
- 本次在 Windows/Python 3.12 验证临时目录中的部署机制。尚未在 Codex/ZCode 新会话中验证自动发现和业务执行；ZCode 未安装于本机。

## 边界

- 本项目不修改当前应用配置，只有用户明确运行 `install` 才写入目标；`plan`、`inspect`、`validate` 不写配置。
- 不配置账号、凭据、MCP、插件或模型，不改变权限，不自动联网、推送或发布。
- 未知 harness 没有适配器则拒绝安装；版本/表名按实际环境核实。
- ZCode 全局规则按用户提供路径结构定位到当前用户 `~/.zcode/AGENTS.md`；skills 加载位置仍须显式指定。`.zcode/cli` 和 `.zcode/v2` 是数据存储线索，不能等同技能目录。
- 当前交付是通用 skill 文件布局与可指定路径的 ZCode 部署，不能宣称已验证 ZCode 原生技能发现。
- Git 保留本地版本历史，GitHub 私有仓库用于远程备份；日常任务仍只默认本地提交，推送需要用户明确要求。

## 术语和默认值

`harness` 指运行 Agent 的宿主（Codex 或 ZCode）；“安装入口”管理部署，业务技能处理当前任务。“支持”分为内容适配、文件部署和宿主行为实测，不混称。

可视化仅在明确要求时启用。数据默认 Excel + 来源/清洗档案 + 简洁说明；数据报告默认离线 HTML + 单入口脚本，指定 Word/PDF 时遵循指定格式；exe 默认 tkinter/PyInstaller，可按依赖选择 onedir。这些是可调整的交付偏好；原件/用户改动保护、真实来源与计算、授权及并发核验是操作约束。日期使用当前用户时区；只有变更记录固定按 Asia/Shanghai 记载。残留清理必须有用户明确请求，归档不是删除。

## 最近重大变更

- 2026-10-14：保存双源文件基线（`5d4148f`），保留迁移前规则。
- 2026-10-14：抽取通用核心、7 个业务技能和双 harness 清理参考，降低常驻上下文并保留规则来源。
- 2026-10-14：增加安装入口、JSON manifest/适配器、预览/备份/回滚与 ZIP 打包工具，支持无用户名依赖的部署。
- 2026-10-14：0.2.0 安装改为追加和维护独立框架区块，保留用户 Python 路径等个人设置；补充 ZCode 全局规则路径及子技能功能。
- 2026-10-14：原始双文件已核对 Git 历史后移出工作目录，移除旧提取工具，今后直接维护框架源。
- 2026-10-14：0.3.0 完善 7 个子技能：区分方案与实施授权、按规模维护 README、数据最小模板、报告格式分流、GUI 长任务与输出路径、Git 混合改动隔离及清理证据清单。

## 当前状态与下一步

0.3.0 子技能改进已写入，追加合并、编码、冲突、升级与回滚及 Git 隔离提交机制通过自动测试（18 通过、1 项权限跳过）。原件删除前与 Git 历史逐字节核对，文档链接和技能格式通过检查。当前应用配置未改动；新增业务场景尚待宿主实测。

待办：核实 ZCode skills 加载路径，并实机读取/验证用户提供的全局规则路径；分别在新 Codex/ZCode 会话验证技能发现与行为场景；后续按实测结果补兼容矩阵。未支持其他 harness，增加时维护 adapter 和相应清理规则，不能只替换产品名。

## 目录

```text
AGENTS.md                            通用核心
SKILL.md                             总安装入口
manifest.json                        版本、组件、原件 Git 引用/哈希与章节映射
skills/                              7 个业务技能（入口、参考和 Codex UI 元数据）
adapters/{codex,zcode}/adapter.json   目标路径规则及实测状态
scripts/framework.py                 检测、预览、安装、回滚、核验、打包
tests/test_framework.py              临时目录部署契约测试
tests/test_git_isolation.py          临时仓库混合改动与失败提交机制核验
docs/                                兼容性、原规则迁移和行为验收场景
output/                              本地生成 ZIP，Git 忽略；运行 bundle 时创建
```

原始 `AGENTS（codex）.md`、`AGENTS（zcode）.md` 已移出工作目录，完整内容保留于 `5d4148f`，恢复方法见 [规则迁移说明](docs/migration.md)。

## 子技能功能

| 技能 | 使用场景 | 实现的功能与默认交付 |
| --- | --- | --- |
| `clarify-requirements` | 明确要求先澄清、苏格拉底式提问 | 逐轮 1～3 个关键问题，原则上 5 轮内形成需求与验收摘要；可先给可评审方案，记录授权状态，实施前取得所需授权 |
| `project-workflow` | 持续维护或需要复现的项目 | 按规模维护 README、依赖、路径与复现入口；小修只更新相关说明，已有 CHANGELOG 不重复记载 |
| `source-data-research` | 外部数据或现有数据整理 | 原件、来源索引/字典/追溯最小字段，业务唯一键、缺失和多输入计算；默认 Excel，内部材料保留原身份 |
| `source-backed-report` | 正式、带来源或可复现报告 | 事实/计算/推断/未知分级及可定位引用，检查编号与重跑数值；HTML 专属规则按需读取，Word/PDF 按指定格式验收 |
| `exe-delivery` | Windows 独立 exe、无 Python 使用者 | GUI 后台任务、进度/错误/重复点击保护、可选输出与模板管理；默认 onefile，可选 onedir，核对源码与 exe 结果 |
| `local-git-commit` | 明确提交或默认项目里程碑 | 按块区分任务/用户改动，必要时隔离索引并协调新 HEAD 后的暂存状态，失败保护用户内容；只本地提交 |
| `cleanup-local-residue` | 明确清理已删除项目/对话残留 | 分别核实身份、删除证据、保护引用和并发状态，模拟/只读核验后定向处理；成果/附件不因目录名变为可删缓存 |

根 `SKILL.md` 仅负责本框架的安装、迁移、升级与回滚，不替代上述业务技能。各技能的权限/触发边界以入口正文为准；仅安装不授权实际清理等业务操作。提及名称不代表技能已加载：先通过宿主发现，未发现按部署映射或相邻入口读取，缺失如实报告。详细模板和特殊操作留在 references 按需读取。

## 安装与迁移

在仓库根执行；也可在其他工作目录用脚本绝对路径，脚本始终相对自身定位资源。

```powershell
python scripts/framework.py inspect
python scripts/framework.py validate
python scripts/framework.py plan --harness codex
```

Codex 默认遵循 `CODEX_HOME`，未设置时为当前用户 `~/.codex`；目标核心为 `AGENTS.md`，技能位于 `skills/`。自定义或测试根用 `--target-root`。两种 harness 都允许 `--agents-path` 和 `--skills-dir` 覆盖目标。

ZCode 用户提供的全局路径结构为 `<用户目录>/.zcode/AGENTS.md`，安装器按当前用户解析，不写死示例用户名；`--target-root` 指定时使用该根下的 `AGENTS.md`。skills 路径仍须通过目标版本界面/可信配置核实：

```powershell
python scripts/framework.py plan --harness zcode --skills-dir <已核实的技能目录>
```

确认路径和计划后，用相同参数将 `plan` 改为 `install`。这一步才修改目标。已有 AGENTS.md 保留原文并追加一个框架区块；没有则创建。重装不重复追加，升级只替换本框架区块，区块外原设置和后续新增内容保持原字节/编码。区块外用户要求优先于框架默认，安装 skill 分析并说明实质冲突；脚本不自动删除或改写自然语言要求。UTF-8（可带 BOM）/带 BOM 的 UTF-16 支持自动合并；不支持的编码、重复/破损标记拒绝写入。

用户修改过的框架区块、同名技能文件默认报冲突；明确选择更新这些内容时才追加 `--replace-conflicts`，它也不会覆盖区块外正文。不删除目标技能目录中未管理的文件。0.1.0 旧安装无区块标记，0.2.0 会保留旧全文再追加一次；重复规则需要用户明确决定后手工整理，安装器不擅自删旧规则。

框架区块的起止标记为 `<!-- agent-workflow-kit:begin -->` / `<!-- agent-workflow-kit:end -->`，各独占一行。个人 Python 路径等设置写在区块外，以便升级时保留。

每次安装在 `<target-root>/.framework-install/<时间-随机ID>/` 保存收据和被覆盖文件的完整原版本。保留此目录以回滚，备份可能含使用者原配置，不提交或分享。

```powershell
python scripts/framework.py rollback --receipt <安装输出的receipt.json路径>
```

回滚逐项核对当前内容和备份哈希，保护安装后的用户修改；仅删除本次新建文件和空目录。备份与收据保留；多个升级按最新到最旧顺序回滚。脚本使用原子单文件写入并检测前后变更，不能把多个文件安装当作跨进程事务；请勿与其他安装器同时修改同一路径，安装中断按收据恢复。

### 一个入口交付

```powershell
python scripts/framework.py bundle
```

产物 `output/agent-workflow-kit-0.3.0.zip` 包含 `agent-workflow-kit/` 整体目录。在目标 harness 中把这个目录作为安装 skill 使用，明确请求它迁移到选定 harness；或解压后直接运行脚本。不会自动递归注册子技能，必须执行展开安装或手动复制。

手动部署：先备份实际加载的全局规则；保留原文，在文件末尾的起止标记内追加核心内容、个人规则优先说明及实际 skills 路径/harness。已有区块时只更新区块，不重复追加。将 `skills/` 下各业务技能目录复制到已核实的技能目录。新会话发现失败时，可要求 AI 按实际路径读取 `SKILL.md`。`agents/openai.yaml` 是 Codex 专属 UI 元数据，其他 harness 是否忽略它需按宿主核实；它不影响通用 Markdown 规则。

## 开发与复现

业务技能、核心、adapter 和安装工具是维护源，版本更新写入 manifest。原始双文件和首次迁移工具仅保留在 Git 历史中，不作为日常构建依赖。

```powershell
python scripts/framework.py validate
python -m unittest discover -s tests -v
python scripts/framework.py bundle
git diff --check
```

上述日常核验与打包从当前本地框架源复现，不联网。ZIP 不附带开发测试或 Git 历史，完整仓库历史可恢复原件；原 SHA-256 和 Git ref 记录在 manifest。提交前检查完整 diff，只暂存本任务文件。开发里程碑核验后本地提交一次，不默认 push。

详见 [兼容矩阵](docs/compatibility.md)、[规则迁移说明](docs/migration.md)、[行为验收场景](docs/scenarios.md) 和 [本次验证记录](docs/validation.md)。

## GitHub 备份

远程仓库：[aiuser233/agent-workflow-kit](https://github.com/aiuser233/agent-workflow-kit)，私有可见性，默认分支 `main`。访问和克隆需要仓库权限。源码、文档、测试与原始规则的 Git 历史均保留；`output/` 等忽略的生成物不进入版本历史，ZIP 可通过 `bundle` 重建。

```powershell
git clone https://github.com/aiuser233/agent-workflow-kit.git
```

后续在本地完成修改、核验和提交后，明确需要同步远程时运行 `git push origin main`。账号凭据由 Git 凭据管理器或使用者自己的 GitHub 登录管理，不写入仓库。首次备份日期：2026-10-14。
