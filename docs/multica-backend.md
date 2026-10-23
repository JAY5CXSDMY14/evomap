> 现状说明，不是约束；Claude 审查后可提议修改（决策岗用 `propose`，老板点「做不做」）。

# evo × Multica 派工后端 · 设计稿（第 20 轮）

> 状态：2026-10-22 14:15 老板确认方向；**同日第二十轮代码已写完并推送（ac802ed…，9 个提交，第 8 节），等 Air 按第 6 节验收**。Orca 后端还在，老项目照旧走 Orca。
> 前提：Air 上第二轮 1–9 步全部通过（~/tmp/MULTICA-HANDOFF-2.md，install.sh 已修到 aca3749）。

## 0. 一句话
**Multica 只负责「派人干活、看到干到哪」，Orca 的执行器角色由它接替。排队、闸门、返工上限、找老板、上线，这些还是 evo 管。**
evo 和 Multica 之间只通过 `multica` CLI（加 `--output json`）交互，不 fork、不改服务端。Orca 后端代码保留，但默认关掉。

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
        ⋯ 每个 tick：multica issue list --fields … 看哪个 issue 有动静 → issue get / issue runs / issue comment list --full（CLI 没有 issue show）
        └─ 进 in_review → evo 读施工报告（评论里的 ```json，格式同 report.schema.json）
           └─ multica issue assign EVO-7 --to 验收-Claude（追加验收规格做评论）
              └─ 验收评论 json：pass → evo 走 look 闸门 / 合并 / 上线（照旧在 evo 面板）
                               fail → 返工：round+1，再派施工-DSH（受 2 次决策返工 / 12 次派工 / 6 小时上限约束）
决策批次：evo 每 30 分钟把「escalated / asking」的条目攒成一个 issue「EV 决策批次 mm-dd hh:mm」，派给决策-Claude；
         它的最后一条评论里放 ```json 决定（retry / rework / drop / split / ask_owner / answer / propose），evo 读到后照旧执行。
```
- **闸门不搬过去**：做不做、看效果、上线这几道闸门还在 evo 面板和推送里。Multica 的 in_review 只当「施工做完了」的信号，不算老板批过。
- **合并**：worktree 分支 `agent/dsh/<issue>` 由 evo 合并（用 evo 自己的 clone `~/.evoloop/repos/<code>`），流程和 Orca 时代一样。
- **收件箱**：Multica 的 Inbox 只给老板顺手看，权威入口还是 evo 面板。

## 4. 代码改法（strangler：先抽接口，再一个功能一个 commit 地迁）
1. 抽一个 `Executor` 接口（新文件 `kit/bin/evo_exec.py`）：`ensure_project`、`create(kind, title, spec)`、`assign(task, role)`、`poll(task) → {state, report, branch, last_activity}`、`comment`、`close`、`health`。
2. 现在散在 evo 里的 ~40 处 `orca(...)` 调用收进 `OrcaExecutor`，行为不变，现有 ~300 个测试全过才算这一步完成。
3. 新增 `MulticaExecutor`：只调用 `multica … --output json`，每个调用都有超时（加到 `TIMEOUT_DEFAULTS`）；daemon 或服务端连不上时走现有的 `orca_up` 路径，改名为 `exec_up`（不通就推一次，这一轮不派工）。
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

## 8. 第二十轮实现说明（2026-10-22，代码已推送）
提交：ac802ed（接口，Orca 行为不变）→ 9400b23（MulticaExecutor + exec_up）→ 576210f（配置）→ afca824（state.json 迁移）→ 4884be6（流程）→ 0e8b7e6（假 multica + 测试）→ baa7c5b（面板 / App 文案）→ 之后是两处小修和文档。

**配置（项目 config.json）**
```json
"executor": "multica",
"multica": {"project": "EV", "agents": {"build": "施工-DSH", "verify": "验收-Claude", "decide": "决策-Claude"},
            "app_url": "<Multica 网页地址，可空>", "workspace": "<workspace slug，如 evo>", "issue_url": "{app_url}/{workspace}/issues/{identifier}"}
