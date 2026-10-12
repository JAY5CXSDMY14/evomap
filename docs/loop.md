# 循环规格：八个阶段

每个阶段按同一结构描述：**输入 → 动作 → 输出 → 闸门 → 反模式**。闸门是硬性的：不满足就停在当前阶段，不允许"先合了再说"。

---

## ① 入口 Intake

**输入**：用户、社区、维护者发现的问题或想法。来源可以是 GitHub Issue、Discord、X、微信群、维护者口述。

**动作**
- 非 GitHub 来源的反馈，由 Triage Agent 代为开 Issue，标题末尾标注来源：`（张三 on 微信群）`、`（the owner）`。
- 用户提供的截图、日志、配置**原样保存**为 Issue 附件，后续测试以此为准。
- 维护者的一句话指令原文保留，例如 `the owner: 这个按钮为什么一直显示？不是说 hover 才出现吗`。

**输出**：一个 Issue，包含：现象、复现步骤、期望、原始数据、来源。

**闸门**
- 所有工作必须有 Issue 编号（维护者直接下指令时也要补开）。
- 不接受外部直接改代码的 PR 作为需求入口；外部 PR 走 `docs/contributors.md` 的安全审查。

**反模式**
- 根据转述的二手描述动手，而不是报告人原始数据。
- 一个 Issue 里塞三个不相关的需求。

---

## ② 分诊 Triage

**输入**：新 Issue。

**动作**（Triage Agent，提示词见 `prompts/triage.md`）
1. 判断类别：bug / 功能 / 体验 / 文档 / 安全 / 重复。
2. 查重：搜索已关闭和进行中的 Issue、最近 7 天的 commit。
3. 对照 `AGENTS.md` 的「产品边界」和「已拍板决定」，判断是否符合方向。
4. 打标签并评论理由。

**输出**：标签之一：
| 标签 | 含义 | 下一步 |
|---|---|---|
| `evo:ready` | 可以做，信息齐全 | Builder 可认领 |
| `evo:needs-info` | 缺复现或原始数据 | 评论列出缺什么，等报告人 |
| `evo:needs-human` | 涉及产品取舍、安全、对外承诺 | 等维护者一句话拍板 |
| `evo:wontfix` | 不符合方向或推翻已拍板决定 | 评论引用 AGENTS.md 里的依据 |
| `evo:duplicate` | 重复 | 链接原 Issue |

**闸门**：只有 `evo:ready` 才能进入认领。

**反模式**：什么 Issue 都无条件实现；Agent 自己替维护者做产品决定。

---

## ③ 认领 Claim + 隔离

**输入**：`evo:ready` 的 Issue。

**动作**（`scripts/claim.sh <issue>`）
1. `git fetch origin`，检查 `origin/main` 最近的 commit 和 open PR 是否已在处理同一 Issue。
2. 在 Issue 下评论：`🔧 claimed by <session-id> at <time>`，加标签 `evo:in-progress`。
3. 建立独立 worktree：`git worktree add ../wt-<issue> -b evo/<issue>-<slug> origin/main`。

**输出**：一个独立工作区 + 认领记录。

**闸门**
- 已有 `evo:in-progress` 且认领未超过 2 小时 → 不得重复认领。
- 永远不在共享 checkout 里提交。

**反模式**：两个会话在同一分钟修同一个 flaky 测试（magpie 实际发生过）；两个 agent 共用一个 index，提交了彼此的文件。

---

## ④ 实现 Implement + 自证

**输入**：worktree + Issue。

**动作**（Builder Agent，提示词见 `prompts/builder.md`）
1. **读规则**：`AGENTS.md` → 相关 `docs/subsystems/*.md` → `docs/code-standards.md` → `LESSONS.md`。
2. **先复现**：用报告人的原始场景和原始数据复现，写一个此刻失败的测试。
3. **修一类不修一例**：`grep` 同类代码路径，兄弟路径一并修，或在 commit 里写明为什么不需要。
4. **一个 commit 一个目标**：顺手发现的问题另开 Issue。
5. **自证**：
   - Red check：`scripts/red-check.sh` 把改动之外的测试放到旧代码上跑，必须失败且失败信息指向错误行为；
   - 全量检查：格式化、lint、类型检查、全量测试、构建；
   - 真实使用：能用真实账号 / 真实配置 / 真实接口就用；做不到写明。
6. **写 commit**（格式见 code-standards「commit 规范」）。
7. 推分支、开 PR，PR 正文复用 commit 正文。

**输出**：一个 PR，正文包含：来源、原因、改了什么、Red check 结果、跑了什么、**没跑什么**。

**闸门**（全部满足才可请求 review）
- [ ] 存在回退必挂的测试，且实际回退验证过（编译失败或被跳过不算失败）
- [ ] 测试在隔离环境（临时 HOME / 临时数据库 / mock 外部服务）
- [ ] 全量检查通过
- [ ] 没跑的检查列为 Not run

**反模式**
- 自己编一个"差不多"的测试样例，而不是用报告人的原始字节。
- 只改报错文案，不改报错原因。
- "main 上也一样失败"却没写当时 main 的 sha。

