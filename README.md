# evoloop · 自进化循环

> 让 AI Agent 不只是写代码，而是**发现问题 → 解决问题 → 自证 → 互审 → 合并发布 → 复盘 → 把教训写回规则**，每转一圈，系统就更难犯同样的错。

evoloop 是一套**可直接套进任何代码仓库的 AI 开发循环架构**：一组文档模板、Agent 提示词、自动化脚本和 CI 工作流。它提炼自 [yetone/magpie](https://github.com/yetone/magpie) 的公开实践（19 天 2,862 个 commit、1,204 个版本，写、审、合、发全部由 agent 完成），并结合作者 2026-10-13 公开的做法（Claude Code `/loop` 并行 3 条循环），把编排补成可落地的四档方案：**常驻 loop 会话、手动、GitHub Actions、调度器**，以及配套的复盘提示词。

---

## 土布循环 · 一图看懂

- [`docs/loop-topology.html`](docs/loop-topology.html)：整体拓扑、一件事的状态机、睡一晚怎么推进、岗位与担任者、和 Mac mini 现有机制对照（下载后用浏览器打开；源稿 [`docs/loop-topology.md`](docs/loop-topology.md)，用 [answer-me-with-html](https://github.com/QingYunA/answer-me-with-html) 生成）
- [`docs/autopilot-explainer.html`](docs/autopilot-explainer.html)：面板长什么样、你怎么交互

## 一张图看懂

```
            ┌──────────────────────────────────────────────────────────┐
            │                    规则层（Agent 每次开工必读）            │
            │  AGENTS.md 路由表 · code-standards.md 硬标准 · LESSONS.md 错题本 │
            └──────────────▲───────────────────────────────┬───────────┘
                           │ ⑧ 进化：Seen 3× 升级为硬标准      │ 读取
                           │                               ▼
 ① 入口      ② 分诊       ③ 认领+隔离    ④ 实现+自证     ⑤ 互审        ⑥ 合并        ⑦ 发布
 Issue/反馈 → Triage  →  Claim+Worktree → Implement  →  Review   →  Merge@sha  →  Release
                                                                                     │
                           ▲                                                         │
                           └──────────── ⑧ 夜审复盘 Nightly Retro ◀─────────────────────┘
                                        找：返工 · 不该合 · 验证太薄
```

**一句话本质**：不是让 agent 自动写代码，而是让 **agent 犯过的错自动变成下一轮 agent 的约束**。

---

## 八个阶段（详见 [docs/loop.md](docs/loop.md)）

| # | 阶段 | 谁做 | 产出 | 闸门（不过不往下走） |
|---|---|---|---|---|
| ① | 入口 Intake | 用户 / 社区 / 维护者 | Issue（复现、期望、原始数据） | 必须是 Issue，不收外部直接改代码 |
| ② | 分诊 Triage | Triage Agent + 人拍板 | 标签：接受 / 拒绝 / 需信息 / 需人决定 | 符合产品方向；涉及安全或产品取舍 → 人 |
| ③ | 认领 Claim | Builder Agent | Issue 评论"我在做" + 独立 worktree | 无人正在做同一问题 |
| ④ | 实现 Implement | Builder Agent | 一个目标一个 commit；带证据的 commit 正文 | 回退必挂测试 + 全量检查 + 写明没跑的 |
| ⑤ | 互审 Review | Reviewer Agent（≠Builder） | PR 评论：Harm / Red / Break / Ran / Not run | 合到最新 main 重跑；故意改坏必挂 |
| ⑥ | 合并 Merge | Reviewer Agent | `--match-head-commit <审过的 sha>` | head 变了就重审 |
| ⑦ | 发布 Release | Release Agent | tag + 产物 | CI 在该 commit 全绿（取消不算）；攒批发 |
| ⑧ | 复盘 Retro | Retro Agent（每晚定时） | LESSONS.md 新条目、Seen 计次、升级 | 每条有 sha/issue 证据，且 sha 已校验存在 |

---

## 人与 Agent 的分工

| 人（维护者）负责 | Agent 负责 |
|---|---|
| 产品方向、需求取舍 | 读懂需求、复现问题 |
| 已拍板的产品决定（Agent 不得推翻） | 实现、测试、自证 |
| 安全闸门放行（凭证 / 网络 / CI / 依赖 / 数据删除） | 互审、合并已审 head |
| 拉黑、对外承诺 | 发布准备、写 Release Notes |
| 用**一句话**指出"哪里不对" | 把一句话变成可验证的改动 + 几百字的证据 |

magpie 的作者给 agent 的指令通常就一句话，例如 `(the owner: 这个太丑了)`、`(the owner: 这里为啥是原生的 selector 而不是我们抽象的 ComboBox？)`，agent 把原话放进 commit 标题、把其余全部补齐。evoloop 保留这个习惯：**需求来源永远写进 commit 标题**。

---

## 仓库结构

```
evoloop/
├── README.md                    ← 你在这里
├── docs/
│   ├── loop.md                  ← 八个阶段的详细规格（输入 / 动作 / 输出 / 闸门 / 反模式）
│   ├── lessons-system.md        ← 错题本机制：格式、计次、升级、降级、清理
│   ├── orchestration.md         ← 四档编排（L0 = magpie 实际的 /loop 做法）、派活、并行、agent 选型
│   ├── adoption.md              ← 分阶段接入一个现有项目（以 tubu-platform 为例）
│   └── magpie-reference.md      ← 原始调研：magpie 的循环、数据、来源
├── templates/                   ← 拷进目标仓库根目录的文件
│   ├── AGENTS.md                ← 路由表：干什么活之前读哪份文档
│   ├── CLAUDE.md                ← 两行：@AGENTS.md @LESSONS.md
│   ├── LESSONS.md               ← 错题本（空白 + 示例条目）
│   ├── docs/code-standards.md   ← 验收标准 + Review 清单 + commit 规范
│   ├── docs/contributors.md     ← 外部贡献的安全闸门
│   ├── docs/subsystems/_template.md
│   └── .github/                 ← Issue 模板、PR 模板、夜审 & 守卫工作流
├── prompts/                     ← 每个角色的系统提示词
│   ├── triage.md
│   ├── builder.md
│   ├── reviewer.md
│   ├── release.md
│   ├── nightly-retro.md
│   └── loops/                   ← L0 档的三条 /loop 提示词（渠道 / 社媒反馈 / 清理复盘）
└── scripts/
    ├── install.sh               ← 一键把 templates 装进目标仓库
    ├── claim.sh                 ← 认领 Issue + 建 worktree
    ├── red-check.sh             ← 回退检查：旧代码下新测试必须失败
    ├── merge-reviewed.sh        ← 只合并审过的 sha
    ├── release-gate.sh          ← CI 全绿才允许打 tag
    ├── retro-collect.sh         ← 收集复盘窗口内的 commit/PR/返工线索
    └── lessons.py               ← 错题本工具：校验格式、校验 sha、列出该升级的条目
```

---

## 快速开始

```bash
# 1. 装进目标仓库（不会覆盖已有文件，冲突会生成 .evoloop.new）
git clone https://github.com/JAY5CXSDMY14/evomap.git evoloop
./evoloop/scripts/install.sh /path/to/your-repo

# 2. 填写占位符（搜索 {{ 即可）
grep -rn "{{" /path/to/your-repo/AGENTS.md /path/to/your-repo/docs/code-standards.md

# 3. 第一次复盘：对最近 3 天的 commit 跑一遍，生成第一版 LESSONS.md
cd /path/to/your-repo
../evoloop/scripts/retro-collect.sh --since "3 days ago" > /tmp/retro-context.md
# 把 prompts/nightly-retro.md + /tmp/retro-context.md 交给你的 coding agent

# 4. 打开夜审定时任务（.github/workflows/evoloop-nightly-retro.yml）
```

接入建议**分四期**，不要一次全上，见 [docs/adoption.md](docs/adoption.md)。

---

## 设计原则

1. **规则写在仓库里，不写在人脑里。** Agent 每次启动都会读到；口头叮嘱下次就没了。
2. **规则从事故里长出来。** 不预先设计一百条规范；每晚只记真实发生的返工和错误合并。
3. **事不过三。** 同一条教训在 3 个不同日子出现，升级为硬标准，review 逐条核对。
4. **证明，而不是声称。** 回退必挂（Red check）、改坏必挂（Break check）、没跑就写没跑（Not run）。
5. **写的人不审自己。** Builder 与 Reviewer 是不同会话、最好不同模型。
6. **只合并审过的那一个 sha。** 审的过程中有人 push，合并直接失败。
7. **慢下来也是规则的产物。** magpie 引入错题本后，日发版数 168 → 42 → 15，没人开会。
8. **人只管方向和闸门。** 其余交给循环。

---

## 土布配置档（本仓库现以土布为基准）

- `profiles/tubu/`：土布的岗位表与现场路径
- `docs/role-slots.md`：岗位而非工具，担任者可替换
- `docs/autopilot.md`：自动接棒、不冲突并行、自动合并、老板收菜（图解 `docs/autopilot-explainer.html`）
- `docs/intake.md`：五类问题来源统一进 GitHub issue、网站反馈转发、分诊、老板三处点头
- `docs/live-monitoring.md`：实时进度与卡死监测（等权限 / 待接棒 / 停了没交付 / 卡死 / 进程没了）
- `docs/relay-layer.md`：传话层（L1 一键接力）规范：收件箱、扣留审批、忙闲状态

## 第二个参考案例

Readest 在 magpie 基础上加了人工审批台、只处理自己的 PR、事件唤醒、人工发版和种子错题本，见 [docs/readest-case.md](docs/readest-case.md)。

## 致谢与来源

- [yetone/magpie](https://github.com/yetone/magpie)：`AGENTS.md`、`LESSONS.md`、`docs/code-standards.md`、`docs/contributors.md`
- WquGuru《yetone 的魔法：magpie 是怎么让 AI 自己维护项目的》（X，2026-10-12）
- magpie 的子系统文档与语义变更审查来自社区成员 Junjie Zhou（PR #889）

evoloop 本身也用 evoloop 维护：见本仓库根目录的 [LESSONS.md](LESSONS.md)。
