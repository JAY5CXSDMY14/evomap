# kit/multica：本机 Multica 执行端（daemon + DSH）

在一台机器上装好「能用 DSH 干活的 multica daemon」。Air 先用，mini 接 TB 时直接跑同一份脚本。
来源：2026-10-22 Air 实测踩过的 10 个坑（docs/multica.md 第 7 节），这里全部固化。

## 一次性前提（每台机器做一次）
1. `brew install multica-ai/tap/multica`
2. 登录：在网页 Settings → Tokens 建 PAT，`multica login --token mul_…`（浏览器回调方式在 tailnet 自建上会超时，不用）。
   服务端地址：`multica config set server_url https://<mini>.<tailnet>.ts.net:9443`，app 地址 `…:8443`（按 `multica --help` 实际命令）。
3. 有 Node 22+（`brew install node@22`）。
4. Magpie 在 127.0.0.1:3425 能用，知道它的 gateway key。

## 安装
```bash
bash kit/multica/install.sh                          # 只检查
MAGPIE_GATEWAY_KEY=… bash kit/multica/install.sh --apply   # 第一次；之后不用再带 key（存在 env 文件里）
bash kit/multica/install.sh --apply --from-tmp       # Air：顺便把旧 ~/tmp/dsh-home-multica 里 profiles/ 以外的文件拷过来；同名不覆盖，旧目录不删
MULTICA_DSH_RUNTIME_PATH=~/某处/dsh-multica-runtime bash kit/multica/install.sh --apply   # 已有构建好的 runtime 源码就用它，省得重新 clone
multica daemon stop   # 停掉手动起的
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.evoloop.multica-daemon.plist
multica runtime list  # 应看到 claude / codex / dsh / pi 都 online
```

## 装了什么（都在 ~/.evoloop/multica/）
| 路径 | 作用 |
|---|---|
| `dsh/` | 隔离的 `@deepseek-ai/dsh@0.1.0-rc.6`；`overrides` 把 `cordis-plugin-hmr` 钉在 1.0.17；postinstall 自动给 `dsh-app-boot` 打 hmr 轮询补丁 |
| `src/dsh-multica-runtime/`、`vendor/*.tgz` | Multica 的 dsh profile 包还没上 npm（multica#6936）：脚本 clone、build、npm pack，再 `dsh plugin --profile multica add` 装进 dsh-home，最后跑 `--probe` 验证 |
| `bin/node` | 指向 Node 22+ 的软链（避开带空格的路径） |
| `bin/dsh` | wrapper：用 Node 22 绝对路径跑隔离 dsh（daemon 会重置 PATH） |
| `dsh-home/profiles/multica/cordis.patch.yml` | 用户补丁层：重新打开 hmr；模型走 Magpie（分组列表在 kit 里改） |
| `env` | daemon 的环境变量（600 权限，含 Magpie key，不进 git） |
| `start-daemon.sh` | 读 env 后 `multica daemon start` |
| `logs/` | npm 安装日志、daemon 输出 |
| `~/Library/LaunchAgents/com.evoloop.multica-daemon.plist` | 开机自启，异常退出 30 秒后重启 |

不碰：全局 dsh（DSH 桌面端在用）、`~/.dsh`、evo 状态、Multica 服务端；不用 sudo。

## 可选：代理软件劫持 *.ts.net
Shadowrocket/Clash 的 fake-ip 会把 ts.net 解析成 198.18.x，Chrome 报 ERR_CONNECTION_CLOSED（curl 正常）。
`MULTICA_HOST=<mini>.<tailnet>.ts.net bash kit/multica/open-multica.sh` 开一个绕过代理的独立 Chrome。

## 已知限制
- dsh 0.2.x 和 `@multica-ai/dsh-runtime` 不兼容，所以钉在 0.1.0-rc.6；上游修好后改 package.json 版本再 `--apply`。
- 补丁脚本找不到原句会报错退出（说明 dsh 版本变了），不会悄悄装一个坏的。
- 本地目录项目只能用 CLI 建：`multica project create … --type local_directory`。
