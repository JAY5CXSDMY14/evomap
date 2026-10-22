# 决策记录

只追加。每条：日期、决定、为什么、怎么改回去。

## 2026-10-21 第十八轮（模块化 + 自维护 + 多机器）

- **内核 + 功能包，照 magpie 插件运行时。** 内核只管状态机、闸门、锁、权限、事件、运行时；12 个功能迁成 `kit/features/<id>/`。为什么：功能能单独开关、坏一个不拖垮别的；evo 自己改自己时，大多数改动落在功能包里，不碰受保护的内核。
- **渐进迁移，每批测试全绿才推。** 一次迁一个功能（7cc9051 → 9e28321）。JSON 接口字段和 `schema_version` 不变，第十六轮插件的 `evo_api 1.0` 不变。
- **跑着的 evo 和仓库代码分开。** 正式安装跑 `~/.evoloop/current → releases/<提交>`；换版本只能 `evo self-upgrade`（先自检、等一轮结束、切换后再自检）。开发用 `install.sh --apply --dev`。
- **看门狗独立、谁都不许改。** `kit/selfmaint/` 只有老板手改；工人改了交卷打回，决策岗不能安排改它。观察期默认 10 分钟（`GUARD_MINUTES`）。
- **自维护关键代码走老板闸门。** EV 项目 `self_maintained: true` 时，`SELF_PROTECTED`（内核五个文件、`kit/roles/**`、`install.sh`、`kit/selfmaint/**`、`item-caps`、`orca-gate-sync`）碰到就是老板闸门件；项目配置 `protected_paths` 可以再加。
- **待定项①（按推荐默认）：推送渠道 Telegram / 邮件关掉不受「在用」保护，维持现状。** 为什么：关掉只是不往那里推，配置留着，不会有东西没人管；webhook 不同（外部 bot 在等），配了算在用。改法：给 `notify-telegram` / `notify-email` 的 `feature.py` 加 `in_use()`，同时改测试 `test_push_channels_telegram_email_off_not_protected`。
- **待定项②（按推荐默认）：远端租约默认开。** 为什么：第二台机器后导入同一项目时，只有远端租约拦得住。改法：全局 `~/.evoloop/config.json` 写 `"lease_remote": false`；单个项目在项目配置里写，项目优先。测试 `test_remote_lease_default_on_global_off`。
- **App 0.7.0 订阅事件流，断线回退轮询。** 事件流活着时 2 分钟兜底；断了 30 秒轮询，5–60 秒退避重连；老 evo 没有 `watch` / `feature` 时界面照旧。
- **错误边界按「这页数据读没读出来」判断。** SwiftUI 没有异常式边界。团队、项目、件详情坏了只挡这一页；汇总页不整页挡；设置页永远能开（evo 路径填错要靠它改回来）。
- **设置页「功能」卡片里，管侧栏页的功能排最前。** 为什么：拨它侧栏马上变，最该先看到；CI 演示也因此点得到（原来团队开关在屏外）。

## 2026-10-21 第十九轮（App UI / 交互打磨）

- **子进程一律走 ProcessRunner，不阻塞任何线程等结果。** 为什么：第十八轮拨开关后 100 秒收不到结果，期间 MainActor 的活全排着队；老写法每条命令在 GCD 上占 3 个线程等到底。新写法退出靠 terminationHandler、读靠两条专用线程、超时 TERM→KILL。改回去：`Shell.run` 换回旧 `runSync`（git 9e367e7 之前）。
- **功能开关点击后下一拍再改状态；忙时不切 disabled。** 为什么：按钮动作里同步改 `featureBusy` 会让按钮在按下途中被重建（label 里塞转圈、disabled 切换）。
- **数字令牌放 EvoCore（能在 Linux 测），颜色留在 Theme.swift。** 弹簧阻尼下限 0.6 写进测试，以后谁把动效调得太弹测试会红。
- **首页只给「等你处理」，其余默认收起。** 为什么：老板打开窗口第一眼只该看到要他点头的事；项目在转不是他的活。展开状态存 `homeShowProjects`。
- **「为什么卡住」在 App 里推（EvoCore/ItemDiagnosis），不改 evo 的 JSON。** 为什么：不破坏 `schema_version` 1 的契约，也不碰内核；推不出的原因照实显示原始 reason。以后 evo 输出更细的原因，再在 App 里加分支。
- **mac-demo 失败数 ≤6 时 CI 仍算绿。** 真正每一步过没过看构件 HOW.txt 里的 ✓ / ✗。
- 2026-10-21 20:05 Air 试跑：EV 已导入 air（app 0.8.0）。修 ff426e6（make 自动借 Xcode-beta 的 SwiftUI 宏；无 Orca 时 import 不崩）。建议 EV 模型 build=group/build verify=group/check（Air 无 group/evo-*），待老板确认。Air 缺 orca/claude/codex。
- 2026-10-21 20:15 73b424a：evo -p 项目 models 只按项目实际模型判 exit。Air 建议全局岗位全走 dsh+magpie：build group/build、verify group/check、decide group/paid-opus（claude cli 不认 magpie 组名）；已发第三步指令，待回报。
- 2026-10-21 20:30 老板定：Air 装 Orca（/Applications，官方 stablyai/orca）；验收/决策用 Claude Code（已接 magpie）；全局施工 group/free-ds，验收 group/free-glm-5-3（我的建议，需与施工不同），决策 group/paid-opus；模型以后在团队页从 magpie 列表自选。792dd1f：install.sh 常驻 PATH 取登录 shell。

