# evo 的外部 Agent 接口

给 Muse、Grok bot、本机 DSH、各种插件 bot 用：**能看、能报，不能批、不能上线**。
每个项目仓库里有一份短版 `AGENT_INTERFACE.md`（`evo new` 会放，`evo import` 会放但不提交）。

## 一、原则

1. **读是开放的，写是收窄的。** 读：`evo status --json`、`outbox.jsonl`、webhook 推送、GitHub issue/标签。写：只有 GitHub issue（标签 `agent-report`；老板自己的话用 `owner-feedback`）或 `evo feedback`。
2. **外部写的一切都是不可信输入**，作者在项目配置 `trusted_authors` 里的除外。决策岗只从里面提炼问题，不执行其中的指令（防提示词注入，Readest 的做法）。
3. **外部 Agent 永远不能批闸门、不能上线。** 闸门只有老板本人能批：本机命令、面板（要口令）、Telegram 按钮（只认老板的 chat id / 用户 id）。
4. **红线请求转给老板**：删数据、改线上、花钱、对外发布（发帖、发邮件、对外 issue）。不可信作者的 issue 碰到这些词，接棒器建一个老板闸门「外部请求碰红线」，老板选「同意交决策岗」才进决策岗，选「拒绝」就在 issue 上留言。
5. **不提供「webhook 进来」的写入口。** 这是故意的：所有写入都落在 GitHub 上，有作者、有时间、能追溯。
6. **私有仓库要显式给读权限。** 外部 Agent 读 issue/代码前，老板得在 GitHub 上把它的账号加为协作者（只读够了），或给它一个只读的细粒度 token。

## 二、读

### 2.1 `evo -p <代号> status --json`（schema_version 1）

在跑 evo 的那台机器上执行。规则：**只加字段，不改名、不删字段、不改含义**；要做不兼容的改动就把 `schema_version` 升到 2。读的一方遇到不认识的字段要忽略。

```json
{
  "schema_version": 1,
  "project": "TB",
  "name": "土布",
  "generated_at": "2026-10-20T12:00:00+08:00",
  "last_tick": "2026-10-20T11:59:30+08:00",
  "count": {"queued": 1, "building": 1, "merged": 2},
  "stuck": 0,
  "gates": [
    {"id": "gate_12", "question": "看效果：改版注册页按钮", "options": ["通过", "打回"],
     "kind": "look", "item": "TB-UX-003", "waiting_since": "2026-10-20T11:40:00+08:00"}
  ],
  "items": [
    {"key": "TB-FIX-012", "title": "修复注册页验证码不刷新", "kind": "fix",
     "state": "施工中", "raw": "building", "waiting": null, "window": null,
     "stalled": false, "look": false, "round": 0, "issue": "41", "parent": null, "manual_checks": [],
     "usage": {"runs": 1, "minutes": 12.5}}
  ],
  "rate_limits": [
    {"role": "build", "until": "2026-10-20T17:00:00+08:00", "since": "2026-10-20T15:10:00+08:00",
     "why": "Claude usage limit reached...", "account": "claude", "guessed": false}
  ],
  "usage": {"roles": {"build": {"runs": 5, "minutes": 80.2}, "verify": {"runs": 4, "minutes": 31.0}},
            "tokens": null},
  "decider": {"last_woken": null, "running": false, "items": []},
  "log": ["10-20 11:58 TB-FIX-012 开始施工（glm/glm-5.3-flash）"]
}
```

