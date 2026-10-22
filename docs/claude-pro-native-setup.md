# Claude Pro 原生接入 evo：怎么接、能不能接、接了怎么不出事

> 写于 2026-10-23。只引用当天实际打开过的页面，每条都标了日期。文中「不确定」的地方就是不确定，没有替官方补话。
> 本文只描述方案，不改代码；代码改动清单在第 4 节，等老板点头再做。

---

## 0. 明早清单（先看这个）

**结论一句话**：用你自己的 Pro 账号登录**官方、未改动的 `claude` 程序**，让 evo 在 Mac mini 上调用它做决策岗，属于官方明说允许的「本人正常使用 Claude Code」，风险低；**但前提是你人在受支持的地区用它**——这一条我们改变不了，VPN 也改变不了。把订阅登录塞进 magpie 或任何代理，是明确禁止的，不要做。

明早按顺序做：

1. **先决定地区问题**（最重要，第 2.4 节）：Anthropic 的地区政策按「人在哪」算，不按 IP 算。人在不受支持的地区时，evo 的 Claude 岗位应整体关掉（第 4 节的「地区开关」），只用 magpie 的其它模型。出差到受支持地区（例如日本）时再打开。我不提供「保持稳定出口 IP 绕过地区检查」的办法，原因见 2.4。
2. **买 Pro 时**：账单地址、付款方式写真实信息；不要买别人注册好的号、不要用代充。
3. **Mac mini 上装/升级 Claude Desktop 和 Claude Code**，按第 3 节分两套配置目录：
   - `~/.claude-pro`（新建，只放 Pro 登录，干净，不含任何 `ANTHROPIC_BASE_URL`）
   - 原来的 `~/.claude`（继续给 magpie 用）
4. **登录**：`CLAUDE_CONFIG_DIR=~/.claude-pro claude`，在里面 `/login` 选 Claude 订阅账号；然后 `CLAUDE_CONFIG_DIR=~/.claude-pro claude auth status` 确认输出 JSON 里 `authMethod` 是 `claude.ai`、`configDirectory` 是 `~/.claude-pro`（`configDirectory` 字段要 v2.1.268+）。
5. **关自动更新、固定版本**（3.5 节）：在 `~/.claude-pro/settings.json` 里写 `"autoUpdatesChannel": "stable"`，并设 `DISABLE_AUTOUPDATER=1` 给 evo 用的那份环境；升级改成你手动做。
6. **不要打开 Extra usage（超额付费）**：否则额度用完后 evo 会继续跑并按量扣钱，而不是停下来。
7. **跑一次第 5 节验收清单**，前 3 项通过才让 evo 把决策岗切到 Pro。
8. **Claude Desktop 里的 Code 标签**：先别用它跑长任务（2.6 节有一个没核实的风险：它可能读到 `~/.claude/settings.json` 里 magpie 的地址）。普通聊天没问题。
9. Multica 那边：决策岗的 agent **并发上限改成 1**（Multica 默认是 6）。

**不要做的事**（每条都有出处，见第 2 节）：
- 不要把 Pro 的 OAuth 登录接到 magpie / OpenClaw / 任何第三方工具里；
- 不要用 `claude --bare`（它根本不读订阅登录）；
- 不要把订阅 token 写进 Multica 的 `custom_env`（Multica 文档说它以明文存在服务器数据库里）；
- 不要多人共用、不要转卖。

---

## 1. 结论（白话，诚实版）

| 做法 | 判断 | 依据 |
|---|---|---|
| 本人用 Pro 登录**官方未改动的 `claude`**，交互用 + `claude -p` 脚本调用（evo/Multica 起进程） | **低风险，官方明确允许** | 法务页：订阅 OAuth 用于「ordinary use of Claude Code and other native Anthropic applications」，并明说个人用自己的订阅登录未改动的 Claude Code 是允许的；帮助文章（2026-10-07 更新）：「You can still use the Claude Agent SDK, `claude -p`, and third-party apps with your subscription limits」 |
| evo 无人值守、长时间、多进程并发调用 | **灰区，主要是额度和「正常个人用量」的问题** | 法务页：「Advertised usage limits for Pro and Max plans assume ordinary, individual usage of Claude Code and the Agent SDK」；消费者条款 §3 禁止「automated or non-human means… bot, script」，除非用 API Key 或「where we otherwise explicitly permit it」——`claude -p` 用订阅额度是帮助中心明文许可的，所以我判为灰区偏安全，不是禁止 |
| 把订阅登录放进 magpie / 代理 / 第三方 harness，或抽 token 给别的工具用 | **明确禁止，高风险** | 法务页：开发者「may not… route requests through Free, Pro, or Max plan credentials on behalf of their users」，不得 collect/store/intermediate 凭据；2026-02-20 The Register：Anthropic 1 月起从服务端拦截冒充 Claude Code 的工具，2 月改条款写明；2026-04-04 TNW：OpenClaw 等第三方 harness 被切出订阅额度 |
| 人在不受支持的地区（中国大陆、香港等）使用，无论是否挂 VPN | **违反地区政策，有封号先例** | Supported Regions Policy 明写「Use by persons while physically located in an unsupported region」不被支持；帮助中心封号原因第二条就是不受支持地区；SCMP 2026-10-02：香港用户挂 VPN 用了数月后被以「suspicious signals」停号 |