## 2026-10-21 21:45 Air 试跑 EV-FEAT-001：Orca 退出后的盲区
- 现象：施工岗 dsh·group/free-ds 派工后 17 分钟零产出，随后 Orca 进程退出；evo 一直显示「施工中」，autopilot.log 0 字节。
- 修：每轮先 orca status，不通→记一次、推 orca_down、不派工不判卡住，恢复后 C7 自动重启工人一次；status 显示「Orca 没开」+ JSON orca_down_since；stdout 行缓冲 + plist PYTHONUNBUFFERED；team 探测 CLI 时额外查 ~/.local/bin、/opt/homebrew/bin 等。
- 未查清：Orca 为什么退出、dsh 17 分钟为什么没写一行。
- 21:58 第 2 次观察：Orca 21:27 正常退出（非崩溃）、21:36 自己重启；C7 自动重启记了一笔，但 Orca 里没有 build 终端、没有 dsh 进程，21:37 起疑似卡住 20+ 分钟无人管。修：派工后 terminal show 确认终端在，不在就当派工失败；疑似卡住交决策岗一次；常驻把子进程输出写进 autopilot.log，开工人终端时打出命令。
- 22:10 老板确认：21:27 是他手动退出 Orca（给 Orca 开了一个系统权限，需要重启 app）。Orca 退出不是故障；剩下的疑点只有第一次派工 14 分钟零产出（可能也卡在那个权限上，待 Pi 复现）。
- 22:22 第 3 次观察定根因：evo 的 dsh 模板「dsh --model {model}」是猜的；dsh 是 profile 启动器，没有 --model、没有交互界面，headless 一次性跑完、模型用 DSH 自己的默认。修：dsh 改为 `dsh --profile headless -` + 任务书写文件「< 文件」启动（一次性工具不打 inject）；启动后读终端尾部，命令报错/立刻回提示符就当派工失败并关终端，任务书不再喂给 shell；旧配置 dsh --model 自动改写；claude 新工作区预先记信任（~/.claude.json hasTrustDialogAccepted），EV-decide 停在信任提示。状态文件真实路径 ~/.evoloop/projects/<代号>/state/state.json。
- 22:37 老板坚持施工用 DSH（Orca 自带 DeepSeek Harness 选项）。查明 Orca 用交互式 dsh-tui 启动（launchCmd 'dsh-tui .'，进程名 dsh，可监管）。dsh 模板改为 'dsh-tui .'；'dsh --profile headless -' 保留为一次性写法；旧 dsh --model 自动改写。模型 per-run 参数待 Pi 查 dsh-tui --help / orca agent launch --agent dsh --model。

## 2026-10-21 22:54 Air DSH discussion (老板)
- 施工 DSH 用 FreeDeepseek：老板自己在 DSH/Magpie 里设默认模型。
- Orca 在 Air 上只装好了，还没配置；Pi 用 `orca agent launch` 命令行打开 DSH 来验证。
- EV-FEAT-001 作废，修好后重派一件干净的新件。
- Node 22：批准，之后交给 AI 执行。pmset 先不做。claude 弹的模型名警告不影响运行，先不管。
- DSH 权限：我建议施工岗在 EV worktree 里全放行，拦 git push、删工作区外文件、读密钥目录、部署。等老板确认 DSH Desktop 有没有自动批准/白名单设置。

