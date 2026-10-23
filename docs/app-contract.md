# App ↔ evo 接口约定（第十六轮，schema_version 1）

Evo.app 不读 evo 的内部文件，只跑 `evo … --json` 拿数据。这份文档写清楚 App 调了哪些命令、每个字段是什么类型、什么意思、哪些可选。机器能读的版本在 `kit/schemas/*.schema.json`（JSON Schema 2020-12），kit 测试（`kit/tests/test_round16.py`）每次都拿真输出去校验。

## 一、版本规则

1. 每个给 App 用的 `--json` 输出，顶层都有 `schema_version`（整数，现在是 `1`）。它是**大版本**。
2. **小改动不升版本**：只加字段、加枚举值、加事件种类。App 解码时忽略新字段。EvoCore 里所有解码都是宽松的：缺了用默认值，多出来就跳过。
3. **不兼容的改动才升大版本**：改字段名、删字段、改类型或含义。升了以后，老 App 读到 `schema_version: 2` 不解码、不崩溃，只在窗口顶上显示一条黄色横幅：
   - 版本号比 App 认得的大：「evo 版本比 App 新（… 是第 2 版接口，这个 App 只认第 1 版），请更新 Evo App。」
   - 版本号小于 1：「evo 版本比 App 旧 …，请更新 evo」。
4. 没有 `schema_version` 的老输出（例如第十五轮之前的 `evo log --json`）按 1 处理。
5. App 侧逻辑在 `app/Sources/EvoCore/Contract.swift`（`ContractCheck`），测试在 `app/Tests/EvoCoreTests/ContractTests.swift`。

第二十五轮（老板 10-23 批，不升版本）：#26 `gates[].kind` 只出 `do`/`look`/`ship`/`other`，以前的 `external`/`ask`/`budget` 并进 `do`，新增可选 `reason`；#27 新件的件号是 `TB#123`（GitHub issue 号），老件号不变，所有接受件号的命令也接受 `123` / `#123`；#12 App 冻结、不再跑 `approve`（按钮只提示去 Telegram 批），网页面板只读（写接口 410），`status --json` 加 `approve_via`。老 App 读新输出不崩（kind 本来就认 do；件号本来就当字符串）。

第二十四轮（#16）删了插件：`evo plugin list|run --json` 两个命令、`plugin-list` / `plugin-run` / `plugin-manifest` / `card` 四个 schema 一起没了（老板批准的删除，不升版本）。老 App 跑 `evo plugin list` 会失败，它本来就按「老 evo 没有插件」处理：不显示插件分组，不崩。`evo feature list --json` 的 `third_party` 字段留着、恒为 null。

## 二、App 调的命令一览

| 命令 | 什么时候 | Schema | 失败时 App 怎么办 |
|---|---|---|---|
| `evo projects --json` | 每 30 秒 | `projects.schema.json` | 退回 `evo projects`（纯文本，老 evo） |
| `evo -p <代号> status --json` | 每 30 秒，每个项目 | `status.schema.json` | 该项目卡片显示「读不出状态」 |
| `evo -p <代号> log <件号> --json` | 打开件详情 | `log.schema.json` | 详情页显示错误 |
| `evo team --json` | 每 30 秒 | `team.schema.json` | 团队页显示错误 |
| `evo team init --json` | 首次设置向导 | `team-init.schema.json` | 向导里显示错误 |

App 还会跑这些**写**命令（输出是给人看的文字，不是接口）：`feedback`、`add`、`tick`、`ship`、`watchdog`、`team set|dismiss|init --apply`、`feature on|off|set`、`panel --show-token`。

另外 `evo models --json` 也带 `schema_version: 1`，App 现在不读，面板 / 外部 Agent 用（`evo ui` / `evo arch` 第二十五轮随预设删了）。`evo status --json` 的详细字段说明以 [agent-interface.md](agent-interface.md) 2.1 为准。

## 三、逐个命令

类型写法：`string?` = 可以是 `null` 或不出现；「可选」= 可能不出现，App 不能假定有。

### 3.1 `evo projects --json`

```json
{"schema_version": 1, "projects": [{"code": "TB", "name": "土布", "repo": "/Users/boss/code/tubu", "github": "JAY5CXSDMY14/tubu-platform"}]}
```

| 字段 | 类型 | 必有 | 含义 |
|---|---|---|---|
| `projects[].code` | string（2–4 个大写字母） | 是 | 项目代号，`-p` 用它 |
| `projects[].name` | string | 是 | 项目名（没写就等于代号） |
| `projects[].repo` | string? | 否 | 本机仓库目录 |
| `projects[].github` | string? | 否 | `用户/仓库` |
| `projects[].work_repo` | string? | 否 | 第十七轮：evo 实际合并、推送的目录（专用克隆 `~/.evoloop/repos/<代号>`）；`repo` 是老板的工作副本，evo 只读 |

不带 `--json` 的纯文本输出保持不变（每行「代号 名字 仓库 GitHub」），老 App 照读。

### 3.2 `evo -p <代号> status --json`

