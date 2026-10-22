> 现状说明，不是约束；Claude 审查后可提议修改（决策岗用 `propose`，老板点「做不做」）。

# evo 架构：内核 + 功能包（第十八轮）

写给要改 evo 的 AI Agent。读完你能做三件事：看懂一个功能装在哪里、加一个新功能包、把内核里的老功能迁成功能包。
做法照 magpie 的插件运行时（`internal/pluginrt`）：内核只管状态机和接线，功能都是可开关的包。

## 1. 分层

| 层 | 在哪 | 管什么 | 谁能改 |
|---|---|---|---|
| 内核 | `kit/bin/evo`、`evo_rt.py`、`evo_bus.py`、`evo_notify.py`、`evo_plugin.py` | 件的状态机、闸门、锁、权限、事件总线、功能包运行时、自升级 | 改动走老板闸门（见 `docs/self-maintenance.md`） |
| 内核库 | `kit/bin/evo_deps.py`、`evo_roles.py`、`evo_time.py` 等 | 几个功能包共用的工具 | 和普通代码一样 |
| 功能包 | `kit/features/<id>/` | 一个可开关的功能（推送渠道、上线、GitHub、团队页……） | 和普通代码一样；`item-caps`、`orca-gate-sync` 两个安全类除外 |
| 第三方插件 | `~/.evoloop/plugins/<名字>/` | 老板自己装的外部插件，子进程跑 | 插件作者；接口见 `docs/plugins.md` |
| 看门狗 | `kit/selfmaint/evo-guard.sh` | 自升级后的回退 | **只有老板手改**，evo 和工人都不许碰 |

规矩只有一条最要紧：**内核从不 import 某个功能包**。内核拿功能只走两条路：

- `svc("服务名")`：拿某个功能包 `provides` 的服务；功能关着就拿到 `None`，内核按「没有这个功能」走。
- `hook("槽位")`：拿某个槽位上所有功能包的贡献 `[(功能id, key, 值)]`。

`kit/tests/test_round18.py::test_kernel_imports_no_feature` 和 `test_features_do_not_import_each_other` 守着这条边界，越界测试就红。

## 2. 现在有的 12 个功能包

| id | 名字 | 精简也开 | 占的槽位 / 服务 |
|---|---|---|---|
| `ui-preset` | UI 栈预设 | 否 | cli `ui`、任务书开头、交卷检查 |
| `arch-preset` | 架构预设 | 否 | cli `arch`、任务书开头、交卷检查、status |
| `notify-telegram` | Telegram 推送 | 否 | 推送渠道、cli `bot` |
| `notify-email` | 邮件推送 | 否 | 推送渠道、服务 `mail.send`、设置 |
| `notify-webhook` | Webhook 推送 | 否 | 推送渠道（配了就算在用） |
| `item-caps` | 每件上限 | 是 | 服务 `caps`、cli `limits`、设置（受保护） |
| `orca-gate-sync` | Orca 端闸门同步 | 是 | 订阅 `tick.gates`、设置（受保护） |
| `deploy` | 上线 | 是 | 服务 `deploy`、订阅 `tick.before_save`、设置 |
| `digest` | 早报和每晚汇总 | 否 | cli `digest`、设置 |
| `github` | GitHub 来源 | 是 | cli `pull`、服务 `gh` |
| `team` | 团队 / 模型协调 | 是 | 服务 `team`、cli `team` / `models`、App 页 `team` |
| `plugins` | 第三方插件 | 否 | 服务 `plugins.host`、cli `plugin`、App 页 `plugins` |

看实时状态：`evo feature list`（人看）或 `evo feature list --json`（App 读，格式见 `kit/schemas/feature-list.schema.json`）。

## 3. 一个功能包长什么样

```
kit/features/<id>/
  feature.json    清单（manifest）
  feature.py      必须有 apply(ctx)；可选 in_use(k, config)
  （可以有别的 .py，模块名全仓唯一，test_feature_module_names_unique 查）
```

### 3.1 feature.json

```json
{
  "id": "item-caps",
  "api": "^1",
  "version": "1.0.0",
  "name": "每件上限",
  "sub": "返工 / 派工次数 / 累计小时到了就暂停，问老板继续还是不做",
  "essential": true,
  "requires": ["state", "orca"],
  "provides": ["caps"],
  "parts": [
    {"slot": "settings", "key": "item-caps"},
    {"slot": "status", "key": "limits"},
    {"slot": "cli", "key": "limits"}
  ],
  "one": "有 1 个上限闸门等老板",
  "many": "有 {n} 个上限闸门等老板",
  "settings": {
    "type": "object",
    "x-order": ["decider_reworks", "item_hard_runs"],
    "properties": {
      "decider_reworks": {"type": "integer", "title": "决策岗指导返工最多几次", "minimum": 0, "maximum": 50, "default": 2}
    }
  }
}
```

字段说明：

