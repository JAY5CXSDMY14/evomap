# Release Agent

## 1. 检查是否该发
```bash
scripts/release-gate.sh <commit-sha>
```
脚本确认：该 commit 的 CI 全部完成且成功（cancelled 不算）；距上次发布间隔 ≥ {{MIN_RELEASE_INTERVAL}}（P0 除外）。不通过 → 停止，说明原因。

## 2. 生成 Release Notes
- 列出上次 tag 以来合并的 PR，按 Issue 归类：修复 / 新功能 / 体验 / 内部
- 每条写用户能看到的变化，附 Issue 号和来源致谢
- 列出已知问题（未修的 regressed、Not run 项中影响用户的部分）

## 3. 发布
- 打 tag，等待发布工作流完成，确认**所有产物都已上传**
- 产物不全 → 不对外宣布，开 Issue

## 4. 通知
- 在每个已修复的 Issue 下评论：`已在 <version> 发布，请确认是否解决`，保持 `evo:fixed-pending-confirm`
- 报告人确认 → 关闭；说没好 → 重开，加 `evo:regressed`
