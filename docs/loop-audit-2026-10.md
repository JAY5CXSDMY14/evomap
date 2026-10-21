---
template: doc
title: evo 整套循环体检 · 2026-10
subtitle: 第十五轮之后，按一件事的生命周期逐段查漏洞、卡点和可优化处
lang: zh
source: kit 第十五轮（069d8c5）
---
本轮只读：没改任何代码。读了 kit/README.md 各轮、kit/bin/evo 和 evo_*.py、roles、templates、install.sh、contract-v2、presets、profiles/tubu 与 st、docs（loop-topology、optimization-review、agent-interface、model-coordination 等）、notes/decisions.md、app/README.md 和 App 调用 evo 的代码。optimization-review 里 B1–B5、C6–C9、D10–D11 已修，本文不重复。

能跑的都跑了：用 kit/tests 的假 Orca 夹具写了 4 段复现脚本（见文末附录），其中 4 条问题已实测复现。各测试文件单独跑都是绿的，但在 2 核沙箱里每个文件要 80 秒或更久，全套无法在 2 分钟里跑完（见 L-28）。

## A 结论
```callout warn 主路径没问题，卡点在「常驻 + 真 Orca + 真网络」三处
单元测试查的是「一轮 tick 做对没有」，高危问题都在测试没模拟的地方。

- 常驻进程不放锁
- 有人绕过 evo 在 Orca 里结闸门
- 一条坏消息让项目每轮崩溃
- 远端主线红了误伤在途的件
- 外部命令没有超时

前 4 条已用假 Orca 复现。
```

| 严重度 | 条数 | 其中确定的 bug | 其中真机才能验证 |
|---|---|---|---|
| 高 | 7 | 6 | 1（L-07） |
| 中 | 14 | 11 | 3（L-09、L-10、L-21） |
| 低 | 9 | 9 | 0 |

字段说明：**环节**按生命周期（来源→issue→调度→施工→验收→决策→闸门→部署→回滚→通知→早报）或横向主题；**证据**写 `文件:行`（行号以 069d8c5 为准）或复现脚本；**工作量** S ≤ 半天、M ≈ 1 天、L ≥ 2 天；**拍板**只在删数据、线上变更、花钱、产品体验时写「要」。

## B 高严重度（7 条）

### L-01 单项目常驻时锁永远不放，所有写命令卡死
- **类型**：确定的 bug（已实测）
- **环节**：并发与锁 / 老板闸门 / App 接口
- **现象**：只登记了一个项目时，`evo run` 自动选中它，在本进程里循环（不走子进程）。`load()` 第一次调用 `lock()` 拿到 `flock` 后从不释放，进程不退出锁就一直在。之后 `evo approve`、`add`、`feedback --item`、`retry`、`ship`、`status`、面板写接口、Telegram 按钮、App 的通过/打回全都无限等待。现在 Mac mini 上很可能只有 TB 一个项目，正好命中。
- **证据**：`kit/bin/evo:208-216`（lock 只加不放）、`kit/bin/evo:2993-3002`（单项目分支在本进程里循环）。复现 `t_lock.py`：后台起 `evo run --every 2`，再跑 `evo -p TB add …`，15 秒仍卡住。
- **附带问题**：这个分支里配置只在启动时读一次（`CFG`、`_UI`、`_ARCH` 缓存）。面板和 App 改的模型、目标、预设，要等常驻进程重启才生效。这和文档写的「下一次派工生效」不符。
- **修法**：`cmd_run` 一律每轮起子进程 `evo -p <代号> once`（多项目分支已有现成写法）。锁随子进程退出自动释放，配置每轮重新读。另外把 `lock()` 改成上下文管理器，`cmd_tick` 结束就释放。补测试：起常驻，同时 `approve` 必须在 5 秒内返回。
- **工作量**：S
- **拍板**：不用

### L-02 只读命令也抢写锁：tick 期间 App、面板、bot 读不到状态
- **类型**：确定的 bug
- **环节**：App 与 evo 接口 / 可观测性
- **现象**：`evo status --json` 走 `load()`，要拿写锁；tick 里含整套测试（合并前、推送前、建上线闸门都跑），一轮可能十几分钟。这段时间 App（status 超时 60 秒）显示「evo 跑不起来」，面板空白，Telegram bot 的 `gate_options` 读不到闸门，回「已经处理过或不存在」。项目处于 `PAUSED` 时 `load()` 直接退出，status 报错，老板正需要看的时候反而看不到。`cmd_status` 还会调 `coord()`，Orca 里协调终端没了就顺手新建一个：读命令有副作用。
- **证据**：`kit/bin/evo:3487-3492`、`kit/bin/evo:219-223`（PAUSED 直接退出）；App 侧 `app/Sources/Evo/AppState.swift:179`（timeout 60）；bot 侧 `kit/bin/evo_notify.py:375-382`。`read_state_ro()` 已存在（`kit/bin/evo:2713`），只给了 `log` 用。
- **修法**：`status`、`digest` 打印、bot 查闸门全部改用 `read_state_ro()`；闸门列表用 `s["coord"]` 只读查询，查不到就标 `gates_stale: true`，不新建终端。status JSON 加 `paused`（原因文本）和 `tick_running`（锁被占且持有多久），schema 仍为 1，只加字段。App 收到 `paused` 显示「暂停：原因」，不显示出错。
- **工作量**：S–M
- **拍板**：不用

