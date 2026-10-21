# App ↔ evo 接口约定（第十六轮，schema_version 1）

Evo.app 不读 evo 的内部文件，只跑 `evo … --json` 拿数据。这份文档写清楚 App 调了哪些命令、每个字段是什么类型、什么意思、哪些可选。机器能读的版本在 `kit/schemas/*.schema.json`（JSON Schema 2020-12），kit 测试（`kit/tests/test_round16.py`）每次都拿真输出去校验。

## 一、版本规则

1. 每个给 App 用的 `--json` 输出，顶层都有 `schema_version`（整数，现在是 `1`）。它是**大版本**。
2. **小改动不升版本**：只加字段、加枚举值、加事件种类。App 解码时忽略新字段。EvoCore 里所有解码都是宽松的：缺了用默认值，多出来就跳过。
3. **不兼容的改动才升大版本**：改字段名、删字段、改类型或含义。升了以后，老 App 读到 `schema_version: 2` 不解码、不崩溃，只在窗口顶上显示一条黄色横幅：
   - 版本号比 App 认得的大：「evo 版本比 App 新（… 是第 2 版接口，这个 App 只认第 1 版），请更新 Evo App。」
   - 版本号小于 1：「evo 版本比 App 旧 …，请更新 evo」。
4. 没有 `schema_version` 的老输出（例如第十五轮之前的 `evo log --json`）按 1 处理。
5. App 侧逻辑在 `app/Sources/EvoCore/Contract.swift`（`ContractCheck`），测试在 `app/Tests/EvoCoreTests/PluginTests.swift`。

插件接口另有自己的版本（`evo_api`，现在是 `1.0`），见 [plugins.md](plugins.md)。

## 二、App 调的命令一览

| 命令 | 什么时候 | Schema | 失败时 App 怎么办 |
|---|---|---|---|
| `evo projects --json` | 每 30 秒 | `projects.schema.json` | 退回 `evo projects`（纯文本，老 evo） |
| `evo -p <代号> status --json` | 每 30 秒，每个项目 | `status.schema.json` | 该项目卡片显示「读不出状态」 |
| `evo -p <代号> log <件号> --json` | 打开件详情 | `log.schema.json` | 详情页显示错误 |
| `evo team --json` | 每 30 秒 | `team.schema.json` | 团队页显示错误 |
| `evo team init --json` | 首次设置向导 | `team-init.schema.json` | 向导里显示错误 |
| `evo plugin list --json` | 每 30 秒 | `plugin-list.schema.json` | 不显示插件分组；设置里说一句 |
| `evo plugin run <名字> <类型> <id> --json …` | 打开插件页、点击按钮、输入框 `/命令`、件按钮 | `plugin-run.schema.json`（卡片：`card.schema.json`） | 只在那一页 / 那条回话显示错误 |

App 还会跑这些**写**命令（输出是给人看的文字，不是接口）：`approve`、`feedback`、`add`、`tick`、`ship`、`watchdog`、`team set|dismiss|init --apply`、`plugin enable|disable`、`panel --show-token`。

另外 `evo models --json`、`evo -p X ui show|check --json`、`evo -p X arch show|check --json` 也带 `schema_version: 1`，App 现在不读，面板 / 外部 Agent 用。`evo status --json` 的详细字段说明以 [agent-interface.md](agent-interface.md) 2.1 为准。

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
| `gates[]` | 对象列表 | 是 | 等老板点头的闸门：`id` string、`question` string?、`options` [string]、`kind` = `do`/`look`/`ship`/`external`/`ask`/`budget`/`other`、`item` string?、`waiting_since` string?；第十七轮可选 `confirm` bool（Orca 端被点了放行类结果、要在 evo 入口再确认，试运行）、`orca_choice` string? |
| `items[]` | 对象列表 | 是 | 每件：`key`、`title`、`state`（中文）、`raw`（内部状态）必有；`kind`、`waiting`、`stalled`、`look`、`round`、`manual_checks`、`state_since`、`no_live_path`、`look_gate`、`usage` 可选 |
| `log` | [string] | 是 | 最近 15 条动静 |
| `roles` | 列表 | 可选 | 岗位状态 `{role, name, status, label, items, why, until}` |
| `stale` / `no_live_path` | 列表 | 可选 | 卡太久 / 没活路的件 `{key, title?, state?, reason?, hours?, minutes?}`（老格式可能是数字或布尔，App 都认） |
| `goal`、`ui_preset`、`arch_preset`、`rate_limits`、`usage`、`decider`、`team` | — | 可选 | 见 agent-interface.md |
| `paused` | string? | 可选 | 第十七轮：项目暂停原因；没暂停为 null。status 只读，暂停时照常返回（以前退出码非 0） |
| `tick_running` | 对象? | 可选 | 第十七轮：正在跑的一轮 `{pid, cmd, since, minutes}`；这时返回的是上次存盘的状态 |
| `gates_stale` | bool | 可选 | 第十七轮：这次没读到 Orca 闸门（status 不新建协调终端） |
| `main_red` | bool | 可选 | 第十七轮：主线本身测试红，在途的件等它（件的 `waiting` = `main_red`） |
| `limits` | {键: 数字} | 可选 | 第十七轮：每件上限 `decider_reworks` / `item_hard_runs` / `item_hard_hours`（0 = 关）；件的 `waiting` = `owner_budget` 表示上限到了在等老板 |