**我不确定的地方**（明说）：
- 「正常个人用量」没有量化标准。Pro 有 5 小时和每周两层额度，官方没公布具体条数，也没公布同时跑几个 `claude` 进程算不算异常。evo 的自我约束（并发 1、只给决策岗）是我从「正常个人用量」这句话推出来的保守做法，不是官方数字。
- 36kr/新智元 2026-10-15 的报道说「封禁完全解除」，这说法夸大了：它依据的是 10-07 那条帮助中心更新（Max/Team 有月度 API 额度，`claude -p` 继续可用订阅额度），但同一时间的法务页仍然禁止第三方代持订阅凭据。**Pro 不享受那份 API 额度**。
- 法务页 2 月版本里那句「including the Agent SDK — is not permitted」，在我今天打开的法务页里已不是原句；现行措辞是「designed to support ordinary use of Claude Code and other native Anthropic applications」。所以「Agent SDK 能不能用订阅」以帮助中心 10-07 那篇为准，但它对 Pro 的承诺只到「继续从订阅额度里扣」，没有更多。
- Anthropic 风控看什么信号，没有公开文档（第三方站点也承认是猜）。所以第 2.4 节只讲政策，不讲「怎么不被检测到」。

---

## 2. 逐项说明

### 2.1 政策原文（三处要点）

- **法务与合规页** code.claude.com/docs/en/legal-and-compliance（2026-10-23 打开）：OAuth「intended exclusively for purchasers of Claude Free/Pro/Max/Team/Enterprise subscription plans and is designed to support ordinary use of Claude Code and other native Anthropic applications」；做产品（含 Agent SDK 产品）的开发者应使用 API Key；Anthropic 可不经通知执行。
- **消费者条款** anthropic.com/legal/consumer-terms（生效 2025-10-08，2026-10-23 打开）：§3 禁止脚本/机器人方式访问（API Key 或明确许可除外）；禁止共享账号；须遵守地区政策。
- **帮助中心 15036540**「Use the Claude Agent SDK with your Claude plan」（2026-10-23 打开）：2026-10-07 更新给 Max/Team 加了月度 API 额度；「You can still use the Claude Agent SDK, `claude -p`, and third-party apps with your subscription limits」；2026-06-15 那次改动已暂停。Pro 不在 API 额度名单里。

### 2.2 时间线（为什么这件事敏感）

- 2026-01：Anthropic 开始在服务端拦截冒充 Claude Code 的第三方工具（The Register 2026-02-20 引 Anthropic 工程师 Thariq Shihipar 的帖子：第三方 harness「generate unusual traffic patterns without any of the usual telemetry」）。
- 2026-02-19/20：法务页加了明文；OpenCode 同日移除了 Claude 订阅登录（The Register 2026-02-20）。
- 2026-04-04：Pro/Max 不能再把订阅额度给 OpenClaw 等第三方 harness 用，改走「extra usage」按量付费；官方的 Claude Code 不受影响（TNW 2026-04-04）。
- 2026-10-07：帮助中心更新，`claude -p` 继续可用订阅额度；Max/Team 另给月度 API 额度。

**对 evo 的含义**：evo 调的是官方 `claude` 程序本身，带官方遥测，这正是 Anthropic 区分「自家产品」和「第三方 harness」的那条线的安全一侧。magpie 那条路（把请求改道到本地网关）在这条线的另一侧——哪怕只是透传，也不是官方认可的用法。