### L-03 绕过 evo 结的闸门，evo 不看结果：打回照样合并
- **类型**：确定的 bug（假 Orca 实测；真 Orca 解锁规则待真机确认）
- **环节**：老板闸门 / 部署 / 密钥与权限
- **现象**：evo 只在 `evo approve` 里处理闸门的选择。老板在 Orca 手机 App 上点（README 第 4 步就让老板配手机），或者工人自己调 `orca orchestration gate-resolve`，Orca 只是把闸门结掉、任务解锁，evo 不读结果：
  - 看效果点「打回」→ 合并任务变 ready → evo 照常合并并推送（实测：状态 merged、已推送）。
  - 做不做点「不做」→ 施工任务变 ready → evo 照常开工。
  - 上线闸门点「上线」→ evo 什么也不做，件上的 `ship_gate` 一直留着，`ship_batch` 永远不再收这些件，`merged` 是安静状态也不查活路：从此卡在「可收菜」。
  - 施工、验收工人跑在同一台机器上，能调 orca 命令，被不可信 issue 注入后可以自己批自己的看效果闸门。
- **证据**：`kit/bin/evo:1966-1968`（verified 且合并任务 ready 就合并，不核对是谁、选了什么）、`kit/bin/evo:1969-1971`（只认施工任务 failed 才算不做）、`kit/bin/evo:3699-3705`（已挂 ship_gate 的件不再入批）；假 Orca `kit/tests/fakes/orca:49-54`（任何结果都解锁）。复现 `t_phone.py`。
- **修法**：
  1. 合并前置条件：看效果件必须有 `it["look_ok"] == 当前 look 闸门号`，只在 `cmd_approve` 选「通过」时写入（L-16 防住工人冒充之后）。
  2. 每轮读 `gate-list` 的 `resolution`：发现没经过 evo 就结掉的闸门，按拍板规则处理。「打回」→ 照 approve 打回流程走（原话写「手机端打回，未写原因」）；「不做」→ drop；「上线」或「通过」→ 见拍板。处理完记时间线 `gate_external`。
  3. 上线闸门在 Orca 被结掉而 evo 没处理时，清掉件上的 `ship_gate`，让下一批能重新收。
  4. 补测试：手机端打回、手机端不做、手机端上线三条。
- **工作量**：M
- **拍板**：**要**（产品体验 + 线上）。问题：Orca 端点「通过 / 上线」算不算数？推荐：打回、不做照办；通过、上线不自动执行，推一条「请在 Telegram / App / 面板确认」，因为工人也能调 orca 命令。

### L-04 一条消息处理出错，整个项目每轮崩（毒消息）
- **类型**：确定的 bug（已实测）
- **环节**：崩溃、重启、重复投递幂等 / 施工 / 验收
- **现象**：`cmd_tick` 先 `handle_msg()`，成功后才把消息号记进 `msg_seen`。`handle_msg` 里只要抛异常，这条消息就不会记成已处理。例如 git 读不到工作区、未跟踪文件冲突、Orca 字段缺失。下一轮重投、再崩，循环不会结束，心跳也停。真 Orca 的消息若没有 `id` 字段（README 列为待验），重投直接复现：合并后工作区已删，重投的「验收通过」去跑 `git rev-parse`，每轮抛 RuntimeError。另外 `handle_msg` 不核对消息属于哪一次派工、件当前是什么状态：一条迟到的「验收通过」能把已合并的件改回 `verified`。
- **证据**：`kit/bin/evo:1810-1820`、`kit/bin/evo:1894`（验收通过分支不看状态）、`kit/bin/evo:1966-1968` 里 `merge_one` 也没有异常隔离。复现 `t_noid.py`（去掉消息 id + 确认丢失）：第 2 轮起 tick 每次退出码 1，报 `cannot change to …/worktrees/ab-fix-001`。
- **修法**：
  1. 每条消息套 `try/except`：出错也记进 `msg_seen`。
  2. 同时写时间线 `msg_error`（含异常摘要），交决策岗一次，再处理下一条。
  3. 只接受「本次派工」的回报：`worker_done` 必须满足 `tid == it[role]` 且状态是 `building` / `verifying`，否则记 `msg_stale` 后丢弃。
  4. 没有消息号时用 `(task_id, type, outcome, body 的 sha1)` 生成替代号去重。
  5. `merge_one`、`do_push` 按件套异常隔离，失败的件转 `escalated` 并写明原因，不影响别的件和心跳。