`evo [-p 代号] limits [show | set 键=值 …] --json`（第十七轮，App 现在不读）：`{"schema_version": 1, "project": "TB" | null, "limits": {…}, "labels": {…}}`。

### 3.3 `evo -p <代号> log <件号> --json`

| 字段 | 类型 | 必有 | 含义 |
|---|---|---|---|
| `key` | string | 是 | 件号 |
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

### 3.5 `evo plugin list --json`

```json
{"schema_version": 1, "evo_api": "1.0", "plugins_dir": "/Users/boss/.evoloop/plugins",
 "plugins": [{"name": "example-hello", "version": "0.1.0", "description": "…", "evo_api": "^1",
   "enabled": true, "valid": true, "compatible": true, "active": true, "errors": [],
   "contributes": {"sidebar_pages": [{"id": "hello", "title": "你好", "icon": "hand.wave"}],
                   "composer_commands": [{"id": "hello", "name": "hello", "title": "打个招呼", "usage": "/hello 名字"}],
                   "notify_channels": [{"id": "hello-log", "title": "写到本地文件", "events": "push"}],
                   "item_actions": [{"id": "hello-item", "title": "跟这件打招呼", "icon": "hand.wave"}]}}]}
```

| 字段 | 类型 | 含义 |
|---|---|---|
| `evo_api` | string | 这版 evo 的插件接口版本 |
| `plugins_dir` | string | 插件目录（默认 `~/.evoloop/plugins`，环境变量 `EVO_PLUGINS_DIR` 可改） |
| `plugins[].enabled` | bool | manifest 里的开关（新装的一律 false） |
| `plugins[].valid` | bool | plugin.json 合格 |
| `plugins[].compatible` | bool | 插件要的 `evo_api` 范围包含这版 evo |
| `plugins[].active` | bool | `enabled && valid && compatible`；**App 只显示 active 插件的贡献点** |
| `plugins[].errors` | [string] | 不合格的原因（中文） |
| `plugins[].contributes.*` | 列表 | 四种贡献点（不含插件的命令行，App 用不着也不该看） |

### 3.6 `evo plugin run <名字> <类型> <id> --json`

参数：`<类型>` = `sidebar_page` | `composer_command` | `notify_channel` | `item_action`；`<id>` 是贡献点的 id（输入框命令也可以用 `name`）。可选 `--args 文字`（输入框 `/名字` 后面的话）、`--action A --payload JSON`（点了卡片上的按钮）、`--project 代号`、`--item 件号`。

```json
{"schema_version": 1, "ok": true, "plugin": "example-hello", "kind": "sidebar_page", "id": "hello",
 "card": {"schema_version": 1, "title": "你好，老板 👋", "blocks": [ … ]}, "error": null, "elapsed_ms": 41, "stderr_tail": ""}
```

| 字段 | 类型 | 含义 |
|---|---|---|
| `ok` | bool | 插件跑成功、输出合格 |
| `card` | 卡片? | 成功时的卡片（`notify_channel` 为 null） |
| `error` | string? | 失败原因：没打开、不兼容、超时（20 秒）、输出超过 256 KB、退出码非 0、不是 JSON、卡片不合格 |
| `elapsed_ms` | 整数 | 用时 |
| `stderr_tail` | string | 插件 stderr 的最后 500 字（排错用） |

**插件失败时 evo 退出码是 3，但 stdout 照样是这个信封**；App 先读信封。evo 自己的用法错误（参数不对）退出码 1/2，stdout 不是 JSON。

### 3.7 卡片（`card.schema.json`，插件写、App 画）

```json
{"schema_version": 1, "title": "标题", "subtitle": "可选副标题",
 "blocks": [
   {"type": "text", "text": "一段话", "style": "body|caption|title|mono", "tone": "neutral|accent|success|warning|danger"},
   {"type": "list", "items": [{"title": "一行", "subtitle": "小字", "badge": "角标", "symbol": "SF Symbol 名", "tone": "success"}]},
   {"type": "table", "columns": ["列1", "列2"], "rows": [["a", "b"], ["c", 3]]},
   {"type": "buttons", "buttons": [{"label": "按钮", "action": "动作名", "style": "primary|secondary|danger", "payload": {"任意": "JSON"}}]}
 ]}
```

上限：50 块、列表 200 条、表格 200 行 12 列、按钮 6 个、每段文字 2000 字（超长截断）、payload 4 KB。不认识的块：evo 校验时报错（插件按 v1 写）；App 解码时直接跳过（给以后的小版本留余地）。

## 四、改接口的流程

1. 只加字段：改 evo、改 `kit/schemas/` 对应文件（加 `properties`）、改这份文档的表、在 EvoCore 解码里加可选字段。`schema_version` 不动。
2. 要做不兼容改动：先想能不能「加新字段、旧字段留着」。实在不行：`APP_SCHEMA_VERSION`（kit/bin/evo）升 2 → 新 schema 文件 → App 的 `ContractCheck.supported` 升 2 并发版。老 App 会看到「请更新」横幅。
3. kit 测试会拿每个命令的真输出过 schema；App 测试用 `Tests/EvoCoreTests/Fixtures/` 里的样例（`plugin_list.json`、`plugin_run_page.json`…）。
