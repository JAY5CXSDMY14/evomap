# 2026 年 agent 工程实践摘编：对 evo 有用的 16 条

> 写于 2026-10-23。起因是 Thomas Zhou 2026-10-22 转发的 OpenAI 文章（三段提示词）。这里只收**当天实际打开过**的页面，每条注明日期、作者/机构和权威级别。
> 权威级别：**A** = 模型厂商官方文档或官方工程博客；**B** = 同行评审或预印本论文；**C** = 个人/社区，只作线索。
> 「对 evo 的用法」都落到具体岗位文件（`kit/roles/decider.md`、`builder.md`、`verifier.md`、`retro.md`）、`kit/bin/evo` 的功能或 `docs/` 下的文档。注意：`kit/roles/`、`kit/README.md`、`docs/role-file-references.md`、`docs/claude-cold-audit-prompt.md` 此刻正被另一位改，这份文档只提建议，不动它们。

---

## 一、规则文件：写少、写准、能测

### 1. 用「重放 A/B」测一条 AGENTS.md 规则到底有没有用

- **来源**：https://developers.openai.com/blog/maintaining-software-with-the-gpt-6-family ，2026-10-14，Rodrigo Roim（OpenAI Core Experimentation 团队），**A**
- **一句话要点**：挑一次「被某条规则带偏」的历史会话，在同一仓库快照、同一模型上重放两遍——规则原样 / 只删或只改这一条——比较质量、行为、工具调用数、token、耗时和成本。
- **对 evo 的用法**：给 `retro` 岗加一个固定动作「规则 A/B」。evo 已经有会话记录和 `lessons`，复盘时每周挑 1 条最可疑的岗位规则（来自 `kit/roles/*.md` 或 `AGENTS.md`），按下面的提示词跑。结果写进 `docs/lessons-system.md` 的「规则变更」一节，只有「改了更好」才提交规则修改。
- **可直接用的提示词**（原文，作者给的 Sol Medium 档就够）：

```text
Look through my recent Codex sessions and find one AGENTS.md instruction that appears
to have misdirected an agent or caused unnecessary work. Choose the original session
prompt where that happened. Replay that same prompt twice from the same repository
snapshot and model: 1. With the current AGENTS.md instruction unchanged. 2. With only
that one instruction removed or fixed. Compare task quality, agent behavior, tool calls,
token usage, runtime, and cost. Show the instruction and whether updating it helped.
```

### 2. 上下文文件对成功率帮助不大，却让成本涨 20%

- **来源**：https://arxiv.org/html/2602.11988v2 ，v2 2026-06-23，Gloaguen 等（ETH Zurich / LogicStar.ai），**B**
- **一句话要点**：在 SWE-bench 和新建的 CTXbench 上，LLM 生成的上下文文件让成功率略降、成本涨 20% 以上；人写的略升（不显著）。规则会被很好地遵守，但「仓库总览」没用——它不会让 agent 更快找到要改的文件。结论：只写仓库里**读不出来的**非常规要求，并且上线前要评测。
- **对 evo 的用法**：
  - `kit/roles/*.md` 里凡是「目录介绍 / 项目概况」的段落，候选删除，交给第 1 条的 A/B 去验证。
  - evo 生成给 Multica agent 的 instructions（`docs/multica-backend.md` 里那份 brief）不要自动附仓库总览。
- **可直接用的检查句**（给 retro 岗）：

```text
对每一段岗位规则问一句：这条信息能不能从仓库文件、README 或 git log 直接读出来？
能读出来的标「候选删除」；读不出来、但模型不照做就会出错的，才保留。
```

### 3. 每一行都问「删掉会不会出错」

- **来源**：https://code.claude.com/docs/en/best-practices ，Anthropic 官方文档（2026-10-23 读到的现行版），**A**
- **一句话要点**：CLAUDE.md 每次会话都加载，所以只写广泛适用的。逐行问「Would removing this cause Claude to make mistakes?」，否则删。规则一长，重要的那条就会被淹没；只给真正常被跳过的那一行加「IMPORTANT」。
- **对 evo 的用法**：
  - 给 `kit/roles/` 定一个行数预算，例如每个岗位文件 ≤ 120 行，超了就在 `evo doctor` 里报黄。
  - 这是对 `kit/bin/evo` 的功能建议，等 claude-prep 那位改完 roles 再加。
- **可直接用的表**（官方原表，按此删改）：