- **工作量**：S–M
- **拍板**：不用

### L-05 远端主线红了，在途的件全被当成自己的错返工
- **类型**：确定的 bug（已实测）
- **环节**：合并 / 推送 / 成本
- **现象**：别人往远端推了一个让测试变红的提交（或者「并入远端后测试红」）。`do_push` 已把远端合进本地 main，测试红就停在那，每 30 秒重试一次，每次重跑全量测试，没有退避。之后每件合并前在本地 main 上测试都是红的，被判「合并前测试不绿 → 自动返工」。任务书还叫施工「把测试修绿」，施工只能越界改别处或空转。2 轮后交决策岗。
- **证据**：`kit/bin/evo:663-677`（并入远端、测红留标记、每轮重测）、`kit/bin/evo:612-617`（合并前测红一律算本件返工）。复现 `t_red.py`：远端带红后，新登记的 AB-FIX-002 返工 3 轮进 escalated，日志「推送未成」13 次。
- **修法**：
  1. 合并前测红时，先在当前 main（不含本件）上跑一次，按 main 的提交号缓存结果。
  2. main 本身就红：本件进「等主线修绿」，不算轮次、不返工。
  3. 全项目只登记一件 `OPS` 修主线，推一次 `main_red`。
  4. 推送重试按远端提交号去重：远端没变、本地没变，就不再重跑测试；失败间隔 1、2、4…最长 30 分钟。
  5. `waiting` 加 `main_red`，App 和面板显示「等主线修绿」。
- **工作量**：M
- **拍板**：不用

### L-06 外部命令几乎都不设超时，一处卡住全机停
- **类型**：确定的 bug
- **环节**：长时间卡住检测 / 多项目互相影响
- **现象**：只有 `orca()` 设了 120 秒超时，而且超时抛的 `TimeoutExpired` 不是 `SystemExit`，单项目常驻循环接不住，进程直接退出（靠 launchd 拉起）。`git`（含 fetch）、`gh`、`test_cmd`、`push_cmd`、`deploy_cmd`、多项目常驻里每个项目的 `once` 子进程都不设超时。一套测试卡住 → 全局 `SUITE_LOCK` 被占 → 所有项目的合并、推送都在等；多项目循环是串行的，一个项目卡住别的项目也不转。看门狗能发现「停了」，但没有任何自动恢复。
- **证据**：`kit/bin/evo:195`（orca 超时未捕获）、`:423-427`（git）、`:700-711`（run_suite 持锁无超时）、`:657`、`:679`、`:3669`、`:2988`（once 子进程）。
- **修法**：加 `limits.timeouts`（建议默认：test 30 分钟、git 网络 3 分钟、git 本地 1 分钟、gh 1 分钟、push 5 分钟、deploy 20 分钟、单项目一轮 45 分钟）。统一用 `start_new_session=True` 起子进程，超时就杀整个进程组。`orca()` 捕获 `TimeoutExpired` 和 `FileNotFoundError` 并转成 SystemExit。超时按「这一步失败」处理：测试超时算红，推送超时算推送未成，once 超时记一次并推送 `tick_timeout`。
- **工作量**：M
- **拍板**：不用

### L-07 TB 的 fetch 不走代理，国内直连 GitHub 推不上去
- **类型**：真机才能验证的风险（代码事实确定，影响看 Mac mini 网络）
- **环节**：推送
- **现象**：土布的 `push_cmd` 自带 `HTTPS_PROXY=socks5h://127.0.0.1:1082`，说明直连 GitHub 不通；但 `do_push` 在推送前先跑一句不带代理的 `git fetch origin`，失败就算推送未成，每轮重试，第 3 次推送「推送连续失败」；没有超时时还可能直接挂住（叠加 L-06）。`gh` 命令同样只认常驻进程的环境变量。
- **证据**：`kit/profiles/tubu/project.json`（push_cmd）、`kit/bin/evo:657`。
- **修法**：项目配置加 `git_env`（例如 `{"HTTPS_PROXY": "socks5h://127.0.0.1:1082"}`），所有 git 网络操作和 gh 调用都带上；或在 `evo import` 时检测 push_cmd 里的代理，提示写进仓库的 `http.proxy`。`evo doctor`（见 L-19）里加一项「fetch 能不能通」。
- **工作量**：S
- **拍板**：不用

## C 中严重度（14 条）