```
- 没写 `executor` 的老项目一律按 orca 跑（不会因为升级突然换执行端）；`evo new / import` 新建的项目写 `multica`（`--executor orca` 可改；全局配置写了 `executor` 就按全局）。
- 每条 multica 命令的超时：`limits.timeouts.multica`，默认 1 分钟。
- 网页路由带 workspace slug：`{app_url}/<slug>/issues/EVO-13`（10-22 Air 实测，不带会跳 /login）。填 `workspace` 即可，`issue_url` 一般不用改。

**和设计稿不一样、或设计稿没写到的地方**
1. **接口比 7 个动作宽。** 七个动作（ensure_project / create / assign / poll / comment / close / health）都有。内核原来把 Orca 当任务、闸门和收件箱用。返工上限、决策批次、闸门作废都挂在这上面。为了不改这些逻辑，`Executor` 保留了这套编排原语。Multica 后端把任务和闸门记在 `state/exec-multica.json`。这本账和 Orca 的状态一样，不进 state.json。收件箱靠轮询 issue 合成：run 结束就算 worker_done。
2. **派工全是 `issue assign`。** 10-22 决策岗连续 5 次超时的根因是 `orca orchestration dispatch --inject` 派给卡在 Claude 引导页的终端；Multica 后端没有「往已有终端注入」这一步，所有派工（施工、返工、验收、决策批次、工人重启）都是 `issue assign`。
3. **一件一个 issue。** 施工第一次建 issue，正文是任务书和交卷方式。之后返工、验收都在同一个 issue 上。先 `assign --no-start` 换人，再把这一岗的任务书写成评论。评论会叫醒被指派的 agent。留言没叫醒，就再跑一次 `issue rerun`。决策批次每批一个新 issue，交完就标 done。
4. **施工分支取进 evo 的克隆。** 施工交卷后，evo 用 `git fetch <run 的 work_dir> <branch_name>` 把分支取到 `refs/evo/fetch/<件号>`，在自己的克隆里开验收副本 `state/worktrees/<件号>`（分支 `evo/<件号>`）。验收 agent 的评论里会写这个副本的路径；验收指纹、看效果、合并、推送都基于这份副本，和 Orca 时代一样。所以 Multica 项目绑定哪个目录都可以，推荐绑 evo 的专用克隆 `~/.evoloop/repos/<代号>`。
5. **验收结论看评论里的 verdict。** run 成功只说明 agent 跑完了，结论要看最后一条评论的 ```json {"verdict": "pass"|"fail"}```；没写 json 就认「验收通过 / 不通过」这类字样，什么都没写按不通过处理（会用掉一次返工）。
6. **提问。** 施工把 issue 标成 blocked，就算「有提问」，交给决策岗；决策岗的答复照旧随返工送回去。
7. **换执行端。** 老状态读进来时自动升到 schema 2。件加 `exec`，Orca 的任务号进 `exec.legacy`。项目换成 multica 后，第一次 tick 重建没做完的件。任务和闸门都在新执行端重建。施工中、验收中的件退回排队，在 Multica 从头施工。轮次不清零。挂在 Orca 上的上限闸门、外部请求闸门不迁过来。EV 现在没有这类闸门。
8. **掉线判断。** 每一轮先跑 `multica daemon status --output json`，再跑 `multica agent list --output json`。下面三种都算执行端掉线：daemon 停了；服务端连不上（退出码 2）；登录失效（退出码 3）。掉线时推一次「执行端掉线」，这一轮不派工。恢复后接着跑。
9. **轮询的开销。** 每轮先用一次 `issue list --fields id,identifier,status,assignee_id,last_activity_at` 找出有动静的 issue。有动静的才去读 run 和评论。run 失败可能不留评论，也不改活动时间。所以每 5 分钟都细看一次，不管有没有动静。

**还没在真机上确认的（Air 验收时顺带看）**
- 成员留言会不会叫醒被指派的 agent。会的话不用 rerun；不会的话 evo 会补 rerun。如果服务端排队有延迟，可能多跑一次。
- 同一个 issue 返工时，Multica 是复用 `agent/dsh/<issue>` 分支，还是重开一个工作区。两种情况 evo 都按 run 报的分支去取。
- 验收 agent 在自己的工作区里看不看得到施工的改动。所以评论里给了 evo 验收副本的路径，让它直接去读。
- run 的状态值：已知 queued / dispatched / running / waiting_local_directory 是进行中，completed 是成功；其它值一律按失败处理。


## 9. 第二十三轮：施工模型 ≠ 验收模型的保护（issue #15，2026-10-23）
Orca 后端由团队功能包在每次派工时查「撞模型」；Multica 下模型绑在 agent 上，evo 不选模型，这条保护原来是空的。现在补上：

- **什么时候查**：每轮 `exec_up` 通过之后、派工之前（`model_guard_check`），读 `multica.agents.build` 和 `multica.agents.verify` 两个 agent 的模型。
- **怎么读**：先 `multica agent list --output json` 找到这个 agent 的条目，看 `model` 字段（也认 `runtime_config.model` / `config.model` / `settings.model`）；条目里没有再 `multica agent get <id> --output json`。
- **怎么判**：
  | 情况 | 结果 |
  |---|---|
  | 两边模型名相同（去首尾空白、不分大小写） | 停派施工 / 验收，推一次「施工和验收撞模型」 |
  | 施工、验收配成同一个 agent | 停（放行开关也不管用） |
  | 模型名不同 | 照常派 |
  | 有一边读不到 | 默认停，推一次「没法确认施工和验收用的是不同模型」；项目配置写 `"multica": {"allow_unverified_models": true}` 才放行（只认 JSON 的 true），放行时只记日志不推 |
- 停的时候件显示「等换模型」，`evo status` 多一行「停派施工 / 验收：原因」，`status --json` 多一个字段 `model_guard`（ok / code / why / build / verify / at）。改好后下一轮自动接着派，同一个原因只推一次。决策岗不受影响。
- **假设**：magpie 组名（`group/evo-build` 和 `group/evo-verify`）和档位名（`sonnet`、`fable`）这里展不开成员，名字不同就按「不同」算。组里实际成员重叠时看不出来。

**真机待核实（Air）**
1. `multica agent list --output json` / `agent get <id> --output json` 里模型字段到底叫什么（假 multica 用 `model`，文档 multica.ai/docs/cli 只写了 create/update 有 `--model`）。
2. 施工-DSH 的模型如果只在 daemon 环境变量 `MULTICA_DSH_MODEL` 里设、agent 上没填 model，evo 会读不到 → 默认停派工。真机上要么在 agent 上填 model，要么显式写 `allow_unverified_models: true`。
3. agent 上模型留空时（用 runtime 默认），list 返回的是空字符串、null 还是没有这个键——三种 evo 都按「读不到」处理。

