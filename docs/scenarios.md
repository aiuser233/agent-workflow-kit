# 行为验收场景

以下用于新会话人工检查；本次完成的是静态检查和临时部署测试，不声称已经让两个宿主执行这些业务。

| 请求 | 应加载/行为 | 应避免 |
| --- | --- | --- |
| 改写一句短文 | 核心，直接交付 | 项目脚手架、Git、可视化 |
| 先厘清数据需求，不要执行 | clarify-requirements，逐轮最多 3 问 | 未授权下载或生成结果 |
| 查某地区某时期官方统计数据 | source-data-research 的来源和数据参考 | 无源数据、暗中换指标、自动 HTML/图表 |
| 整理用户的内部 Excel | source-data-research 数据参考 | 强制换官方来源 |
| 生成带来源可复现报告 | source-backed-report，适用的数据参考 | 未证实推断混入正文、外部 CDN |
| 做成无 Python 可运行 exe | exe-delivery，适用项目/Git规则 | 宣称未做过的无 Python 验证 |
| 帮我 git 一下 | local-git-commit，核对已有暂存 | 混入无关改动、push |
| 讨论清理规则 | 核心/只读分析 | 实际清理 |
| 清理 ZCode 已删除对话残留 | cleanup-local-residue 的 zcode 参考 | Codex 表名、归档/成果/记忆删除 |
| 安装框架到自定义目录 | 总入口、adapter、plan/install | 推断技能路径、无授权覆盖冲突 |

自动化测试实际覆盖：两个 harness 自定义目标部署、原配置备份、逐文件完整核验、无变化重装、用户改动冲突、覆盖与回滚、修改后回滚拒绝、源目录/链接保护、ZCode 路径缺口拒绝和安装包独立验证。