### L-08 决策岗批次自己卡住没人管
- **类型**：确定的 bug
- **环节**：决策岗 / 长时间卡住检测
- **现象**：决策岗任务一直处于 `dispatched`（工人挂了或在等权限弹窗），`decider_wake` 每轮看到「上一批没做完」就直接返回，永远不再叫；`live_path` 又把「决策岗正在看」算成有活路，不报警。`check_stalls` 只管施工和验收。结果：所有交决策岗的件悄无声息地停住。
- **证据**：`kit/bin/evo:1715-1719`、`:2404-2406`、`:2053-2056`。
- **修法**：`limits.decide_timeout_minutes`（默认 45）：超时就关终端、任务标 failed、记 `decider_timeout`、推一次「决策岗卡住」，`decide.last` 清零让下一轮重叫；同一批连续超时 2 次再转老板。决策岗工人也走 `worker-show` 死活检查。
- **工作量**：S
- **拍板**：不用

### L-09 Orca 重启或协调终端丢失后，在途任务可能全部变成孤儿
- **类型**：真机才能验证的风险
- **环节**：Orca 消息丢失 / 崩溃重启
- **现象**：`coord()` 发现协调终端不在了就新建一个，再 `run-create` 一个新 run。若真 Orca 的 `task-list --from` 按终端或 run 隔离，旧任务全查不到，所有件变 `task_dead`；30 分钟后每件各进一次「没有活路」，决策岗被逐件叫去返工，浪费一整轮额度。旧终端收件箱里没确认的回报也丢了。假 Orca 的 task-list 不分 run，测不到。
- **证据**：`kit/bin/evo:430-439`；`kit/tests/fakes/orca`（task-list 返回全部任务）。
- **修法**：状态里记 `run_id`。重建协调终端后，先核对已知任务号能否查到。查不到就整项目 `PAUSED`（写清原因）并推一次，不让无活路检查逐件报警；查得到就继续。真机上按 README 第 15 节补测「关掉 Orca 再打开」。
- **工作量**：M
- **拍板**：不用

### L-10 Orca 丢了 worker_done 时不对账
- **类型**：真机才能验证的风险
- **环节**：Orca 消息丢失 / 施工 / 验收
- **现象**：工人已经交卷，Orca 里任务是 `completed` / `failed`，但回报消息没送到 evo。evo 仍认为在施工：15 分钟后推「疑似卡住」，`check_stalls` 看到任务已完成就不重启，30 分钟后进「没有活路」交决策岗。活其实已经做完。
- **证据**：`kit/bin/evo:2071-2087`。
- **修法**：`check_stalls` 发现任务已是 completed / failed，但本次派工的回报没处理过。这时用 `task-show` / `dispatch-show` 取结果正文，合成一条消息走 `handle_msg`（受 L-04 的派工核对保护），时间线记 `reconciled`。
- **工作量**：S–M
- **拍板**：不用

### L-11 交决策岗可以无限循环，用量只提醒不拦
- **类型**：确定的 bug
- **环节**：决策岗 / 成本与用量
- **现象**：`decide_rework` 每次把轮次清零，次数只记不限；施工 2 轮不过 → 决策岗返工 → 再 2 轮 → 再交决策岗……没有尽头。`usage_abnormal` 每件只推一次，推完照跑。optimization-review E 段「每件时长、轮数硬上限」至今没做。
- **证据**：`kit/bin/evo:2181-2188`、`:1016-1029`。
- **修法**：`limits.decider_reworks`（默认 2），超了自动转 `ask_owner`；`limits.item_hard_runs` / `item_hard_minutes`（默认 0 = 关）：超了把件转「等你：继续还是不做」闸门，不再派工。
- **工作量**：S
- **拍板**：**要**（花钱）。推荐：决策岗返工最多 2 次后转老板；单件派工超过 12 次或工人累计 6 小时，暂停等老板点「继续」。

### L-12 上线批次和实际部署的代码不一致，也没有回滚
- **类型**：确定的 bug（TB 现在 `deploy_cmd` 为空，暂不触发）
- **环节**：部署 / 回滚
- **现象**：上线闸门建好时记的是一批件，`deploy_cmd` 却在主工作区当前 HEAD 上跑。闸门建好后才合并的件会一起上线，本地已合并、未推送的件也会。可是只有闸门里的件标「已上线」，其余件留在「可收菜」，下一批再「上线」一次。整个流程没有 `rollback`：上线后发现坏了，只能手动处理。TB 的 `deploy_cmd` 是空字符串，点「上线」只是改标签。
- **证据**：`kit/bin/evo:3699-3716`（建闸门不记提交号）、`:3660-3682`（在 `CFG["repo"]` 里跑 deploy_cmd）。
- **修法**：建上线闸门时记 `ship_sha`（要求等于已推送的远端提交）；部署时在临时 worktree 里检出这个提交，传环境变量 `EVO_SHIP_SHA`；部署成功后把提交号是 `ship_sha` 祖先的件全部标已上线。加可选的 `rollback_cmd` 和 `evo rollback [批次]`（同样走老板闸门），以及可选的 `healthcheck_cmd`（失败只推送，回不回滚由老板点）。
- **工作量**：M
- **拍板**：**要**（线上变更），可以等 TB 真有部署时再定；推荐先只做 `ship_sha`，回滚做成老板手动点。