```text
保留：猜不到的命令；和默认不同的代码风格；测试命令；仓库礼仪；项目特有的架构决定；环境怪癖；不显然的坑
删除：读代码就知道的；语言通用规范；详细 API 文档（改成链接）；经常变的信息；长篇解释；逐文件说明；「写干净代码」这类废话
```

### 4. 规则放哪：CLAUDE.md 是索引，硬约束交给 hook

- **来源**：https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more ，2026-06-18，Michael Segner（Anthropic），**A**
- **一句话要点**：七种给 Claude 下指令的方式，各自的加载时机、压缩后是否保留、权威性不同。
  - CLAUDE.md 控制在 200 行内，有人负责，像代码一样评审。
  - 「每次都要做 Y」用 hook；「绝不能做 X」用 hook 或权限（PreToolUse 返回 exit 2 即拦截），不要写成一句话规则。
  - 30 行的流程放 skill。
  - 只对某目录生效的规则加 `paths:`。
- **对 evo 的用法**：
  - `builder.md` 里「不准改 X 目录」「必须跑 Y 检查」这类红线，迁成 `.claude/settings.json` 的 PreToolUse / Stop hook（Claude 接入后）。在 Codex/magpie 侧对应的是 evo 派工前后的脚本闸门。
  - 这正好对应仓库已有的「红线 / 接口 / 现状」三层（提交 `c351f37`）：红线层尽量变成确定性闸门。
- **可直接用的片段**：

```yaml
# .claude/rules/api.md —— 只在动到 src/api 时才加载
---
paths:
  - "src/api/**"
---
All API handlers must validate input with Zod before processing.
```

### 5. 新模型来了就做减法：规则让位给判断

- **来源**：https://claude.dev/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models/ ，2026-07-24，Thariq Shihipar（Anthropic），**A**
- **一句话要点**：
  - Claude Code 给新一代模型删掉了 80% 以上的系统提示词，编码评测没有可测量的损失。
  - 冲突的规则（「酌情写注释」vs「不要写注释」）会逼模型多想。
  - 示例会把模型限制在一个狭窄的探索空间，不如把接口设计清楚（例如用枚举）。
  - 用渐进披露；CLAUDE.md 的 token 多花在「坑」上。
- **对 evo 的用法**：每次 magpie 换主力模型，`retro` 岗做一次「规则审计」，把为老模型加的强硬措辞列出来，交给第 1 条的 A/B 验证。决策岗的输出格式用 JSON schema 枚举（见第 14 条），不要靠举例。
- **可直接用的替换句**（官方前后对照）：

```text
旧：In code: default to writing no comments. Never write multi-paragraph docstrings...
新：Write code that reads like the surrounding code: match its comment density, naming, and idiom.
```

### 6. Skill 描述要短，读文档要「按需」

- **来源**：https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra ，2026-09-11，Eric Provencher（OpenAI），**A**
- **一句话要点**：
  - skill 描述越短越好，但要写清楚「什么时候用」。
  - 多流程的 skill，根文件只做路由。
  - AGENTS.md 不要「每次编辑前先读 a/b/c」，改成「做 X 时看 a」。
  - 新模型更谨慎，要事先定义「做完」是什么样，并明确授权安全的流程（如本地测试）。
- **对 evo 的用法**：
  - `kit/README.md` 和各岗位文件里的「先读这些文档」改成条件式。
  - `builder.md` 加一句授权：本地测试可直接跑、失败可自修，减少无谓的停下来问。
- **可直接用的句子**（原文两句）：

```text
Use architecture.md for service boundaries, database.md for schema changes, and deployment.md when preparing a deployment.

The local tests use disposable fixtures and have no production access. Run them, fix failures caused by the requested change, and rerun affected tests without asking for approval at each step.
```

### 7. Codex 的 AGENTS.md 叠加规则与 32 KiB 上限

- **来源**：https://developers.openai.com/codex/guides/agents-md ，OpenAI 官方文档（现行版），**A**
- **一句话要点**：
  - 加载顺序：全局 `~/.codex/AGENTS.md`（或 `AGENTS.override.md`）→ 项目根 → 逐级子目录，近的覆盖远的。
  - 合并后超过 `project_doc_max_bytes`（默认 32 KiB）就截断。
  - 可用 `codex --ask-for-approval never "Summarize the current instructions."` 检查实际加载了什么。
