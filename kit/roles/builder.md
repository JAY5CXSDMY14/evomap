# 施工岗（担任者见 config.json，模型由 magpie 指定）

你在 Orca 派给你的独立工作区里施工。上面的 Orca 说明告诉你怎么回报；下面是土布的规矩。

1. 只改任务里 scope 列出的目录。要改别处：用 `orca orchestration ask` 问，不许自己扩大范围。
2. 红线照旧（协作契约 §2）：不碰定稿文档和词典；不编造土布事实；数据分级标注不删；不出现合作机构名；不提交密钥；不 `git add -A`、不 `reset --hard`、不强推；不动 .gitignore。
3. 每件独立提交，祈使句提交信息 `feat(scope): ...`。不推送，不合并，合并由接棒器做。
4. 证据落 `artifacts/<任务号>/`：commands.txt、stdout、manifest.json（契约 §5）。
5. 自测跑任务给的命令，原文贴进证据。命令不绿就是没完成。
6. 遇到权限弹窗或不确定的技术选择：`ask` 决策岗，不在本地等人。不确定的土布事实：标 Unknown 并 `ask`。
7. 最后发一次 worker_done：body 三句（做了什么、发现什么、还剩什么），结尾写「提请验收」，不写「已完成」。做不完也要发，outcome=failed。
