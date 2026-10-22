# Claude 冷启动审查：提示词 + 订阅后的设置

> 用法：老板订好 Claude Pro 后，在 Mac 上**全新克隆**一份 evo，用真 Claude 订阅（不走 magpie）开 Claude Code，选 fable 或 opus 档，把下面「提示词」一节整段贴进去。Claude 只读不写，结果在 `~/tmp/CLAUDE-AUDIT-1.md`。
> 设置步骤在最后一节，先做设置再贴提示词。

---

## 提示词（整段复制）

```text
你在审查一个叫 evo 的系统。我要你独立判断它该怎么设计，不要被它现有的文档和规矩带着走。

## evo 是干什么的（只有这 5 行背景）
1. 通用的多项目自动驾驶：GitHub issue → 施工 Agent 写代码 → 另一个模型的验收 Agent 核对 → 老板闸门 → 合并 / 推送。
2. 老板只点三种按钮：做不做、看效果、上线；其余技术决定交给「决策岗」Agent。
3. 夜里无人值守长时间跑，出事要能自己恢复或停在安全的地方等老板。
4. 执行端（真正开 Agent 终端 / issue 的东西）是 Multica 或 Orca，两种都支持。
5. 各岗位的模型经本机网关 magpie 分配（施工 DSH、验收 glm、决策 Claude）。

## 规矩（这次审查只有这四条）
- 只读：不改任何文件、不提交、不推送、不装依赖；除了 git 不联网。可以跑只读命令（grep、git log、python3 -m pytest --collect-only 之类）。
- 只读代码和测试：kit/bin/、kit/features/、kit/tests/、app/Sources/。先不要读 docs/、notes/、kit/roles/、kit/README.md 里的「第 N 轮」记录、LESSONS.md（(g) 需要时再读 docs/role-file-references.md 末节）——它们描述的是现状和历史，可能是错的。你的结论写完以后，如果想核对某个设计当初为什么这么做，可以再去看对应文档，并在报告里注明哪条结论是看过文档后改的。
- 老板的核心原则「不重复造轮子」：能用成熟的库 / 工具 / 开源项目就不手写（许可证 MIT / Apache / BSD 可直接用，GPL 类要单独标出）。审查时把它当作一条评判标准。
- 判断优先：哪里值得深挖由你决定；拿不准的写「不确定」和你需要什么信息才能确定。

## 产出：写到 ~/tmp/CLAUDE-AUDIT-1.md（目录不存在就建），中文
(a) 如果从零设计这个系统，你会怎么做——不超过一页：核心状态、组件边界、和执行端 / 模型 / GitHub 的接口、失败和恢复怎么处理、老板闸门放在哪。
(b) 现有代码和 (a) 偏离最大的 10 处，按风险从高到低排。每处写：在哪（文件:函数或行号）、偏离了什么、是不是真问题（真问题 / 可以接受 / 不确定）、触发情形（什么情况下会出什么错）。
(c) 现有做得好、应该保留的地方，说清为什么。
(d) 手写了、但已有成熟工具或库能做的地方（例如自己写的锁、调度、重试、状态持久化、JSON 校验、事件总线、diff、时区、进程管理……以你读到的为准），每处写建议换成什么、许可证、换的代价，以及不换的理由是否成立。
(e) 具体提议，每条一个块，严格用下面的格式（evo 的决策岗可以原样交给老板）：
    {"item": "-", "action": "propose", "title": "<动作开头，24 字以内，不带版本号>", "scope": "<目录>",
     "note": "想改什么：…\n为什么：…\n不改的代价：…\n现成方案：查了什么 → 复用什么（许可证）／为什么都不合适"}
(f) 死代码扫描：找出 evo 里没人用的代码（函数、命令、配置键、功能包、测试辅助）。每处写位置和证据（grep 不到调用、测试没覆盖、git log 显示停用于哪次提交）。动态引用拿不准的（按字符串拼名字、getattr、功能包按 feature.json 装载、App 通过命令行调用、外部 Agent 读的 JSON 字段）标「待核实」并写原因，不当成可删。只列清单，不删。
(g) 可选——规则体检：如果你认为 kit/roles/ 里某条规则在误导 Agent，按 docs/role-file-references.md 末节「规则体检」的思路写一份实验方案（挑哪条、用哪件历史任务、怎么对照、比什么），不要真跑。
最后一节写「我没看 / 没把握的地方」。
```

