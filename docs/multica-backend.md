# evo × Multica 派工后端 · 设计稿（第 20 轮）

> 状态：2026-10-22 14:15 老板确认方向，代码还没写。写这份稿子是为了在动 evo 核心之前把边界定清楚。
> 前提：Air 上第二轮 1–9 步全部通过（~/tmp/MULTICA-HANDOFF-2.md，install.sh 已修到 aca3749）。

## 0. 一句话
**Multica 只负责「派人干活、看到干到哪」，Orca 的执行器角色由它接替。排队、闸门、返工上限、找老板、上线，这些还是 evo 管。**
evo 和 Multica 之间只通过 `multica` CLI（加 `--json`）交互，不 fork、不改服务端。Orca 后端代码保留，但默认关掉。

## 1. 老板已定的 5 件事（10-22 14:10–14:14）
| # | 问题 | 定了 |
|---|---|---|
| 1 | 定位 | (b) Multica 接替 Orca 当执行器，evo 继续当大脑（调度、闸门、上限）。不做 (a) 重写，也不只做 (c) 看板同步 |
| 2 | state.json | 仍然是 evo 自己的状态文件，加字段、升 schema_version；人和 Pi 都不手改 |
| 3 | evo 健康 | 先只读查清「决策岗连续 5 次超时」，再接新后端 |
| 4 | 对应关系 | 一个 evo 项目对应一个 Multica project，三个固定 agent：施工、验收、决策 |
| 5 | 决策岗模型 | 先不买 Claude Pro：决策-Claude 用 `fable` 档位，经 Magpie 走「决策脑·任务书」，先试 5 条，质量不够再买 |

## 2. 三个 agent（每台机器在 Multica 网页里各建一次）
| 岗位 | Multica agent | runtime | 模型 | 说明 |
|---|---|---|---|---|
| 施工 | 施工-DSH | dsh | `deepseek-official/group/free-ds` | 实测 29–42 秒；group/build 31s 可备用；free-qwen 107s，避开 |
| 验收 | 验收-Claude | claude | `sonnet`（Magpie 转 glm-5.3-flash） | 只读；和施工模型不同 |
| 决策 | 决策-Claude | claude | `fable`（Magpie 转「决策脑·任务书」） | 新建；只做技术决定，四类红线回老板 |

claude 日志里的 `unrecognized_model` 警告不用管：Multica 不换 claude 的配置目录，会读 `~/.claude/settings.json`（BASE_URL 是 127.0.0.1:3425），请求照样走 Magpie。

## 3. 一件事在两边怎么走
```
evo 队列里的条目 EV-xxx
  └─ multica issue create（project=EV，正文=施工规格+岗位规则+ponytail）→ 拿到 issue 号，比如 EVO-7
     └─ multica issue assign EVO-7 --to 施工-DSH
        ⋯ 每个 tick：multica issue show EVO-7 --json → 状态 / 最新评论 / 分支
        └─ 进 in_review → evo 读施工报告（评论里的 ```json，格式同 report.schema.json）
           └─ multica issue assign EVO-7 --to 验收-Claude（追加验收规格做评论）
              └─ 验收评论 json：pass → evo 走 look 闸门 / 合并 / 上线（照旧在 evo 面板）
                               fail → 返工：round+1，再派施工-DSH（受 2 次决策返工 / 12 次派工 / 6 小时上限约束）
决策批次：evo 每 30 分钟把「escalated / asking」的条目攒成一个 issue「EV 决策批次 mm-dd hh:mm」，派给决策-Claude；
         它的最后一条评论里放 ```json 决定（retry / rework / drop / split / ask_owner / answer），evo 读到后照旧执行。
```
- **闸门不搬过去**：做不做、看效果、上线这几道闸门还在 evo 面板和推送里。Multica 的 in_review 只当「施工做完了」的信号，不算老板批过。
- **合并**：worktree 分支 `agent/dsh/<issue>` 由 evo 合并（用 evo 自己的 clone `~/.evoloop/repos/<code>`），流程和 Orca 时代一样。
- **收件箱**：Multica 的 Inbox 只给老板顺手看，权威入口还是 evo 面板。

## 4. 代码改法（strangler：先抽接口，再一个功能一个 commit 地迁）
1. 抽一个 `Executor` 接口（新文件 `kit/bin/evo_exec.py`）：`ensure_project`、`create(kind, title, spec)`、`assign(task, role)`、`poll(task) → {state, report, branch, last_activity}`、`comment`、`close`、`health`。
2. 现在散在 evo 里的 ~40 处 `orca(...)` 调用收进 `OrcaExecutor`，行为不变，现有 ~300 个测试全过才算这一步完成。
3. 新增 `MulticaExecutor`：只调用 `multica … --json`，每个调用都有超时（加到 `TIMEOUT_DEFAULTS`）；daemon 或服务端连不上时走现有的 `orca_up` 路径，改名为 `exec_up`（不通就推一次，这一轮不派工）。
4. 配置：项目里写 `executor: multica|orca`（默认 multica）；还有 `multica.project`、`multica.agents.{build,verify,decide}`。
5. state.json：条目加 `exec: {backend, issue, agent, branch}`，schema_version +1，旧状态自动迁移（Orca 的 task id 留在 `exec.legacy`）。
6. 测试：仿 fake Orca 写 fake multica CLI。覆盖派工 → in_review → 验收 pass/fail → 返工上限 → 决策批次 → daemon 掉线这几种情况。
7. App / 面板：只改文案（「Orca 终端」改成「Multica issue」，点了打开 Multica 网页里的 issue），JSON 合约不变。

## 5. 在接新后端之前先做：只读体检（交给 Air 上的 Pi）
- 看 `~/.evoloop/projects/EV/state/state.json` 里的 `decide` 和最后 50 行日志：5 次超时卡在哪（Orca 没起来终端？claude 起来了但模型名不认？跑完了没写 worker_done？）。
- 不恢复 autopilot / guard，不改 state.json，只汇报。
- 预期：多半是 Orca 那条执行路径的问题（dsh-tui 不存在、claude 吃不了 group 名）。换成 Multica 之后自然就不走这条路了，但要先确认不是 evo 自己的逻辑 bug。

## 6. 验收标准（Air，EV 项目）
1. `evo -p EV` 用 multica 后端，从一条 README 小任务开始跑完：施工 → 验收 pass → look 闸门推到面板 → 老板批 → 合并。
2. 造一条故意验收不过的，看到返工一次，然后通过。
3. 造一条需要技术决定的，看到决策-Claude 被叫醒，json 决定被执行；在 Magpie 日志里确认请求走的是决策脑。
4. 停掉 multica daemon：evo 推一次「执行端掉线」，不再派工；恢复后能接着跑。
5. 跑完后 Multica 网页上 issue 状态和 evo 面板一致。

## 7. 不做 / 以后再说
- 不拿 Multica 审核替代 evo 闸门。原因：手机上看不到，也没有四类红线。
- 不碰 Mac mini 服务端；TB 要等 Air 上跑顺两周后，按切换清单来接。
- Orca 后端保留不删，等 Multica 后端稳定一个月再决定要不要删。