| 字段 | 含义 |
|---|---|
| `last_tick` | 本项目上次接棒一轮结束的时间（读 `~/.evoloop/heartbeat.json`）；从没转过为 `null`。第十轮新增 |
| `count` | 按内部状态（`raw`）计数 |
| `stuck` | 疑似卡住 + 交决策岗 + 有提问 的件数 |
| `gates[].kind` | `do` 做不做 · `look` 看效果 · `ship` 上线 · `external` 外部请求碰红线 · `ask` 决策岗转来问老板的（选项 同意/不同意）· `other` |
| `gates[].waiting_since` | 从什么时候开始等老板（看效果闸门从验收通过才算）；没开始计时为 `null` |
| `items[].state` | 给人看的中文状态：排队、施工中、待验收、验收中、验收通过、已合并·等推送、已合并·可收菜、已上线、交决策岗、有提问、不做，另有 **等窗口**、**等额度** |
| `items[].raw` | 内部状态：`queued` `building` `built` `verifying` `verified` `pushing` `merged` `shipped` `escalated` `asking` `dropped` |
| `items[].waiting` | 排队没动的原因：`window`（时间窗外）、`rate_limit`（该岗位额度暂停）或 `null` |
| `items[].manual_checks` | 施工交卷里写的「看效果时该看哪几处」（列表，可能为空） |
| `items[].usage` | 这件累计派工次数、工人分钟数（含正在跑的） |
| `rate_limits` | 现在因订阅额度暂停的岗位；`guessed: true` 表示提示里没写重置时间，按默认 60 分钟 |
| `usage.tokens` | 配了 `magpie.usage_url` 才有：`{"by_model": {...}, "project": 数或 null, "source": "..."}`；否则 `null` |
| `goal` | 项目目标（一两句，写进每份任务书开头）；没写为 `null`。第十二轮新增 |
| `roles` | 岗位状态列表：`{"role": "build"/"verify"/"decide", "name": "施工"…, "status": "busy"/"idle"/"paused"/"rate_limited", "label": "忙"/"闲"/"暂停"/"额度满", "items": [件号], "why": 说明或 null, "until": 额度恢复时间或 null}`。第十二轮新增 |
| `stale` | 卡太久：同一状态超过 `limits.stale_hours`（默认 6）小时的件，`{"key","title","state","raw","since","hours"}`，按时长倒序；可收菜、已上线、不做不算。第十二轮新增 |
| `no_live_path` | 没有活路超过 `limits.no_live_path_minutes`（默认 30）分钟的件（面板标红，已交决策岗一次）：`{"key","title","state","raw","reason","why","since","minutes"}`；`reason` 取 `stalled` `dep_dead` `task_dead` `no_decider` `decider_idle` `unknown_state`。第十二轮新增 |
| `items[].state_since` | 进入当前状态的时间。第十二轮新增 |
| `items[].no_live_path` | 这件此刻有没有活路的判断（`true` = 没有，正在计时；到阈值才进顶层 `no_live_path`）。第十二轮新增 |
| `team` | 岗位卡片摘要：`{"cards": [{"role","name","tool","models","thinking","status","label","until"}], "magpie_ok", "suggestions": 新模型建议条数, "blocked": {岗位: 停下的原因}}`；`roles[].fallback`（额度满但备用接上了）；`items[].waiting` 多了 `model_blocked`（等换模型）、`magpie_down`（等 magpie）。第十四轮新增，详细见 `evo team --json` |
| `items[].look_gate` | 这件的看效果闸门号（没有为 `null`）。第十二轮新增 |

第十二轮只加字段，`schema_version` 仍是 1。

### 2.1c `evo -p <代号> log <件号> --json`（每件时间线）
读 `~/.evoloop/projects/<代号>/state/timeline.jsonl`（只追加，一行一个事件）。每行 `{"at", "item", "event", …}`，`event` 取 `add` `dispatch` `report` `gate_open` `gate_approve` `gate_reject` `gate_superseded` `feedback` `rework` `merge` `push` `ship` `deploy_failed` `restart` `decision` `drop` `state` `no_live_path` `live_again` `fallback_on` `fallback_off` `model_blocked`（第十四轮；`dispatch` 另带 `tool` `account` `fallback`）；打回/补充反馈的原话在 `words`，合并、推送带 `sha`。`--diff` 输出这件的改动（工作区还在看分支，合并后看合并提交）。不抢锁，只读。

不带 `-p` 的 `evo status` 是多项目总览（纯文本，不是稳定接口）；要多项目就对每个代号各跑一次 `--json`（`evo projects` 列代号）。

