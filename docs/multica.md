# Multica 自建记录与切换方案（2026-10-22）

> 状态：服务端已在 mini 上跑起来；Air 的执行端和 DSH 实测正在进行。Orca 路线暂停，evo 的代码暂时不动，等实测结果出来再改。

## 1. 为什么换成 Multica

| 需求 | Orca | Multica |
|---|---|---|
| 用 DSH 施工 | 用 `dsh-tui .` 启动，可 dsh 包里没有这个命令，起不来 | 原生支持：`dsh --profile multica --stdio`，模型用 `MULTICA_DSH_MODEL` 指定 |
| 每个岗位单独设模型 | `worker-start --model` 不支持 dsh | 每个 agent 可以单独设模型、思考强度和参数 |
| 审核关 / 收件箱 | gate 建出来了，但手机上看不到 | issue 自带 in_review 状态和 Inbox |
| 失败重试、超时、定时任务 | 要 evo 自己做 | 自带（重试、超时、Autopilots、Squads） |

## 2. 部署现状（mini）

- 版本 v0.6.5；compose 项目名 `multica2`；目录 `~/Projects/multica`（官方 selfhost compose 加 `.env`）。
- 用手动方式部署（官方安装脚本写死了 INSTALL_DIR，也没法改项目名），启动命令是 `docker compose -p multica2 up -d`。
- 端口只绑 127.0.0.1：前端 3000，后端 8080，postgres 不暴露到宿主机。
- 用 Tailscale serve 转发，只在 tailnet 内可达：
  - 网页 `https://mac-mini.taila6de43.ts.net:8443` → 127.0.0.1:3000
  - API `https://mac-mini.taila6de43.ts.net:9443` → 127.0.0.1:8080
  - 443 根路径（Funnel → 8010）保持原样，没有动。
- `.env` 的关键项：`DO_NOT_TRACK=1`，`ALLOWED_EMAILS` 只放老板一个人；`FRONTEND_ORIGIN`、`MULTICA_APP_URL`、`CORS_ALLOWED_ORIGINS` 都填 8443 的地址；`NEXT_PUBLIC_WS_URL` 填 9443（以后升级镜像如果实时更新失效，把这一行清空，会回落到同源的 /ws）。
- 没有 Redis，后端日志会提示 auth rate limiting disabled，单用户用没关系。
- 没配邮件，注册验证码从 backend 日志里取：`docker logs multica2-backend-1 --since 2m | grep -i code`。
- 2026-10-22 02:43 老板已注册，工作区叫 `evo`。
- mini 上不跑 daemon，以后接 TB 时再开。
- 10-17 的旧试点 `~/Desktop/项目/Multica-shadow-pilot-20261017` 保持原样：不删，也不启动。

## 3. 已踩的坑

1. **Chrome 打不开 ts.net:8443（ERR_CONNECTION_CLOSED），mini 本机也一样**：Chrome 的「安全 DNS」绕过了 MagicDNS，走公网 DNS 时，这个域名因为开了 Funnel 会解析到 Funnel 中转；中转不转发 8443，连接就被关掉。解决：Chrome 设置里关掉安全 DNS，然后在 `chrome://net-internals/#dns` 点 Clear host cache。Clash 用户还要在 fake-ip-filter 里加 `+.ts.net`，并把 `DOMAIN-SUFFIX,ts.net,DIRECT` 和 `IP-CIDR,100.64.0.0/10,DIRECT,no-resolve` 加到规则最前面。
2. 旧试点给 compose 加了 internal 网络，和端口发布冲突。这次不加。
3. 旧试点只绑了 127.0.0.1，别的机器连不上。这次不改成 0.0.0.0，改用 Tailscale serve 反代。

## 4. 角色分工（目标）

- **Multica = 身体**：issue、agent、执行端（Air 的 daemon）、审核状态、收件箱、重试和超时。
- **evo = 大脑（以后瘦身）**：施工完交给验收（模型不能和施工一样）、三道老板关（做不做 / 看效果 / 上线）、决策岗兜底、上限（2 次返工 / 12 次派工 / 6 小时）、预设和 Ponytail 规则注入。只通过 `multica` CLI 和 API 对接，不 fork Multica。
- **Air**：EV 的执行端（dsh / claude / codex / pi）。**mini**：服务端，以后也是 TB 的执行端。

## 5. 实测清单（B 段，Air）

1. 暂停 evo 的 launchd；关掉 4 个卡住的 Claude 终端；EV-FEAT-001 和 EV-DOC-001 只记录状态，不处理。
2. `brew install multica-ai/tap/multica`，然后运行 `multica setup self-host --server-url …:9443 --app-url …:8443`。
3. 装好 DSH 的 Multica 配置，运行 `multica daemon start`，确认能识别到 dsh、claude、codex、pi。
4. 建 probe 项目（指向 `~/tmp/multica-probe`），再建 agent「施工-DSH」。
5. 派一个只改 README 的小 issue，看这几件事：dsh 有没有启动、用的是什么模型、改出来的 diff、最后有没有到 in_review、收件箱有没有提醒。

## 6. 实测通过后 evo 要改的（暂不动代码）

- 新增 `multica` 派工后端，和 Orca 后端并列，用开关切换：派工 = `multica issue create --assignee <agent>`；进度 = `multica issue runs` 加 `run-messages`。
- 验收岗、决策岗都换成 Multica 里的 agent（每个 agent 单独绑模型，施工和验收用不同模型）。
- 老板关映射到 issue 状态和标签（`look` 对应看效果）；收件箱当推送的第一渠道，Telegram 留作兜底。
- 先冻结 Orca 后端、Evo App 和网页面板的新功能。