### L-13 推送会丢：通道都失败不重试，早间汇总先删后发
- **类型**：确定的 bug
- **环节**：推送通知 / 早报
- **现象**：`deliver()` 里 Telegram 和邮件都失败（代理断、SMTP 挂），事件只剩 outbox，没人再发。`flush_digest()` 先删 `held` 文件再发送，发失败时整夜攒的事件全部丢失。每个闸门只提醒一次（`gate_pushed`）。那次没送到或老板没看到，就再也不提醒。闸门越堆越多，最后只触发「等你超过 5 件暂停新施工」。
- **证据**：`kit/bin/evo_notify.py:173-187`、`:240-276`；`kit/bin/evo:1694-1705`。
- **修法**：加 `retry.jsonl` 队列：投递失败的要推事件按 1、5、30 分钟重试，超过 6 小时并进下一次汇总；`held` 改成发送成功后再删（失败就改名回去）。闸门提醒分级：5 分钟、2 小时，之后每天早报再带一次；暂停新施工时单独推一次「等你的已有 N 件，新施工已暂停」。
- **工作量**：M
- **拍板**：不用

### L-14 早报承诺和实现不符
- **类型**：确定的 bug（文档与行为不一致）
- **环节**：早报
- **现象**：loop-topology E 段写「8:30 Telegram 晨报：等你 1 件，可收菜 2 件」。实际 08:30 只在夜里攒了要推的事件时才发；夜里平静就没有早报。23:30 的晚间汇总 `digest_nightly` 不在要推的类型里，只走邮件。老板每天早上得不到一条固定的总览。
- **证据**：`kit/bin/evo_notify.py:242`（没有 held 文件直接返回 0）、`kit/bin/evo:2899-2903`、`docs/loop-topology.md` E 段。
- **修法**：08:30 固定发一条「早报」，全部项目合起来。内容：等你点头的件和按钮、可收菜、卡住或没活路、昨日合并数、额度暂停。再附夜里攒下的事件；全空就不发。复用 `status_doc`，不另写统计。
- **工作量**：S–M
- **拍板**：不用（发送时间和内容沿用已批的 08:30 汇总）

### L-15 主动暂停也会被报「接棒器停了」
- **类型**：确定的 bug
- **环节**：可观测性 / App 接口
- **现象**：App 的「暂停循环」是 `launchctl bootout` 掉常驻进程。`evo bot` 里的看门狗和 App 自己调的 `evo watchdog` 不知道这是主动暂停，10 分钟后推「接棒器停了，看看常驻进程、Orca 和 Mac 是否睡着」。项目因状态损坏 `PAUSED` 时也报同一句话，原因说错。
- **证据**：`kit/bin/evo:3761-3786`；`app/Sources/Evo/Shell.swift:132-141`、`AppState.swift:230`。
- **修法**：加 `evo pause [--all|-p 代号] [原因]` / `evo resume`，写 `~/.evoloop/PAUSED` 或项目 `PAUSED`；App 的暂停改为调用它（再 bootout 也行）。看门狗跳过暂停中的项目，status 里给出暂停原因；项目 `PAUSED` 时看门狗的消息写明原因。
- **工作量**：S
- **拍板**：不用

### L-16 工人能冒充老板：EVO_AGENT 只是约定
- **类型**：确定的 bug（被利用要靠提示词注入，属于真机风险）
- **环节**：密钥与权限
- **现象**：施工、验收、决策工人跑在 Orca 终端里，环境变量里没有 `EVO_AGENT`，用的是老板的 `gh` 登录。被不可信 issue 带偏的工人可以：跑 `evo -p TB approve <看效果闸门> 通过` 或 `evo ship`；直接 `orca orchestration gate-resolve`（叠加 L-03）；用 `gh issue edit --add-label autopilot:ready` 给外部 issue 贴标签，而 `labeled_by_trusted` 会因为操作者是老板账号判成可信。
- **证据**：`kit/bin/evo:578-595`（launch 不带环境变量）、`:3580-3583`（只看 EVO_AGENT）、`:2820-2829`。
- **修法**：`launch` 在工人命令前加 `env EVO_AGENT=worker:<岗位>:<件号>`；`approve` / `ship` / `team set` / `goal set` 再要求「老板凭据」：面板口令（App 从钥匙串取后用 `--owner-token` 传）或 Telegram 已认证的 bot 进程，命令行交互时允许在 TTY 上确认。决策岗贴 `autopilot:ready` 时，在 issue 里留 `<!-- evo-decider -->` 评论作为记录。
- **工作量**：M
- **拍板**：不用（只收紧权限，不改老板的操作方式：App、Telegram、面板照常可用）