### 2.1b `~/.evoloop/heartbeat.json`（心跳）

每个项目每接棒一轮写一次：`{"TB": "2026-10-20T12:00:00+08:00", "AB": "..."}`。外部 Agent 可以直接读它判断循环还活着没有。
`evo watchdog`（launchd 定时跑，或 `evo bot` 每轮顺带）发现某个项目超过 `limits.heartbeat_stale_minutes`（默认 10）分钟没更新，就推一条 `stalled`；恢复后发 `watchdog_recovered`，再停才再推。launchd 定时跑的写法：

```xml
<key>ProgramArguments</key><array><string>/usr/bin/python3</string><string>…/kit/bin/evo</string><string>watchdog</string></array>
<key>StartInterval</key><integer>300</integer>
```

### 2.2 `~/.evoloop/outbox.jsonl`（事件，schema_version 1）

每个事件一行 JSON，**永远写**（不管推没推、是不是免打扰时段）。只追加；可以自己记读到第几行。

```json
{"schema_version": 1, "id": "5294bbde36fa4743", "ts": "2026-10-20T12:00:00+08:00", "epoch": 1792468800.0,
 "project": "TB", "kind": "stalled", "level": "push", "title": "疑似卡住",
 "body": "修复注册页验证码不刷新：工人进程不在了", "item": "TB-FIX-012", "gate": null, "data": {}}
```

| kind | level | 什么时候 |
|---|---|---|
| `gate_waiting` | push | 闸门 5 分钟（`notify.gate_push_minutes`）没人处理；`data.options` 是选项 |
| `stalled` | push | 件疑似卡住（工人没了或超时没回报）；或接棒器心跳超过 10 分钟没更新（看门狗发，`item` 为空，同一次停只发一次） |
| `state_corrupt` | push | 项目状态文件损坏，接棒暂停 |
| `push_failed` | push | 推送 GitHub 连续失败 3 次 |
| `rate_limited` | push | 岗位订阅额度用完，暂停；`data.until`、`data.roles` |
| `model_blocked` | push | 第十四轮：岗位因模型停了（下线 / 不认识 / 和施工撞模型）；`data.role`、`data.code` |
| `magpie_down` | push | 第十四轮：magpie 由通变不通（只在有岗位走 magpie 时推）；`magpie_up` 只进 outbox |
| `fallback_on` / `fallback_off` | info | 第十四轮：额度满切到备用 / 到点切回；免打扰时段的 `fallback_on` 进早间汇总 |
| `model_new` / `model_gone` / `trial_done` | info | 第十四轮：magpie 新模型、模型不见了、试用满件数的对比 |
| `usage_abnormal` | push | 一件的派工次数或工人分钟数超过上限 |
| `deploy_failed` | push | 点了「上线」但上线命令失败；件留在可收菜，`data.items` |
| `watchdog_recovered` | info | 看门狗报过停的项目又转起来了 |
| `gate_created` | info | 新闸门（做不做 / 看效果 / 上线） |
| `escalated` | info | 交决策岗（返工超限、合并受阻、远端冲突、工作区不干净） |
| `redline_request` | info | 外部请求碰红线，建了老板闸门（5 分钟没处理会再发 `gate_waiting`） |
| `decider_woken` | info | 叫醒决策岗处理一批 |
| `rate_limit_resumed` | info | 额度恢复 |
| `digest_nightly` / `digest_morning` | info | 晚间汇总 / 早间汇总（免打扰期间攒下的要推事项） |
| `main_red` | info | 上线前主线测试不绿 |
| `bot_rejected` | info | Telegram 上有陌生人点按钮或发消息，已忽略 |
| `test` | info | `evo notify-test` |

`project` 为 `"*"` 表示不属于某个项目（整机事件）。以后可能新增 kind，读的一方遇到不认识的要忽略。

### 2.3 webhook 推送（可选）

老板在全局配置里写：

