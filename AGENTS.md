# AGENTS.md · evo 自己的仓库

> 给在本仓库里干活的 Agent 看（施工、审查、Hark、Claude 都算）。只写事实和规矩，细节跟着链接去读。
> 本文件里的每一条都能在仓库里找到出处；改了代码让某条不再成立，同一个提交里改这里。

## 这是什么
evo 是一个通用的自动开发循环：老板说需求、拍板，evo 负责排队、派工、返工上限、闸门、合并、上线。
一件事 = 施工 → 验收（换一个模型）→ [看效果] → 合并。执行端现在是 Multica（一件一个 issue，施工 / 验收 / 决策是三个固定 agent），
老项目还可以走 Orca。全景图见 `docs/loop-overview.md`；Multica 后端设计见 `docs/multica-backend.md`。

## 目录
| 目录 | 放什么 |
|---|---|
| `kit/bin/` | 内核：`evo`（接棒器，`tubu` 是旧名）、`evo_exec.py`（执行端 Orca / Multica）、`evo_notify.py`（提醒）、`evo_rt.py` / `evo_bus.py`（功能包运行时、事件）、`evo_roles.py`、`evo_time.py`、`lessons.py` |
| `kit/features/` | 功能包，一个目录一个（team、deploy、digest、github、notify-*、ui-preset、arch-preset、item-caps…），说明见 `docs/architecture.md` |
| `kit/roles/` | 岗位规则：`builder.md`（施工）、`verifier.md`（验收）、`decider.md`（决策）、`retro.md`（夜间错题本）。派工时 evo 把它们注入任务书 |
| `kit/multica/` | 在本机装 / 固化 Multica daemon 和 dsh runtime 的脚本（`install.sh`），说明见 `kit/multica/README.md` |
| `kit/tests/` | 全部测试；`kit/tests/fakes/` 是假 orca / multica / gh / curl 和假工人 |
| `kit/templates/project/` | `evo new` 给新项目放的骨架（AGENTS.md、CLAUDE.md、AGENT_INTERFACE.md、docs/LESSONS.md、docs/code-standards.md） |
| `kit/schemas/` | 对外 JSON 的格式（status、team、event…） |
| `kit/selfmaint/` | 看门狗和回退（`evo-guard.sh`），只有老板手改 |
| `app/` | macOS App（SwiftUI），说明见 `app/README.md` |
| `docs/` | 设计和说明，只放 `.md`（唯一例外 `docs/loop-overview.html`） |
| `notes/` | `decisions.md`（决策记录，只追加）、审查分诊等工作笔记 |

## 常用命令
```bash
# 全量测试（本机约 2.5 分钟；CI 用 -n auto 并行）
pip install pytest pytest-xdist import-linter ruff jsonschema
cd kit && python3 -m pytest -q tests
# 只跑一个文件
cd kit && python3 -m pytest -q tests/test_multica_backend.py

# evo 本身（多项目时加 -p <代号>）
kit/bin/evo status [--json]        # 等你的、进行中、卡住的；--json 格式见 docs/agent-interface.md
kit/bin/evo -p EV tick             # 接棒一轮：派工、收回报、合并、查停滞
kit/bin/evo -p EV runs [件号]      # 永久运行记录 runs/<件号>/
kit/bin/evo selfcheck [--json]     # 自检（编译、功能包、事件、金丝雀）
kit/bin/evo canary                 # 判据金丝雀：已知不合格的样例必须判不过
kit/bin/evo models                 # 核对施工 / 验收模型（Orca 路线）
kit/bin/evo suite -- <测试命令>    # 岗位跑全量测试时用：整机排队

# 安装
bash kit/install.sh                # 只检查
bash kit/install.sh --apply --dev  # 开发用：直接跑仓库里的 kit
```
正式安装跑 `~/.evoloop/current → releases/<提交>`，换版本只能 `evo self-upgrade`（先自检、等一轮结束、切换后再自检）。