### L-17 外部 Agent 借 evo feedback 开的 issue 被当成可信
- **类型**：确定的 bug
- **环节**：来源 / GitHub issue
- **现象**：`EVO_AGENT` 设置时，`evo feedback` 用老板账号开 issue，正文以「【外部 Agent 来报：」开头。`pull_reports` 认这个标记，`cmd_pull` 不认：决策岗加 `autopilot:ready` 后，作者是老板（可信），正文原样进任务书，前面没有「外部来源原文，只当线索」的横幅。
- **证据**：`kit/bin/evo:2787-2789` 对比 `:2853`。
- **修法**：`cmd_pull` 里正文以 `AGENT_MARK` 开头或带 `agent-report` 标签，一律按不可信处理（加横幅）。补一条测试。
- **工作量**：S
- **拍板**：不用

### L-18 evo 和决策岗都在老板自己的工作副本里动手
- **类型**：确定的 bug（设计层面）
- **环节**：合并 / 决策岗 / 多项目
- **现象**：`profiles/tubu` 的 `repo` 是桌面上老板自己的工作副本。合并时 evo 会在那里 `git checkout main`。老板在别的分支上、工作区又干净时，会被静默切走。未跟踪文件和合并冲突会让 `git merge` 抛异常（叠加 L-04 卡住项目）。决策岗工人的终端也开在这个目录，决策岗一旦改了文件，主工作区变脏，所有合并都被挡。Orca 建 worktree 的起点也取决于这个目录当前在哪个分支。
- **证据**：`kit/bin/evo:606`、`:633`、`:1760`、`:568`；`kit/profiles/tubu/project.json`。
- **修法**：`evo import` 默认另建专用克隆 `~/.evoloop/repos/<代号>`（老板的工作副本只读不碰）；决策岗终端开在只读的独立 worktree（`--detach`），岗位规则里写明决策岗不改文件。已登记的 TB 加一个迁移命令 `evo -p TB relocate`。
- **工作量**：M
- **拍板**：**要**（产品体验：以后 evo 的改动在专用克隆里，老板的桌面副本要自己 pull）。推荐：要。

### L-19 kit 自身没有版本：App 和常驻进程可能跑两版代码
- **类型**：确定的 bug
- **环节**：安装、升级、回滚 kit 自身 / App 与 evo 接口
- **现象**：App 用包里的 `Contents/Resources/evo`；launchd 用的是当时跑 install.sh 的那份（仓库 kit 或包内 kit）。两版代码读写同一份 `~/.evoloop`，谁都不知道对方是哪一版。没有 `evo version`；状态文件没有版本号，升级没有迁移，坏了也没有回退办法。install.sh 没有把看门狗装成定时任务，它只在 `evo bot` 里跑。bot 只在设了 Telegram 变量时才装，所以没配 Telegram 就没有看门狗。README 里提到的 StartInterval 300 并不存在。
- **证据**：`app/Sources/Evo/Shell.swift:17-37`；`kit/install.sh:103-133`（只装 autopilot 和可选 bot）；`grep -n version kit/bin/evo` 只有 status 的 schema_version。
- **修法**：加 `kit/VERSION`，`evo version --json`，status JSON 里加 `kit_version` 和 `kit_path`；App 发现和常驻进程版本不一致就提示「用包里的版本重装常驻」。状态加 `schema` 字段，读到更高的版本就拒绝写入。install.sh 增加 `com.evoloop.watchdog`（StartInterval 300，不依赖 Telegram）。加 `evo doctor`：一次查 python、git、gh 登录、fetch 能不能通、Orca、magpie、launchd 三个常驻、版本是否一致。
- **工作量**：M
- **拍板**：不用

### L-20 拉取入口出错会拖垮整轮，gh 失效时没有提醒
- **类型**：确定的 bug
- **环节**：来源 / GitHub issue
- **现象**：`cmd_once` 先 `cmd_pull` 再 `cmd_tick`。gh 输出不是 JSON（网络错误页、限流）时，`json.loads` 抛 ValueError，本轮的合并、推送、心跳都不做。反过来，gh 登录过期时 `stdout` 为空，`json.loads("[]")` 正常返回，入口安静地什么都拉不到，没有任何提醒。
- **证据**：`kit/bin/evo:2978-2981`、`:2766-2771`、`:2350`、`:2825`。
- **修法**：`cmd_pull` 整体包在 try 里；检查 `returncode`，失败计数，连续 3 轮失败推一次 `intake_down`（恢复后记 `intake_up`）；`cmd_tick` 无论 pull 成败都要跑。
- **工作量**：S
- **拍板**：不用

