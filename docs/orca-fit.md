# Orca 适配评估（2026-10-20）

来源：x.com/lxfater/status/2110731820429946883；onorca.dev（stablyai/orca，MIT，YC，macOS/Win/Linux + iOS/Android 伴侣 App）。

## 它是什么
Agent 开发环境（ADE）：多个 CLI Agent（Claude Code、Codex、Grok、Pi、OpenCode 等 27 种，其他 CLI 也能接）并行跑，每件事一个 git worktree；统筹 Agent 拆任务、派给其他 Agent、收回报；Agent 卡住可提问；任务状态、手机端看实时状态（含 awaiting permission）；GitHub issue/PR 原生；Design Mode 点页面元素把 HTML/CSS/截图发给 Agent；diff 逐行批注退回 Agent；Orca CLI 让 Agent 自己开 worktree；SSH 远程机器。

## 和我们设计的对应
| 我们的设计 | Orca | 结论 |
|---|---|---|
| 循助（编排）+ 中台接棒 | 统筹 Agent 派工、收回报 | 可替代人工传话 |
| 一件事一个 worktree、并行 | 原生 | 直接用 |
| 状态守护 + 手机推送 | 任务状态 + 手机 App（含等权限） | 大部分可替代，自建守护降级为兜底 |
| 面板「等你」栏 | GitHub 任务 + diff 审阅 | 部分；三处点头仍需我们的规则 |
| U14 元素级反馈（开发侧） | Design Mode | 开发侧可直接用；网站用户侧仍要自建 |
| 契约、闸门、脱敏、冲突判定、issue 统一入口 | 无 | 仍由 evomap 规范提供，写进统筹 Agent 的提示词 |

## 建议
- 定位：control_plane 岗位的候选担任者（与 Multica 并列），不是替代契约。
- 试点：Mac mini 上装，用副本仓库，只接 Codex + cc，跑 2 件小 UI 件；看三点：DSH 能否作为自定义 CLI 接入且 hook 照常记录；手机 App 能否在等权限时提醒；统筹 Agent 能否遵守「施工≠验收」「范围不重叠才并行」。
- 时机：与 Reason 试点同前置（U10 公网部署、OPS-PERM-STALL 落地后），且需老板批准安装第三方工具。
