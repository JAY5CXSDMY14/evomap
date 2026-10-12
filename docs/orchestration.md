# 编排：谁来触发、谁来派活、怎么并行

magpie 仓库没有公开这部分：4 个 workflow 都不是定时任务，LESSONS.md 的更新时间（03:10、03:49、00:23、23:46、03:48、14:24、05:26）不规律，更像本地手动或私有脚本触发；夜审提示词和 agent 编排也未公开。evoloop 给出一套可直接落地的默认方案，按自动化程度分三档。

---

## 档位 L1：手动循环（第一周推荐）

人就是调度器，所有角色在本地用同一个 coding agent（Claude Code / Codex / Amp 等）的不同会话完成。

| 时机 | 你做什么 |
|---|---|
| 有新反馈 | 开 Issue（或让 agent 代开），一句话写清哪里不对 |
| 开工 | 新会话：`读 prompts/builder.md，处理 #123` |
| 完成后 | **另开一个会话**：`读 prompts/reviewer.md，审 PR #45` |
| 睡前 | 新会话：`读 prompts/nightly-retro.md，复盘今天`，配合 `scripts/retro-collect.sh` |

优点：零基础设施；你能直观看到每个阶段的质量。
缺点：吞吐受你在线时间限制。

## 档位 L2：GitHub Actions 驱动（推荐常态）

| 事件 | 工作流 | 角色 |
|---|---|---|
| Issue 新建 / 编辑 | `evoloop-triage.yml` | Triage Agent 打标签 |
| 每日 03:00 Asia/Shanghai | `evoloop-nightly-retro.yml` | Retro Agent 复盘并开 PR 更新 LESSONS |
| PR 打开 / 同步 | `evoloop-guard.yml` | 机械检查：PR 正文含 Ran / Not run；LESSONS 格式；sha 存在 |
| 手动 `workflow_dispatch` | `evoloop-nightly-retro.yml` | 补跑复盘 |

Builder 和 Reviewer 仍可在本地跑（需要真实环境验证时更方便），也可接入 `anthropics/claude-code-action` 等在 Issue 里 `@claude` 触发。

**夜审 PR 的处理**：Retro Agent 开 PR 而不是直接推 main。维护者早上扫一眼 diff 即可合并；稳定两周后可改为自动合并（只改 `LESSONS.md` 和 `docs/` 的 PR）。

## 档位 L3：常驻调度器

一个常驻进程（或定时任务）轮询 `evo:ready` 的 Issue，按优先级派给空闲的 Builder 会话，完成后自动派 Reviewer。适合日均 Issue > 20 的项目。

最小调度逻辑：
```
loop every 10 min:
  ready = issues(label=evo:ready, not evo:in-progress) sorted by priority, age
  for issue in ready[:MAX_PARALLEL - running_builders]:
      spawn builder(issue)            # 内部执行 scripts/claim.sh
  for pr in prs(label=evo:needs-review):
      spawn reviewer(pr, model != pr.builder_model)
  for pr in prs(label=evo:approved):
      scripts/merge-reviewed.sh pr pr.reviewed_sha
```

---

## 并行规则

1. **每个会话一个 worktree**，路径 `../wt-<issue>`，分支 `evo/<issue>-<slug>`。
2. **认领先于动手**：Issue 评论 + `evo:in-progress` 标签；超过 2 小时无推送视为放弃。
3. **同一子系统同时最多 1 个 Builder**，避免互相冲突的修复（在 Issue 上加 `area:<subsystem>` 标签判断）。
4. `MAX_PARALLEL` 初始设为 3，观察夜审里"并发冲突"类教训的数量再调整。

## Agent 选型建议

| 角色 | 建议 | 理由 |
|---|---|---|
| Builder | 最强的编码模型 | 实现质量 |
| Reviewer | **与 Builder 不同的模型或厂商** | 避免同源盲区，magpie 的 commit 署名里同时出现 Claude、Amp、factory-droid |
| Triage | 便宜快速的模型 | 高频、低风险 |
| Retro | 长上下文模型 | 一次读完一整天的 commit 正文 |

## 成本与刹车

- 夜审窗口 commit 数 > 150 → 拆成两段分别复盘，再合并结论。
- 单个 Issue 返工 ≥ 3 次 → 自动加 `evo:needs-human`，停止派活，等维护者看。
- main 上出现红测试 → 暂停派发新功能类 Issue，优先修红（硬标准）。