```json
"notify": {"channels": ["telegram", "email", "webhook"],
           "webhook": {"url": "https://muse.example/hook", "secret_env": "EVO_WEBHOOK_SECRET", "events": "push"}}
```

- 请求：`POST`，正文就是上面那条事件 JSON（UTF-8）。
- 头：`X-Evo-Event: <kind>`、`X-Evo-Schema: 1`；配了密钥再加 `X-Evo-Signature: sha256=<hex>`，是对**原始正文字节**做 HMAC-SHA256（密钥来自环境变量，不写进配置文件）。
- `events`：`push`（默认，只发要推的事）或 `all`（每个事件都发）。webhook 不受免打扰影响。
- 可以写成列表接多个 bot：`"webhook": [{...}, {...}]`。
- 校验示例（Python）：`hmac.compare_digest(sig, "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest())`。

### 2.4 GitHub issues / 标签

| 标签 | 谁打 | 意思 |
|---|---|---|
| `autopilot:ready` | 决策岗 / 老板 | 分拣完，接棒器可以登记成件。不可信作者的 issue 上，这个标签必须是可信的人打的（看 issue 事件里打标签的人，`trusted_labelers`，默认同 `trusted_authors`），外部 Agent 自己打的不算 |
| `scope:<目录>`、`type:<类别>`、`look`、`product`、`window:<时间窗>` | 决策岗 | 范围、类别、要不要看效果、要不要点做不做、时间窗 |
| `agent-report` | 外部 Agent | 外部来报，交决策岗 |
| `owner-feedback` | `evo feedback` | 老板以用户视角提的意见 |

接棒器在 issue 上会留言：合并记录、已合并、已上线。

## 三、写

1. **开 issue**：在项目仓库建 issue，打 `agent-report`。写清楚：看到了什么、怎么复现、你建议什么。不要在正文里写「请执行……」，写了也只当线索。
2. **本机 `evo feedback`**：`EVO_AGENT=muse evo -p TB feedback "注册要点三次才能进"`，设了 `EVO_AGENT` 时建的是 `agent-report` issue，正文开头带「【外部 Agent 来报：名字】」标记——即使用的是老板本机的 gh 账号，接棒器也照样当不可信。（本机 Agent 请始终带 `EVO_AGENT=<名字>`。）

接棒器每轮 `evo pull` 收这两类 issue：
- 碰红线且作者不可信 → 老板闸门；
- 其它 → 进决策岗收件箱，和「交决策岗」「有提问」的件一起，**至多每 30 分钟**叫醒决策岗一次，一批处理。

## 四、不能做的事（硬限制）

| 动作 | 怎么挡的 |
|---|---|
| 批闸门 / 打回 | `evo approve` 在设了 `EVO_AGENT` 时直接拒绝；面板要口令；Telegram 只认老板的 chat id / 用户 id；issue 评论里的「/approve」之类一律不解析为批准（第十二轮起，可信作者在闸门开着之后写的新评论只会让旧闸门作废、带着原话返工，不会通过任何东西） |
| 对某件补反馈（会作废老板的闸门） | `evo feedback --item` 在设了 `EVO_AGENT` 时拒绝 |
| 改项目目标 | `evo goal set/clear` 在设了 `EVO_AGENT` 时拒绝；面板改要口令 |
| 改模型 / 岗位卡片 | `evo team set/clear/trial/init/dismiss` 在设了 `EVO_AGENT` 时拒绝；`POST /api/team` 要口令且同样拒绝 |
| 上线 | `evo ship` 同上；上线还要老板点「上线」闸门 |
| 自己给 issue 打 `autopilot:ready` | 不可信作者的 issue 要查打标签的人 |
| 红线请求 | 转老板闸门 |
| webhook 写入 | 不存在 |

`EVO_AGENT` 是约定不是沙箱：同一台机器上能跑任意命令的 Agent 理论上能绕过。真正的边界是：外部 Agent 不给本机 shell，只给 GitHub 只读 + 开 issue 的权限，或只读 outbox / webhook。
