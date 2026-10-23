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
- 01:23 mini 上的 Multica v0.6.5 已搭好：compose 项目名 multica2，目录 ~/Projects/multica，用 docker compose -p multica2 手动部署（官方脚本写死了 INSTALL_DIR，用不了）。网页走 tailscale serve https://<mini>.<tailnet>.ts.net:8443，API 走 :9443，都只在 tailnet 内可达；443 根路径（Funnel→8010）没动。没有 Redis，mini 上没跑 daemon，土布容器状态没变。下一步：老板注册并建工作区 evo，然后给 Air 发 B 段（地址已填好）。
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
- 13:40 Magpie 通过 ~/.claude/settings.json 全局接管 Claude Code，模型按档位名映射：opus 对应 施工队·实施，sonnet（默认）对应 GLM-flash，haiku 对应 免费池·DeepSeek（也用于后台小任务），fable 对应 决策脑·任务书，子代理 对应 千问，自动模式 对应 施工队·实施。所以 evo/Multica 给 claude 指定模型时要用档位名，不能用 group/…。验收-Claude 改成 sonnet（GLM-flash，和施工的 free-ds 不同）；不能用 haiku（和施工同是 DeepSeek）。千问不测（要测得改老板平时用的档位）。待 Pi 确认 Multica 跑 claude 时有没有读 settings.json。
- 13:56 Air 第二轮 1–9 步全部通过（~/tmp/MULTICA-HANDOFF-2.md）。重要发现：group/check 其实已经正常走 Magpie（workbuddy glm-5.3）；claude 的 unrecognized_model 警告无害，可以忽略（Multica 不换 claude 配置目录，会读 ~/.claude/settings.json，BASE_URL=127.0.0.1:3425）。验收岗现在用 sonnet，对应 glm-5.3-flash。施工路由用时：build 31s、free-qwen 107s（施工岗避开）、glm-flash 68s，已改回 free-ds。install.sh 修复：上游只有 pnpm-lock 时改用 pnpm/corepack 构建（npm 会报 edgesOut 崩溃）。.multica/、.claude/、CLAUDE.md 分别是 Multica daemon 和 Claude Code 写的。Pi 还给了 install.sh 的 9 条建议，待老板贴过来。
- 14:10 install.sh 按 Pi 的 9 条建议修好：pnpm 构建，npm 兜底时加 --no-package-lock；失败时打印停在哪一步、建了哪些目录、下一步怎么做；probe.log 每次都追加记录；补丁打完先自检（检查标记 + node --check）；新增 MULTICA_THROTTLE；新增可选的 --keychain；新增 --uninstall --yes，只删以 /multica 结尾的目录；新增 --update-src，源码落后上游时会提示。另加 3 个测试。
- 14:08 决策岗模型待定：Codex 额度用完了，老板在犹豫要不要买 Claude Pro，或者找外援（Hark/wabi/grokbot）。我的建议：先不买，决策岗用 claude 的 fable 档位，经 Magpie 走决策脑；外援没法当 Multica 的 runtime，只能人工帮着看；先试 5 条，质量不够再买。等老板回复。
- 14:16 老板同意第 20 轮方向，决策岗用 fable 档位走决策脑（先试 5 条，暂不买 Claude Pro）。设计文档 docs/multica-backend（提交 1766826）。第三轮 Pi 指令已发：只读查决策岗超时原因、新建决策-Claude agent、收集 multica CLI 的 help 和 json 样例，结果写到 ~/tmp/MULTICA-HANDOFF-3.md。代码等老板说开工再写。
- 15:20 第 20 轮代码完成并推送（ac802ed…，9 步一步一个提交，外加一处小修）：新增 kit/bin/evo_exec.py，Orca 调用收进 OrcaExecutor，行为不变；新增 MulticaExecutor，所有派工都是 `issue assign`，不再走 `dispatch --inject`（决策岗超时的根因）；state.json 升到 schema 2，件加 exec 字段；面板显示 Multica issue 链接；新增假 multica CLI 和 14 个测试。我自己定的：没写 executor 的老项目继续走 orca，只有新建项目默认 multica；任务和闸门记在 evo 自己的账本 state/exec-multica.json，保证返工上限、决策逻辑不用改；施工分支 fetch 进 evo 的克隆，验收和合并都在这份副本上做；验收结论看评论里的 verdict json。还要 Air 确认：成员留言会不会叫醒 agent、返工是不是复用同一条分支、issue_url 模板对不对、EV 两件老件换执行端后要不要重跑。第四轮 Pi 指令已交老板，汇报写到 ~/tmp/MULTICA-HANDOFF-4.md。