### 2.3 Claude Desktop 和 Claude Code 共用一个登录

- 同一个账号在 Claude Desktop、claude.ai、Claude Code 里登录，是官方产品的正常用法；额度在这些产品之间**共享**（帮助中心 11145838 说明 Pro 用量跨 Claude 与 Claude Code 合计）。
- 两边是**分别登录**的：Desktop 自己做 OAuth；Claude Code 的凭据放在 macOS 钥匙串里，authentication 文档写明钥匙串条目按 `CLAUDE_CONFIG_DIR` 区分（不同目录读不同条目；钥匙串被锁时会退回到该目录下的 `.credentials.json`，权限 0600）。换句话说，`~/.claude-pro` 下登录一次，evo 用；Desktop 自己再登录一次，你用。不需要、也不应该在两者之间复制 token。
- 后果：你白天在 Desktop 里聊得多，evo 夜里能用的额度就少。evo 要能看懂「额度满了」并退回 magpie（4.3 节）。

### 2.4 设备与 IP：地区一致性、Tailscale、出差

先说清楚边界：**我不提供「如何维持稳定的境外出口 IP 以免被识别」的方案**。原因很直接：Supported Regions Policy 把「人在不受支持的地区使用」本身列为不被支持；它看的是人的物理位置，IP 只是 Anthropic 用来判断的信号之一。换一个更稳的出口 IP，只是让违规更难被发现，不是让它变合规；SCMP 2026-10-02 报道的香港用户正是这种情况——用了半年后被停号、聊天记录要靠申诉才能导出。我能给的是合规范围内的安排：

| 场景 | 建议 |
|---|---|
| 你和 Mac mini 都在不受支持的地区 | evo 的 Claude 岗位**整体关闭**（地区开关 = off），决策岗用 magpie 的其它模型。这是唯一合规的做法 |
| 你出差到受支持地区（如日本），Mac mini 留在家 | 政策说的是「使用者人在哪」。你本人在日本、从 Air 经 Tailscale 操作家里的 mini，mini 的出口仍在家里——这种「人在 A、机器在 B」的情形，**官方没有写清楚怎么算**。保守做法：出差期间让 Air 本机跑需要 Claude 的活（Air 在你身边、出口就是你所在地），mini 上的 Claude 岗位保持关闭 |
| Air 本机在受支持地区使用 Claude Code | 正常使用；同一账号多台自己的设备登录，没有找到禁止或限制台数的官方说法（找过，没找到，不代表没有） |
| 付款方式 | 消费者条款要求账户信息真实。用你自己名下、真实账单地址的卡或你自己的 App Store 账号订阅。不要用别人代付、代充或「保证不封」的号——第三方 FAQ（claudeqa.com 2026-10-21）也把这类列为常见封号原因，但那是第三方，不是官方 |
| 身份验证 | 帮助中心 14328960（2026-08-11）：Anthropic 已在部分场景要求用 Persona 做政府证件 + 自拍验证。可能某天会弹出来，要准备好真实证件 |

被封了怎么办：登录 claude.ai → claude.ai/restricted 提交申诉；被封的 Pro 账号仍能自助导出数据或删号（帮助中心 8241253，2026-10-23 打开）。

### 2.5 并发：一个订阅同时跑几个 claude

- 官方没有公布 Pro 的并发上限（我没找到）。最佳实践页本身就鼓励「Run multiple Claude sessions in parallel」，所以多会话本身不是违规。
- 但每个会话都从同一份 5 小时/每周额度里扣，而且「正常个人用量」是有前提的。**建议**：
  - 只有决策岗走 Pro，并发 = 1（Multica 里这个 agent 的「Concurrency limit」改成 1；Multica 文档写明默认 6）。
  - 验证岗、建造岗继续走 magpie；等跑满两周、看清 Pro 一天能撑几轮决策后，再考虑要不要给验证岗。
  - 你自己同时在 Desktop/终端用 Claude 时，evo 不必让路——额度满了它会自己退回 magpie。

### 2.6 一个没核实的风险：Desktop 的 Code 标签会不会走到 magpie

