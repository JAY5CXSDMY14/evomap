# evo 循环全景（2026-10-23，第二十五轮后）

```callout
你只做两件事：**说需求**，**拍板**。其余的事由 evo 和工人做。
```

## 1. 一件事怎么走完

```flow TB
(老板)
老板 -> 入口: 说需求
group 入口: Hark 聊天, 任意外部 agent
Hark 聊天 -> [(GitHub issue 账本)]: 我提 issue
任意外部 agent -> GitHub issue 账本
GitHub issue 账本 -> *evo 调度
evo 调度 -> 决策岗 Claude: 拆任务、技术决定
决策岗 Claude -> evo 调度
evo 调度 -> Multica: 派工
Multica -> 施工岗 DSH -> 验收岗 Claude
验收岗 Claude -> evo 调度: 通过或打回
evo 调度 -> {要老板拍板?}
要老板拍板? -> 推送卡片: 是（做不做 / 看效果 / 上线）
推送卡片 -> 老板: Telegram
老板 -> evo 调度: 在 Telegram 点做 / 不做、通过 / 打回、上线 / 再等等
要老板拍板? -> [(main 上线)]: 否，自动合并
```

- **GitHub issue** 是唯一账本。谁提的都一样。**件号就是 issue 号**（`TB#123`，说「#123」也认；老件 `TB-FIX-012` 照旧）。
- **evo** 是调度和把关：排队、上限、返工、闸门。它自己合并，不走 PR。
- **Multica** 是工位：工人在这里干活，你只在排障时看。
- **老板卡只有三种**：做不做、看效果、上线。决策岗转来的红线问题、外部来报碰红线、每件上限到了，都是「做不做」卡，卡上写清为什么问你。
- **批卡只在 Telegram**。Telegram 没配好时 evo 会推一次提醒（邮件 / 本机通知），邮件里带 `evo -p 代号 approve 闸门 选项` 命令，在 Mac 上跑也能批。
- **网页面板**只读，是「看效果」页：件、截图、状态、diff，不能批。**App 冻结**：不批卡、不加功能。
- **代码规则**交给各项目自己的 lint / CI：项目配置的 `checks` 写命令，验收岗逐条跑；evo 不再自带 UI / 架构预设。

## 2. 谁改什么

| 场景 | 谁动手 | 怎么走 |
| :--- | :--- | :--- |
| 项目的功能、文档、小修（TB / ST / EV 日常） | evo 的工人 | 你跟我说，我提 issue；你也可以在别的 agent 里提 |
| evo 自己卡住的 bug（今天的 scope、空提问） | 我 | 我直接改 kit、跑全量测试、推 main；Air 上 git pull |
| 要你拍板的事 | 你 | 点 Telegram 卡片（没配 Telegram 时在 Mac 上跑 `evo approve`） |
| 看不懂的卡片 | 你问 | 现在问我；以后可问「秘书」（见第 4 节） |

```callout warn
不要两条路同时改同一件事。evo 的工人在做的东西，我不直接改；我在修的 evo bug，不再给工人提 issue。
```

## 3. 三台机器

| 机器 | 角色 | 跑什么 |
| :--- | :--- | :--- |
| Mac mini | 正式环境 | TB 土布、Multica 服务端（Docker）、magpie |
| MacBook Air | 试运行 | EV 项目、evo、Multica daemon（四个 runtime 在线） |
| GitHub | 账本和代码 | issue、main 分支、kit-tests |

## 4. 现在等你定

```ask
evo 里加一个专门跟你聊的「秘书」吗？
* 加 | Multica 里的 agent，Claude Code + sonnet，只读 evo explain，不能批卡
- 先不加 | 看不懂的卡片先问 Hark
```

```ask
以后我们讨论出要改的东西，默认怎么落地？
* 我提 issue，evo 去做 | evo 自己的紧急 bug 例外，我直接修
- 我直接改代码推上去 | 快，但绕过了 evo 的验收
```

## 5. 只是待办，不用决定

- Claude Pro：在 Air 上登录 `~/.claude-pro`，过文档 §5 前三项，再切决策岗。
- EV-DOC-007（老件号）：施工岗连续没交 JSON，已交决策岗处理。
- ST 的 7 个问题：你说过先放着。
