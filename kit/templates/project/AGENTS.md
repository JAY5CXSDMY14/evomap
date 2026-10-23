# AGENTS.md — 路由表

> 本文件不写具体规则，只告诉 Agent **干什么活之前读哪份文档**。
> 本项目由 evo 自动循环推进：施工、验收（换一个模型）由 agent 做，合并和推送由 evo 做（不走 PR），每晚复盘的教训写入 docs/LESSONS.md。

## 项目一句话
{{PROJECT_ONE_LINER}}

## 开工前必读（按顺序）
1. 本文件
2. 你要改动的子系统文档：`docs/subsystems/<name>.md`（下表；还没有就在同一个提交里建一份）
3. `docs/code-standards.md` —— 验收标准、检查清单、commit 规范（硬性）
4. `docs/LESSONS.md` —— 近期犯过的错和能拦住它的规则（CLAUDE.md 已自动加载）
5. 任务书里的岗位规则 —— evo 派工时注入，以它为准

## 子系统路由
| 子系统 | 目录 | 文档 | 负责什么 |
|---|---|---|---|
| {{api}} | `{{api/}}` | `docs/subsystems/{{api}}.md` | {{...}} |
| {{web}} | `{{web/}}` | `docs/subsystems/{{web}}.md` | {{...}} |

改了某个子系统的行为、状态或契约 → **同一个提交里**更新对应文档。

## 按岗位路由
岗位规则不放在本仓库：evo 派工时把 evoloop 仓库 `kit/roles/` 里对应的那份注入任务书。本仓库不需要 `prompts/` 目录。
**不走 PR**：施工在自己的工作分支上提交，验收通过后由 evo 合并、推送；不开 PR、不自己合并、不推送。

| 岗位 | 先读 | 岗位规则（evoloop 仓库） |
|---|---|---|
| 施工（修 bug / 做功能 / 文档） | 子系统文档 + code-standards + docs/LESSONS.md | `kit/roles/builder.md` |
| 验收（另一个模型，只读复核） | code-standards 全文 + 任务书验收标准 | `kit/roles/verifier.md` |
| 决策（拆任务、技术决定、转老板） | 本文件「产品边界」「已拍板的产品决定」 | `kit/roles/decider.md` |
| 夜间错题本 | docs/LESSONS.md | `kit/roles/retro.md` |

分诊新 issue 由决策岗按「产品边界」做；上线由老板在 evo 里点「上线」闸门，agent 不发版。

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
lint / 类型检查 / CI 命令同时写进 evo 项目配置的 `checks`（`evo new --check '…'`），验收岗逐条跑；代码风格、分层、依赖方向的规则放进这些工具自己的配置。新依赖、新开目录先问决策岗。

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

遇到与这些决定冲突的需求 → 交决策岗转老板（施工 / 验收用 `ask`，Multica 下把 issue 标 blocked 写清问题），不要自己改。

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
- 每件在执行端（Multica / Orca）给的独立工作区里做；永不在共享 checkout 提交。
- 派工由 evo 做，不用自己认领 issue。
- 一个 commit 一个目标；顺手发现的问题另开 Issue。
