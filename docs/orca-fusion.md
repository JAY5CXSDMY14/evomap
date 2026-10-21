# Orca 融合方案：Orca 当身体，evo 当大脑

> 2026-10-21 · 依据 Orca 官方文档（CLI reference、Orchestration、Scheduled automations、Mobile companion、Agent hooks）。标「待验证」的条目需要在 Air 上实测确认。

## 一句话结论

**可行，而且大部分已经现成。** 估计 8 成需求 Orca 原版就能满足，evo 本来就在用 Orca 的编排接口（run-create、task-create、gate-create）。剩下的 2 成由 evo 补上，**目前没有发现必须改 Orca 源码的地方**。真正要实测的只有 3 个点。

## 三层结构

| 层 | 是谁 | 负责 | 我们维护吗 |
|---|---|---|---|
| 身体 | Orca 原版（自动更新） | 工作区、终端、diff、PR 和 issue、手机端、通知、远程机器、用量 | 不维护 |
| 大脑 | evo（Python 常驻进程） | 状态机、施工→验收→决策、三道关、卡住自救、上限、预设、合并上线 | 维护，只依赖 `orca` CLI |
| 补丁 | 先给上游提 PR，被拒才自己留 | Orca 缺的钩子 | 目前预计为零 |

## 逐条对照

### A. Orca 现成就有（直接用，evo 删掉自己那份）

1. **任务编排**：Orca Orchestration 自带 Run、Task、Dispatch、worker_done、heartbeat、decision gate 和任务依赖。evo 已经在用，只是没用全。
2. **按工人指定模型**：`worker-start --model --effort` 支持 Claude、Codex、OpenCode 等，每次派工单独生效，不影响全局默认。
3. **重派**：`worker-start --retry-of <dispatchId>`，正好补上我们缺的「重新派工」。
4. **工人状态**：Agent status hooks 会上报 working、waiting、done；`terminal wait --for tui-idle` 可以等到空闲。卡住检测改读这些，比现在自己猜终端尾巴准。
5. **手机端**：iOS 和 Android 都有。能看每个工作区的状态（干活中、完成、等输入）。能回复等输入的 agent。能看 diff、能提交。能切账号、看用量。agent 干完会推送。可以替掉 Evo App 和 Telegram。
6. **多机器**：Remote Orca Servers 和 federated workers（`worker-start --on`）。Mac mini 和 Air 挂在同一个界面下，手机端一个列表看两台机器。
7. **无窗口常驻**：`orca serve service install` 会写一个 LaunchAgent，Mac mini 不开窗口也能跑，手机照样能连。
8. **GitHub**：在应用里看 PR、issue、Actions，工作区可以直接关联 issue 号或 PR 号（`--pr`、`--reference`）。
9. **用量和限额**：Claude 和 Codex 账号的用量、重置倒计时，桌面端和手机端都能看。
10. **定时任务**：Automations 支持 cron，可以按次指定模型（`--extra-agent-args`），还有 precheck，前置命令失败就跳过这一轮。适合放每周审计、每日 8:30 摘要这类活。
11. **工作区初始化钩子**：建好工作区后自动跑 pnpm install、恢复 .env 等。

### B. evo 来补（Orca 没有，但不需要改 Orca）

1. **确定性的循环状态机**：一件活走到哪一步，由 evo 的代码判定。什么条件进下一步，也由代码定，不交给大模型去记。Orca 的 Run 只是容器，自己不会调度。
2. **异模型验收**：施工和验收必须用不同模型，Orca 不管这个规则，由 evo 派工时保证。
3. **你的三道关**：做不做、看效果、上线。evo 用 Orca 的 decision gate 存这道关，判定也归 evo。
4. **上限和自救**：最多重做 2 次，最多派工 12 次，单件最长 6 小时。卡住后交决策岗。主线变红自动开运维件。
5. **合并和上线**：deploy_cmd、自升级、回滚看门狗。
6. **预设和规范**：UI 和架构预设、Ponytail 规则，写进派工任务书。
7. **Magpie 模型路由**：模型名映射、按机器加前缀、额度用完切换。
8. **安静时段和摘要**：0 到 8 点不打扰，8:30 发摘要。

### C. 需要实测的 3 个点（待验证）

1. **DSH 能不能按次指定模型**：文档里 `--model` 支持的名单没有 DSH。做法：DSH 用 Magpie 里设好的默认模型（你正在调 FreeDeepseek），evo 不传模型参数；或者施工改用名单里的 OpenCode。
2. **手机上怎么审批**：手机端明确能做的是回复「等输入」的 agent。decision gate 会不会显示在手机上，文档没写。备选做法不用打补丁：开一个专门的「审批终端」，挂起来问「EV-FEAT-002 上线吗？yes/no」。手机上显示为等输入并推送，你回 yes 就行。
3. **卡住或关没人处理时怎么推送**：Orca 只在 agent 干完时推送。`worktree set --unread` 会不会也推送，要实测。不行就让上面那个审批终端来问（它在等输入，本身就会推送），或者保留 Telegram 当后备。

## 要停掉和删掉的

- **冻结**：Evo 菜单栏 App、网页面板、Telegram 和邮件推送（只留作后备）、自建的用量页。
- **简化**：evo 自己猜终端状态的代码，换成 Orca 的 status hooks 和 `terminal wait`。
- **保留**：evo 内核（状态机、事件、锁、存储）、功能包机制、所有测试，外加一套「Orca CLI 契约测试」。Orca 升级后接口一变就报警。

## 风险

| 风险 | 影响 | 应对 |
|---|---|---|
| Orca CLI 改参数 | evo 派工失败 | 契约测试每天跑；Orca 的 `--json` 输出相对稳定 |
| Orchestration 还是实验功能 | 行为可能变化 | 只用文档写明的命令；出问题退回 worktree 加 terminal 的低级接口 |
| 手机端审批体验不如自己做的 | 关不顺手 | 先用审批终端方案；真不够再给上游提一个「gate 显示在手机上」的 PR |
| 依赖一家创业公司 | 项目停更 | MIT 协议，最坏情况 fork 一个能用的版本留着 |

## 落地步骤

1. **Air 实测（约 30 分钟，交给 Pi）**：Orca 里开 DSH 看模型。手机配对。试 decision gate 在手机上显不显示。试审批终端和 `--unread` 会不会推送。
2. **evo 第 20 轮：瘦身**。卡住检测改用 status hooks；派工改用 worker-start 加 retry-of；审批改走审批终端和 decision gate；冻结 App 和面板；加 Orca 契约测试。
3. **Air 上用 EV 跑通一件新活**：新开一件替代 EV-FEAT-001。从派工走到施工、验收、手机审批、合并。
4. **跑顺后搬到 Mac mini**：`orca serve service install` 常驻，手机配对两台机器，TB 切过去。

## 可行性打分

| 维度 | 评分 | 说明 |
|---|---|---|
| 技术可行 | 高 | evo 已经在用 Orca 编排，这次是用全，不是推倒重来 |
| 自主程度 | 高 | 循环逻辑全在 evo，Orca 只当执行器和界面，不受它的节奏限制 |
| 工作量 | 中低 | 一到两轮瘦身，主要是删代码和改接口 |
| 维护成本 | 低 | 不 fork，Orca 自己更新，我们只守 CLI 契约 |
| 不确定性 | 中 | 3 个待验证点；最坏情况保留 Telegram 推送当后备 |
