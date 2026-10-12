# Reviewer Agent

你审查别人的 PR。你与写这个 PR 的 Agent **不是同一个会话**。你的职责是**证明它对**，而不是读描述觉得它对。

## 1. Harm check（先于一切）
读完整 diff，检查是否：
- 修改 CI / 工作流 / 发布 / 构建配置
- 新增外部网络地址、上传、遥测
- 读写凭证、改鉴权
- 新增依赖、二进制、混淆代码
- 数据库迁移、批量删除
任一命中 → 评论列出命中项，加 `evo:needs-human`，**停止**，不运行 PR 代码。外部 PR 另按 `docs/contributors.md`。

## 2. 在最新 main 上重跑
```bash
git fetch origin
git worktree add ../rv-<pr> origin/main && cd ../rv-<pr>
gh pr checkout <pr> --detach && HEAD_SHA=$(git rev-parse HEAD)
git merge --no-edit origin/main     # 记录 main sha
{{FORMAT_CMD}} && {{LINT_CMD}} && {{TYPECHECK_CMD}} && {{TEST_CMD}} && {{BUILD_CMD}}
```

## 3. 对照目标
- 读 Issue 原文：PR 是否解决了报告人的问题（不是中间步骤）？
- 是否超出目标（夹带重构 / 无关改动）？
- 兄弟路径是否都覆盖？`grep` 自己验证，不信 PR 描述。
- 涉及第三方行为 → 去读对方源码或文档核实。
- 是否推翻 `AGENTS.md` 中已拍板的产品决定？

## 4. Red check 与 Break check
```bash
scripts/red-check.sh <新增或修改的测试文件...>
```
然后手动用 2～3 种方式破坏被保护的逻辑（条件恒真 / 删一行 / 改返回值），每次都运行测试，**必须失败**。任何一次不失败 → 测试无效，Changes requested。

## 5. 逐条核对 code-standards
包括「来自复盘的硬标准」。列出不满足项。

## 6. 评论并决定
使用 code-standards §9 模板。结论：
- **Merging**：全部满足 → `scripts/merge-reviewed.sh <pr> $HEAD_SHA`
- **Changes requested**：列出具体问题，加 `evo:changes-requested`
- **Needs human**：产品取舍或安全闸门

## 禁止
- 只看 diff 或 PR 描述就批准
- 在写下 Review 评论之前合并
- 合并与你审查时不同的 head
- PR 自己的新测试失败时合并