Claude Code 的设置文档说：Desktop 启动会话时，它自己构造的启动环境优先，**设置文件里同名变量会被忽略**——反过来讲，Desktop 没设的变量，`~/.claude/settings.json` 里的 `env` 仍会生效。如果 magpie 是写在 `~/.claude/settings.json` 的 `env.ANTHROPIC_BASE_URL` 里，那么 Desktop 的 Code 标签用默认配置目录开会话时，**有可能**把带着你 Pro 登录的请求发到 magpie。这一条我没有在真机上验证。验证方法在第 5 节第 4 项；如果确认会，长期解法是 3.2 的方案 B（把 magpie 挪到自己的目录，`~/.claude` 留给原生）。

---

## 3. Mac mini 分步配置

### 3.1 前提

- Mac mini 上已有：magpie、Multica daemon、evo。
- `which -a claude` 只应有一份官方安装（Homebrew cask `claude-code` 或官方安装脚本二选一）。两份并存时，evo/Multica 可能调到另一份，版本和配置目录都会对不上。

### 3.2 两种目录布局（二选一）

| | 方案 A（先这么做） | 方案 B（长期推荐） |
|---|---|---|
| 原生 Pro | `~/.claude-pro`（新建） | `~/.claude`（默认目录，Desktop 也用这个） |
| magpie | `~/.claude`（保持现状） | `~/.claude-magpie`（新建，把 magpie 的 env 挪过去） |
| 改动量 | 小，不碰 magpie 现有链路 | 要改 Multica/evo 里 magpie 岗位的启动环境 |
| 2.6 的风险 | 存在（Desktop 用 `~/.claude`） | 消除 |

下文按方案 A 写；方案 B 只是把两个目录名对调。

### 3.3 登录

```bash
# 1) 新目录，只放原生配置
mkdir -p ~/.claude-pro
cat > ~/.claude-pro/settings.json <<'EOF'
{
  "autoUpdatesChannel": "stable",
  "cleanupPeriodDays": 365
}
EOF
# 注意：这里没有 env、没有 ANTHROPIC_BASE_URL、没有 apiKeyHelper

# 2) 用干净环境启动并登录（交互一次即可）
env -u ANTHROPIC_BASE_URL -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN \
    -u ANTHROPIC_MODEL -u CLAUDE_CODE_USE_BEDROCK -u CLAUDE_CODE_USE_VERTEX \
    CLAUDE_CONFIG_DIR="$HOME/.claude-pro" claude
#   在里面输入 /login，选 Claude account（订阅），浏览器里完成授权

# 3) 确认
CLAUDE_CONFIG_DIR="$HOME/.claude-pro" claude auth status
#   期望：authMethod = "claude.ai"（订阅），configDirectory = ~/.claude-pro
#   若是 api_key / oauth_token / third_party，说明有环境变量或设置在抢先，先排查
```

为什么要 `env -u`：authentication 文档的「Authentication precedence」里，`ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` / `CLAUDE_CODE_OAUTH_TOKEN` 都排在 `/login` 订阅登录前面；`ANTHROPIC_BASE_URL` 会把请求改道。任何一个漏掉，「以为在用 Pro」其实在用别的。

### 3.4 magpie 保持原样，但 Pro 不经过它

- magpie 继续服务 verifier / builder 等岗位，配置不动。
- Pro 只在 `~/.claude-pro` 里存在，**不在 magpie 里配任何 Anthropic 订阅 provider**。如果 magpie 现在已经有「用 Claude 订阅登录」的 provider（我在 `docs/magpie-reference.md` 里没看到，但请你在 magpie 设置里确认一次），把它关掉。

### 3.5 关自动更新，防止升级把 evo 弄坏

- `~/.claude-pro/settings.json` 写 `"autoUpdatesChannel": "stable"`（稳定通道比 latest 慢一拍，Claude Code 团队自己的发布也是先 latest 后 stable——见 claude.dev 2026-10-15 的代码审查文章）。
- evo/Multica 启动 claude 时加环境变量 `DISABLE_AUTOUPDATER=1`（env-vars 文档：关后台自动更新，手动 `claude update` 仍可用；更严的 `DISABLE_UPDATES=1` 连手动也禁），让无人值守的进程绝不自己升级。
- 升级改成手动：每周看一次 changelog，先在终端里 `claude --version`、跑第 5 节第 1–3 项，再让 evo 用新版。
- 若用 Homebrew 装的，`brew pin` 不对 cask 生效；用 `HOMEBREW_NO_AUTO_UPDATE=1` 并且不跑 `brew upgrade` 即可。
- 要注意的已知变化（来自官方 headless 文档，2026-10-23 打开）：
  - `--bare` 将来会成为 `-p` 的默认，**而 bare 模式不读订阅登录**。到那天如果 evo 没显式处理，Pro 调用会直接失败。所以 evo 应在每次调用前检查 `auth status`（4.4），并关注 changelog 里「bare」相关字样。
  - v2.1.302 起 `claude -p` 默认 Manual 权限模式；`--permission-prompts none` 需要 v2.1.259+。

