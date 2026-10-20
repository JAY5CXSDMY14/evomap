# Ponytail 固定副本（施工岗 / 验收岗用）

| 项 | 内容 |
|---|---|
| 来源 | https://github.com/DietrichGebert/ponytail |
| 固定提交 | `09c434ab73ca43761c5d8b0c5d341926c2fba710`（2026-10-21 取，`git ls-remote … HEAD`） |
| 许可 | MIT，原文见同目录 `LICENSE`（Copyright (c) 2026 DietrichGebert） |
| 拷了什么 | `ponytail/SKILL.md`（主规则，施工岗用 full 档）、`ponytail-review/SKILL.md`（审查清单，验收岗用），一字未改 |
| 没拷什么 | 插件、hook、安装脚本、其它 skill（audit 每周由决策岗提醒去官方仓库同一提交下的 `skills/ponytail-audit/SKILL.md` 跑） |

## 怎么用
- `roles/builder.md`、`roles/verifier.md` 各有一节说明怎么用；工人自己装了 ponytail skill 就用自己的，没装就读这里的副本。
- 只取官方仓库、固定到一个提交。作者升级时，先读 diff，再改上面的提交号并整份替换两份 SKILL.md；不要局部改写。
- 规则冲突时：任务书的验收标准 > ponytail 的「最少代码」；协作契约红线 > 一切。
