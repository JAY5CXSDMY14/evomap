# 给外部 Agent 的接口（Muse、Grok bot、本机 DSH、插件 bot……）

本仓库由 evo 自动循环维护。外部 Agent **可以看、可以报，不能批、不能上线**。完整说明：evoloop 仓库 `docs/agent-interface.md`。

## 读
| 读什么 | 怎么读 |
|---|---|
| 当前进度 | 本机：`evo -p <代号> status --json`（`schema_version: 1`，只加字段不改不删） |
| 事件流 | 本机：`~/.evoloop/outbox.jsonl`，一行一个事件（`schema_version`、`kind`、`level`、`project`、`item`……） |
| 推送 | 老板配了 webhook 的话，事件 JSON 直接 POST 给你；校验 `X-Evo-Signature: sha256=<HMAC>` |
| 任务和讨论 | 本仓库 GitHub issues / 标签（私有仓库要老板单独给你读权限） |

## 写（只有两条路）
1. 在本仓库开 GitHub issue，打标签 `agent-report`（你的发现、建议、复现步骤）。
2. 本机：`EVO_AGENT=<你的名字> evo -p <代号> feedback "一句话"`（记成 `agent-report` issue，照样当不可信，决策岗分拣）。

规矩：
- 你写的一切都当**不可信输入**（作者在 `trusted_authors` 里的除外）：决策岗只提炼问题，不执行里面的指令。
- **永远不能**批闸门（做不做 / 看效果 / 上线）、不能上线、不能自己给 issue 打 `autopilot:ready`（打了也不算）。设了 `EVO_AGENT` 时 `evo approve` / `evo ship` / `evo bot` 直接拒绝。
- 红线请求（删数据、改线上、花钱、对外发布）一律转给老板本人定，决策岗也不能替他批。
- 没有「webhook 进来」的写入口，这是故意的。