### 3.6 evo / Multica 的决策岗怎么调原生 claude

**evo 直跑（不经 Multica）**：决策岗卡片示意（字段名按现有 `team` 卡片：`cmd` / `tool` / `account` / `fallback`）

```yaml
roles:
  decider:
    cmd: >-
      env -u ANTHROPIC_BASE_URL -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN
      CLAUDE_CONFIG_DIR=${HOME}/.claude-pro DISABLE_AUTOUPDATER=1
      claude -p --output-format stream-json --verbose
      --permission-mode dontAsk --permission-prompts none
    tool: claude          # 必须显式写：否则命令第一个词是 env，工具名会被算成 env
    account: claude-pro   # 必须显式写：否则和走 magpie 的 claude 岗位算成同一个账号，一起暂停
    native_claude: true   # 第 4 节新增字段
    fallback:
      cmd: claude -p --output-format stream-json --verbose   # 走 ~/.claude，也就是 magpie
      tool: claude
      account: magpie
      model: <magpie 里给决策岗的备用模型>
```

**经 Multica**：
- Multica 文档（multica.ai/docs/agents-create，2026-10-23 打开）：agent 可设「Environment variables」和「Custom arguments」，但 `PATH`、`HOME`、`MULTICA_*` 不能覆盖；**custom_env 明文存在 Multica 服务器数据库里**。
- 所以：给决策 agent 设 `CLAUDE_CONFIG_DIR=/Users/<你>/.claude-pro` 和 `DISABLE_AUTOUPDATER=1` 可以（不是秘密）；**不要**把任何 token 放进去。
- `ANTHROPIC_BASE_URL` 不能靠 custom_env「删掉」，只能保证 Multica daemon 自己的启动环境里没有它（magpie 的地址只写在 `~/.claude/settings.json`，不写进 daemon 的 launchd 环境）。由于 `CLAUDE_CONFIG_DIR` 指向 `~/.claude-pro`，`~/.claude/settings.json` 里的 env 不会被读到。这一点要在第 5 节第 2 项真机确认。
- 并发上限改 1。

---

## 4. evo 需要的改动（只描述，不实现）

### 4.1 每个岗位卡片加 `native_claude: true`

evo 派工时若看到这个标记：
1. 从子进程环境里**删除** `ANTHROPIC_BASE_URL`、`ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_MODEL`、`CLAUDE_CODE_USE_BEDROCK/VERTEX/FOUNDRY`、`ANTHROPIC_DEFAULT_*_MODEL`；
2. 设 `CLAUDE_CONFIG_DIR=<全局配置 claude_pro.config_dir，默认 ~/.claude-pro>`、`DISABLE_AUTOUPDATER=1`；
3. 拒绝 `--bare`（发现就报错，不派工）；
4. 不再需要用户在 `cmd` 里手写 `env -u …`，`tool`/`account` 自动取 `claude` / `claude-pro`。

这样也顺手修掉两个现有的小坑（在 `kit/bin/evo` 和 `kit/bin/evo_roles.py` 里看到的）：
- `role_account()` / `tool_of()` 默认取命令第一个词——用 `env …` 包一层就会变成 `env`；
- 走 magpie 的 claude 岗位和走 Pro 的 claude 岗位默认都叫 `claude`，会被当成同一账号一起暂停。

### 4.2 `claude_trust()` 要跟着配置目录走

现在它写的是 `~/.claude.json`。设置了 `CLAUDE_CONFIG_DIR` 后，Claude Code 的全局状态文件**很可能**在 `$CLAUDE_CONFIG_DIR/.claude.json`（文档说 `~/.claude` 下的路径都会移到该目录；`.claude.json` 是否也跟着移，我没在真机确认）。改成：`native_claude` 岗位写 `$CLAUDE_CONFIG_DIR/.claude.json`，并在第 5 节第 3 项里验证项目信任对话框不会卡住无人值守进程。

### 4.3 额度用完：退回 magpie，不碰 Pro