- **对 evo 的用法**：
  - `evo doctor` 增加一项：对每个 Codex 岗位的工作目录跑一次「列出已加载的指令文件」，确认没被截断，也没被某个 override 意外替换。
  - 临时规则用 `AGENTS.override.md`，用完删掉，不改主文件。
- **可直接用的命令**：

```bash
codex --cd <岗位工作目录> --ask-for-approval never "List the instruction sources you loaded."
```

---

## 二、任务说明书（task spec）怎么写

### 8. 任务要写「去哪找证据」和「哪些不能动」

- **来源**：同第 1 条，OpenAI 2026-10-14，**A**；以及 Thomas Zhou 的转发 https://x.com/thomaszhou_/status/2113155161313202354 ，2026-10-22，**C**
- **一句话要点**：
  - 死代码清理的短提示词能成功，是因为它告诉了模型证据来源（Slack、Statsig、git 历史、线上画像）。
  - 过期实验清理的提示词写明了要保留什么（生产行为、kill switch），以及交付形态（每项清理一个小的 draft PR，附配置链接）。
  - 全库审计的 `/goal` 版本明确「不改线上配置」，产出是按负责人/文件分组、可并行的 Markdown 报告。
  - 转发下的回复补了两条：不确定的动态引用标「待核实」并写阻塞原因；规则只留少数几条硬的。
- **对 evo 的用法**：`docs/intake.md` 的任务单模板加三栏：**证据来源**、**必须保留**、**交付形态**；决策岗派单时三栏缺一就退回。
- **可直接用的任务单模板**（据原文改写成中文骨架）：

```markdown
## 目标
<一句话>
## 证据来源（去哪确认）
- git log / 相关 PR / 线上日志 / 配置后台 / 群聊记录：<具体位置>
## 必须保留（不许动）
- 生产行为；开关/降级用的配置；<目录或文件>
## 交付形态
- 每项一个小的 draft PR，摘要里附证据链接；不确定的标「待核实」，写清阻塞原因
## 做完的标准
- <可运行的检查命令> 通过；附命令和输出
## 不在范围内
- <明确写出来>
```

### 9. 最好的 spec：自包含、说明不做什么、以端到端验证收尾

- **来源**：同第 3 条，Claude Code 最佳实践（现行版），**A**
- **一句话要点**：
  - 大功能先让 Claude 采访你、写 SPEC.md，再开一个干净会话去实现。
  - 好 spec 要点名涉及的文件和接口，写明不在范围内的事，最后一步是证明功能可用的端到端验证。
- **对 evo 的用法**：决策岗 `decider.md` 的「立项」动作，产出物从一句话任务改成 SPEC.md（放在事项目录）。建造岗只读 SPEC，不读决策岗的对话。
- **可直接用的提示词**（原文）：

```text
I want to build [brief description]. Interview me in detail using the AskUserQuestion tool.
Ask about technical implementation, UI/UX, edge cases, concerns, and tradeoffs. Don't ask obvious questions, dig into the hard parts I might not have considered.
Keep interviewing until we've covered everything, then write a complete spec to SPEC.md.
```

### 10. 写「做完」的合同，再动手

- **来源**：https://www.anthropic.com/engineering/harness-design-long-running-apps ，2026-03-24，Prithvi Rajasekaran（Anthropic Labs），**A**
- **一句话要点**：
  - planner / generator / evaluator 三岗。每个冲刺前，生成方和评估方先通过文件协商一份「sprint contract」，写清本轮做什么、怎么验证，谈妥才写代码。
  - 评估方要专门调「挑剔」，因为模型给自己打分总偏宽。
  - 每个 harness 组件都编码了一个「模型做不到」的假设，新模型来了要逐个拆掉测试（一次只拆一个）。
- **对 evo 的用法**：正好对应 evo 的 decider → builder → verifier。
  - 建议在 builder 开工前加一个轻量的「合同」文件 `contract.md`：builder 写「我打算做什么、怎么证明」，verifier 只看这份合同和产物，不看 builder 的推理。
  - 结合 `docs/contract-review.md` 现有流程。
- **可直接用的片段**：

```markdown
# contract.md（builder 起草，verifier 审，谈妥才开工）
- 本轮交付：<3–5 条可观察行为>
- 每条怎么验证：<命令 / 页面操作 / 期望输出>
- 不做：<明确排除>
- verifier 判定：任何一条不达标即 FAIL，附文件:行号证据
```

---

## 三、验证与评审

### 11. 给它一个能跑的检查，然后用确定性闸门收口