- `id`：小写字母、数字、连字符，和文件夹同名。
- `api`：内核接口范围。现在内核是 1.0，写 `^1`。
- `essential`：`true` 表示「精简」预设下也开。
- `requires`：要用的服务。内核自带的服务是 `core`、`state`、`config`、`notify`、`orca`、`git`、`bus`、`clock`；别的服务要有功能包 `provides`。缺服务时这个功能停在 `pending`（等服务）。
- `parts`：它占的槽位。槽位只有这几种：`cli`（子命令）、`page`（App 侧栏页）、`settings`（设置区）、`status`（`status --json` 加字段）、`notify.channel`（推送渠道）、`prompt.head`（任务书开头）、`delivery.check`（交卷检查）。
- `settings`：一个 JSON Schema 对象。`properties` 里每个设置一项，`type` 只能是 `boolean`、`integer`、`number`、`string`，可写 `title`、`description`、`enum`、`minimum`、`maximum`、`default`；`x-order` 给显示顺序。App 按它自动画表单，不用写界面代码。
- `one` / `many`：「正在用」时怎么说，`{n}` 换成数量。

### 3.2 feature.py

```python
K = None                      # 内核接口，apply 时填上


def in_use(k, config):
    """可选。返回整数，>0 = 正在用，关不掉。抛异常也算在用。"""
    return 0


def apply(ctx):
    global K
    K = ctx.k
    ctx.provide("caps", Caps())                                   # 只能提供 manifest 里 provides 声明过的
    ctx.contribute("cli", "limits", {"help": "…", "setup": setup, "run": run})
    ctx.subscribe("tick.after_dispatch", on_tick, priority=50, timeout=30)
    ctx.on_dispose(lambda: None)                                  # 关掉时要收尾的
```

`ctx` 上有：`id`、`dir`、`config`（合成后的设置值）、`k`（内核接口）、`bus`、`data_dir`（`~/.evoloop/feature-data/<id>/`，自己的文件放这）、`provide`、`service`、`contribute`、`subscribe`、`publish`、`on_dispose`。

### 3.3 内核接口（ctx.k）

`ctx.k` 就是 evo 自己的全局名字。功能包常用、可以放心依赖的这些：

- 配置：`CFG`（项目配置）、`GCFG`（全局配置）、`CODE`、`HAS_PROJECT`、`EVO_ROOT`、`HOME_DIR`、`effective_config`、`_read_json`、`_project_cfg_path`、`_write_project_cfg`、`_global_path`
- 状态：`load`、`save`、`log`、`tl`（写件时间线）、`QUIET_STATES`、`item_minutes`、`list_projects`
- 外部：`orca`、`git`、`gh_run`、`run_cmd`、`tmo`（超时分钟）、`magpie_http`
- 推送：`notify`、`NOTE`
- 权限：`refuse_agents`（外部 Agent 不许做的事先调它）
- 闸门：`pending_gate_ids`、`mark_evo_resolved`、`GATE_OPTIONS`、`NEG_CHOICES`
- 运行时：`svc`、`rt`、`APP_SCHEMA_VERSION`

别的名字也拿得到，但内核改名时不保证兼容。要用新的内核函数，先在这里加一行，算内核改动（走老板闸门）。

## 4. 运行时怎么合成开关

开关文件是 `~/.evoloop/features.yml`，只存老板改过的：

```yaml
preset: all            # all（全开）| essentials（精简：只开 essential: true 的）
features:
  - id: digest
    enabled: false
  - id: item-caps
    config:
      item_hard_runs: 20
```

合成顺序：默认全开 → 预设 → 老板写的行 → **正在用的强制开**。

每个功能的状态是这五种之一：`off`、`pending`（等服务）、`active`、`failed`（apply 抛错或 API 不兼容，它注册过的东西全撤掉）、`disposed`。一个功能失败不影响别的。

`features.yml` 写坏了：evo 照全开跑，并拒绝改开关（`evo feature list` 第一行会说），修好或删掉文件就恢复。

命令：

```bash
evo feature list [--json]                 # 看
evo feature off digest                    # 关（在用的关不掉，会说为什么）
evo feature on digest
evo feature set item-caps item_hard_runs=20      # 按 schema 校验类型和范围
evo feature preset essentials             # 精简
```

每次改动发一个 `feature.changed` 事件，App 收到就重读功能列表。

### 「在用」保护

`in_use()` 返回大于 0，就关不掉（App 里开关是灰的，写着「正在用（…），关不掉」）。现在的取舍：

- **Webhook 配了就算在用**：外部 bot 在等它，关掉它们会默默收不到。要关先从配置里删掉 webhook。
- **Telegram、邮件推送不算在用**（第十八轮老板待定项，按推荐维持现状）：关掉只是不往那里推，配置留着，outbox、别的渠道照旧。想改成受保护：在 `kit/features/notify-telegram/feature.py`（或 `notify-email`）加一个 `in_use(k, config)`，配置齐了返回 1；`test_round18.py::test_push_channels_telegram_email_off_not_protected` 要跟着改。

## 5. 事件总线

内核在固定点发事件，功能包订阅。事件名只加不改：

