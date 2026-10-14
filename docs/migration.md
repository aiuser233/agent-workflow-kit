# 原规则迁移记录

双源文件保留根目录，首个 Git commit 仅包含这两份文件。manifest 记录它们的 SHA-256 和每个技能对应的来源章节。

| 原章节 | 当前位置 | 调整 |
| --- | --- | --- |
| 1、9 | `AGENTS.md` | 压缩常驻原则、交付习惯，模式表改为技能名 |
| 2 | `skills/clarify-requirements/SKILL.md` | 保留明确触发、5 轮与执行授权边界 |
| 3 | `skills/project-workflow/SKILL.md` | 保留 README、目录、路径与复现规则 |
| 4 | `skills/source-data-research/` | 来源规则仅外部检索时读取；现有内部材料不强求外部机构 |
| 5 | `skills/source-backed-report/SKILL.md` | 保留 F/C/I/U、来源批注和默认 HTML |
| 6 | `skills/exe-delivery/SKILL.md` | 保留 GUI、模板、构建、真实输入验证 |
| 7 | `skills/local-git-commit/SKILL.md` | 保留默认本地提交条件及暂存保护 |
| 8 | `skills/cleanup-local-residue/references/{codex,zcode}/cleanup.md` | 双版本保留，按 harness 加载 |

独立技能中旧的“第 N 节”引用转成核心原则、明确技能名或具体路径规则。不会因安装而执行被引用技能；普通澄清与完整等待流程区分。

两版清理的操作差异未静默合并：Codex 禁止直接改现用 SQLite；ZCode 原材料允许受控事务并发访问及整库备份。入口提醒 busy_timeout 不等同并发安全，无法核实引用/应用回写则跳过。ZCode 长期记忆和现存工作区检查点仍受保护，残留目录中的文件成果/附件也受保护。此框架没有实现自动删库脚本。

保持默认自动发现业务技能，其正文仍明确限制触发和实际动作授权。自动发现不表示用户授权清理。安装入口的描述只匹配安装/迁移/升级，避免对普通业务调用总包。内容加载后仍消耗上下文，不能把节省常驻核心等同全部对话 token 成本。
