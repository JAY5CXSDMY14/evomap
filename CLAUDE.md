# CLAUDE.md

先读 `AGENTS.md`（项目是什么、目录、命令、硬规则、已知的坑）。然后按需要读：
- `docs/loop-overview.md`：循环全景，谁改什么
- `notes/decisions.md`：每个决定和为什么（只追加）
- `notes/review-2026-10-23-triage.md`：外部「架构减法」审查的分诊，哪些能直接做、哪些等老板拍板

## 审批边界
- 你可以：读代码、跑测试、写改动和测试、提 issue、在 issue 下评论、用 `propose` 提议（决策岗）。
- 你不可以：批闸门（做不做 / 看效果 / 上线；老板只在 Telegram 批，没配时用本机 `evo approve`）、上线、改项目目标、改模型或岗位卡片——这些只有老板本人能做；你的运行环境要带 `EVO_AGENT=<名字>`，evo 会拒绝。
- 要老板拍板的：删数据、改线上、花钱、对外发东西；`kit/selfmaint/` 的改动；`notes/review-2026-10-23-triage.md` 第 2 节列的事。
- 不走 PR，不强推；施工和验收必须是不同模型。