`item.created`、`build.started`、`build.done`、`verify.started`、`verify.passed`、`verify.failed`、`gate.pending`、`gate.resolved`、`item.merged`、`push.done`、`deploy.done`、`deploy.failed`、`item.shipped`、`item.dropped`、`item.timeline`、`tick.before_dispatch`、`tick.after_dispatch`、`tick.gates`、`tick.before_save`、`tick`、`feature.changed`、`feature.error`、`watch.ping`。另有 `project.claimed`、`self.upgraded`。

规矩：

- 每个订阅者单独兜错。抛异常或超时，只记一条 `feature.error`，别的订阅者和内核照常。
- `timeout` 秒到了就不等了（默认 30）。`timeout=0` 是同步直接调，只给内核自己的快订阅者用。
- 按 `priority` 从小到大调。
- 每个事件追加一行到 `~/.evoloop/events.jsonl`（超过 5 MB 挪成 `.1`）。一行的格式：`{"schema_version": 1, "id", "ts", "event", "project", "item", "data"}`，见 `kit/schemas/event.schema.json`。
- 功能包发自己的事件，名字写成 `<功能id>.xxx`。

`evo watch --json` 就是 tail 这个文件：每行一个事件，15 秒没事件吐一行 `watch.ping`。可选 `--replay N`（先吐最后 N 条）、`-p X --project-only`。

## 6. App 怎么跟着功能走（App 0.7.0）

- 启动后读 `evo feature list --json`。老 evo 没有这个命令：当作「全开」，界面照旧。
- 侧栏：声明了 `page` 槽位的功能（`team`、`plugins`）关着，它的页就不出现；正选着它就退回「等你处理」。没有功能包声明的页（等你处理、项目、卡太久、设置）一直在。
- 设置页「功能」卡片：每个功能一个开关；有 `settings` 的多一个「设置」按钮，展开后按 schema 自动画表单（boolean → 开关，enum → 一排按钮，数字 → 数字框带范围，字符串 → 文本框）。输入先在 App 里按 schema 校验，不合格就红字，不跑 evo；合格才跑 `evo feature set`，evo 再校验一次，拒了就把原话挂在字段下面。
- 订阅 `evo watch --json`：有事件就刷新（去抖 1.2 秒）；事件流活着时只做 2 分钟一次的兜底轮询；45 秒没收到任何一行就当断了，回到 30 秒轮询，并按 5、10、20、40、60 秒退避重连。
- 每页错误边界：团队页、项目页、件详情读不出来时，只这一页画「出错了 + 重试」卡片，侧栏和别的页照常。等你处理、卡太久是汇总页，不整页挡住；设置页永远能打开（evo 路径填错了要靠它改回来）。

纯逻辑在 `app/Sources/EvoCore/Features.swift`，测试在 `app/Tests/EvoCoreTests/FeatureTests.swift`。

## 7. 照做：加一个新功能包

1. 建目录 `kit/features/<id>/`，写 `feature.json`（照第 3.1 节）。名字、一句话说明写中文。
2. 写 `feature.py` 的 `apply(ctx)`。只 import 标准库和内核库（`evo_notify`、`evo_time`、`evo_deps`、`evo_roles` 等），不 import 别的功能包。
3. 老板能改的值写进 `settings`。代码里读 `ctx.config["键"]`：老板改过就是改过的值，否则是 `default`；手改进来不合 schema 的值会被丢掉。不要再往全局 `config.json` 加新键。
4. 子命令走 `cli` 槽位：`ctx.contribute("cli", "名字", {"help": "…", "setup": lambda parser: …, "run": lambda args: …, "no_project": False})`。功能关着时，evo 会让这个子命令回一句「功能关着」，并给出 `evo feature on <id>`。
5. 要在一轮里做事就订阅 `tick.*` 事件；要加 `status --json` 字段就占 `status` 槽位，字段只加不改。
6. 在 `kit/tests/` 加测试：开着能用、关掉后子命令给出提示、坏输入不拖垮内核。
7. 跑全套：`python -m pytest kit/tests -q -n auto`（含 ruff F821 查漏名、manifest 校验、边界测试）。
8. App 不用改：设置表单、侧栏可见性都跟着 `feature list --json` 自动变。要加新的 App 页才需要改 App。

## 8. 照做：把内核里的老功能迁出来

渐进迁，一次一个，每批测试全绿再推：

1. 找出老功能在内核里的所有入口（子命令、一轮里的调用点、status 字段、配置键）。
2. 在内核调用点换成 `svc("服务名")` 或 `hook("槽位")`，拿不到就按「没有这个功能」走。
3. 代码搬进 `kit/features/<id>/feature.py`；几个包都要用的工具放进内核库（例如第十八轮的 `evo_deps`、`evo_roles`）。
4. 老配置键照旧能读，不要逼老板改配置。先读哪个由功能包自己定，并写进这个设置的 `description`。例如 `deploy`：项目或全局 `config.json` 写了 `auto_ship_gate` 就以它为准，没写才用功能设置。
5. JSON 接口（`status --json` 等）字段名和 `schema_version` 不变；第十六轮外部插件的 `evo_api 1.0` / `schema_version 1` 不变。
6. 跑全套测试，绿了再提交，提交信息写「迁出 `<id>`」。

第十八轮已经按这个步骤迁了 12 个（提交 7cc9051 到 9e28321）。
