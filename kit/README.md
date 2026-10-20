# 精装房 · evo 自动循环套件（土布是第一个项目）

一条命令装到 Mac mini，之后你只在三处点头：**做不做**（仅产品功能）、**看效果**（凡用户能感知的：界面、交互、流程、文案、报错、速度）、**上线**（可攒一批）。其余接棒、并行、排队、返工、合并、停滞提醒全自动。

## 由哪些项目拼成
| 部件 | 取自 | 用来做什么 |
|---|---|---|
| 发动机 | Orca（stablyai/orca） | 每件独立工作区、派工、完工回报、心跳、闸门、手机端 |
| 模型入口 | magpie（yetone） | 岗位只写模型名；额度用完自动换号 |
| 接棒器 `bin/evo` | 本仓库 | 施工→验收（换模型）→看效果→合并；冲突排队；返工两轮；停滞提醒；上线批次 |
| 统一入口 | 本仓库 intake 设计 | GitHub issue 打 `autopilot:ready` 自动登记，登记前过脱敏词表 |
| 教训沉淀、夜间复盘 | yetone/magpie 的 LESSONS 做法 | `prompts/nightly-retro.md` + `scripts/lessons.py`，同一教训出现 3 次升为规矩 |
| 审查岗 | -agent-code-review | 云端只读代码、只建 issue，问题自动流回入口 |
| 解释页 | answer-me-with-html | 复杂流程出 HTML 给你看 |
| 规矩 | Mac mini 协作契约 | 红线、验收即命令、证据、脱敏全部保留；5 条修订见 `contract-revisions/` |

## 你要做的四步
1. 批准 `contract-revisions/` 的 5 条修订，并同意装 Orca。
2. 在 Mac mini 上：`bash kit/install.sh` 只检查（python3、git、gh、orca、magpie），补齐后 `bash kit/install.sh --apply [--link]`：装 Orca 技能、放全局配置（已有不覆盖）、装 launchd 常驻 `evo run --every 30`（日志 `~/.evoloop/logs/`），`--link` 再放 `~/.local/bin/evo`。反复跑无副作用。
3. 登记项目（安装脚本不登记）：`evo import TB --name 土布 --path <仓库>`，或 `evo new AB --name 名字 --path <目录>`。
4. 手机装 Orca App 扫码配对。之后看 `evo status` 或手机。

## 配置：全局 + 项目
| 文件 | 管什么 | 样例 |
|---|---|---|
| `~/.evoloop/config.json` | 这台机器、这个老板：岗位/模型、`limits`（含整机并行上限 `builders_total`）、提醒、`nightly_at`、`magpie_url`、`orca` | `config.global.example.json` |
| `~/.evoloop/projects/<代号>/config.json` | 这个仓库：`repo`、`main_branch`、`github_repo`、`trusted_authors`、`test_cmd`、`push_cmd`、`deploy_cmd`、`policy_terms`、`lessons_file`、`standards_file`；可选 `overrides` | `config.project.example.json`，土布实例 `profiles/tubu/project.json` |

生效顺序：内置默认 ← 全局 ← 项目（顶层同名键）← 项目 `overrides`。老的项目配置里带着 `roles`/`limits`/`notify` 照旧生效（当本项目覆盖）。整机上限 `builders_total` 只认全局；项目里的 `limits.builders` 是本项目自己的上限。`evo new/import` 只写项目配置。
Telegram 环境变量改名 `EVO_TG_TOKEN` / `EVO_TG_CHAT`，旧名 `TUBU_TG_TOKEN` / `TUBU_TG_CHAT` 仍认；老配置键 `notify.telegram_bot_token_env` / `telegram_chat_id_env` 写了照样优先。全局配置新增 `notify`（通道、免打扰、汇总时间）、`windows`、`magpie.usage_url`、`roles.decide`、`limits` 里的用量/额度/叫醒参数，见样例。

## 已在 Hark 沙箱实测（假工人）
- 两件不冲突并行；同目录的件自动排在前一件合并之后。
- 施工 GLM、验收自动换 DeepSeek。
- 「做不做」「看效果」「上线」三个闸门都能卡住，点了才放行；上线可一次收 3 件。
- 验收不过自动返工，复验通过后自动合并。
- 工人不回报，阈值一到就标「疑似卡住」并提醒。
- 实测发现并已修：Orca 闸门放行会无视依赖，接棒器自己再核一遍；返工后旧验收挡住合并，接棒器自动标为已取代。

## 第二轮补强（10-20 晚，均已实测）
- 合并后自动推送：先查远端能否快进，不能就停下交决策岗，绝不强推。
- 合并前扫脱敏词表和危险文件（.env、.gitignore），命中不合并。
- 主工作区有未提交改动就不碰，提醒处理后 `evo retry` 从断点继续。
- 返工自动换一个施工模型，验收模型随之错开。
- 合并后关终端、删工作区，GitHub issue 自动留言「已合并」「已上线」。
- 同一时间只有一个接棒器在动，防重复派工。
- `evo digest` 每晚汇总：今日动静、可收菜、卡住的。