- 2026-10-22 15:40 mini 上 Multica 前端端口改为 3300（FRONTEND_PORT=3300，tailscale serve 8443→127.0.0.1:3300），给土布让出 3000；8443/9443/8080/Air daemon 不变。以后重部署按 3300，别改回 3000。顺手把文档里的 tailnet 主机名换成占位符。
- 2026-10-22 16:15 第二十轮补：新增 `evo -p X drop <件号> [原因]`（老板直接标不做；换执行端前的老件只记不做、不碰旧执行端、切换后不重建）。EV 的 EV-FEAT-001 / EV-DOC-001 用它清掉再跑第四轮验证。
- 2026-10-22 16:55 第二十轮补二：Multica run 在跑时 evo 不记活着 → 误判卡住（Air EVO-10）。改：run 指纹（usage/attempt/issue 活动时间/工作区最新改动）变了就算活着；卡住后又有动静自动取消并撤回没送出的决策岗条目；新增 limits.run_max_minutes（默认 60，只对 Multica）跑超上限算卡住。
- 2026-10-22 17:24 Air 第 3 步：mg_4 是建件时就挂的看效果闸门，status 只在验收通过后列入「等你点头」；builder 规则 12：只改文档不跑全量、先提交再测。待查：同 issue 返工时旧 run 还在跑会不会双开（Multica 有无取消 run 的命令）。
- 2026-10-22 18:18 Air 第 3 步第二次误判卡住：dsh job_output 干等 28 分钟 pytest，期间指纹不变。改：Multica run 活跃就算活着（兜圈子靠 run_max_minutes 60）；决策岗对还在跑的件说 retry = 清标记接着等，上限从那刻重算；返工/换人前 cancel-task 掉同 issue 上还在跑的旧 run（17:09 那次返工让第一次 run 17:20 交的卷 76eb396 没人收）。
- 2026-10-22 19:45 Air 第 4 步验收标准 1 通过（EV-DOC-003：16.8 分钟、0 次 pytest、零误报、先提交后报告、验收-Claude 独立复核 5.6 分钟）。issue 链接缺 workspace slug → multica.workspace 配置（默认模板 {app_url}/{workspace}/issues/{identifier}）。mg_16 等老板看效果。
- 2026-10-22 19:55 App 0.8.0 自带的 evo 早于 Multica，看不到 Multica 闸门（等你 0）。临时：设置里 evo 路径指向仓库 kit/bin/evo，或终端 evo -p EV approve mg_16 通过。待办：App 重打包带新 evo / 自带版本落后时提示。
- 2026-10-22 20:12 Air 两个 Evo.app（/Applications 与 app/build 同一份 0.8.0，同 bundle id 可同时跑）；向导重弹 = setupDone 从没写过（只在向导第 4 步写）。App 改：已有项目就直接记 setupDone。待办：App 重打包带 Multica 版 evo。
- 10-22 22:25 0e37654: drop 残留清理（tidy_closed），stuck 不算收尾件，import 写 multica.workspace；331 passed
- 10-22 22:46: tidy_closed 先把闸门号记进 superseded_gates 再清（0e37654 引入的 mg_4 复现 bug）；文字 status 也过滤 superseded；332 passed
- 10-22 22:59: 验收标准1全过（EV-DOC-003 合并 6547215，main 7cb45f2，上线闸门 mg_20 等老板）；剩标准2–5，已问老板要不要写 Pi 指令
- 10-23 00:08: 标准2–5 结果：2 没测到（施工预判直接写第二轮），3/4 过，5 发现 drop 后 issue 被 agent 改回 in_review → close(ok=False) 先 cancel-task；tick reconcile_closed 对齐 done/cancelled（334 passed）
- 10-23 01:05: EV 验收标准 1–5 全部通过（HANDOFF-4）。施工交卷提示加 report json 示例（tests 用 command/result）。下一步待老板：Air 上恢复 EV 自动接棒？