### L-21 停滞阈值 15 分钟对真模型偏短
- **类型**：真机才能验证的风险
- **环节**：施工 / 长时间卡住检测 / 推送通知
- **现象**：`idle` 只看收到的消息。若真 Orca 不替工人发心跳，任何超过 15 分钟的施工都会被推「疑似卡住」；`live_path` 把 stalled 算成没有活路，30 分钟后又交决策岗。白天会频繁打扰老板。
- **证据**：`kit/bin/evo:2066`、`:2082-2085`、`:2381-2382`。
- **修法**：先在真机确认 Orca 心跳频率。不管有没有心跳，都把「终端输出在变」算作活着（每轮对 `terminal_tail` 取哈希，变了就刷新 `last_seen`）；默认 `stall_minutes` 改 30。
- **工作量**：S
- **拍板**：不用

## D 低严重度（9 条）

| 编号 | 环节 | 现象 | 证据 | 修法 | 工作量 |
|---|---|---|---|---|---|
| L-22 | 日志与可观测性 | `s["log"]` 只留 200 行，推送失败每 30 秒一行就能刷满；夜审和晚间汇总按 `s["log"]` 取当天事件会漏。`state/logs`、`outbox.jsonl`、`timeline.jsonl`、`~/.evoloop/logs/*.log` 都没有轮转 | `kit/bin/evo:248`、`:2890-2893`、`:2910-2912` | 夜审和汇总改读 timeline；同一句日志连续重复只记次数；日志按天轮转，保留 14 天 | S |
| L-23 | 来源 | `gh issue list --limit 50`：已登记、没上线的 issue 仍开着且带 `autopilot:ready`，超过 50 件后新 issue 永远拉不到 | `kit/bin/evo:2766-2767` | 登记后贴 `evo:registered` 标签，查询加 `-label:evo:registered`；或分页 | S |
| L-24 | 推送通知 | bot 打回后等原话没有过期，几小时后随手一句话会被当成原话；`run_evo` 超时抛异常让 bot 进程退出，那次按钮丢失也没回话 | `kit/bin/evo_notify.py:361-366`、`kit/bin/evo:3405-3407` | 等原话 10 分钟过期；捕获超时，回「evo 正忙，稍后再点」 | S |
| L-25 | 老板闸门 | 自动收菜在 08:20 遇到主线红就当天不再试（先写了 `auto_ship_day`） | `kit/bin/evo:3729-3735` | 只有建成闸门或「已有闸门」时才记当天 | S |
| L-26 | 并发 | App「立即 tick」和常驻进程同时转不同项目时，`other_projects_load` 不加锁，整机施工上限可能多 1 | `kit/bin/evo:1938-1940` | 整机施工名额用 `~/.evoloop/slots.lock` 分配 | S |
| L-27 | 施工 | 模型写成单个 magpie 组名时，返工「换一个施工模型」不起作用 | `kit/bin/evo:557-563` | 文档写明；或返工时改用卡片的 fallback | S |
| L-28 | 测试覆盖 | 2 核沙箱单个测试文件要 80 秒或更久，全套约 220 个无法在 2 分钟内跑完；没有并行 | 本次实测（`/tmp/pt/*.log`） | 加 pytest-xdist；把慢的端到端测试标 `slow`，提交前先跑快集 | S |
| L-29 | 崩溃安全 | `save()` 写临时文件不 fsync，断电后可能出现空文件，被判损坏进入暂停 | `kit/bin/evo:238-243` | `flush` + `os.fsync`；保留 `state.json.prev`，损坏时先自动用上一版并推送 | S |
| L-30 | 来源 | 拓扑图里的「CI 与线上报警 → issue」还没有接入代码 | `docs/loop-topology.md` B 段 | 加 `evo intake ci --run <url>` 或 GitHub Actions 失败时用 `gh issue create` 贴 `type:ops` | S–M |

## E 测试覆盖缺口
```callout info 假 Orca 是同步的，所以「时序」一类问题都测不到
假 Orca 在 dispatch 时同步跑完假工人，回报在同一轮就到；任何闸门结果都解锁；task-list 不分 run；消息都有 id。下面这些只在假 Orca 下测过，或完全没测。
```

