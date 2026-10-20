# AGENTS.md — 路由表

> 本文件不写具体规则，只告诉 Agent **干什么活之前读哪份文档**。
> 本项目使用 evoloop 自进化循环：代码由 agent 编写、审查、合并、发布，每晚复盘的教训写入 LESSONS.md。

## 项目一句话
{{PROJECT_ONE_LINER}}

## 开工前必读（按顺序）
1. 本文件
2. 你要改动的子系统文档：`docs/subsystems/<name>.md`（下表）
3. `docs/code-standards.md` —— 验收标准、Review 清单、commit 规范（硬性）
4. `LESSONS.md` —— 近期犯过的错和能拦住它的规则（CLAUDE.md 已自动加载）
5. 审外部贡献时：`docs/contributors.md`

## 子系统路由
| 子系统 | 目录 | 文档 | 负责什么 |
|---|---|---|---|
| {{api}} | `{{api/}}` | `docs/subsystems/{{api}}.md` | {{...}} |
| {{web}} | `{{web/}}` | `docs/subsystems/{{web}}.md` | {{...}} |

改了某个子系统的行为、状态或契约 → **同一个 PR 里**更新对应文档。

## 按任务路由
| 你要做的事 | 先读 | 用哪个提示词 |
|---|---|---|
| 分诊新 Issue | 本文件「产品边界」 | `prompts/triage.md` |
| 修 bug / 做功能 | 子系统文档 + code-standards + LESSONS | `prompts/builder.md` |
| 审 PR | code-standards 全文 + contributors（外部 PR） | `prompts/reviewer.md` |
| 发版 | code-standards「发布」 | `prompts/release.md` |
| 夜间复盘 | evoloop/docs/lessons-system.md | `prompts/nightly-retro.md` |

## 检查命令
```bash
# 格式 / lint / 类型
{{FORMAT_CMD}}
{{LINT_CMD}}
{{TYPECHECK_CMD}}
# 全量测试（隔离环境）
{{TEST_CMD}}
# 构建
{{BUILD_CMD}}
```

## 测试隔离
{{例如：测试使用临时 HOME、临时数据库 schema、临时对象存储 bucket；任何测试都不得连接生产或开发数据库。}}

## 产品边界（Triage 依据）
- 做：{{...}}
- 不做：{{...}}

## 真实复现环境
| 环境 | 怎么访问 | 用途 |
|---|---|---|
| {{例：macOS 本机}} | {{本机}} | {{桌面端复现}} |
| {{例：Windows + Linux 虚拟机}} | {{ssh / 远程}} | {{跨平台复现}} |

修 bug 必须在报告人所用的环境里复现；环境不可用时在 Not run 里写明。

## 已拍板的产品决定（Agent 不得推翻）
> 核心决策与审美偏好只由人修改，和 loop 运行中积累的工作记忆分开。详细背景可放 `docs/product-decisions.md`。

| 决定 | 日期 | 来源 |
|---|---|---|
| {{例：按钮只在 hover 时出现}} | {{YYYY-MM-DD}} | {{the owner / #issue}} |

遇到与这些决定冲突的需求 → 标 `evo:needs-human`，不要自己改。

## 必须人放行的改动
- CI / 发布脚本 / 工作流
- 新的外部网络地址、上传数据到外部
- 读写凭证、改鉴权
- 新依赖、二进制、混淆代码
- 数据库迁移、批量删除数据或资产
- {{项目特有}}

## 容易误判的知识
> "哪段代码实际在跑"这类坑写在这里。例如：某功能已迁移到插件，旧目录的代码不再生效，修复要改插件。
- {{...}}

## 协作规则
- 每个会话独立 `git worktree`；永不在共享 checkout 提交。
- 开工前在 Issue 评论认领（`scripts/claim.sh`）。
- 一个 commit 一个目标；顺手发现的问题另开 Issue。