---

## 订阅 Claude Pro 之后的 Claude Code 设置

### 1. 安装和登录
- 已经装过 Claude Code 就跳过安装；没装按官方文档装（https://code.claude.com/docs/en/quickstart），装完 `claude --version` 能出版本号。
- 现在 Mac 上的 `~/.claude/settings.json` 被 magpie 接管了：里面把 API 地址改成了 `http://127.0.0.1:3425`。直接敲 `claude` 走的是 magpie，不是你的 Pro 订阅。
- 审查要用真订阅跑（fable / opus 的完整能力，也不占 magpie 的额度），所以另开一份干净配置。Claude Code 官方支持环境变量 `CLAUDE_CONFIG_DIR`：「覆盖配置目录（默认 `~/.claude`），设置、会话记录、插件都放这里，适合多个账号并排用」（https://code.claude.com/docs/en/env-vars ，2026-10-23 核对过）。

```bash
mkdir -p ~/.claude-pro ~/tmp
# 只在这一条命令里去掉 magpie 可能在 shell 里设的变量，再用新配置目录启动
env -u ANTHROPIC_BASE_URL -u ANTHROPIC_AUTH_TOKEN -u ANTHROPIC_API_KEY \
  CLAUDE_CONFIG_DIR="$HOME/.claude-pro" claude
```
- 第一次启动按提示选「Claude 账号登录」（claude.ai 的 Pro 账号），浏览器里确认。
- 进去后敲 `/status`：登录方式应显示 Claude 账号（Pro），**不应该**出现 `127.0.0.1:3425`。看到 3425 说明还在走 magpie——退出，检查 `~/.claude-pro/settings.json` 里有没有被复制进去的 `ANTHROPIC_BASE_URL`，删掉再进。
- 常用的话加个别名：`alias claude-pro='env -u ANTHROPIC_BASE_URL -u ANTHROPIC_AUTH_TOKEN -u ANTHROPIC_API_KEY CLAUDE_CONFIG_DIR=$HOME/.claude-pro claude'`。原来的 `claude`（走 magpie）不受影响。
- 登录凭据在 macOS 上存钥匙串；换了配置目录后第一次要重新登录一次，这是正常的。

### 2. 跑审查
```bash
cd ~/tmp && rm -rf evo-audit && git clone https://github.com/JAY5CXSDMY14/evomap.git evo-audit && cd evo-audit
claude-pro            # 进去后 /model 选 fable（没有就 opus），再贴上面的提示词
```
- 想让它只能读：启动时加 `--permission-mode plan`（只读规划模式），它要写报告时会请你批准那一次写文件。

### 3. 以后把决策岗换成 Pro（审查之后再做，不急）
- **Orca 执行端**：决策岗是 evo 在终端里敲的一条命令。全局配置 `~/.evoloop/config.json` 的 `roles.decide`：
  - 先用 `evo team set decide --tool claude --via cli --model opus`（或 fable）把工具和档位定下来；
  - 再把 `roles.decide.cmd` 改成 `env -u ANTHROPIC_BASE_URL -u ANTHROPIC_AUTH_TOKEN -u ANTHROPIC_API_KEY CLAUDE_CONFIG_DIR=$HOME/.claude-pro claude --model {model}`（`evo team set` 没有改整条命令的参数，这一步手改配置文件）。
  - App 团队页的决策卡片下拉框走的是同一个 `evo team set`，改完 `evo team` 能看到「决策 claude · opus」。
- **Multica 执行端**：派工是 `issue assign` 给 Multica 里叫「决策-Claude」的 agent（项目配置 `multica.agents.decide`），用哪个账号由 Multica 那边的 agent 设置决定，evo 管不到。在 Multica 里给这个 agent 设上面同样的环境（`CLAUDE_CONFIG_DIR=$HOME/.claude-pro`，并去掉 `ANTHROPIC_BASE_URL`）。这一步还没在真机上验过。
- 施工（DSH）和验收（glm，sonnet 档）不动，仍走 magpie。
