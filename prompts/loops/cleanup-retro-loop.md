# Loop ③：清理与复盘循环（即"夜审"）

> 用法：在 Claude Code 中输入 `/loop`，粘贴本节以下正文。建议间隔较长（例如每天一到两次）。

本项目的代码由 agent 自动修改、并自动合并社区 PR，所以要定期清理，防止项目变得难以维护直至报废。每轮：

1. 运行 `scripts/retro-collect.sh` 收集上次复盘以来的 commit、PR、返工线索。
2. 按 prompts/nightly-retro.md 找五类问题：返工、不该合、验证太薄、代码腐化与恶意代码、贡献者信誉。
3. **清理屎山**：重复实现、死代码、绕过项目既有抽象、无理由的新依赖 → 开清理 Issue，或在独立分支上小步清理（同样要过全部验收闸门）。
4. **恶意代码**：外发请求、读取凭证、混淆代码、偷偷修改 CI / 安装 / 更新逻辑 → 立即加 evo:needs-human 并通知维护者，不要自行处理。
5. **写经验**：哪些不该合并、哪些验证不缜密，按 docs/lessons-system.md 的格式写进 LESSONS.md，防止以后的 agent 犯同样的错误；Seen 满 3 个不同日期的升级进 code-standards.md。
6. **黑名单与分级**：反复提交低质量代码的作者，按 docs/contributors.md 第 4 节的条件**提议**拉黑；有用但总漏同样东西的，提议列入 Watched 并写明合并前必查项。都由维护者决定。
7. 用 `python3 scripts/lessons.py lint && python3 scripts/lessons.py verify` 校验后，开 PR 提交，附 5 行摘要给维护者。