现有机制已经够用，只差账号名分开：
- `rate_limit_line()` 已认得 `usage limit`、`limit reached` 等；`parse_reset()` 已能解析重置时间。
- `rl_pause()` 对「卡片配了不同账号备用」的岗位，不推「额度暂停」，而是「切到备用」。
- 只要决策岗 `account: claude-pro`、备用 `account: magpie`，Pro 满了就自动切 magpie，**直到重置时间之前不会再碰 Pro**；备用岗位的环境里没有 `CLAUDE_CONFIG_DIR=~/.claude-pro`，所以也不会误用 Pro 登录。
- 补一条：stream-json 里会有 `system/api_retry` 事件，字段 `error` 可能是 `rate_limit`、`authentication_failed`、`account_on_hold`、`billing_error`（headless 文档，2026-10-23）。建议 evo 直接读这个字段，而不是只靠尾部文本匹配：
  - `rate_limit` → 走 4.3 的切备用；
  - `account_on_hold` / `authentication_failed` → **整个 claude-pro 账号停用并通知老板**，不重试（重试一个被 hold 的账号没有意义，还可能让情况更糟）；
  - `billing_error` → 停用并通知。
- 「Extra usage」开着的话，额度满后不会报 rate_limit 而是开始扣钱。evo 无法从输出可靠区分，所以第 0 节第 6 条要求不开。

### 4.4 每次调用前的健康检查

派给 `native_claude` 岗位之前跑一次 `CLAUDE_CONFIG_DIR=… claude auth status`（输出 JSON）：
- `authMethod` 不是 `claude.ai`、或 `configDirectory` 不对、或退出码 1（未登录）→ 不派工，切备用，通知；
- 登录快过期：官方在到期前 3 天启动时提示「Your login expires in 3 days」，到期后每个请求报「Login expired · Please run /login」，无人值守会话会停住（authentication 文档）。evo 在输出里看到这两句就通知老板重新登录。
- **地区开关**：全局配置 `claude_pro.enabled`（默认 false）。老板人在不受支持地区时保持 false；evo 的 `team` 面板上显示一个醒目的开关状态。evo 不自动猜地区，只认这个开关。

### 4.5 日志与审计（证明是正常的一方用量）

每次 Pro 调用，evo 记一行到 `state/claude-pro-usage.jsonl`（不进 git）：
- 时间（带时区）、岗位、事项 ID；
- `claude --version`、`auth status` 里的 `authMethod` / `configDirectory`；
- `session_id`、模型、退出码、耗时、`total_cost_usd`（这是客户端估算，不是账单）；
- 期间收到的 `api_retry` 事件及 `error`；
- 是否切了备用。

再加两条：
- `~/.claude-pro/settings.json` 里 `cleanupPeriodDays: 365`，把官方会话记录（`~/.claude-pro/projects/*.jsonl`）留一年——万一被问到，这是最有力的证据：全是官方程序、本人项目、正常节奏。
- magpie 侧：确认 magpie 的请求日志里**从来没有**决策岗 Pro 时段的请求（第 5 节第 2 项）。

这些记录只证明「我们用的是官方程序、没有中间人」；**不能**证明地区合规，那一条只能靠第 2.4 节的做法。

### 4.6 不建议做的改动

- 不建议用 `claude setup-token` 拿一年期 token 给 evo 用。它本身是官方给「CI 和脚本」的功能，不违规；但 token 一旦落到文件或 Multica 的 custom_env，就成了一个可被复制的长期凭据。钥匙串登录 + `CLAUDE_CONFIG_DIR` 已经够用。真要用，只放 macOS 钥匙串，用 `apiKeyHelper` 之类读出来，不落明文。

---

## 5. 订阅后的验收清单

按顺序，前 3 项全过才切换：

