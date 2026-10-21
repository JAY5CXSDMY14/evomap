# evo 插件：怎么写（给 AI 照着写）

丢一个文件夹进 `~/.evoloop/plugins/<名字>/`，在 App 设置里打开。App 就多一个**侧栏页**、**输入框命令**、**通知渠道**或**件详情页按钮**。不用改 App 本体，也不用改 evo。

示例：`kit/plugins/example-hello/`（四种贡献点各一个，纯 Python 标准库，100 行）。

## 一、参考了谁（没有自造协议）

| 部分 | 照着谁 | 怎么借的 |
|---|---|---|
| manifest（plugin.json） | VS Code 扩展的 `package.json` | `engines.vscode` 兼容范围 → `evo_api`；`contributes.<贡献点>` 列表 → `contributes.sidebar_pages` 等 |
| 执行方式 | git / kubectl 插件 | 插件就是一个外部可执行文件，作为子进程跑；退出码 0 = 成功 |
| 输入输出 | git credential helper、Terraform external data source | 一次性 JSON over stdio：evo 往 stdin 写一个请求 JSON，插件往 stdout 写一个结果 JSON，然后退出 |

为什么不用 JSON-RPC over stdio（LSP / MCP 那种）：那是给常驻进程、来回问答很多轮用的。我们每次都是一问一答、无状态，一次性子进程最简单、最不容易卡死，超时一杀了之。

## 二、目录和 plugin.json

```
~/.evoloop/plugins/
  my-plugin/
    plugin.json      ← 必须
    main.py          ← 你的程序（任何语言都行：python3、bash、node、编译好的二进制）
```

```json
{
  "name": "my-plugin",
  "version": "0.1.0",
  "description": "一句话说明",
  "evo_api": "^1",
  "enabled": false,
  "timeout_seconds": 20,
  "contributes": {
    "sidebar_pages":     [{"id": "main", "title": "我的页", "icon": "chart.bar", "run": ["python3", "main.py", "page"]}],
    "composer_commands": [{"id": "ask", "name": "ask", "title": "问一下", "description": "…", "usage": "/ask 问题", "run": ["python3", "main.py", "ask"]}],
    "notify_channels":   [{"id": "bark", "title": "推到手机", "events": "push", "run": ["python3", "main.py", "notify"]}],
    "item_actions":      [{"id": "open", "title": "在某处打开", "icon": "arrow.up.right.square", "run": ["python3", "main.py", "item"]}]
  }
}
```

规则（`evo plugin validate` 会逐条查）：

| 字段 | 规则 |
|---|---|
| `name` | 小写字母、数字、连字符，≤40；**必须和文件夹名一样** |
| `version` | 字符串，随你 |
| `evo_api` | 兼容范围（semver 子集）：`^1`、`1`、`>=1 <2`、`>=1.0,<3`、`*`。现在 evo 的插件接口是 `1.0` |
| `enabled` | 新装的一律 `false`（`evo plugin install` 会强制改成 false）；老板在 App 设置里打开或 `evo plugin enable` |
| `timeout_seconds` | 可选，1–60，默认 20；每个贡献点也可以单独写 |
| `contributes` | 至少一个贡献点；只认上面四个键 |
| 每个贡献点 `id` | 小写字母、数字、连字符；同类里不重复 |
| `title` | ≤40 字，侧栏 / 按钮上显示 |
| `run` | **字符串列表**（不是一条 shell 命令）。第一个词是 `python3` / `python` 时用 evo 自己的那个 python；带 `/` 或插件目录里有这个文件时是插件目录里的；否则在 PATH 里找。工作目录是插件目录 |
| `icon` | SF Symbols 名（https://developer.apple.com/sf-symbols/），可选，默认拼图块 |
| 输入框命令 `name` | 小写字母开头，≤24；输入框里打 `/name 参数`。保留词不能用：help add feedback team evo plugin plugins settings tick ship approve |
| 通知渠道 `events` | `push`（默认，只收要推的事，和 Telegram 一样受免打扰）或 `all`（每个事件都收，立刻收） |

## 三、请求（stdin）

evo 每次跑插件都往 stdin 写一个 JSON：