- **来源**：同第 3 条，Claude Code 最佳实践（现行版），**A**
- **一句话要点**：没有能跑的检查，「看起来做完」就是唯一信号。闸门由软到硬有四档：
  - 同一条提示词里要求它跑检查；
  - `/goal` 条件，由独立评估器每轮复查；
  - Stop hook，脚本不过就不许结束；
  - 验证子代理，换一个新上下文去反驳。
- **对 evo 的用法**：
  - `verifier.md` 已经是第四档。
  - 建议 builder 在 Claude 接入后加 Stop hook，把 `evo` 的验收命令挂上去，做成确定性闸门。
  - 无人值守的 builder 用 `/goal` 写「全部测试通过且 contract.md 每条有证据」。
- **可直接用的提示词**（原文）：

```text
Use a subagent to review the rate limiter diff against PLAN.md. Check that every requirement
is implemented, the listed edge cases have tests, and nothing outside the task's scope changed.
Report gaps, not style preferences.
```

### 12. 评审要收敛：最多三轮，只看新 diff，不重复报

- **来源**：https://claude.dev/blog/solving-code-review-at-anthropic/ ，2026-10-15，Addy Osmani、Morgan Westlee Lunt、Qing Wang（Anthropic Claude Code 团队），**A**
- **一句话要点**：
  - agent 写、agent 审，可能互相折腾一整夜（有个 PR 过夜跑了 50 多轮）。
  - 改进措施：三轮封顶，之后请作者退一步重想方案；前几轮之后只审新 diff；按类报 bug，让作者一次修完；不重复已报项。改后一轮通过率 65%→78%，五轮以上 8.9%→1.5%。
  - 另外两条：机器人的批准永远不能顶替要求人来批的那一票；风险分级由改动决定，不由作者决定。
- **对 evo 的用法**：
  - evo 的 builder↔verifier 回合设上限 3（超过就把事项退回 decider 重新拆）。
  - verifier 第 2 轮起只看增量 diff。
  - 在 `docs/loop.md` 写明「agent 的通过不等于老板的批准」。
  - 另建 `REVIEW.md`，写这个仓库里「失败长什么样」，限制吹毛求疵的条数，要求给文件和行号证据。
- **可直接用的 REVIEW.md 骨架**（依文中要点）：

```markdown
# REVIEW.md
- 这个仓库里「坏」的定义：文档说谎；配置路由错；状态文件写坏
- 先报一个数：发现 N 个必须修的问题；没有就明说「无须修改」
- 每条发现必须带 文件:行号 证据，不靠函数名猜
- 风格类意见最多 3 条；跳过路径：docs/*.html、work/
- 第 2 轮起只看新增 diff；不重复已报项；同类问题合并成一条
```

### 13. 把事故变成评测集，每次改提示词都重跑

- **来源**：同第 12 条，**A**
- **一句话要点**：过去引起事故或被回滚的 PR，经熟悉代码的工程师确认后，变成评审器的每日评测集。改评审器的提示词、工具或模型，分数涨才保留。噪声也要量：看人对每条评审意见的反应（修了 / 说不对 / 说是故意的 / 不重要）。
- **对 evo 的用法**：
  - evo 已经有 `lessons`。把「verifier 漏放、后来出问题」的事项自动标成 eval 案例，存到 `state/evals/verifier/`。
  - 改 `verifier.md` 前后各跑一遍，分数不涨就不合并。
  - 这就是老板要的「规则文件的评测」。
- **可直接用的记录格式**：

```json
{"case": "2026-10-xx-<事项>", "diff_ref": "<commit>", "bug": "<一句话>", "where": "path:line",
 "confirmed_by": "老板", "verifier_should": "FAIL", "added": "2026-10-23"}
```

### 14. 评测要防自欺：拆训练/测试，不把失败案例贴进提示词

- **来源**：https://claude.dev/blog/automating-eval-design-and-hillclimbing/ ，2026-09-28，Lance Martin（Anthropic），**A**
- **一句话要点**：
  - 好评测的四个特征：像生产；更强的模型 / 更高的推理档得分更高；顶尖模型也到不了满分；同一配置多跑几次分差小。
  - 爬坡时随机拆训练集和测试集，训练集涨、测试集不涨就回滚。
  - 每轮只改一处；永远不把失败内容直接贴进提示词。
  - 先确认评测噪声小于你在意的最小提升。
  - 一个持续拿零分的题，多半是题或评分器坏了。