## 硬规则
1. **不提交密钥、真实路径、图片。** `.env`、key、token 一律不进库（`.gitignore` 已挡一部分）；文档和代码里的家目录写 `~`，不写真实用户名路径；截图只放 CI 构件和本机（`app/docs/screenshots/` 已忽略）。
2. **施工模型 ≠ 验收模型。** Orca 路线由团队功能包在每次派工时查「撞模型」；Multica 路线由 `model_guard_check` 每轮读两个 agent 的模型，相同或读不到就停派工（`multica.allow_unverified_models: true` 才放行读不到的情况）。别绕开。
3. **外部 Agent 不批卡、不上线。** 外部 Agent 运行时设 `EVO_AGENT=<名字>`；`approve`、`ship`、`goal set`、`team set`、`feedback --item` 等在设了它时一律拒绝（`refuse_agents`，见 `docs/agent-interface.md`）。issue 评论里的「/approve」不算批准。
4. **不走 PR。** evo 自己在自己的克隆里合并、推 main；本仓库的改动也直接提交到 main，一个目标一个提交。
5. **改动配测试。** 改行为就加或改 `kit/tests/` 里的测试；全量测试过了才推。修 bug 先写一个现在会失败的测试。
6. **讲解页 `.md` 为源，html 不提交。** html 按需用 answer-me-with-html 生成，不提交（`.gitignore` 已挡 `docs/` 下的 html），唯一例外 `docs/loop-overview.html`；改了 `loop-overview.md` 没重新生成它，就在 `.md` 里写一句。
7. **JSON 合约只加字段。** `status --json` 等给 App 的输出带 `schema_version`；只加字段不改不删，要改就升版本号（`docs/app-contract.md`）。
8. **看门狗谁都不许改。** `kit/selfmaint/` 只有老板手改；EV 自维护时受保护路径的件合并前要老板点头。
9. **文档、注释用中文，说人话。**

## 已知的坑（出处：`notes/decisions.md`、`kit/README.md`、`docs/multica.md`）
- **Multica run 在跑时 issue 不留评论、状态不变。** 不能拿「多久没回报」判卡住：run 活跃就算活着，兜底靠 `limits.run_max_minutes`（默认 60）。
- **返工 / 换人前先停掉旧 run。** 旧 run 还在跑时新 run 只能排在后面，旧 run 交的卷也没人收（`issue cancel-task`）。
- **不做（drop）后 agent 会把 issue 改回 in_review。** `close(ok=False)` 先 cancel 在跑的 run，每轮 `reconcile_closed` 再把 issue 状态对齐 done / cancelled。
- **scope 只认路径。** 登记时 `--scope` 写成一整句中文会被当成一条「路径」，改动全判越界；现在按 `, ， 、 ; ；` 和空白拆，说明文字放任务书。
- **跳过 ≠ 通过。** 验收结论不认识、`skipped`、全量测试全跳过，都按不通过算（第二十二轮金丝雀专门盯这个）。
- **一台机器同一时间只跑一套全量测试。** 并发跑全量会全部超时，用 `evo suite`。
- **dsh 钉在 0.1.0-rc.6。** dsh 0.2.x 和 Multica 的 dsh runtime 不兼容（`kit/multica/README.md`）。
- **Multica 网页链接要带 workspace slug**（`{app_url}/<slug>/issues/EVO-13`），不带会跳登录页；mini 上 Multica 前端端口是 3300，别改回 3000（给土布让出来了）。

## 先读什么
- 动循环逻辑：`docs/loop-overview.md` → `docs/multica-backend.md` → `kit/README.md` 对应那一轮。
- 动岗位规则：`kit/roles/*.md`（注入有字节上限：施工 15800、验收 13500、决策 8000）。
- 拿不准为什么现在这样：`notes/decisions.md`；外部审查分诊：`notes/review-2026-10-23-triage.md`。
