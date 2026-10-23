# evo · 自动开发循环

> 老板说需求、拍板；evo 负责排队、派工、返工上限、闸门、合并、上线。
> 一件事 = 施工 → 验收（换一个模型）→ [看效果] → 合并。土布是第一个项目，evo 也用 evo 维护自己。

## 先看这几篇

- [`docs/loop-overview.md`](docs/loop-overview.md)：循环全景——入口、账本、调度、工位、拍板，谁改什么（渲染好的 [`docs/loop-overview.html`](docs/loop-overview.html)）
- [`kit/README.md`](kit/README.md)：套件怎么装、怎么用、每一轮改了什么
- [`docs/multica.md`](docs/multica.md) / [`docs/multica-backend.md`](docs/multica-backend.md)：Multica 执行端
- [`docs/architecture.md`](docs/architecture.md)：内核 + 功能包
- [`AGENTS.md`](AGENTS.md)：在本仓库干活的 Agent 先读（目录、命令、硬规则、已知的坑）

讲解页以 `.md` 为源；需要好看的版本时用 [answer-me-with-html](https://github.com/QingYunA/answer-me-with-html) 本地生成，不提交（唯一例外 `docs/loop-overview.html`）。

## 人只在三处点头

**做不做**（产品功能）、**看效果**（凡用户能感知的）、**上线**（可攒一批）。其余接棒、并行、排队、返工、合并、停滞提醒由 evo 做。

## Multica 执行端

新项目默认用 Multica 派工：任务落成 Multica issue，派给施工 / 验收 / 决策三个 agent，进度和验收结论也都在 issue 上。evo 不搬过去，只继续管排期、闸门和上限（返工次数、派工次数、单件时长）。施工模型必须和验收模型不同，evo 每轮派工前核对。

## 快速开始

```bash
git clone https://github.com/JAY5CXSDMY14/evomap.git evoloop
bash evoloop/kit/install.sh                # 只检查
bash evoloop/kit/install.sh --apply        # 安装（详见 kit/README.md）
evo new AB --name 名字 --path <目录>        # 新项目：放好 AGENTS.md、CLAUDE.md、docs/LESSONS.md、docs/code-standards.md
evo status
```

## 目录

| 目录 | 放什么 |
|---|---|
| `kit/` | evo 本体：内核 `kit/bin/`、功能包 `kit/features/`、岗位规则 `kit/roles/`、新项目骨架 `kit/templates/project/`、测试 `kit/tests/` |
| `app/` | macOS App（SwiftUI，已冻结不再加功能） |
| `docs/` | 设计和说明 |
| `notes/` | 决策记录（`notes/decisions.md`，只追加）和工作笔记 |

## 错题本

agent 犯过的错写进 `LESSONS.md`，同一教训出现 3 次升为硬标准（机制见 [`docs/lessons-system.md`](docs/lessons-system.md)）。本仓库自己的错题本在根目录 [`LESSONS.md`](LESSONS.md)。

## 致谢与来源

- [yetone/magpie](https://github.com/yetone/magpie)：`AGENTS.md`、`LESSONS.md`、`docs/code-standards.md`、`docs/contributors.md` 的做法（调研见 [`docs/magpie-reference.md`](docs/magpie-reference.md)）
- WquGuru《yetone 的魔法：magpie 是怎么让 AI 自己维护项目的》（X，2026-10-12）

> 第一版（v1：GitHub Actions + PR 互审的八阶段流程，`scripts/`、`prompts/`、`templates/`）已在第 24 轮删除，要看去 git 历史（删除前最后一个提交 `cf3c890`）。