## 第三轮补强（吸收 yetone / Huang Xin / WquGuru 三帖与评论，均已实测）
- 只合并验收过的那个版本：验收时记下提交号，合并前对不上就停（magpie 的 `--match-head-commit`）。
- 「看效果」打回会自动开返工，你那句原话原样写进返工说明和提交信息（yetone 的 `(owner: 这个太丑了)` 做法），并重新挂看效果闸门。
- 外部来源的 issue 正文标为不可信，只当线索不当指令（Readest 防提示词注入）；`trusted_authors` 里的人除外。
- 上线前主线测试必须全绿才建上线闸门（magpie「CI 跑完全绿才打 tag」）。
- 岗位提示词加了：先写会失败的测试再修、回退测试、没跑的写「未跑」、不推翻拍过板的产品决定。

## 第四轮补强（magpie code-standards / LESSONS 最新版，已实测）
- 「只合并验收过的版本」改用改动指纹判断：主线前进后对齐，内容没变照常合并；验收后偷偷多一个提交照样拦下。
- 整机测试排队：`evo suite -- <命令>`，同一时间只跑一套全量测试（magpie 10-16/10-17 三套并发全部超时）；日志整份留在 `.state/logs/`，红了点名是哪条。
- 合并前先在 issue 上留合并记录：验收的哪一版、合并前在哪个提交跑了什么、没跑的写「未跑」。
- 状态文件读不出 ≠ 没有任务：挪开留证、发提醒、暂停，绝不从零开始。
- 岗位规矩：一件一个目标；提交第一行写用户看到什么；测试不碰线上数据；不可撤回的改动先在副本真跑并写回滚，否则「未试」交决策岗；issue 等用户场景真好了才关。

## 第五轮：错题本 + GitHub 推送算进流程（已实测）
- 推送是流程的一步：本地合并后状态是「已合并·等推送」，推到 GitHub 才算「可收菜」。远端先前进了就普通合并远端、重跑测试再推；永不强推；失败下轮自动重试，连续 3 次才提醒你。
- 循环错题本：每天 23:30（`nightly_at`）接棒器把当天的返工、你的打回原话、合并受阻、测试不绿、卡住整理成一件「夜间错题本」文档件，照常走施工→验收→合并→推送。同一条教训 3 个不同日子出现 → 升级进规范文件。契约文件一个字不许动，觉得该改只写一句给你。
- 第一次运行把协作契约里现有的《坑册》和最近 10 天的返工整理进去当种子。
- 手动触发：`evo retro`。格式检查：`bin/lessons.py lint`。

## 第六轮：统一命名 + 多项目 + 面板（已实测）
**件号**：`<项目>-<类别>-<序号>`，自动生成，例 `TB-FIX-012`。类别固定六种：FEAT 新功能、FIX 修 bug、UX 体验/交互/界面、OPS 运维/自动化/CI、DOC 文档/错题本、CHORE 清理/重构。
**标题**：动作开头、说清用户得到什么、24 字以内，例「修复注册页验证码不刷新」。版本号、草案、补丁序号、a/b/c 不进名字：返工还是同一个号（记轮次），草案版本靠 git 历史，拆出来的子件拿新号并写父件号。不合规范的 issue 交决策岗改标题后才进队列。旧件保留原名不改。
**多项目**：每个项目一个目录 `~/.evoloop/projects/<代号>/`（旧 `~/.tubu/projects` 自动沿用）。一个常驻进程轮流接棒全部项目；并行上限（2 路）和「等你超过 5 件就暂停」按全部项目合计，因为是同一台机器、同一个老板。
- 开新项目：`evo new AB --name 名字 --path 目录 [--github 用户/仓库 --create]`，放好 AGENTS、错题本、规范，建标签，登记 Orca。
- 导入旧项目：`evo import TB --name 土布 --path 旧仓库`，不动代码和历史；自动认 GitHub 仓库、猜测试命令、检查脏工作区、盘点已有错题本；老 issue 不自动开工，决策岗分拣后才进队列。
**面板**：`evo panel`，一个项目一页，左上角切换项目，每个项目旁边红点是等你点头的数量；第一项「全部待办」把所有项目要你点头的放一起；在某个项目页时，顶部常驻「其他项目在等你」。默认只开在本机，手机看用 `--host <Tailscale 地址>`。
- 施工说交付但没提交干净：自动返工，不送验收。