---

## ⑤ 互审 Review

**输入**：PR。

**动作**（Reviewer Agent，必须与 Builder 不是同一会话，提示词见 `prompts/reviewer.md`）
1. **Harm check（先查危害再看功能）**：改了 CI/发布脚本？新网络地址？读写凭证？新依赖/二进制？删数据？任一命中 → 加 `evo:needs-human`，停止。
2. 拉取 PR head，合并到**最新** `origin/main`，在合并结果上重跑全部检查。
3. 读完整 diff，对照 Issue：是否超出目标？是否漏了兄弟路径？
4. **Red check**：回退修复，确认新测试失败。
5. **Break check**：用 2～3 种方式故意破坏被保护的逻辑（条件恒真、删一行、换返回值），测试必须每次都失败。
6. 涉及第三方行为时去读对方源码或文档，不信 PR 描述。
7. 逐条核对 `docs/code-standards.md` 的硬标准。
8. 发 Review 评论（模板见 code-standards「Review 评论模板」）。

**输出**：Review 评论，结论为 `Merging` / `Changes requested` / `Needs human`。

**闸门**
- PR 自己新增的测试失败 → 不合。
- Review 列出的问题未解决 → 不合。
- 推翻维护者已拍板的产品决定 → 不合，转 `evo:needs-human`。

---

## ⑥ 合并 Merge

**动作**（`scripts/merge-reviewed.sh <pr> <reviewed-sha>`）
- 先确认 Review 评论已写明审过的 sha 和运行记录。
- `gh pr merge <pr> --squash --match-head-commit <reviewed-sha>`。
- 合并后在 Issue 下评论修复版本，加 `evo:fixed-pending-confirm`，**不关闭 Issue**。

**闸门**：Review 之后 head 有新提交 → 合并会失败 → 回到 ⑤ 重审。

**反模式**：先合并后补写"跑了什么"（magpie 某天 10 次合并中 9 次如此，后被写进硬标准）。

---

## ⑦ 发布 Release

**动作**（Release Agent，`scripts/release-gate.sh <sha>`）
1. 确认目标 commit 的 CI **已完成且全绿**；被取消（cancelled）的 run 不算。
2. 攒批：距离上次发布不足 `{{MIN_RELEASE_INTERVAL}}`（建议 2 小时）且无 P0 → 等下一批。
3. 打 tag、生成 Release Notes（按 Issue 归类）、确认所有产物都已上传。
4. 在已修复的 Issue 下通知报告人新版本号，请其确认。
5. 报告人确认 → 关闭；报告人说没好 → 重开并加 `evo:regressed`（这是夜审的头号线索）。

**闸门**：CI 未完成 / 产物不齐 → 不发布，不对用户宣称"已发布"。

**反模式**：每个 commit 都打 tag，导致 CI 永远被下一次 push 取消（magpie 曾 51 小时 294 个 tag，没有一轮 CI 跑完）。

---

## ⑧ 夜审复盘 Retro → 规则进化

**触发**：每天定时（`templates/.github/workflows/evoloop-nightly-retro.yml`，默认北京时间 03:00），或维护者手动触发。

**动作**（Retro Agent，提示词见 `prompts/nightly-retro.md`）
1. `scripts/retro-collect.sh --since <上次复盘的 sha>` 收集窗口内：全部 commit（含正文）、合并的 PR 和 Review 评论、被重开的 Issue、`evo:regressed`、CI 失败/取消记录、revert commit、同一文件 24h 内被改 ≥3 次的热点。
2. 只找三类问题：
   - **返工**：修完又被修（同一 Issue 多个修复 commit、revert、regressed）；
   - **不该合**：违反硬标准、超出目标、推翻已拍板决定、Review 未解决就合；
   - **验证太薄**：没有 Red check、没写 Not run、用编造数据、没在真实环境验证却宣称可用。
3. 同时记录 **Done right**：做得好的正面案例。
4. 对每个发现：已有同类教训 → Seen 计数 +1（同一天只算一次）；没有 → 新增条目。
5. `scripts/lessons.py promote` 列出 Seen ≥ 3 的条目 → 移入 `docs/code-standards.md` 的「来自复盘的硬标准」，在 LESSONS.md 留存档指针。
6. `scripts/lessons.py verify` 校验每个引用的 sha 在仓库中真实存在。
7. 提交一个只改文档的 commit：`lessons: <日期> review — <摘要>`，正文写窗口、commit 数、版本范围、新增/计次/升级各几条、`Ran: lessons.py verify`。

**输出**：更新后的 LESSONS.md / code-standards.md；一段复盘摘要（可推送给维护者）。

**闸门**
- 每条教训必须有可点开的证据（sha 或 Issue 号）。
- 只改文档，不改代码。发现需要修的 bug → 开 Issue，不顺手修。

**为什么有效**：下一个 Builder 开工时 `CLAUDE.md` 会自动加载 LESSONS.md，Reviewer 会逐条核对 code-standards.md。规则改变，所有后续 agent 的行为随之改变，不需要开会。