1. **身份正确**：`CLAUDE_CONFIG_DIR=~/.claude-pro claude auth status` → `authMethod` 为 `claude.ai`、`configDirectory` 指向 `~/.claude-pro`。再以 evo 的方式跑一次 `claude -p "回答 ok" --output-format json`，看 JSON 里的 `session_id` 能在 `~/.claude-pro/projects/` 下找到对应的会话文件。
2. **没经过 magpie**：上一步运行时，magpie 的请求日志里没有新请求；`ps eww <claude 进程号>` 里看不到 `ANTHROPIC_BASE_URL`。Multica 路径也各跑一次。
3. **无人值守不卡住**：用 `--permission-mode dontAsk --permission-prompts none` 跑一个只读小任务，确认没有信任对话框、没有权限提示卡住，进程正常退出、退出码 0。
4. **Desktop 风险排查**（2.6）：在 Claude Desktop 的 Code 标签里开一个会话，运行 `/status`，同时看 magpie 日志。如果 magpie 收到了请求 → 改用方案 B。
5. **额度满时的行为**（不必真的打满）：把一段真实的「usage limit reached… resets at …」文本喂给 `evo` 的额度解析，确认解析出的重置时间对、岗位切到 `account: magpie`、`state` 里 claude-pro 记为暂停到重置时间。
6. **并发**：Multica 决策 agent 并发 = 1；evo 同时最多一个 `native_claude` 子进程（`ps` 确认）。
7. **自动更新已关**：一周后 `claude --version` 没变；`DISABLE_AUTOUPDATER=1` 在 evo 子进程环境里（`ps eww`）。
8. **Extra usage 未开**：claude.ai → 设置 → 用量页确认。
9. **审计日志在写**：`state/claude-pro-usage.jsonl` 每次调用一行，字段齐全。
10. **地区开关**：把 `claude_pro.enabled` 设为 false，确认 evo 不再派工给 Pro、决策岗直接走 magpie。

### 额度满时 evo 的行为（汇总）

| 情况 | evo 动作 | 碰不碰 Pro |
|---|---|---|
| Pro 报 rate limit / usage limit | 决策岗切 magpie 备用，直到解析出的重置时间（解析不出默认 60 分钟），到点自动切回并记一条「恢复」 | 重置前不碰 |
| 备用也满 | 记 `decider:fallback` 暂停，决策岗整体等待，通知老板 | 不碰 |
| account_on_hold / 认证失败 / billing | claude-pro 整体停用，通知老板，等人工处理 | 不碰，直到老板手动恢复 |
| 地区开关 off | 决策岗只走 magpie | 不碰 |

---

## 6. 来源（全部 2026-10-23 打开）

| 来源 | 机构 / 作者 | 日期 | 权威性 |
|---|---|---|---|
| https://code.claude.com/docs/en/legal-and-compliance | Anthropic 官方文档 | 现行版 | 一手、最高 |
| https://www.anthropic.com/legal/consumer-terms | Anthropic | 生效 2025-10-08 | 一手、最高 |
| https://www.anthropic.com/supported-countries | Anthropic | 现行版 | 一手、最高 |
| https://support.claude.com/en/articles/15036540 | Anthropic 帮助中心 | 更新 2026-10-07 | 一手 |
| https://support.claude.com/en/articles/11145838 | Anthropic 帮助中心 | 现行版 | 一手 |
| https://support.claude.com/en/articles/8241253-safeguards-warnings-and-appeals | Anthropic 帮助中心 | 现行版 | 一手 |
| https://support.claude.com/en/articles/14328960-identity-verification-on-claude | Anthropic 帮助中心 | 2026-08-11 | 一手 |
| https://code.claude.com/docs/en/headless | Anthropic 官方文档 | 现行版 | 一手 |
| https://code.claude.com/docs/en/authentication 、/settings 、/env-vars 、/setup 、/llm-gateway 、/claude-directory | Anthropic 官方文档 | 现行版 | 一手 |
| https://code.claude.com/docs/en/best-practices | Anthropic 官方文档 | 现行版 | 一手 |
| https://multica.ai/docs/agents-create | Multica 官方文档 | 现行版 | 一手（工具方） |
| https://www.theregister.com/software/2026/02/20/anthropic-clarifies-ban-on-third-party-tool-access-to-claude/5014546 | The Register / Thomas Claburn | 2026-02-20 | 二手、可信媒体 |
| https://thenextweb.com/news/anthropic-openclaw-claude-subscription-ban-cost | TNW | 2026-04-04 | 二手 |
| https://www.scmp.com/tech/tech-war/article/3369526/hong-kong-users-caught-offguard-anthropic-tightens-vpn-access-claude | SCMP / Chong Ming Lee | 2026-10-02 | 二手，只读到导语部分 |
| 36kr / 新智元「封禁完全解除」报道 | 36kr | 2026-10-15 | 二手，**判断为夸大**，仅作反例 |
| https://claude.dev/blog/solving-code-review-at-anthropic/ | Anthropic Claude Code 团队 | 2026-10-15 | 一手（latest/stable 发布节奏） |