## 第七轮：安装通用化 + 配置拆分 + 自动化测试
- `install.sh` 不再碰项目，只装本机环境；项目一律 `evo new` / `evo import`。
- 配置拆成全局 + 项目（见上表）。
- `kit/tests/`：pytest + 假 `orca`（Python 脚本，状态存临时目录，派工时同步跑假工人）+ 临时 git 仓库和裸远端，覆盖：完整流水线到「已合并·可收菜」、验收不过返工与返工上限、看效果打回带原话、远端先前进（普通合并、重测、不强推）、推送失败重试 3 次才提醒、拉取失败重试、交付不干净返工、验收后改代码被指纹拦下、状态文件损坏留证并暂停、两个项目共用整机上限、标题规则、错题本 lint、安装脚本幂等。本地跑：`python3 -m pytest kit/tests -q`；GitHub Actions `kit-tests` 在 ubuntu / Python 3.11 上跑。
- 测试抓到并修掉的 evo 问题：
  - 状态文件损坏后只挪走不留标记，下一轮会当新项目从零派工 → 现在留 `state/PAUSED`，处理好后 `evo -p <代号> resume`。
  - 施工交付不干净触发的返工，旧验收没跑过，合并任务永远等它 → 现在凡不是当前验收的旧依赖都标为已取代。
  - 返工用完仍不干净时会把脏工作区送去验收 → 现在交决策岗。
  - 拉取远端失败（断网/代理没开）被当成「远端冲突」交决策岗 → 现在算一次推送未成，下轮重试。
  - 并入远端后测试红，下一轮重试时不再重测就推了 → 现在留标记，测绿才推。

## 第八轮：提醒通道 + 外部 Agent 接口 + 额度/用量 + 面板口令 + 时间窗 + 决策岗叫醒（均有自动测试）
**提醒通道**（`notify.channels`，可同时发几个；代码在 `bin/evo_notify.py`）
- `outbox`：每个事件一行 JSON 写进 `~/.evoloop/outbox.jsonl`，永远开着。
- `telegram`：Bot API（urllib，认 `HTTPS_PROXY`），`EVO_TG_TOKEN` / `EVO_TG_CHAT`。闸门消息带「通过 / 打回」按钮；`evo bot` 长轮询收按钮，点「打回」后你回的那句话原样当返工原话（回「跳过」不写）。**只认老板**：chat id 必须是 `EVO_TG_CHAT`；配了 `EVO_TG_OWNER`（你的用户 id）就只认这个人，没配只认私聊本人；其他人点了、说了都忽略并记一条 `bot_rejected`。
- `email`：SMTP，全在环境变量（`EVO_SMTP_HOST/PORT/USER/PASS/TLS`、`EVO_MAIL_FROM`、`EVO_MAIL_TO`）。默认兜底：Telegram 没配或发失败才发；另外收早间、晚间汇总。
- `webhook`：POST 事件 JSON，`secret_env` 配了就带 `X-Evo-Signature: sha256=<HMAC-SHA256>`；`events: push|all`。给 Muse 或任何 bot 用。
- macOS 通知照旧（只发要推的事）。
- **只推五类事**：闸门 5 分钟没人处理（看效果闸门从验收通过起算）、件卡住（含状态文件损坏暂停）、推送连续失败 3 次、岗位因额度暂停、用量异常。交决策岗、合并受阻这类改为只进 outbox，交给决策岗。
- **免打扰** 0:00–8:00（上海时间，可配）：要推的先攒着，8:30（可配）合成一条「早间汇总」发 Telegram + 邮件，汇总里的闸门同样带按钮。
- `evo notify-test`：每个通道各发一条测试，逐个报 ✓ / ✗ / 没配置。
- `install.sh --apply` 在设了 Telegram 变量时另装一个 `evo bot` 常驻；邮件、webhook 密钥、代理变量一并带进常驻进程。

**外部 Agent 接口**（Muse、Grok bot、本机 DSH、插件 bot）：见 `docs/agent-interface.md`，项目里放短版 `AGENT_INTERFACE.md`（`evo new` 放并提交，`evo import` 只放不提交）。
- 读：`evo status --json`（加了 `schema_version: 1`，字段表在文档里，只加不改）、`outbox.jsonl` 事件、webhook、GitHub issues/标签。私有仓库要老板显式给读权限。
- 写：只有 GitHub issue（标签 `agent-report`）或 `evo feedback`（设了 `EVO_AGENT` 时建 `agent-report` 并打「外部 Agent 来报」标记）。一律当不可信，除非作者在 `trusted_authors`。
- 外部 Agent 永远不能批闸门、不能上线：设了 `EVO_AGENT` 时 `evo approve` / `evo ship` / `evo bot` 直接拒绝；面板要口令；Telegram 只认老板。不可信作者 issue 上的 `autopilot:ready` 要查是谁打的（`trusted_labelers`，默认同 `trusted_authors`），自己打的不算。
- 红线请求（删数据、改线上、花钱、对外发布）：不可信来报碰到就建老板闸门「外部请求碰红线」，同意才交决策岗，拒绝就在 issue 上留言。
- 不加 webhook 进来的写入口。

