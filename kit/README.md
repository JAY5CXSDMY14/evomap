# 精装房 · 土布自动循环套件

一条命令装到 Mac mini，之后你只在三处点头：**做不做**（仅产品功能）、**看效果**（仅 UI）、**上线**（可攒一批）。其余接棒、并行、排队、返工、合并、停滞提醒全自动。

## 由哪些项目拼成
| 部件 | 取自 | 用来做什么 |
|---|---|---|
| 发动机 | Orca（stablyai/orca） | 每件独立工作区、派工、完工回报、心跳、闸门、手机端 |
| 模型入口 | magpie（yetone） | 岗位只写模型名；额度用完自动换号 |
| 接棒器 `bin/tubu` | 本仓库 | 施工→验收（换模型）→看效果→合并；冲突排队；返工两轮；停滞提醒；上线批次 |
| 统一入口 | 本仓库 intake 设计 | GitHub issue 打 `autopilot:ready` 自动登记，登记前过脱敏词表 |
| 教训沉淀、夜间复盘 | yetone/magpie 的 LESSONS 做法 | `prompts/nightly-retro.md` + `scripts/lessons.py`，同一教训出现 3 次升为规矩 |
| 审查岗 | -agent-code-review | 云端只读代码、只建 issue，问题自动流回入口 |
| 解释页 | answer-me-with-html | 复杂流程出 HTML 给你看 |
| 规矩 | Mac mini 协作契约 | 红线、验收即命令、证据、脱敏全部保留；5 条修订见 `contract-revisions/` |

## 你要做的三步
1. 批准 `contract-revisions/` 的 5 条修订，并同意装 Orca。
2. 在 Mac mini 上：`bash kit/install.sh` 看缺什么，补齐后 `bash kit/install.sh --apply`。
3. 手机装 Orca App 扫码配对。之后看 `kit/bin/tubu status` 或手机。

## 已在 Hark 沙箱实测（假工人）
- 两件不冲突并行；同目录的件自动排在前一件合并之后。
- 施工 GLM、验收自动换 DeepSeek。
- 「做不做」「看效果」「上线」三个闸门都能卡住，点了才放行；上线可一次收 3 件。
- 验收不过自动返工，复验通过后自动合并。
- 工人不回报，阈值一到就标「疑似卡住」并提醒。
- 实测发现并已修：Orca 闸门放行会无视依赖，接棒器自己再核一遍；返工后旧验收挡住合并，接棒器自动标为已取代。

## 第二轮补强（10-20 晚，均已实测）
- 合并后自动推送：先查远端能否快进，不能就停下交决策岗，绝不强推。
- 合并前扫脱敏词表和危险文件（.env、.gitignore），命中不合并。
- 主工作区有未提交改动就不碰，提醒处理后 `tubu retry` 从断点继续。
- 返工自动换一个施工模型，验收模型随之错开。
- 合并后关终端、删工作区，GitHub issue 自动留言「已合并」「已上线」。
- 同一时间只有一个接棒器在动，防重复派工。
- `tubu digest` 每晚汇总：今日动静、可收菜、卡住的。

## 只能在 Mac mini 上验的
- DSH、Claude Code、Codex 真跑时会不会按说明回报（Orca 已认得 `dsh`）。
- magpie 下施工和验收同用一个工具时，各自指定模型是否生效。
- Hook 日志照常记录；手机提醒。
- 真工人的权限弹窗：Claude Code 建议用 acceptEdits 模式，危险动作仍由现有 Hook 拦截；DSH 同理配置。