| 字段 | 类型 | 必有 | 含义 |
|---|---|---|---|
| `project` / `name` | string | 是 | 代号 / 项目名 |
| `generated_at` / `last_tick` | string?（ISO 8601） | 是 / 是 | 生成时间 / 上次接棒一轮的时间（从没转过为 null） |
| `count` | {状态: 整数} | 是 | 按内部状态计数（`building`、`built`、`verifying`、`merged`…） |
| `stuck` | 整数 | 是 | 疑似卡住 + 交决策岗 + 有提问 |
| `gates[]` | 对象列表 | 是 | 等老板点头的闸门：`id` string、`question` string?、`options` [string]、`kind` = `do`/`look`/`ship`/`other`（第二十五轮 #26 起；老 evo 还会出 `external`/`ask`/`budget`，App 一律按 `do` 读）、可选 `reason` = `item`/`decider`/`external`/`budget`（第二十五轮新增）、`item` string?、`waiting_since` string?；第十七轮可选 `confirm` bool（Orca 端被点了放行类结果、要在 evo 入口再确认，试运行）、`orca_choice` string? |
| `items[]` | 对象列表 | 是 | 每件：`key`、`title`、`state`（中文）、`raw`（内部状态）必有；`kind`、`waiting`、`stalled`、`look`、`round`、`manual_checks`、`state_since`、`no_live_path`、`look_gate`、`usage` 可选 |
| `log` | [string] | 是 | 最近 15 条动静 |
| `roles` | 列表 | 可选 | 岗位状态 `{role, name, status, label, items, why, until}` |
| `stale` / `no_live_path` | 列表 | 可选 | 卡太久 / 没活路的件 `{key, title?, state?, reason?, hours?, minutes?}`（老格式可能是数字或布尔，App 都认） |
| `goal`、`checks`（第二十五轮：项目自己的检查命令）、`retired_keys`（config 里还写着已删的预设键）、`ui_preset` / `arch_preset`（第二十五轮起不再出）、`rate_limits`、`usage`、`decider`、`team` | — | 可选 | 见 agent-interface.md |
| `paused` | string? | 可选 | 第十七轮：项目暂停原因；没暂停为 null。status 只读，暂停时照常返回（以前退出码非 0） |
| `tick_running` | 对象? | 可选 | 第十七轮：正在跑的一轮 `{pid, cmd, since, minutes}`；这时返回的是上次存盘的状态 |
| `gates_stale` | bool | 可选 | 第十七轮：这次没读到 Orca 闸门（status 不新建协调终端） |
| `main_red` | bool | 可选 | 第十七轮：主线本身测试红，在途的件等它（件的 `waiting` = `main_red`） |
| `limits` | {键: 数字} | 可选 | 第十七轮：每件上限 `decider_reworks` / `item_hard_runs` / `item_hard_hours`（0 = 关）；件的 `waiting` = `owner_budget` 表示上限到了在等老板 |

`evo [-p 代号] limits [show | set 键=值 …] --json`（第十七轮，App 现在不读）：`{"schema_version": 1, "project": "TB" | null, "limits": {…}, "labels": {…}}`。

### 3.3 `evo -p <代号> log <件号> --json`

| 字段 | 类型 | 必有 | 含义 |
|---|---|---|---|
| `key` | string | 是 | 件号。第二十五轮（#27）起新件是 `代号#issue 号`（`TB#123`，同一个 issue 第二件起 `TB#123-2`），没有 issue 的件和老件仍是 `TB-FIX-012`；App 把它当不透明字符串 |
| `events[]` | 列表 | 是 | 时间线，每条 `{at, item, event, …}`，附加字段随 `event` 不同 |
| `title`、`state`、`raw`、`goal` | string? | 是 | 现状 |
| `report` | object? | 是 | 施工交卷（`summary`、`changes`、`tests`…） |
| `manual_checks` | [string] | 是 | 看效果时该看哪几处 |
| `has_diff` | bool | 是 | 有没有改动可看 |
| `merged_sha` | string? | 是 | 合并提交 |
| `notes` | [string] | 是 | 老板说过的话 |
| `artifacts` | 列表 | 可选（以后加） | 产出物 `{path, kind, bytes, too_big}` |

### 3.4 `evo team --json` / `evo team init --json`

`team --json`：`magpie {ok, url, models, groups, retired}`、`cards[]`（`role` = build/verify/decide、`name`、`tool`、`models`、`thinking`、`status {code, label, why?, until?}`、`fallback`、`stats`、`recommendation {text, switch_to}`、`warnings`…）、`suggestions[] {model, at}`、`thinking_levels`、`projects[] {code, name, overrides}`。字段说明见 [model-coordination.md](model-coordination.md)。

`team init --json`：`{schema_version, cards: {岗位: {tool, models, thinking, fallback?}}, notes: [string], magpie}`；`team init --apply --json`：`{schema_version, ok, applied, notes}`。

## 四、改接口的流程

1. 只加字段：改 evo、改 `kit/schemas/` 对应文件（加 `properties`）、改这份文档的表、在 EvoCore 解码里加可选字段。`schema_version` 不动。
2. 要做不兼容改动：先想能不能「加新字段、旧字段留着」。实在不行：`APP_SCHEMA_VERSION`（kit/bin/evo）升 2 → 新 schema 文件 → App 的 `ContractCheck.supported` 升 2 并发版。老 App 会看到「请更新」横幅。
3. kit 测试会拿每个命令的真输出过 schema；App 测试用 `Tests/EvoCoreTests/Fixtures/` 里的样例（`feature_list.json`、`status_future.json`…）。
