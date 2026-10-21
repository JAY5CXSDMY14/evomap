# evo 自维护：让 evo 改 evo 自己（第十八轮）

读者有两类。一类是在 EV 项目里干活的 AI Agent（EV 就是 evo 自己的仓库）。另一类是要装、升级、回退 evo 的人。
目标：evo 可以像改别的项目一样改自己，但改坏了不会把正在跑的 evo 拖垮，关键代码只有老板能拍板。

## 1. 三条底线

1. **跑着的 evo 和仓库代码分开。** 常驻进程跑 `~/.evoloop/current` 指向的版本，不跑仓库里的 `kit/`。工人在仓库里改代码、合并、推送，都不会影响正在跑的 evo；要换版本只能走 `evo self-upgrade`。
2. **关键代码走老板闸门。** 碰到受保护路径的件，「做不做」和「看效果」都要老板点头，决策岗不能批。
3. **看门狗谁也不许改。** `kit/selfmaint/`（看门狗和回退逻辑）只有老板手改。工人改了，交卷直接打回。

## 2. 目录长什么样

```
~/.evoloop/
  releases/
    <版本>/          一个完整的 kit（bin、features、roles、install.sh…），版本名 = 仓库提交号
    PREVIOUS         上一版的版本名（回退用）
  current -> releases/<版本>      常驻进程跑这个
  guard/evo-guard.sh              看门狗（不在 releases 里，自升级碰不到）
  upgrade.json                    最近一次自升级：from、to、at、state（switched / ok / rolled_back）、why
  runner.json                     常驻进程心跳（pid、at、release、kit）
  UPGRADING                       正在切换（evo run 看到它就不开新的一轮）
  features.yml                    功能开关（见 docs/architecture.md）
  events.jsonl                    事件日志
```

装法：

```bash
bash kit/install.sh --apply          # 正式：拷成 releases/<提交号>、current 指过去、装看门狗（launchd com.evoloop.guard，每分钟一次）
bash kit/install.sh --apply --dev    # 开发：常驻进程直接跑仓库里的 kit，不建 releases、不装看门狗
```

## 3. 受保护路径

EV 项目的配置写 `"self_maintained": true` 后，下面这些路径受保护（`kit/bin/evo` 里的 `SELF_PROTECTED`）：

| 路径 | 为什么 |
|---|---|
| `kit/bin/evo` | 内核：状态机、闸门、锁、权限、自升级 |
| `kit/bin/evo_rt.py` | 功能包运行时 |
| `kit/bin/evo_bus.py` | 事件总线 |
| `kit/bin/evo_notify.py` | 推送内核（outbox、免打扰） |
| `kit/bin/evo_plugin.py` | 第三方插件宿主（环境变量白名单） |
| `kit/roles/**` | 岗位规则 |
| `kit/install.sh` | 安装 / 版本目录 |
| `kit/selfmaint/**` | 看门狗、回退（**禁止改**） |
| `kit/features/item-caps/**` | 每件上限（安全类功能包） |
| `kit/features/orca-gate-sync/**` | Orca 端闸门同步（安全类功能包） |

项目配置还能加 `protected_paths`（同样的写法，`目录/**` 或文件名）。

evo 怎么执行：

- **登记时**：件的范围碰到受保护路径（范围是 `.` 或空 = 整仓，也算碰到），任务书写上「老板闸门: 是」，件标 `owner_only`。决策岗想直接答复，evo 改成转老板。
- **交卷时**：改到 `kit/selfmaint/` → 打回。改到别的受保护路径但登记时没算上 → 补开一个「看效果（改到受保护路径，老板定）」闸门，合并前要老板点通过。
- **任务书开头**：EV 的每份任务书都带「evo 自维护规矩」一段，`kit/roles/builder.md`、`verifier.md`、`decider.md` 各有一节同样的规矩。

## 4. 自检：evo selfcheck

```bash
evo selfcheck          # 人看：✓ / ✗ 每一项
evo selfcheck --json   # 机器看：{schema_version, ok, release, kit, checks: [{name, ok, detail}]}
```

查四项。`compile`：内核和功能包的 .py 都能编译（只查语法，不写 .pyc）。`features`：没有功能包 `failed`，精简必开的都起来了。`features.yml`：读得懂。`events`：事件日志写得进。全过退出码 0，否则 1。

