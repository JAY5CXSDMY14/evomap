# tubu 配置档（私有）

evomap 现以「崇明土布」的真实循环为基准来写，别的项目复用时复制本目录、改 `roles.yaml` 即可。

现场位置（Mac mini）：`~/Desktop/项目/土布/`
- `协作契约/`：契约、队列（任务书 / 交付 / 验收）、prompts、hooks、调度、坑册（工作区根，不在 git 内）
- `协作契约/.current-task`：当前任务指针
- `.hook-logs/`：hook 事件日志（证据层）
- `tubu-platform/`：产品仓库（GitHub private）

本目录文件：
- `roles.yaml`：岗位 → 当前由谁担任（可替换）
- 岗位与替换规则见 `docs/role-slots.md`
- 传话层规范见 `docs/relay-layer.md`