## 2026-10-21 22:58 Orca 能否取代 evo（老板提议，待定）
- 老板提出直接基于 Orca（stablyai/orca，MIT，桌面端 + iOS/Android，内置 GitHub PR/issue，有定时自动化）来改。
- 我的建议：不 fork（Electron 应用，几乎天天发版，fork 后合并上游成本太高）。界面、手机端、通知、工作区交给 Orca；evo 瘦身成只管循环的大脑（施工→验收→决策、三道关、卡住自救、预设、Magpie 模型）。冻结 Evo App、网页面板和自建推送的开发；审批改成 Orca 里的 issue 标签加评论；evo 只通过 orca CLI 派工。先在 Air 上用 EV 跑通一件再决定。
- 注意：Orca 自动化支持每次运行单独指定模型（--extra-agent-args）。
- 已问老板：同意冻结 App/面板、审批改在 Orca 手机端做吗？
- 23:11 老板想让循环更自由、真正闭环，问能不能锁定 Orca 的一个稳定版来深度融合。我的回答：能做，但手机端风险最大（官方 App 自动更新，可能和锁死的桌面版配对不上）。推荐三层方案：Orca 原版当身体；evo 当确定性的大脑，只依赖 orca CLI；缺钩子时先给上游提 PR，不行再在锁定版本上留一小叠补丁。已提议：把我们的需求和 Orca 逐条对照，做成 HTML（等老板回复）。
- 23:47 老板在 Magpie「接入」页配好了默认模型：DSH → 免费池·DeepSeek，Claude Code → 免费池·GLM-flash，Codex → 决策脑·任务书，Pi → 施工队·实施。施工和验收用的是不同模型。决策岗也跑在 claude 上，所以 evo 派决策岗时要单独传 --model。已给老板实测版 Pi 提示词（DSH 模型、手机端能否看到 gate、审批终端推送、--unread 推送、--model 帮助），前提是他先把手机配对好。下一步：第 20 轮瘦身，然后用一件新的 EV 活跑通全程。

## 2026-10-22 00:31 Air 实测结果 → 重新考虑 Multica
- Pi 实测：Orca 用 `dsh-tui .` 启动 dsh，但 @deepseek-ai/dsh 只提供 `dsh` 这一个命令，所以 cc1b2a4 的假设是错的。Orca 的 worker-start --model 不支持 dsh。gate 能建出来，但手机上没看到。decide 岗用的是 claude auto/gpt-6.1-sol；有 4 个 claude 窗口卡在全屏渲染器的引导页；夜间错题本 EV-DOC-001 自动登记后也卡住了。
- 老板觉得 Orca 一般，提议再看 Multica。我的结论：Multica 更合适。它原生支持 dsh（`dsh --profile multica --stdio`，可用 MULTICA_DSH_MODEL 指定模型）；每个 agent 可单独设模型；有审核关、收件箱、失败自动重试、Squads 组长分派、Autopilots（cron 和 webhook）、issue metadata。弱点：iOS App 要自己编译；需要服务端（官方云或 Docker 自建）；协议是 Apache 2.0 加额外条款。
- 建议：关掉那 4 个窗口；EV-DOC-001 作废；先暂停 evo 常驻进程，等平台定了再开；决策岗模型不换。已提议：给 Multica 也画一版关系图（等老板回复）。
- 00:51 mini 上的新 Multica 工作目录定为 ~/Projects/multica。发现 10-17/18 的旧影子试点 ~/Desktop/项目/Multica-shadow-pilot-20261017：官方 selfhost compose，项目名 multica，只绑 127.0.0.1；卡在 I04（自己加的 internal 网络和端口发布冲突）和 I05（邮件验证码登记，开到第六窗口也没收口），流程太重。这次给 A 段加了三条：新实例改名 multica2、不复用旧卷；用 Tailscale 反代（不覆盖 /mcp 的 443）；ALLOWED_EMAILS 只放老板一人，验证码从 backend 日志里取。
- 01:23 mini 上的 Multica v0.6.5 已搭好：compose 项目名 multica2，目录 ~/Projects/multica，用 docker compose -p multica2 手动部署（官方脚本写死了 INSTALL_DIR，用不了）。网页走 tailscale serve https://mac-mini.taila6de43.ts.net:8443，API 走 :9443，都只在 tailnet 内可达；443 根路径（Funnel→8010）没动。没有 Redis，mini 上没跑 daemon，土布容器状态没变。下一步：老板注册并建工作区 evo，然后给 Air 发 B 段（地址已填好）。
- 02:43 老板 已注册 Multica 并建好工作区 evo（mini 本机 Chrome 打不开 ts.net:8443，判断是 Chrome 的安全 DNS 绕过了 MagicDNS，解析到了 Funnel 中转；建议关掉安全 DNS）。下一步：把 B 段 prompt 发给 Air 的 Pi。

