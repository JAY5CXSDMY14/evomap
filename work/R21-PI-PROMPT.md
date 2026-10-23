你在 Air 上工作，仓库 ~/Projects/evomap（GitHub JAY5CXSDMY14/evomap，main 应 ≥ 817394c）。目标：把 Multica 执行端彻底脱离 ~/tmp，然后让 EV 项目恢复无人值守自动循环，放 2 件真活过夜。

红线（全程有效）：
• 不用 sudo；不碰 Mac mini；不手改 state.json；不删 ~/tmp 里任何东西
• 不装、不启用 com.evoloop.guard（看门狗）
• 同一步失败两次就停，写报告，不要硬绕
• 不打印任何 key / token

报告：追加写到 ~/tmp/MULTICA-HANDOFF-5.md，每步写「命令 → 关键输出 → 结论」。

第 0 步 · 只读摸底
1. cd ~/Projects/evomap && git fetch && git status && git log --oneline -1（落后就 git pull --ff-only）
2. ps -axo pid,etime,command | grep -E "multica daemon|evo .*run|evo .*tick" | grep -v grep
3. launchctl list | grep -E "evoloop"
4. 对正在跑的 multica daemon：lsof -p <PID> | grep -c "/tmp/"，并看它的父进程是不是 launchd（ps -o ppid= -p <PID>，ppid=1 才算）
5. evo -p EV status --json，记下 paused、tick_running、exec_up、未收尾的件
结论写清：daemon 是 nohup 还是 LaunchAgent；有没有还在读 ~/tmp 的东西。

第 1 步 · Multica 执行端固化（脱离 ~/tmp）
1. bash kit/multica/install.sh（只检查），全部 ✓ 再继续；有 ✗ 停下报告
2. 如果第 0 步发现 daemon 是 nohup 起的：kill 那个 PID（只杀 multica daemon，别的不动），确认进程没了
3. bash kit/multica/install.sh --apply --from-tmp
4. launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.evoloop.multica-daemon.plist（脚本已经加载了就跳过）
5. 验证：
   • launchctl print gui/$(id -u)/com.evoloop.multica-daemon | grep -E "state|pid"
   • multica daemon status --output json；multica runtime list 里 4 个 runtime 都 online
   • 新 daemon 的 lsof 里 /tmp/ 计数 = 0（除系统临时目录 /private/var/folders 以外）
   • 重启测试：launchctl kickstart -k gui/$(id -u)/com.evoloop.multica-daemon，30 秒内重新 online
6. evo -p EV tick 手动跑一轮，确认 exec_up = true、没有新推送「执行端掉线」

第 2 步 · 恢复 EV 自动循环（不开 guard）
1. 先确认要跑的 evo 是新代码：看 ~/Library/LaunchAgents/com.evoloop.autopilot.plist 里 ProgramArguments 指向的 evo 文件，grep -c superseded_gates 和 grep -c '"command"' 那个 evo 所在目录的 bin/evo，两者都 > 0 才算新
2. 新的 → launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.evoloop.autopilot.plist
   旧的或没有 plist → bash kit/install.sh --apply --dev（--dev 不装看门狗、直接跑仓库代码）
3. 装完马上确认 launchctl list | grep com.evoloop.guard 为空；如果出现了，launchctl bootout gui/$(id -u)/com.evoloop.guard 并在报告里写明
4. 如果 status 里 paused 不为空且原因是手动暂停：evo -p EV resume
5. 等 2 分钟，看 ~/.evoloop/logs/autopilot.log 里出现正常 tick，evo -p EV status --json 的 last_tick 在 1 分钟内

第 3 步 · 放 2 件真活过夜（老板已授权）
件 A（删探针残留，老板发出本指令即授权删除这些仓库文件）：
evo -p EV add --kind chore --title "清理第二十轮探针残留" --scope "删除 notes/r20-probe.md、notes/r20-rework.md、artifacts/EV-DOC-004/、artifacts/EV-DOC-006/；只删这些，不碰别的文件；README/文档里如有引用一并去掉"
件 B（真实小文档）：
evo -p EV add --kind doc --title "kit/multica/README 补验收结论" --scope "在 kit/multica/README.md 末尾加一节「Air 验收结论（2026-10-23）」：5 条验收标准各一句结论、修复提交 0e37654/6ab6a5d/082ac2e/817394c 各一句作用、已知限制（dsh 钉 0.1.0-rc.6、hmr 钉 1.0.17）。只改这个文件"
放完以后不要手动 tick，让 autopilot 自己跑。闸门出现时不要替老板点，留给他早上处理。

第 4 步 · 收尾报告
在 HANDOFF-5 末尾写：
• daemon：LaunchAgent 常驻、PID、/tmp 依赖 = 0、重启测试结果
• autopilot：在跑、用的哪份 evo、guard 未启用
• 件 A / 件 B 当前状态和 Multica issue 号
• 任何警告或没做完的步骤，以及原因
然后停止，不要再改任何东西。