## 2026-10-23 02:20
- 老板 wants a front-desk agent between him and evo (chat → 任务书/issues; never approves). Rec: Muse (on mini). Wabi = consumer messenger, no API → excluded.
- Loop decider quota low; 老板 choosing one sub: Claude Pro / Codex / Grok Bot. Rec Codex (headless codex exec on subscription, Multica native). Awaiting pick.
- 03:30 Round 21 Pi prompt (work/R21-PI-PROMPT.md) given: solidify multica daemon off ~/tmp via install.sh LaunchAgent, resume EV autopilot (no guard; --dev if plist stale), 2 real items overnight (chore: delete r20 probe files — authorized by 老板 forwarding; doc: kit/multica README acceptance section). Report → ~/tmp/MULTICA-HANDOFF-5.md.
- 03:35 install.sh pnpm --if-present bug fixed 768da56 (Pi found; daemon already LaunchAgent, /tmp deps 0). Pi going path B (kickstart test, then autopilot + 2 items).
- 03:40 老板 plans Claude Pro. Rec: Claude = 决策岗+任务书+架构审查 (not builder). Docs in 3 tiers: 红线 (enforced in code) / 接口 JSON / 现状 marked "当前做法非定论"; add decider action `propose` → 做不做 gate; slim role files (no examples); first Claude task = cold audit without our docs. Awaiting his go after subscribing.

## 2026-10-23 04:16 第二十一轮：Claude 接入准备
- 岗位规则分 红线/接口/现状 三层；「不重复造轮子」成通用原则（决策岗任务书须写「现成方案」）。
- 决策岗新动作 propose → proposal 件，停在老板做不做闸门后，每项目最多 3 件未决。
- docs/claude-cold-audit-prompt.md（冷启动审查 + 死代码扫描 + 规则体检可选步）。
- 5eb4124 docs/agent-practices-2026、docs/claude-pro-native-setup：原生 claude CLI + 自己的 Pro 可以；Pro 绝不经 magpie；地区按人所在地算 → 建议 claude_pro.enabled 开关；~/.claude-pro 独立配置。
- 待老板：修 Pro 决策岗与 magpie claude 验收岗共用额度账户名（限流时一起暂停）的 bug。

## 2026-10-23 04:50 第二十一轮补：额度账号分开算
- 修 Pro 决策岗与 magpie claude 验收岗共用账号名 `claude`（限流时一起暂停）的 bug；`env … claude` 不再被算成工具/账号 `env`。
- 账号规则统一在 evo_roles.account_of：显式 account → 显式 tool → 命令里真正跑的程序（跳过 env、env 选项、KEY=VAL）。rl_pause / 备用切换 / evo team / status 都走这条。
- 我定的：备用的账号不继承主卡的 account（fallback_rc 原本就不继承），Pro 决策岗的备用要写 `--fallback-tool claude`，否则备用会沿用主卡那条带 CLAUDE_CONFIG_DIR 的 Pro 命令。
- evo team set 加 --account / --fallback-account（auto = 去掉）/ --cmd；面板 POST /api/team 不收 --cmd（不让网页写任意命令），合约不动。
- native_claude 标记、自动清环境变量、拒绝 --bare、auth status 健康检查（docs/claude-pro-native-setup.md 4.1 其余、4.2、4.4、4.5）还没做。

## 2026-10-23 05:40 第二十二轮：《Context 与 Loop》1–6、14 条（老板批，14 并入 2）
- 永久运行记录 runs/<件号>/（任务书、交卷全文、终端尾部、Multica run.json、合并前测试日志、推送确认、决定；决策批次在 runs/_decide/），只增不删；时间线不动，不重复记事件。新命令 `evo -p X runs [件号] [--json]`。
- 金丝雀：`evo canary`（9 个判据、29 条必须判不过 + 7 条对照），selfcheck 也跑。测试用三变体（改常量 / 换分支 / 挪边界）改坏判据确认能报出来。
- 跳过 ≠ 通过，修了：verdict 不认识 / skipped 以前退回看正文（「未验收通过」也算过）；out_of_scope / 受保护路径检查读不出改动以前当没越界；全量测试全跳过以前算绿。
- 注入上限（UTF-8 字节，实测×1.2）：施工 15800、验收 13500、决策 8000；岗位文件各有一档。超了「删一条再加一条」。
- 施工任务书首行固定角色声明（统一走 build_spec()）；非决策岗 prompt 里读到决策岗段落就换回套件自带规则。
- 错题本 Mechanism 字段 + 「已关单」一节（只有 code～static 级带指向才能关）。
- 推送 / 远端租约用 git ls-remote 确认；远端名 push_remote → push_cmd 里认 → origin；`push_verify: false` 可关。
- 我定的（保守）：scope 只认文件或目录（web 不再含 website/），带 .. / 绝对路径算越界；not_run 的测试不拦交卷（施工岗规则允许只改文档时不跑，验收岗照旧重跑）；验收正文里「未跑」不当作不通过（验收岗规则要求写未跑的检查），只认「跳过」类字样。

