# 配置备份、回滚与卸载

安装和退出只管理安装清单里的用户级 `AGENTS.md`、7 个技能及生成的 harness 元数据，不扫描或备份业务项目，也不修改登录、模型、MCP 或其他宿主配置。安装和恢复只需 Python 3.10+ 标准库；没有 Git 备份模式，没有 Git 也可使用。

## 强制备份

安装器先保存全部将被修改的已有文件原始字节，记录新建文件此前不存在；再重新读取备份校验 SHA-256、核对收据。全部成功才写目标。备份失败或损坏即停止，不能跳过或以 AI 手工写入代替。

默认位置是 `<target-root>/.framework-install/<时间-随机ID>/`，位于技能目录之外；删除框架技能不会自动删除备份。可在 `plan`、`backup` 和 `install` 中指定 `--backup-dir <独立备份目录>`，该目录不能在技能目录、框架源码或被改文件内。安装器在目标根保存定位记录，`history` 无需再次记住自定义备份路径。手动移动备份会使定位失效，需恢复原路径或提供实际收据路径。

只备份安装涉及的路径（包括存在但无需变更的文件），不安装：

```powershell
python scripts/framework.py backup --harness codex
python scripts/framework.py history --harness codex
```

ZCode 安装/备份仍需显式 `--skills-dir`，自定义 AGENTS 使用 `--agents-path`；查询、回滚和卸载依据收据，不需要再填写这两个路径。非默认目标在命令中带同一个 `--target-root`。

原文件保存在 `backups/*.bin`，收据将原路径与备份逐项对应，`.bin` 是原始文件字节，未做编码转换。备份目录可能包含个人要求和本机路径，只留在用户本地，不自动提交或上传。

## 回滚一次操作

```powershell
python scripts/framework.py rollback --latest --harness codex --dry-run
python scripts/framework.py rollback --latest --harness codex
# 选择某一次记录：
python scripts/framework.py rollback --receipt <receipt.json路径>
```

`--latest` 选最新可恢复的非空操作（安装、备份、卸载或恢复），以 `history` 确认；明确选择某次安装时用收据路径。多次升级按最新到最旧回滚。回滚恢复该次操作前的文件，删除此前不存在、且仍为本次写入内容的文件，校验备份、路径和当前哈希后执行。

发现后续用户修改时默认拒绝覆盖，列出冲突路径。若希望保留新配置并退出框架，选卸载；若明确选择完整恢复旧状态，可以使用：

```powershell
python scripts/framework.py rollback --receipt <receipt.json路径> --restore-modified --dry-run
python scripts/framework.py rollback --receipt <receipt.json路径> --restore-modified
```

该参数会恢复所选快照的完整原内容，并可能移除安装后新增内容，必须说明具体影响后由用户选择。实际恢复前重新备份当前内容，返回 `safety_receipt`；需要撤销恢复时对该安全收据运行普通 `rollback`。独立 `backup` 快照没有安装归属证明，其内容变化后的恢复也必须显式使用 `--restore-modified`。

## 保留个人设置的卸载

```powershell
python scripts/framework.py uninstall --harness codex --dry-run
python scripts/framework.py uninstall --harness codex
```

卸载遍历该目标的有效安装记录，跨升级恢复安装前的同名原件，而不是只撤销最新升级。

- AGENTS 的框架区块未修改：移除区块，保留区块外全部个人内容、编码/BOM及换行。没有后续修改时可逐字节恢复原文件；文件本来不存在且移除后无个人内容时才删除。区块本来已存在时恢复原区块，保留当前区块外内容。
- 框架区块被用户修改：默认保留并列出待处理项；用户审阅并明确允许移除/恢复该区块时才用 `--remove-modified-block`，该操作仍不改区块外内容。
- 技能未修改：安装前已有文件则恢复备份，本次新建文件则删除。技能被用户修改/移除：保留当前状态并列出，不能用整个目录递归删除绕过保护。
- 无关技能、个人新文件和非空目录：保留；只移除本次创建且已经为空的目录。
- 原安装收据和备份：保留。卸载本身也先备份当前文件与归属记录，返回卸载收据，可以通过 `rollback --receipt ...` 撤销卸载。

有待处理内容时状态为 `partially-uninstalled`，清楚报告具体路径；不是全部卸载成功。删除或修订保留的个人文件需用户决定，不自动推断授权。框架区块仍保留时可能引用已移除的技能，说明这一限制；可先用预览查看并决定是否移除修改过的区块。

## 中断与兼容

每个文件原子写入，使用前后哈希检测并发变化，无法提供多个文件跨进程事务或阻止最后瞬间的外部写入。操作期间勿同时编辑目标。安装/卸载/恢复中断时标记 `incomplete`，凭该操作收据回滚；未处理的中断记录会阻止后续安装和卸载。备份准备失败时若有 `preparing` 记录，也先用该记录回滚再重试。

0.1～0.3 的旧收据可以查询、回滚和卸载，原有备份仍使用；没有收据或无法核对备份时，不猜测同名技能是否属于框架，不自动删除。卸载不会删除下载/克隆的源包或最初安装入口本身，这些不在展开安装的变更清单内。