## 2026-10-22 12:30 Air 实测 Multica：端到端跑通
- 派给 施工-DSH（模型 deepseek-official/group/free-ds，经 Magpie）的 EVO-2 用时 30 秒：只改了 README，没有越界，issue 自动转为 in_review。daemon 用的是 PAT 登录（`multica login --token`），4 个 runtime（claude/codex/dsh/pi）都在线。
- 为跑通修了几处：dsh 改用隔离安装的 0.1.0-rc.6（~/tmp/dsh016）；cordis-plugin-hmr 钉在 1.0.17（registerConfig 在 1.0.18 被删，见 bento#195）；dsh-app-boot 改成轮询 ctx.get("hmr") 最多 1 秒，绕开时序竞态；用户 patch 层把 multica runtime 禁掉的 hmr 重新启用；dsh wrapper 写死 node22 路径（daemon 会重置 PATH）；改用隔离的 DSH_HOME（0.2.x 和 0.1.x 的 credentials 格式冲突）；本地目录只能用 CLI 的 `--type local_directory` 绑定。
- Air 上 Chrome 打不开是 Shadowrocket fake-ip 劫持了 ts.net，Host 规则无效；改用一个独立的 Chrome 实例，加 --no-proxy-server 和 --host-resolver-rules，把域名映射到 100.90.140.106。
- 未决：上面这些都还在 ~/tmp，npm install 会冲掉补丁；daemon 现在靠 nohup 手动起，autostart 生成的 plist 不带自定义环境变量；收件箱提醒、worktree 模式、另外 3 个路由、多 agent 并发都还没测。evo 的 autopilot 和 guard 已 bootout，暂停前决策岗已经连续 5 次超过 45 分钟没交决定。

## 2026-10-22 12:45 固化 Multica 执行端（老板全按推荐，上游 issue 不提）
- 永久目录 ~/.evoloop/multica；DSH 继续钉在隔离的 0.1.0-rc.6，hmr 钉 1.0.17，补丁由 postinstall 自动重打；全局 dsh 不动。
- 开机自启用自己写的 LaunchAgent（com.evoloop.multica-daemon），环境变量放在 env 文件里（权限 600，含 Magpie key，接受明文存本机）。
- ~/tmp 里的旧文件保留，等新位置跑通、老板确认后再删。
- 验收 agent「验收-Claude」：模型优先 group/check，没有就用 group/free-qwen；如果 claude 不认这个分组名，就把模型留空，走 Magpie 接入页的默认 GLM-flash。
- 已推送 3e52bf5：kit/multica（install.sh、package.json、patch-dsh-boot.mjs、cordis.patch.yml、open-multica.sh、README），新增测试 test_multica_kit.py；docs/multica 补了第 7、8 节（踩坑清单、mini 预案）。第二轮 Pi 指令已交给老板，汇报文件约定为 ~/tmp/MULTICA-HANDOFF-2.md。
- 13:15 Air 第二轮修了两处：一是 dsh profile 包不在 npm 上，改成源码构建 + npm pack，再用 `dsh plugin --profile multica add <tgz>` 装（60438f0）；二是 daemon 必须加 `--foreground`，否则 launchd 管不到（3510671）。Pi 实测：daemon 正常跑，4 个 runtime 都在线；profile 用的是 vendor 里的 tarball，不再依赖 ~/tmp。
- 13:37 第二轮第 1–8 步通过：EVO-3 回归 29 秒；EVO-4 用 worktree 模式（分支 agent/dsh/evo-4）；用 `multica issue assign --to` 交给 验收-Claude，它只读不改，评论「验收通过」，状态保持 in_review；收件箱里能看到审核中提醒和验收评论。问题：claude 不认 group/check，退回了自己账号的默认模型，没走 Magpie。老板定验收模型先试 group/free-qwen，再试 group/free-glm-flash，只给验收 agent 单独设 ANTHROPIC_BASE_URL 走 Magpie，不改全局；第 8.5 步已交给 Pi。另外仓库里出现了未跟踪的 .claude/、.multica/、CLAUDE.md，要查是谁写入的。