| 场景 | 现状 | 建议补的测试 |
|---|---|---|
| `evo run` 常驻循环（单项目 / 多项目） | 没有测试 | 起常驻，同时 approve / status 必须在 5 秒内返回（L-01、L-02） |
| 绕过 evo 结闸门 | 没有测试 | 手机端打回、不做、上线（L-03） |
| 消息无 id、毒消息、迟到消息 | 只测了有 id 的重投 | 去掉 id + 不确认；handle_msg 抛异常（L-04） |
| 远端主线红 | 只测了远端前进后测绿 | 远端带红提交（L-05） |
| 外部命令超时 | 没有测试 | 假 test_cmd `sleep 999`、假 gh 挂住（L-06） |
| 协调终端丢失、Orca 重启 | 没有测试 | 假 Orca 加「按 run 隔离」开关（L-09） |
| 回报丢失、对账 | 没有测试 | 假 Orca 加「丢消息」开关（L-10） |
| 推送通道失败重试、汇总发送失败 | 只测了成功路径 | http 返回 500（L-13） |
| App 与 evo 版本不一致 | 没有测试 | `evo version --json` 契约测试（L-19） |
| 工人时序（交卷与 tick 并发） | 假工人同步，测不到 | 假 Orca 加「延迟到下一轮再送」开关 |
| kit 测试在 macOS 上跑 | kit-tests 只跑 ubuntu | kit-tests 加 macos-14（optimization-review E 段旧项） |

## F 建议下一轮做的 8 条
```callout ok 先保证「不卡死、不误合并」，再做「不误伤、不白跑」
按顺序做，每条配复现测试（附录的 4 段脚本可以直接改成 pytest）。前 4 条都是 S 到 M，一天内能做完。
```

| 顺序 | 编号 | 一句话 | 工作量 |
|---|---|---|---|
| 1 | L-01 | 常驻进程每轮起子进程，锁随一轮释放 | S |
| 2 | L-02 | status 和查闸门改只读，不抢锁；status 给出暂停原因 | S–M |
| 3 | L-04 | 每条消息异常隔离，只认本次派工的回报 | S–M |
| 4 | L-03 | 合并前核对老板是否真的点了通过；读 Orca 闸门结果（先等拍板） | M |
| 5 | L-06 + L-07 | 外部命令加超时；git 和 gh 带项目代理 | M |
| 6 | L-05 | main 本身红就不算本件返工；推送重试退避 | M |
| 7 | L-08 | 决策岗批次超时重叫 | S |
| 8 | L-20 | 拉取出错不拖垮整轮，gh 失效推提醒 | S |

紧接着做：L-16（工人冒充老板）、L-13（推送重试）、L-19（版本和看门狗常驻）、L-14（固定早报）。

## G 需要老板拍板（3 个，附推荐默认）

| # | 问题 | 推荐默认 | 关联 |
|---|---|---|---|
| 1 | Orca 手机端点「通过 / 上线」算不算数？ | 打回、不做照办；通过、上线不自动执行，推一条请在 Telegram / App / 面板确认（工人也能调 orca 命令） | L-03、L-16 |
| 2 | evo 改用专用克隆，不再动桌面上的工作副本？ | 要。以后 evo 的改动在 `~/.evoloop/repos/TB`，老板的桌面副本自己 pull | L-18 |
| 3 | 给每件设硬上限？ | 决策岗返工最多 2 次后转老板；单件派工超过 12 次或工人累计 6 小时就暂停，等老板点「继续」 | L-11 |

回滚上线（L-12）等 TB 真配了 `deploy_cmd` 再问。

## H 附录：复现脚本（放在 kit 目录下运行）
4 段脚本都用 `kit/tests/conftest.py` 的 `Loop` 夹具（假 Orca、临时仓库、裸远端），本次放在沙箱 `/tmp/audit/`，没有提交。要点如下，可以直接改成 pytest：

- **t_lock.py（L-01）**：只建一个项目 TB，后台 `evo run --every 2`，8 秒后 `evo -p TB add …` 设 15 秒超时 → 超时。
- **t_phone.py（L-03）**：建 `--look` 件，跑到 verified，用假 orca `orchestration gate-resolve --id <看效果闸门> --resolution 打回`，再 tick 3 次 → 件为 merged 且已推送。
- **t_noid.py（L-04）**：PATH 前面放一个包装 orca，把 check 结果里的消息 `id` 去掉，并设 `FAKE_ORCA_NO_ACK=1` → 第 2 轮起 tick 退出码 1（`cannot change to …/worktrees/…`）。
- **t_red.py（L-05）**：`test_cmd="test ! -f BROKEN"`，从另一个克隆往远端推一个带 BROKEN 文件的提交；登记第一件后跑 5 轮，再登记 `api/` 范围的第二件跑 10 轮 → 第二件 round 3、escalated，「推送未成」13 次。