- **对 evo 的用法**：第 13 条的 verifier 评测和第 1 条的规则 A/B，都按这里的纪律跑。
  - 案例少于 10 个时不下结论。
  - 每个案例至少跑 2 次（第 15 条也提到：一个回归只在两次中的一次出现）。
  - 结果附置信区间写进 `docs/lessons-system.md`。
- **可直接用的提示词**（Claude Code 内置命令，接入 Claude 后可用）：

```text
/claude-api build-eval
/claude-api hillclimb
```

---

## 四、长跑与无人值守

### 15. 少拆子代理：先建一个端到端小评测，一次折叠一个

- **来源**：https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop ，2026-10-22，Diane Sarkis（Anthropic Applied AI），**A**
- **一句话要点**：
  - 按组织架构拆子代理会出现「传话游戏」。
  - 单 agent + 渐进披露的 skill 和工具，常常质量更好、成本和延迟更低。
  - 子代理只在三种情况下留：上下文膨胀可测、需要并行的一次性干净上下文、工具选择混乱。
  - 迁移前先有 10 个金标准例子；比较时看哪些题翻转了，每题跑不止一次。
  - 系统提示词由一个小的中心团队负责。
- **对 evo 的用法**：
  - evo 现在是四个岗位加很多文档。判断「要不要再加岗位」时用这个标准：只有能拿出可测的上下文膨胀或并行收益才加。
  - 岗位规则的最终负责人是老板一人（对应「一个小中心团队」），其他 agent 只能提议（`propose` 动作已在 `b430002` 里）。
- **可直接用的判定句**：

```text
新增一个岗位/子代理之前回答：1) 单岗位版本在哪个评测题上可测地变差？2) 新岗位交回的结果能否压缩成一个小 JSON？两题有一题答不出，就做成 skill 或工具，不做岗位。
```

### 16. 定时 agent 的六条纪律

- **来源**：https://claude.dev/blog/building-effective-agent-automations/ ，2026-10-08，Lance Martin、CJ Avilla（Anthropic），**A**
- **一句话要点**：
  1. 每个来源记书签（读到哪了），不用「过去 24 小时」这种固定窗口；
  2. 读失败要报「读不到」，不能当成「今天没事」；
  3. 发出前再核一遍状态；
  4. 只有收到确认才更新书签和台账，结果不明就记「可能已发」；
  5. 每次重新读偏好文件，偏好放在 agent 改不了的地方；
  6. 只读的地方给只读凭据，每次运行设花费上限（正常一次的 3–5 倍）。
- **对 evo 的用法**：evo 的自动驾驶（`docs/autopilot.md`）和通知（`kit/bin/evo_notify.py`）逐条对照：
  - 「读失败≠没事」对应 Multica / GitHub 拉取失败时的提示；
  - 「确认后再记账」对应 evo_bus 的投递状态。
  - Claude 岗位的花费上限可用 `claude -p --max-budget-usd`（headless 文档）。
- **可直接用的规则段**（原文第 5 步）：

```text
Verify. The world moved while you read. For every item you will report, re-check its live source just before posting:
resolved since you read it, drop it; still open but changed, fix the line; cannot confirm, drop it and list it in the
run record's cuts. ... never hedge an item's status: assert it or drop it.
```

### 附：无人值守调用 Claude Code 的几个开关（headless 文档）

- **来源**：https://code.claude.com/docs/en/headless ，Anthropic 官方文档（现行版），**A**
- **要点**：
  - `--permission-prompts none`：没人能批时，拒绝并告诉模型不要重试。需要 v2.1.259+。
  - `--permission-mode dontAsk`：只放行白名单。
  - `--json-schema`：结构化输出，适合决策岗。
  - stream-json 里的 `system/api_retry` 事件有 `error` 字段，取值包括 `rate_limit`、`account_on_hold` 等，比匹配尾部文字可靠。
  - 注意：`--bare` 不读订阅登录（详见 `docs/claude-pro-native-setup.md`）。
- **可直接用的命令**：

```bash
claude -p "<决策任务>" --output-format json \
  --json-schema '{"type":"object","properties":{"action":{"enum":["build","verify","propose","wait"]},"reason":{"type":"string"}},"required":["action","reason"]}' \
  --permission-mode dontAsk --permission-prompts none
```

---

## 五、分组建议

### 建议立刻采用（不依赖 Claude，现在的 magpie 模型就能用）