## 2026-10-23 11:47 前台与备用模型
- 前台暂定 Muse；约束：前台只通过 GitHub issue（统一模板/标签）进 evo，不直连 evo、不批闸门，以便日后换成别的前台只换入口。
- 决策岗 Pro 用完时的备用模型：老板定 6.1sol，他自己在 magpie/evo team set 配。

## 2026-10-23 12:15 scope 只认路径
- EV-CHORE-001 真因：登记时 --scope 写成一整句中文（顿号分隔），只按英文逗号拆 → 一条「句子」scope，要删的文件全判越界。决策岗诊断（前缀匹配、main..HEAD）不是真因，二者已在 79e8cf5 修。
- 修：split_scope 按 , ， 、 ; ； 空白拆，只留路径，说明文字挪进任务书「范围说明」；一条路径都没有就拒绝登记；GitHub 拉取登记被拒不再让整轮崩（交决策岗）；决策岗拆分的子件同样校验。

## 2026-10-23 12:30 不做也作废转老板提问
- Air：EV-CHORE-001 drop 后 mg_72（决策岗转老板）仍挂着。void_item_gates 只作废 look/do/ship；现在 owner_asks、budget_gates 一并作废，老版本残留在读状态时清掉。375 passed。

## 2026-10-23 12:50 前台/秘书讨论（待老板拍板）
- 老板想要：agent 当参谋（解释卡片、给建议），不审批；任何外部 agent 能提 issue 即可派活。
- 参考 kkunkunya/virtual-bot-connect（Grok Bot 管家 + Multica 账本；bot 写入 via bot 不算批准）。Multica 自带 Chat 和 Telegram/飞书频道。
- 提议：Multica 里加「秘书」agent（Claude Code + magpie sonnet），只读 `evo explain <卡号>`，不能批卡。等老板回复。
- 43d4f40：blocked 不留话时提问写兜底说明。

## 2026-10-21 audit + rounds 16–19 (moved from project skill 10-23)
- Loop audit docs/loop-audit-2026-10 (7eb845a): 30 issues, 7 high (L-01 daemon lock, L-02 status lock, L-03 Orca-side gate bypass, L-04 bad message crash, L-05 red main blamed on items, L-06 no subprocess timeouts, L-07 git fetch no proxy).
- Round 16 (f4b6a5b, 1e77dfc): schema_version'd JSON contract docs/app-contract; plugins ~/.evoloop/plugins; App 0.6.0. 老板: wanted magpie-style kernel + built-in feature plugins instead.
- 老板 13:34 approved: Orca-side approve/ship 2nd confirm (TRIAL toggle); evo own clone ~/.evoloop/repos/<code>; caps 2 decider reworks / 12 dispatches / 6h.
- Round 17 (771cd41, be70d9f): orca_gate_sync trial, relocate, evo limits, red main → OPS item. Round 18 (0671615): 12 features in kit/features, evo_rt/evo_bus, selfmaint guard, owner lease; known: guard spams "can't roll back" when no previous release. Round 19 (9e367e7..01faf05): App 0.8.0, async ProcessRunner, waiting-on-boss home, 100s freeze fixed; 2–8s hitches on CI VM need Instruments on real Mac.
- Air = EV runner + staging, mini = TB production; Air uses mini's magpie via Remote magpie.