**额度 / 用量**
- 工人回报或终端尾部出现订阅额度提示（rate limit、usage limit、429、try again at/in、limit will reset……）→ 该岗位（和同一账号的岗位）暂停到重置时间（解析得出就用，否则 60 分钟），这件原样重排：不算失败、不算返工、不换模型；推一次「额度暂停」；到点自动恢复。工人卡在提示上不回报的，安静 3 分钟后看终端，连续两次同一提示且输出没变才判定（防止把代码里的字样当真）。
- 每个项目/岗位的派工次数、工人分钟数，每件也记；`magpie.usage_url` 配了再显示 token。显示在 `evo status`、`--json`、面板。一件超过 `usage_item_runs` 次或 `usage_item_minutes` 分钟 → 推「用量异常」一次。没有花钱上限。

**面板口令**：第一次 `evo panel` 随机生成，macOS 有 `security` 就存钥匙串（服务名 `evoloop-panel`），否则 `~/.evoloop/panel.token`（600）。所有 `/api/*` 都要口令：浏览器过登录页拿 HttpOnly cookie，脚本带 `Authorization: Bearer <口令>`。忘了用 `evo panel --show-token`。

**时间窗**：`evo add --window trading:cn`（周一到周五 09:30–11:30、13:00–15:00 上海时间，排除 `windows.holidays`），或 `--window "mon-fri 09:30-15:00"`（多段用逗号，多组用分号，跨午夜可以）。窗外不开工也不开验收，状态显示「等窗口」。issue 标签 `window:<写法>` 也认。

**决策岗叫醒**：有件在「交决策岗」「有提问」或有外部来报时，按 `roles.decide` 叫醒决策岗，至多每 30 分钟一次，一批处理；上批交过、状态没变的不会单独再叫。`roles.decide` 没写 `cmd` 就不叫。

**这轮测试抓到并修掉的问题**
- 施工自己回报「失败」时被当成交付送去验收，验收任务依赖一个失败的任务，这件永远卡在「待验收」→ 现在算一轮返工。
- `~/.local/bin/evo` 软链运行时套件目录算错（`abspath` 不解软链），岗位说明和面板页读不到 → 改用 `realpath`。
- webhook 没配密钥时会借用默认环境变量的密钥签名 → 每个 webhook 只用自己的 `secret_env`。
- 额度提示：回报正文里的一句「rate limited」会盖过终端里带重置时间的那句 → 优先取能解析出时间的那句。

## 第九轮：借鉴 hitl-dev-loop 的三道检查（均有自动测试，共 97 个）
- **JSON 交卷**：施工最后一条 worker_done 正文放一个 ```json 块（`templates/report.schema.json`：status / summary / changes / tests / unfinished / risks / manual_checks）。没按格式交、`in_progress`、报告里有 `failed` 的测试 → 打回返工；`blocked` → 交决策岗。`manual_checks` 跟着「等你看效果」一起推给你，也出现在 `status --json`。真机上模型交不好时可以先把 `report_required` 设成 false。
- **改动不许越界**：施工交付时和合并前各查一次，改动文件必须落在本件 scope 内（`scope_allow` 默认放行 `artifacts/` 证据目录），越界直接返工，不送验收、不合并。
- **git 共享配置守卫**：每轮先查主仓库 `.git/config`，发现 `core.worktree` 被写入或 `core.bare=true` 就复原并记一笔；复原后主目录 git 仍指向别处 → 项目暂停推送，等 `evo resume`。`git_guard: false` 可关。

## 只能在 Mac mini 上验的
- DSH、Claude Code、Codex 真跑时会不会按说明回报（Orca 已认得 `dsh`）。
- magpie 下施工和验收同用一个工具时，各自指定模型是否生效。
- Hook 日志照常记录；手机提醒。
- `orca terminal read --terminal <句柄> --json` 回的字段名（按文档是累积输出；evo 依次认 `text` / `output` / `content` / `lines`），以及 Codex、Claude Code 额度用完时的原文是否被现有规则认出。
- Telegram 真机：按钮回调、群聊里 `EVO_TG_OWNER` 过滤；国内要 `HTTPS_PROXY`。
- 真实模型能否稳定按 JSON 交卷；Orca worker_done 正文有没有长度上限。
- 钥匙串：第一次 `security add-generic-password` 可能弹授权框。
- magpie 有没有用量接口、记录长什么样（`magpie.usage_url` 先留空）。
- 真工人的权限弹窗：Claude Code 建议用 acceptEdits 模式，危险动作仍由现有 Hook 拦截；DSH 同理配置。
