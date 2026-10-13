# Loop ①：渠道循环（Issue / PR / 社区）

> 用法：在 Claude Code 中输入 `/loop`，粘贴本节以下正文。先替换 `{{占位符}}`。

持续盯 {{仓库 owner/repo}} 的 GitHub Issue 和 PR，以及 {{社区渠道，例如 Discord 服务器 / 微信群}} 的用户反馈。每轮按下面顺序处理，硬规则以 AGENTS.md、LESSONS.md、docs/code-standards.md 为准。

**Issue**
1. 先按 prompts/triage.md 分诊，判断值不值得修 / 实现。
2. 值得做：用 scripts/claim.sh 认领，按 prompts/builder.md 实现，Red check / Break check / Not run 全部写进 PR；合并必须走 scripts/merge-reviewed.sh；发版必须过 scripts/release-gate.sh。完成后**回复报告人**，说明改了什么、哪个版本可用，请对方确认；报告人确认前不关闭。
3. 不值得做：**也要回复**，说明原因。
4. 推广、广告、求合作（例如第三方中转服务）：统一回复"感谢关注！目前没有接入第三方服务的计划，日后如有合作方案会另行公布，敬请期待。"**绝不能把对方的服务直接接进产品。**

**PR**
1. 先按 docs/contributors.md 查危害，命中即停、加 evo:needs-human。
2. 逐行审代码和逻辑。很多 PR 是没测过的 Coding Agent 产物，所以**必须把代码拉到本地实际跑**，验证没有 bug。
3. 验证通过才合并（锁定审过的 sha）；否则回复具体问题，或关闭并说明原因。

**社区**
1. 查看 {{社区渠道}} 的**所有频道，一个都不能漏**。
2. 有价值的反馈 / 建议：转成 Issue（注明来源和报告人），再走上面的流程；值得讨论就继续讨论。
3. 回复时要**真实地 @ 对方**，只写名字对方收不到通知。

**禁止**：替维护者做产品决定、推翻 AGENTS.md 里已拍板的决定、未验证就宣称修好、多条 loop 同时处理同一个 Issue（以 evo:in-progress 标签为准）。
