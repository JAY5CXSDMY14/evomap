# 外部「架构减法」审查分诊（2026-10-23）

来源：issue #12–#28（审查者 claude-sonnet-5-5 #12–#24；Hark #25–#28 + 在 #12/#14/#15/#18/#20 下的补充）。

## 0. 先修（保护缺口，不是减法）
- #15 补充：MulticaExecutor.launch（evo_exec.py:640）不使用 model/rc，「施工 ≠ 验收」在 Multica 下 evo 没有检查，只靠两个 agent 恰好配了不同模型。已核实（sed 640–682 只有签名命中）。
  → 在 selfcheck / exec_up 里读 Multica 两个 agent 的实际模型，一样就停派工并推送。

## 1. 纯技术减法（决策岗级，可直接排）
#14 删 Orca（前提 TB 迁 Multica）→ #25 删仿造任务图/闸门表 → #13 功能包降普通模块 + #16 删插件（插件仅 example-hello，enabled:false，已核实）+ #22 → #18 事件一份 → #19 卡住检测合并 → #20 删 v1 副本（含 kit/templates/project/AGENTS.md 路由表指向 prompts/ 的错误）→ #23。

## 2. 要老板拍板
- #12 入口：只留 Telegram / 留网页面板作「看效果」页 / 保留 App（App 1.2 万行 Swift，已核实；与 dmg 计划冲突）。
- #15 额度满自动切备用账号、模型试用打分：Multica 下已不起作用，删不删。
- #26 闸门六类收三类（do/look/ship）。
- #27 分诊直接登记，件号改用 GitHub issue 号。
- #21 html 不进仓库（老板喜欢 HTML 讲解页）。
- #17 预设换成各项目 lint/CI。