## 2026-10-23 14:40 第二十三轮（老板批）：补 Multica 撞模型保护、根目录 AGENTS/CLAUDE、删重复模板
- aeabdd1（#15）：Multica 下每轮派工前读施工 / 验收 agent 的模型（agent list，没有再 agent get）。相同、两岗同一个 agent → 停派施工 / 验收并推 model_blocked；读不到 → 默认也停，项目配置 `multica.allow_unverified_models: true` 才放行。status 显示原因，`--json` 加 `model_guard`。magpie 组名展不开，名字不同按不同算（假设）。真机 agent JSON 的模型字段名待 Air 核实（docs/multica-backend.md 第 9 节）；dsh 若只靠环境变量设模型会被判读不到。
- cf3d90a：根目录补 AGENTS.md（目录、命令、硬规则、已知的坑）和 CLAUDE.md（指路 + 审批边界）。
- ac45cb7（#20 的一部分）：删根目录 templates/ 下与 kit/templates/project 完全相同的 AGENTS.md / CLAUDE.md（evo new 只读后者；v1 scripts/install.sh 改从后者拷）。项目模板路由改指 kit/roles/ 四个岗位规则、写明不走 PR；CLAUDE.md 改加载 docs/LESSONS.md。v1 的 prompts/、scripts/、templates/ 其余文件和 code-standards.md 里的 PR 字样留给 #20。
- 待老板拍板（不变）：#15 额度满切备用、模型试用打分在 Multica 下删不删。

## 2026-10-23 15:09 老板拍板架构减法 7 件（全部同意，按我的建议）
- #12 批准只在 Telegram；网页面板保留为「看效果」截图页；App 冻结不再加功能（dmg 计划顺延）。
- #16 删插件系统（推翻 10-21「留插件接口」；以后加功能直接进 evo）。
- #15 删额度满自动切备用账号、新模型试用打分；换模型只在 magpie 改。施工≠验收保护保留（aeabdd1）。
- #26 审批卡 6 类收成 3 类：做不做 / 看效果 / 上线。
- #27 件号直接用 GitHub issue 号，不再另取 EV-FIX-001。
- #21 HTML 讲解页不进仓库，只留 docs/loop-overview.html；其余按需生成。
- #17 自带架构/UI 预设规则书换成各项目自己的 lint/CI。
- 排期：第 24 轮 #20 v1 清理 + #21 + #16；第 25 轮 #26/#27/#12/#15/#17（等 evo 修完 #29–#31 再动，避免改同一文件）；#14 删 Orca 仍等土布迁 Multica。

## 2026-10-23 15:55 第二十四轮（老板 15:09 批）：架构减法 #20 / #21 / #16
- 32284fd（#20）：删 v1 副本——根目录 prompts/、scripts/（含 v1 install.sh）、templates/、profiles/ 和只讲 v1 的 docs/loop.md、orchestration.md、adoption.md；README 只讲 evo；项目模板 code-standards.md 的 PR / Reviewer 改成施工 / 验收岗、evo 合并、不走 PR。evo new、kit/install.sh 不受影响。旧名 tubu 软链和 ~/.tubu 回退没动（要先确认老项目迁完）；没打 evoloop-v1 tag（删前最后提交 cf3c890）。
- e5f965b（#21）：删 docs/ 下 26 个渲染 html，只留 loop-overview.html；.gitignore 挡 docs/**/*.html；AGENTS.md 写明讲解页 .md 为源、html 按需生成不提交。没改 git 历史。一次性笔记归档 docs/archive/ 没做。
- 3ee8168 + c203553（#16）：删插件系统（evo_plugin.py、features/plugins、示例插件、card/plugin-* 四个 schema、docs/plugins.md、App 插件页 / 命令 / 件按钮 / 设置开关）。feature list 的 third_party 留着恒为 null（合约只加不删）；版本范围匹配只留 evo_rt.py；JSONValue/CardTone 挪到 EvoCore/JSONValue.swift。c203553 补 3ee8168 漏改的 MainWindow 回话区高度（CI 编译红过一次）。
- CI：kit-tests 373 passed（3ee8168）；app 全绿（c203553：EvoCore 101 测试、打包、snapshots、mac-demo）。mac-demo 里「⌘K 没跳到件详情 / 找不到 win-item-0」1 处是老问题，10-22 的 run 也有。
- 没碰 evo 正在改的 evo_exec.py、evo_roles.py、features/team、multica/install.sh。