1. **规则 A/B 重放**（第 1 条）：每周 retro 挑一条规则做。
2. **删「仓库总览」类段落、条件式读文档**（第 2、3、6 条）：交给第 1 条去验证，不凭感觉删。
3. **任务单三栏：证据来源 / 必须保留 / 交付形态**（第 8 条）：改 `docs/intake.md` 模板。
4. **builder↔verifier 回合封顶 3 轮，第 2 轮起只看增量**（第 12 条）。
5. **REVIEW.md + 漏放事项转评测集**（第 12、13 条）。按第 14 条的纪律跑：拆训练/测试、每题 ≥2 次、案例 <10 不下结论。
6. **定时任务的「读失败≠没事」「确认后再记账」**（第 16 条）：对照 autopilot 和 notify 逐条检查。
7. **`evo doctor` 增加 Codex 指令加载检查**（第 7 条）。

### 等 Claude 接入后再试

1. **Stop hook 做 builder 的确定性闸门、`/goal` 跑无人值守 builder**（第 4、11 条）。
2. **`.claude/rules/` 按路径加载规则、红线迁成 PreToolUse hook**（第 4 条）。
3. **`/claude-api build-eval` / `hillclimb` 给 verifier 规则爬坡**（第 14 条）。
4. **决策岗 `--json-schema` 结构化输出**（附录）：Pro 额度宝贵，结构化能少一轮返工。
5. **sprint contract 文件**（第 10 条）：流程本身不依赖 Claude，可以先在 magpie 上试；但原文的评估器调法基于 Claude，建议 Claude 接入后对比。

### 不适合我们

1. **大规模并行扇出**（如 `/batch` 拆 5–30 个子代理、几十个 `claude -p` 循环）：Pro 额度和「正常个人用量」都撑不住，见 `docs/claude-pro-native-setup.md` 2.5 节。用 magpie 的模型做扇出可以，用 Pro 不行。
2. **按组织架构给每类问题建一个子代理**（第 15 条反例）：evo 只有老板一个人，岗位越多传话越多。
3. **GPT-6 Astra Ultra 档全库审计**（第 1 条原文里的 $109 一次）：我们没有那个预算，也没有 OpenAI 那样的线上遥测来给证据。可以借用它的提示词结构，不借用它的规模。
4. **托管定时 agent（Claude Managed Agents）**（第 16 条的实现方式）：要 API Key 和 Claude Platform 计费，不走 Pro 订阅；我们只借它的六条纪律。

---

## 来源一览（全部 2026-10-23 打开）

| # | URL | 日期 | 作者/机构 | 级别 |
|---|---|---|---|---|
| 1,8 | https://developers.openai.com/blog/maintaining-software-with-the-gpt-6-family | 2026-10-14 | Rodrigo Roim / OpenAI | A |
| 8 | https://x.com/thomaszhou_/status/2113155161313202354 | 2026-10-22 | Thomas Zhou | C |
| 2 | https://arxiv.org/html/2602.11988v2 | 2026-06-23 (v2) | Gloaguen 等 / ETH Zurich, LogicStar.ai | B |
| 3,9,11 | https://code.claude.com/docs/en/best-practices | 现行版 | Anthropic | A |
| 4 | https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more | 2026-06-18 | Michael Segner / Anthropic | A |
| 5 | https://claude.dev/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models/ | 2026-07-24 | Thariq Shihipar / Anthropic | A |
| 6 | https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra | 2026-09-11 | Eric Provencher / OpenAI | A |
| 7 | https://developers.openai.com/codex/guides/agents-md | 现行版 | OpenAI | A |
| 10 | https://www.anthropic.com/engineering/harness-design-long-running-apps | 2026-03-24 | Prithvi Rajasekaran / Anthropic | A |
| 12,13 | https://claude.dev/blog/solving-code-review-at-anthropic/ | 2026-10-15 | Osmani, Lunt, Wang / Anthropic | A |
| 14 | https://claude.dev/blog/automating-eval-design-and-hillclimbing/ | 2026-09-28 | Lance Martin / Anthropic | A |
| 15 | https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop | 2026-10-22 | Diane Sarkis / Anthropic | A |
| 16 | https://claude.dev/blog/building-effective-agent-automations/ | 2026-10-08 | Lance Martin, CJ Avilla / Anthropic | A |
| 附 | https://code.claude.com/docs/en/headless | 现行版 | Anthropic | A |

**说明**：codexinsider、dev.to、aihot.news 等对 OpenAI 文章的二手转述没有收进来——原文已经读到了，转述不再增加信息。
