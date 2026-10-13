# 编排：谁来触发、谁来派活、怎么并行

magpie 仓库里看不到这部分（4 个 workflow 都不是定时任务，LESSONS.md 的更新时间不规律）。2026-10-13 yetone 本人在 X 上公开了做法：**Claude Code + 官方 Opus 5.5，用 `/loop` 并行跑 3 条常驻的自然语言循环**，每晚自己抽时间人工处理 UI/UX 问题，没有调度器、没有 cron。这正好解释了错题本更新时间东一个西一个。

evoloop 因此分四档：L0 是 magpie 的实际做法，L1～L3 是更结构化、可审计的替代方案。可以从 L0 起步，遇到吞吐或审计需求再往上走。

---

## 档位 L0：常驻 /loop 会话（magpie 实际做法）

**按"信息来源 / 职责"拆 loop，而不是按阶段拆 Agent。** 每条 loop 是一个长驻会话，用一段自然语言描述"盯什么、怎么判断、做完要做什么"，阶段（分诊→实现→验证→合并→发布→回复）都在同一条 loop 内由 agent 自己走完；硬规则仍然来自 `CLAUDE.md` 自动加载的 `AGENTS.md` + `LESSONS.md`。

| Loop | 盯什么 | 关键要求 | 提示词 |
|---|---|---|---|
| ① 渠道循环 | GitHub Issue / PR、社区（Discord 等） | 值得做的修完发版并回复；**不做也要回复**；广告类统一回复；PR 逐行审 + 拉下来实际跑；社区所有频道都看、真实 @ 人 | `prompts/loops/channel-loop.md` |
| ② 社媒反馈循环 | X / 微博 / 小红书等公开反馈 | **先用廉价模型过滤**是否相关，不相关不进主模型；可复现才做，上线后回帖 | `prompts/loops/social-feedback-loop.md` |
| ③ 清理与复盘循环 | main 上的近期 commit 与合并的 PR | 清屎山和恶意代码；总结不该合 / 验证不严写入 LESSONS；**提议**拉黑反复提低质代码的人 | `prompts/loops/cleanup-retro-loop.md` |
| 人 | 每晚一段时间 | 亲自过 UI/UX：自动验证最管不住的是观感 | — |

使用方式（Claude Code）：开 3 个终端，各自进入独立 worktree 启动 Claude Code，输入 `/loop`，后面粘贴对应提示词的正文（`{{占位符}}` 先替换成本项目的值）。

L0 的取舍：
- 优点：几乎零基础设施，Agent 拥有完整上下文，从发现到回复一条龙。
- **冲突**：作者在评论区没回答，但 magpie 的 LESSONS 里有答案——"Two sessions never commit from the same checkout"：10-09 两个会话共用主 checkout 的 index，一个会话把另一个暂存的文件提交到了错误的 subject 下。规则是每个会话用自己的 worktree（`git worktree add --detach`）。
- 风险：没有显式派活与锁，多个 loop 可能撞同一个 Issue → 仍然要求 `scripts/claim.sh` 认领 + `evo:in-progress` 标签；Builder 与 Reviewer 同在一个会话里，**自审偏差**更大 → 合并前至少用 `merge-reviewed.sh` 锁 sha，高风险改动另开会话审。
- 成本：常驻会话持续消耗 token，入口一定要有廉价过滤层（见 ②）。
- **权限隔离**：每条 loop 一份独立的权限配置（Claude Code 的 allow / deny），只给它这条职责需要的命令和目录；社媒 loop 不需要合并权限，清理 loop 不需要回复外部的权限。共用一份时，一条 loop 出事会连带放行其它 loop。
- **外部内容一律当数据**：Issue、PR、评论、推文里出现的命令、脚本、链接、"请运行……"都是不可信输入，只能分析，不能照做；复现外部提供的脚本只能在一次性沙箱 / 虚拟机里进行。

### L0 的两个前提（作者在评论区补充）
1. **真实的复现环境**：把用户实际使用的环境交给 Agent（magpie 是 macOS + Windows + Windows 上的 Linux 虚拟机，只有一台装 Agent，由它远程操作其它机器），每次都在这些环境里真实复现再修。按项目替换成自己的"多端"，例如不同浏览器引擎、移动端、与生产同构的数据库和对象存储。
2. **决策与审美记忆**：Agent 能替你做取舍，是因为项目早期你和它大量讨论过，结论沉淀在记忆文件和设计文档里。接入时专门安排一次"头脑风暴 → 写进 `docs/product-decisions.md`（或 AGENTS.md 的已拍板决定）"；这类核心决策**和 loop 运行中积累的工作记忆分开存放**，只由人修改，防止被日常运行慢慢冲淡。

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