```json
{"evo_api": "1.0", "plugin": "my-plugin", "kind": "sidebar_page", "id": "main",
 "action": null, "payload": null, "args": "", "project": "TB", "item": null, "event": null}
```

| 字段 | 什么时候有值 |
|---|---|
| `kind` | `sidebar_page` / `composer_command` / `notify_channel` / `item_action` |
| `action`、`payload` | 老板点了卡片上的按钮：按钮的 `action` 和 `payload` 原样带回来。第一次打开页面时是 null |
| `args` | 输入框命令 `/ask 今天怎么样` 里的「今天怎么样」 |
| `project` | 当前项目代号（输入框选的项目、件所在项目；侧栏页给眼前选中的或第一个项目）；可能为 null |
| `item` | 件详情页按钮：件号 |
| `event` | 通知渠道：一条 outbox 事件（格式见 agent-interface.md 2.2：`kind`、`level`、`title`、`body`、`project`、`item`、`gate`、`data`…） |

环境变量（**只有这些**，白名单）：`PATH HOME LANG LC_ALL LC_CTYPE TZ TMPDIR USER LOGNAME`，加上 evo 给的：

| 变量 | 值 |
|---|---|
| `EVO_API` | `1.0` |
| `EVO_PLUGIN_NAME` | 插件名 |
| `EVO_PLUGIN_DIR` | 插件目录 |
| `EVO_PLUGIN_DATA` | 插件自己的数据目录 `~/.evoloop/plugin-data/<名字>/`（evo 建好了，随便写） |

插件**拿不到**任何密钥类环境变量（`EVO_TG_TOKEN`、`OPENAI_API_KEY`、webhook 密钥……都不传）。插件需要自己的密钥，就让老板放在 `$EVO_PLUGIN_DATA` 里的文件，或插件自己读钥匙串。

## 四、输出（stdout）：卡片 JSON

侧栏页、输入框命令、件按钮都输出**一张卡片**；通知渠道不用输出（退出码 0 就算发成功）。

```json
{"schema_version": 1, "title": "标题（必填）", "subtitle": "可选",
 "blocks": [
   {"type": "text", "text": "一段话", "style": "body", "tone": "neutral"},
   {"type": "list", "items": [{"title": "一行", "subtitle": "小字", "badge": "角标", "symbol": "checkmark.circle", "tone": "success"}]},
   {"type": "table", "columns": ["项", "值"], "rows": [["打开次数", 3]]},
   {"type": "buttons", "buttons": [{"label": "刷新", "action": "refresh", "style": "primary", "payload": {"page": 2}}]}
 ]}
```

| 块 | 字段 |
|---|---|
| `text` | `text`（必填）；`style` = `body`（默认）/ `caption`（灰小字）/ `title`（大标题）/ `mono`（等宽）；`tone` = `neutral` / `accent`（珊瑚橙）/ `success` / `warning` / `danger` |
| `list` | `items[]`：`title`（必填）、`subtitle`、`badge`、`symbol`（SF Symbol）、`tone` |
| `table` | `columns`（1–12 个字符串）、`rows`（每行字符串或数字；多的截掉、少的补空） |
| `buttons` | `buttons[]`（1–6 个）：`label`、`action`（必填）、`style` = `primary` / `secondary`（默认）/ `danger`、`payload`（任意 JSON，≤4 KB） |

上限：50 块、列表 200 条、表格 200 行、每段文字 2000 字（超长截断）、整个输出 256 KB。

**按钮怎么工作**：老板点击按钮后，evo 再跑一次**这个贡献点那条命令**。请求里 `action`、`payload` 就是按钮上写的那两项。插件输出新卡片，App 换上。所以一个插件命令要自己按 `action` 分支（见示例的 `page()`）。

App 用通用渲染器画卡片，样式和弹簧动效跟 App 其他卡片一样。页面有三种状态：**加载中**（转圈）、**报错**（红字 + 「再试一次」）、**空**（插件跑成功但没给内容）。

## 五、出错时会怎样

插件出任何事都只影响它自己那一页 / 那条回话，App 和 evo 主循环照常：