## 5. 自升级：evo self-upgrade

```bash
evo self-upgrade <提交或标签> [--source <evoloop 仓库目录>] [--wait-minutes 30]
```

一步一步：

1. 从仓库 `git archive <提交> kit` 取出来，放到 `releases/<提交号>/`（已经有就跳过）。仓库位置依次看：`--source`、当前版本的 `SOURCE` 文件、全局配置 `self_repo`。
2. **新版本先自检**，没过就不切换，原样退出。
3. 写 `UPGRADING`，等所有项目的锁都放了（当前一轮结束）。等超过 `--wait-minutes` 就放弃，不切换。
4. 把当前版本名记进 `releases/PREVIOUS`，原子地把 `current` 换成新版本（`os.replace` 换软链）。
5. **切换后再自检**一次。没过立刻切回上一版，`upgrade.json` 记 `rolled_back`，推送一条。
6. 过了：`upgrade.json` 记 `switched`，看门狗接着盯 10 分钟；发 `self.upgraded` 事件（App 收到会重读功能列表）。

自升级是老板的事：外部 Agent（环境里有 `EVO_AGENT`）跑会被拒（`refuse_agents`）。

## 6. 看门狗：kit/selfmaint/evo-guard.sh

独立的 bash 脚本，不属于任何功能包，装在 `~/.evoloop/guard/`，launchd 每 60 秒跑一次。只在「刚升级完的观察期」里动手：

- `upgrade.json` 的 `state` 是 `switched`，并且满足任一条：
  1. `current` 的 `evo selfcheck --json` 失败；
  2. 切换已超过 `GUARD_MINUTES`（默认 10）分钟，`runner.json` 的心跳还停在切换之前（新版本没转起来）。
- → 把 `current` 切回 `releases/PREVIOUS`，重启常驻进程，`upgrade.json` 记 `rolled_back` 和原因，推送一条（kind `self_upgrade_rollback`）。
- 观察期过了且心跳正常 → `upgrade.json` 记 `ok`，之后不再管。
- 找不到上一版 → 不动，推送「没法回退，请手动处理」。

测试用的环境变量：`EVO_DIR`（换目录）、`GUARD_NOW`（固定现在的秒数）、`GUARD_MINUTES`。测试在 `kit/tests/test_round18.py::test_selfcheck_and_guard_rollback`、`test_guard_rolls_back_without_heartbeat`、`test_self_upgrade_switches_release`。

## 7. 照做：在 EV 里改 evo

1. 读任务书开头的「evo 自维护规矩」。范围碰到第 3 节的路径，就是老板闸门件，老板点头之前不开工。
2. 新功能放 `kit/features/<id>/`，按 `docs/architecture.md` 第 7 节做。能做成功能包的，就不要改内核。
3. 不要动 `kit/selfmaint/`。需求真的要改它，`ask` 决策岗转老板，说明理由，老板手改。
4. 交卷前跑全套测试：`python -m pytest kit/tests -q -n auto`。
5. 合并后**不会**自动换到新版本。老板（或老板授权的本机命令）跑 `evo self-upgrade <提交>` 才会换；看门狗盯 10 分钟。
6. 新版本坏了：看门狗自动切回；或者手动 `ln -sfn releases/<上一版> ~/.evoloop/current.tmp && mv -fh ~/.evoloop/current.tmp ~/.evoloop/current`，再重启常驻（`launchctl kickstart -k gui/$(id -u)/com.evoloop.autopilot`）。

## 8. 可以改的默认

| 默认 | 改法 |
|---|---|
| 观察期 10 分钟 | 看门狗的环境变量 `GUARD_MINUTES`（改 `~/Library/LaunchAgents/com.evoloop.guard.plist`，老板手改） |
| 等一轮结束最多 30 分钟 | `evo self-upgrade … --wait-minutes N` |
| 受保护路径 | 加：EV 项目配置 `protected_paths`；减：改 `SELF_PROTECTED`（内核改动，走老板闸门） |
| Telegram / 邮件推送关掉不受「在用」保护 | 见 `docs/architecture.md` 第 4 节「在用」保护（第十八轮待定项，按推荐维持现状） |
