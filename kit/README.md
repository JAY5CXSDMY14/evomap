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

## 第十轮：闸路补齐 + 少找你 + 停了能知道（均有自动测试，共 120 个）
- **决策岗的决定自动执行**：决策岗在 worker_done 正文交 ```json `{"decisions":[…]}`（格式见 `roles/decider.md` 第 12 条）。`retry` 从断点继续（没断点就带说明返工）；`rework` 带说明返工、轮次清零；`drop` 不做并清理；`split` 原件不做、登记子件（`parent` 记父件）；`ask_owner` 建「同意 / 不同意」老板闸门并立刻推送，老板答了作为【新】件回到下一批；`answer` 回答施工提问。没交 JSON 或格式不对只记日志，件留到下一批。
- **施工提问有人答**：Orca 目前没有回复工人的命令，`deliver_answer()` 先用兜底——带着「决策岗答复：…」开一轮返工（不扣轮次，原工作区接着做）。以后 Orca 支持回复，只换这一个函数。
- **pull 不再每轮刷屏**：`autopilot:ready` 但缺 `scope:` / `type:` 标签或标题不合规的 issue，按「issue 号 + 原因」只交决策岗一次（`pull_flagged`），补好后下轮自动登记。
- **先上线再标记**：点「上线」先跑 `deploy_cmd`，成功才标已上线、留言并 `gh issue close`；失败件留在可收菜、清掉上线闸门、推送 `deploy_failed`（上线失败）。点「再等等」也清闸门，下次重新攒批。
- **崩溃安全**：派工、返工、合并、改状态后立刻存盘；处理过的 Orca 消息号记在 `msg_seen`（最多 500 个），重投的跳过。
- **对齐主线冲突、合并前测试红 → 自动返工**（算一轮，原因里带冲突/红行，要求施工 rebase 到 main 修好），超上限才交决策岗；脏主目录、脱敏、危险文件、越界、验收后改动照旧直接交决策岗。
- **自动收菜**：每天 `ship_gate_at`（默认 08:20）之后第一次有已合并的件，且没有等着的上线闸门，就自动建上线闸门（主线测试绿才建），一天一次；`auto_ship_gate: false` 关掉。
- **心跳与看门狗**：每轮写 `~/.evoloop/heartbeat.json`；`evo watchdog`（可挂 launchd）和 `evo bot` 每轮检查，超过 10 分钟（`limits.heartbeat_stale_minutes`）没转动推一次「卡住」，恢复后再停才再推；`status --json` 新增顶层 `last_tick`。
- **不做即清理**：任何途径变成「不做」都关终端、删工作区，合并任务标完成，排在它后面的件不再干等。
- **夜审补跑**：过了 23:30 当天没跑的下一轮照跑；第二天中午前开机先补昨天的（只补一天，新项目不补）。日志时间统一走 `evo_time` 的钟。
- **install.sh 防睡眠检查**：macOS 上 `pmset -g` 显示 sleep / disksleep 不是 0 就警告，并给出 `sudo pmset -a sleep 0 disksleep 0`（只提示，不替你跑 sudo）。

## 第十一轮：看效果指纹 + 死工人自动重启 + ponytail + 模型核对与面板覆盖（均有自动测试，共 139 个）
- **看效果指纹**：老板「看效果 通过」时记下本件自己改动的 patch-id（复用 `patch_id()`）和提交号。之后这件又返工（C6 冲突 / 合并前测试红、决策岗返工），合并前重算：指纹相同 → 不重看直接合并；不同 → 在合并任务上重开看效果闸门「看效果（改动后重看）」，说明「解冲突/返工时改了你看过的内容」，和普通看效果闸门一样 5 分钟没人点就推（带按钮）。打回会清掉指纹。配置 `relook_on_change`（默认 true）。
- **C7 死工人自动重启**：`check_stalls` 发现工人进程不在了（`worker-show` 的 orphaned / observation 不是 live），且这次派工的任务还没交 worker_done，就在原工作区、同岗位、同模型重启一次：关旧终端、旧任务标 failed、新建任务（施工连带新验收）、立刻派工，记日志和 `worker_restarted` 事件（只进 outbox）。次数记在派工上（`dispatch.restarts`），重启出来的派工再死 → 老路：标疑似卡住并推送。新一轮返工的派工重新计数。
- **ponytail 进岗位**：`kit/vendor/ponytail/` 放官方仓库固定提交 `09c434ab73ca43761c5d8b0c5d341926c2fba710` 的 `ponytail/SKILL.md`、`ponytail-review/SKILL.md` 和 MIT `LICENSE`（README 写来源和升级办法）。`roles/builder.md` 第 13–16 条：full 档、不用 ultra；任务书验收标准压过「最少代码」；收尾的跳过/没查/风险写进交卷 unfinished / risks；允许 `shortcut:` 注释。`roles/verifier.md` 第 14–18 条：按 review 清单读调用方；必须修 → 打回；应该修 → 结论里建议另开 issue，不挡合并；每条发现要有具体触发情形。工人没装 skill 时提示词里的 `{KIT}` 换成本机套件路径，指向固定副本。
- **每周 audit 待办**：夜审那天是 `audit_weekday`（0=周一 … 6=周日，默认 6 周日）就往决策岗收件箱放一条「每周 ponytail-audit」例行待办（决策岗任务书里单列「例行待办」一节，不和外部来报混），只提醒不自动跑。
- **模型核对**：新命令 `evo models [--json]` 读 magpie `GET {magpie_url}/v1/models`，全局（和改过模型的项目）里 `roles.build.models` / `roles.verify.models` 不在列表里就警告；施工和验收有重叠也警告（列表里的组带 `members`/`models` 字段时按成员比）。magpie 不通只跳过列表核对。退出码：有警告 1。`install.sh` 检查时 magpie 通就顺带跑一遍（只警告不拦）。全局模型可直接写 magpie 组名，如 `group/evo-build`、`group/evo-verify`。
- **装进 Evo 应用**：`install.sh --apply` 写的 launchd plist 环境变量里加 `PYTHONDONTWRITEBYTECODE=1`（常驻进程不在套件目录写 `__pycache__`）；evo 从应用包里跑（路径含 `.app/Contents/Resources`）时 `notify.macos` 默认关（本机通知由应用发），任何一层配置显式写了 `notify.macos` 就听配置的。
- **面板单项目覆盖**：项目页新增「模型（本项目）」：施工模型 / 验收模型下拉框，选项来自 magpie（读不到就改成手填），第一项「跟随全局（…）」。保存写项目配置 `overrides.roles.<岗位>.models=[模型]`，选跟随全局就删掉覆盖。接口 `GET /api/models/<代号>`、`POST /api/models {code, role, model}`，都要面板口令；实际由 `evo -p <代号> models set|clear <岗位> [模型]` 执行，设了 `EVO_AGENT` 一律拒绝；模型名只许字母数字和 `. _ : / @ + -`（会进工人命令行）。下一次派工生效。

## 第十二轮：借 Paperclip 面板 6 处（均有自动测试，共 154 个；见 docs/paperclip-notes.md）
- **无活路检查**：每轮 `check_no_live`：没完结的件（可收菜 / 已上线 / 不做不查）必须有一条活路——施工中/验收中且没标疑似卡住；排队且施工任务 ready（等名额、时间窗、额度、「等你的事太多」都会放开）或 blocked（做不做闸门等你）或 pending 且依赖都还在；待验收且验收任务 ready；验收通过且看效果闸门等你或合并任务还能走；交决策岗/有提问且（决策岗正在看 / 下一批会看到 / 转老板的闸门没答 / 决策岗额度暂停到点会叫）；等推送（每轮自动重试）。都不是就开始计时，超过 `limits.no_live_path_minutes`（默认 30）：往决策岗收件箱放一条「没有活路」（同件、同原因、状态和轮次没变只放一次），时间线记 `no_live_path`，outbox 记事件；`status --json` 顶层 `no_live_path`、每件 `no_live_path`，面板标红。决策岗用原有决定处理：`retry` 对这类件等于带说明返工，`rework` / `drop` / `ask_owner` 照旧。原因代号：`stalled`（自动重启也用过了）、`dep_dead`、`task_dead`、`no_decider`（没配决策岗命令）、`decider_idle`（决策岗看过没给决定、状态没变）。
- **看效果闸门内预览产出物**：面板看效果闸门卡片和件页列出本件工作区 `artifacts/`：png / jpg / gif / webp 直接显示；`.html` 拿文本放进 `<iframe sandbox="allow-scripts" srcdoc>`，前面加 CSP meta（`default-src 'none'`、`connect-src 'none'`，断网），绝不给同源权限；其他文件给下载链接。接口 `GET /api/artifacts/<代号>/<件号>`（清单 + 施工交卷的 manual_checks）、`GET /api/artifact/<代号>/<件号>/<路径>`，都要面板口令；挡 `..`、绝对路径、软链跑出 artifacts/（软链不列出），超过 5MB（全局 `panel.artifact_max_mb`）回 413；所有产出物响应带 `X-Content-Type-Options: nosniff` 和 `Content-Security-Policy: default-src 'none'; sandbox`，HTML 以 `text/plain` 返回，其他非图片以附件下载。
- **面板首页**：项目页顶上「岗位状态」一行（施工 / 验收 / 决策：忙、闲、暂停、额度满；暂停原因如「没配置命令」「等你看效果的超过上限，暂停新施工」），另有「没有活路」「卡太久」清单。卡太久 = 同一状态超过 `limits.stale_hours`（默认 6）小时（进入状态的时间 `state_since` 在每次存盘时记）。`status --json` 新增 `roles`、`stale`、`goal`、`no_live_path`、`items[].state_since / no_live_path / look_gate`，只加字段，schema_version 仍是 1。
- **每件时间线**：`~/.evoloop/projects/<代号>/state/timeline.jsonl` 只追加，记登记、派工、交卷（正文前 2000 字）、开闸门、通过 / 打回（原话在 `words`）、闸门作废、补充反馈、返工（原因）、合并（提交号）、推送、上线 / 上线失败、工人重启、决策岗决定、不做、每次换状态、没有活路 / 恢复活路。`evo -p TB log TB-FIX-012 [--json | --diff]`（只读、不抢锁）；面板点件进件页看时间线、交卷、产出物和 diff（`GET /api/item/…`、`GET /api/diff/…`）。
- **新反馈作废旧闸门**：老板对某件补新话——`evo feedback --item <件号> "原话"`、件页「补充反馈」（`POST /api/note`）、或可信作者在它的 issue 下写的新评论（`evo pull` 时读；只认闸门开之后写的、不带 `<!-- evo -->` 标记的，接棒器自己留的评论都带这个标记）。原话先写进件的任务说明；它等你的看效果闸门（验收已通过）→ 旧闸门在 Orca 结成「作废（有新反馈）」，带着原话返工，新开「看效果（补充反馈后重看）」，验收通过才轮到你；做不做闸门 → 作废，补进任务书重建施工/验收任务，新开「做不做（补充反馈后）」；没开闸门 → 只记下，下一轮返工带上。作废的闸门记在 `superseded_gates`，之后从命令行、面板、Telegram 点它都拒绝执行。看效果闸门在验收通过那一刻绑定这一版的改动指纹（`look_bound`），版本变了照旧由合并前的指纹检查拦。外部 Agent 不能对件补反馈。
- **项目目标进任务书**：项目配置 `goal`（一两句，最多 200 字、两行，过脱敏词表）；`evo new/import --goal "…"`、`evo -p TB goal set "…" | clear`、面板项目页「项目目标」（要口令；设了 `EVO_AGENT` 一律拒绝）。施工、验收、返工、重启、决策岗的每份任务书第一行都是「项目目标：…」，下一份任务书起生效。

## 第十三轮：UI 栈预设（均有自动测试，`kit/tests/test_ui_preset.py` 16 个，全套 170 个）
老板的原则：优先复用成熟库、组件源代码可控、统一设计语言、严格限制重复依赖。预设在 `kit/presets/ui/`（`web-react.json`、`swiftui.json`、中文 `README.md`），逻辑在 `kit/bin/evo_ui.py`。
- **项目配置**：`ui_preset`（`web-react` | `swiftui` | `none`，默认 none = 什么都不加）、可选 `ui_overrides`（类别 → 包名 / 列表 / `{choice, packages}`，老板批准的换库）、可选 `ui_paths`（覆盖预设里「算界面」的目录）。`evo new/import --ui-preset …`；`evo -p AB ui [show [预设]] | set web-react|swiftui|none | set 类别=包名[,包名] | set 类别= | check [--path --base --json]`。`set` 设了 `EVO_AGENT` 一律拒绝（和 goal 一样）；`show 预设名` 只预览不改配置。`status --json` 加 `ui_preset`（schema 仍是 1）。
- **web-react**：UI shadcn/ui（Nova，组件源码进仓库）+ Tailwind、图标 Lucide、动画 Motion、分栏 react-resizable-panels、拖放 dnd-kit、状态 Zustand（老板定）；表单 react-hook-form + zod、请求 TanStack Query、表格 TanStack Table、提示 sonner、图表 Recharts（shadcn Chart）、日期 date-fns（建议）。每类有「同类不另加」清单（例：图标不加 heroicons / react-icons / fontawesome；动画不加 react-spring / gsap；状态不加 redux / jotai / mobx；UI 不加 MUI / antd / chakra）。**swiftui**：系统组件优先、SF Symbols、原生弹簧动画、Swift Charts、Observation，第三方 UI 库要老板批准。
- **现有栈优先**：只管新代码，不整体迁移。某一类仓库（`package.json` / `Package.swift` / Xcode 包引用）已经在用禁用库 → 那一类沿用现有的，预设选的反倒算重复；接棒时日志 + 提醒（`ui_conflict`，只进 outbox）各报一次，冲突变了再报；`import --ui-preset` 当场列出。
- **任务书**：碰界面的件（look，或 scope 落在 `ui_paths`）施工任务书在「项目目标」行后加「UI 规范」块（每类一行：选定｜不另加…，外加加依赖的规矩），验收任务书加「UI 规范检查」（跑 `evo ui check`、手写组件只建议）。返工、额度重排、工人重启、补充反馈重建的任务书都带。
- **交卷时自动查**（所有件，开了预设才查）：施工交卷后、送验收前对比 merge-base 和 HEAD 的清单，新加禁用库 / 同类第二个库 → 直接打回返工（算一轮，原因写哪一类、已定什么、加了什么、怎么申请换库）；lockfile 里才有的禁用库、手写了预设已有的组件（新文件名撞 shadcn 组件且不在 `components/ui/`）、交卷没提到的新依赖 → 只记提示（时间线 `ui_advisory`）。
- **档案**：ST `ui_preset: swiftui`（REASTOCK 原生 SwiftUI）；TB 不动，土布 web 先 `evo -p TB ui show web-react` 看现有栈冲突再决定开不开。`roles/builder.md` 第 17–19 条、`roles/verifier.md` 第 19–20 条。

## 第十四轮：模型协调——岗位卡片、额度满切备用、模型成绩（均有自动测试，`kit/tests/test_model_coord.py` 26 个，全套 198 个；设计见 docs/model-coordination.md）
- **岗位卡片**：`roles.<build|verify|decide>` 多了 `tool`（claude / codex / dsh / pi，决定账号）、`via`（magpie / cli；模型是 `group/…` 时默认 magpie）、`thinking`（off/low/medium/high/max，命令里写 `{thinking}` 才填）、`duty`（一句话职责）、`fallback {tool, cmd?, models, via?, account?}`。没写 cmd 时按 `tools.<工具>.cmd`、内置模板的顺序找。`{model}` / `{thinking}` 为空时连同前面的参数一起去掉。evo 不存任何密钥，模型只从 magpie 来。
- **`evo [-p AB] team [--json] [--refresh]`**：每张卡的工具、模型、思考档位、职责、备用、状态灯（可用 / 用备用中 / 额度满（恢复时间）/ 没装 / 未登录 / 模型已下线 / 模型不认识 / 和施工撞模型 / magpie 不通）、每个模型近 30 天的成绩、一句建议、本周用量（按账号）；加 `-p` 再给「跟随全局 / 本项目专用」和试用进度。JSON 的 `projects` 列出每个项目改了哪些岗位。
- **健康检查**：magpie `GET /v1/models` + 本机 CLI 在不在、登录文件在不在（只是猜），缓存 5 分钟（`~/.evoloop/team_health.json`）。由通变不通推一次「magpie 不通」，恢复记「magpie 恢复」。
- **额度满先切备用**：卡片配了另一账号的备用 → 不推「额度暂停」，记 `fallback_on`（时间线 + outbox；免打扰时段进早间汇总），这件原样重排，下一次派工用备用（同一个工作区）；正在跑的不打断。到重置时间自动切回，记 `fallback_off`。备用也满（记在 `<岗位>:fallback`）或同账号 → 照旧暂停并推送。决策岗同理。
- **停岗位**：走 magpie 的模型不在列表里（或标了下线、或上次在这次没了）→ 这个岗位不派工，件显示「等换模型」，推一次「X 岗停了」带改法；验收挑不到和这件施工不撞的模型（含组成员）→ 同上；magpie 不通且没有工具自带的备用 → 件显示「等 magpie」，工具自带模型的岗位照跑。换好后下一轮自动派。
- **模型成绩**（从时间线算，近 30 天、全部项目）：施工看验收打回率、每件返工轮数、看效果打回率、分钟/件、没活路次数；验收看打回、漏放（放行后被你看效果打回）。少于 5 件不下结论，差 15 个百分点才建议，**只建议不自动换**。决策卡模型不像最强档时只提醒。
- **新模型**：magpie 列表新出现的（第一次只记下）合成一条 `model_new` 建议；`evo team dismiss <模型>` 收起。**试用**：`evo team trial <岗位> <模型> --project AB [--items 5]`，满了发一条 `trial_done` 对比，留用 `team set … --project AB`，不用 `team clear … --project AB`。
- **改卡片**：`evo team set <岗位> [--model M] [--thinking L] [--tool T] [--duty …] [--fallback-model M] [--fallback-tool T] [--no-fallback] [--project AB]`；先在副本上改、过安全栏（施工≠验收含组成员、magpie 通时模型必须在列表里），过了才落盘，下一次派工生效。`evo team clear <岗位> --project AB` 回到跟随全局。`evo team init [--json] [--apply]`：首次安装向导（看装了哪些 CLI、magpie 有哪些组，按「施工验收不同家、决策用最强、备用不同账号」配）。设了 `EVO_AGENT` 一律拒绝（看可以）。
- **状态与接口**：`status --json` 新增顶层 `team`（每张卡一行、`magpie_ok`、`suggestions`、`blocked`），`roles[].fallback`，件的 `waiting` 多了 `model_blocked` / `magpie_down`；schema_version 仍是 1。面板 `GET /api/team[?code=AB]`、`POST /api/team {action: set|clear|trial|dismiss|init, role, model, thinking, tool, fallback_model, fallback_tool, no_fallback, duty, project, items}`，都要口令；实际由 `evo team …` 执行。新推送类：`model_blocked`、`magpie_down`。

## 只能在 Mac mini 上验的
- 真施工模型会不会按「UI 规范」块选库、交卷写清新依赖理由；`npx shadcn@latest create --preset nova` / `add` 在本机网络（代理）下能不能跑通。
- 真 Orca 的消息有没有 `id` 字段（evo 依次认 `id` / `message_id` / `messageId`；都没有就不去重）、没确认的消息会不会重投。
- 真决策岗模型能否稳定按 decisions JSON 交决定；Orca 将来若有「回复工人」的命令，换掉 `deliver_answer()`。
- 真 `deploy_cmd` 的退出码是否可靠（失败必须非 0）；`gh issue close` 用的账号有没有权限。
- launchd 定时跑 `evo watchdog`（StartInterval 300）和 `pmset -g` 的真实输出格式。
- DSH、Claude Code、Codex 真跑时会不会按说明回报（Orca 已认得 `dsh`）。
- magpie 下施工和验收同用一个工具时，各自指定模型是否生效。
- Hook 日志照常记录；手机提醒。
- `orca terminal read --terminal <句柄> --json` 回的字段名（按文档是累积输出；evo 依次认 `text` / `output` / `content` / `lines`），以及 Codex、Claude Code 额度用完时的原文是否被现有规则认出。
- Telegram 真机：按钮回调、群聊里 `EVO_TG_OWNER` 过滤；国内要 `HTTPS_PROXY`。
- 真实模型能否稳定按 JSON 交卷；Orca worker_done 正文有没有长度上限。
- 钥匙串：第一次 `security add-generic-password` 可能弹授权框。
- magpie 有没有用量接口、记录长什么样（`magpie.usage_url` 先留空）。
- 真 Orca 下工人进程死掉时 `worker-show` 回什么（evo 认 `terminal.orphaned` 或 `observation.status` 不是 `live`）；重启后的派工能不能正常回报。
- magpie `/v1/models` 是否列出组（`group/…`）、组有没有成员字段；没有成员字段时重叠检查只比名字。国内设了 `HTTP_PROXY` 时访问本机 magpie 是否被代理挡（要 `NO_PROXY=127.0.0.1,localhost`）。
- 真模型能否按 ponytail full 档写、把收尾写进交卷；验收能否分清必须修 / 应该修并给出触发情形。
- 真工人的权限弹窗：Claude Code 建议用 acceptEdits 模式，危险动作仍由现有 Hook 拦截；DSH 同理配置。
- 真浏览器里看效果闸门的沙盒 iframe：HTML 产出物里的脚本能跑但连不了网、读不到面板 cookie；图片、下载链接正常。
- 真 Orca 对 `gate-resolve --resolution "作废（有新反馈）"` 的显示（手机端会不会当成老板点了一个选项）。
- GitHub 评论的 `created_at` 时区和 `--paginate` 输出格式；`<!-- evo -->` 标记在 gh 留言里是否原样保留。
- 第十四轮：各 CLI 的命令模板（`codex --model … -c model_reasoning_effort=…`、`pi --thinking …`、`dsh --model …`）是按文档猜的，claude 没有思考档位参数；「未登录」只看登录文件（钥匙串里的看不到）；magpie `/v1/models` 有没有 `members`、`retired`/`deprecated`；切到备用后新工具在同一工作区接着做是否顺（对话上下文不会带过去）。