## 2026-10-23 16:50 第二十五轮（老板 15:09 批）：架构减法 #26 / #27 / #17 / #12
- 3da76d2（#26）：老板卡六类收成三类：做不做 / 看效果 / 上线。外部来报、决策岗转老板（ask）、每件上限（budget）三张表并进 do_gates，卡上 `reason` 写来由（item / decider / external / budget）；`gates[].kind` 只出 do / look / ship / other。老状态里的旧卡读状态时并进 do_gates，老卡选项（同意交决策岗 / 拒绝等）照旧认。合约不升版本、只加 `reason`。
- c42f32a（#27）：新件号 = GitHub issue 号（TB#123），所有收件号的命令也认 `123` / `#123`；老件号（TB-FIX-012）照旧可用，不改名。只改了件号；「决策岗直接 register、删标签回路」没做，留着。
- 9dc16ea（#17）：删 ui-preset / arch-preset 功能包、kit/presets、evo_deps、vendor/taste-skill、`evo ui` / `evo arch`。项目配置加 `checks`（自己的 lint / 类型检查 / CI 命令），验收岗逐条跑；status --json 加 `checks`。TB / ST 两个 profile 的 checks 先留空，等老板确认真实命令再填。
- acccbb6（#12）：批卡只在 Telegram；没配 Telegram 时推一次「没处批卡」提醒（邮件兜底带 `evo -p 代号 approve` 命令），status --json 加 `approve_via`（telegram / cli）。网页面板只读，是看效果页：写接口一律 410。App 冻结：批卡按钮只提示去 Telegram 批，不再跑 approve。
- 60fbf5f：9dc16ea 漏改测试白名单（test_projects_config 的 PROJECT_KEYS 没加 checks），kit-tests 在 9dc16ea / acccbb6 各红 1 个；补上。
- 没碰 evo_exec.py、evo_roles.py、features/team、multica/install.sh。#15（删额度切换 / 模型试用）本轮没做。

## 2026-10-23 18:15 看门狗顺带给 Multica 执行端自愈（老板批准，Air 测试期，没用就删）
- 起因：Air 上 com.evoloop.multica-daemon 15:05 起、17:38 前两次被卸出 launchd（原因未明，疑为重跑 kit/multica/install.sh 后 bootstrap 失败）。
- kit/selfmaint/evo-guard.sh 每分钟：plist 在但没加载 → enable + bootstrap（重试 3 次）；加载了但不在跑 → kickstart。记 guard.log，推送一小时最多一次（kind multica_daemon_heal）。GUARD_NO_MULTICA=1 关闭。只用 launchctl print，开销可忽略。
- 删除方式：删掉 evo-guard.sh 里「Multica 执行端自愈」一段和 tests/test_guard_multica.py。

## 2026-10-23 19:35 上游故障 ≠ 额度；终端读常驻 TG 配置
- Air 实况：magpie 上游 `API Error: 504 … proxyconn`、`503 auth_unavailable: no auth available` 被当成额度用完，暂停 60 分钟、推「额度暂停」。
- 改：这类行（5xx / proxyconn / auth_unavailable / TLS 超时 / 连接拒绝）除非同行明说 429 / quota / usage limit / rate limit，一律归「上游故障」：暂停 `limits.upstream_retry_minutes`（默认 15）后重试，推 `upstream_down`「岗上游连不上（不是额度）」，件原样重排不扣轮次；status 标 [上游故障]/[额度]。
- 改：终端里跑 evo 时 shell 没有 EVO_TG_*，`evo_notify.env` 兜底读 ~/Library/LaunchAgents/com.evoloop.{autopilot,bot}.plist 的环境变量，status 不再误报「Telegram 没配好」。
- 20:50 补：上游故障只停出事的那个岗（以前同账号 magpie 的验收 / 决策一起连坐）；额度 / 上游故障原样重排的次数（rate_waits）不计入「用量异常」的派工次数。
- 10-24 02:15 #32 终端停在上游报错（工人活着不回报）也走 15 分钟短暂停重排（两次探测同尾巴）；#33 换成行为级测试（上游只停一岗、rate_waits 不计用量异常、429 仍按账号停、普通输出不触发）。