| 情况 | 结果 |
|---|---|
| 超过超时（默认 20 秒） | 整个进程组被杀，页面显示「插件超时（20 秒），已停掉」 |
| stdout 超过 256 KB | 立刻被杀，显示「插件输出超过 256 KB」 |
| 退出码非 0 | 显示「插件退出码 N：stderr 最后一行」 |
| 输出不是 JSON / 卡片不合格 | 显示具体哪一条不合格 |
| 插件关着 / plugin.json 不合格 / `evo_api` 不兼容 | 侧栏不出现；设置里显示原因；`evo plugin run` 报错 |
| 通知渠道失败 | stderr 记一行，其他渠道照发，outbox 照写 |

## 六、命令

```bash
evo plugin install <文件夹> [--force]      # 拷进 ~/.evoloop/plugins/，默认关着
evo plugin list [--json]                   # 装了哪些、开没开、贡献了什么
evo plugin enable <名字> | disable <名字>  # 开关（外部 Agent 不能用）
evo plugin validate [<名字>|<文件夹>]      # 检查 plugin.json；不带参数查全部；不合格退出码 1
evo plugin run <名字> sidebar_page <id> [--action A --payload JSON] [--project TB]
evo plugin run <名字> composer_command <名字或id> --args "参数"
evo plugin run <名字> item_action <id> --project TB --item TB-FIX-001
evo plugin run <名字> notify_channel <id>  # 发一条测试事件
evo notify-test                            # 每个通道（含插件渠道）各发一条
```

插件目录可以用环境变量 `EVO_PLUGINS_DIR` 换（测试、演示用）。

## 七、给 AI 的写插件清单

照着做就能一次过：

1. 建文件夹 `<名字>/`，名字小写连字符。写 `plugin.json`：`name` 等于文件夹名、`evo_api: "^1"`、`enabled: false`、`contributes` 里每项都有 `id`、`title`、`run`（列表）。
2. 写程序：读 stdin 整段 → `json.loads` → 按 `kind` / `action` 分支 → 往 stdout `print(json.dumps(卡片, ensure_ascii=False))` → 退出码 0。不要往 stdout 打别的东西（日志写 stderr）。
3. 只用标准库最稳（App 里的 python 不一定装了第三方包）。要存东西写 `$EVO_PLUGIN_DATA`。
4. 要读 evo 的数据：在插件里跑 `evo -p <代号> status --json` 之类（PATH 里有 evo 时），字段见 [app-contract.md](app-contract.md)。插件**不能**批闸门、不能上线（和外部 Agent 同一条规矩）。
5. 自测：`evo plugin validate ./<名字>` → `evo plugin install ./<名字>` → `evo plugin enable <名字>` → `evo plugin run <名字> sidebar_page <id> --json`，看 `ok: true`。
6. 卡片别太长：一页 3–6 块最好看；表格 ≤5 列。按钮 action 用英文小写短词。

## 八、例子：最小的侧栏页（10 行）

```python
#!/usr/bin/env python3
import json, sys, datetime
req = json.load(sys.stdin)
n = (req.get("payload") or {}).get("n", 0) + (1 if req.get("action") == "plus" else 0)
print(json.dumps({"schema_version": 1, "title": "计数器", "blocks": [
    {"type": "text", "text": f"现在是 {n}", "style": "title", "tone": "accent"},
    {"type": "text", "text": datetime.datetime.now().strftime("%H:%M:%S"), "style": "caption"},
    {"type": "buttons", "buttons": [{"label": "+1", "action": "plus", "style": "primary", "payload": {"n": n}}]},
]}, ensure_ascii=False))
```

```json
{"name": "counter", "version": "0.1.0", "evo_api": "^1", "enabled": false,
 "contributes": {"sidebar_pages": [{"id": "main", "title": "计数器", "icon": "plus.circle", "run": ["python3", "counter.py"]}]}}
```

## 九、安全边界（老实说）

- 做到了：子进程、超时杀整组、输出上限、环境变量白名单（拿不到密钥类环境变量）。
- 也做到了：默认关着、外部 Agent 不能开关/安装、插件失败不影响主循环。
- **没做到**：文件系统沙箱。插件以你的用户身份运行，理论上能读你家目录里的文件（包括 `~/.evoloop/panel.token`）。所以**只装你看过代码的插件**——这和 git / kubectl 插件、VS Code 扩展是同一个信任模型。以后要更严可以用 macOS `sandbox-exec` 包一层，那是第二版的事。
