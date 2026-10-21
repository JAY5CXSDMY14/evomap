# evo 多机器：一个项目只归一台机器跑（第十八轮）

写给要在第二台 Mac 上装 evo、或者把项目从一台机器搬到另一台的 AI Agent。
场景：老板有 MacBook Air 和 Mac mini，两台都装了 evo，都能看到同一个 GitHub 仓库。两台同时跑同一个项目，会重复派工、重复合并、抢着推送。第十八轮加了「归属租约」防止这件事。

## 1. 规则

- 每个项目只归一台机器。只有这台机器能改它的状态（tick、once、approve、add……）。
- 别的机器照样能**看**：`status`、`status --json`、`projects` 只读，不拦。
- 归属记两处：
  1. **本机记录**：项目配置 `~/.evoloop/projects/<代号>/config.json` 的 `owner_host`。`evo new` / `evo import` 时写成本机。
  2. **远端租约**（默认开）：项目远端仓库上的一个 ref `refs/evo/owner/<机器名>`，指向主线。谁的名字在上面，项目就归谁。用 `git ls-remote origin 'refs/evo/owner/*'` 一眼就能看出来。

## 2. 机器名

`this_host()` 按顺序取：环境变量 `EVO_HOST` → `~/.evoloop/machine.yml` 的 `name` → `hostname` 去掉 `.local`、转小写、非字母数字换成 `-`。

建议每台机器都写 `~/.evoloop/machine.yml`，名字好记、改主机名也不变：

```yaml
name: mini
model_prefix: mini            # 可选，见第 5 节
aliases:                      # 可选，见第 5 节
  fast: mini/group/evo-fast
```

## 3. evo 怎么检查

- **每个动状态的命令**（读状态加锁那一步）：本机记录的 `owner_host` 不是本机 → 拒绝，并提示怎么转过来。
- **每一轮 tick / once** 额外查远端租约（每 10 分钟最多查一次，结果缓存在 `state/lease.json`）：
  - 远端写着别的机器 → 拒绝。
  - 远端还没人认领 → 本机认领（推 `refs/evo/owner/<本机>`）。
  - 没网、读不到 → 不拦，下次再查。
- 远端租约只在项目有 `push_cmd`（有远端）时才用。

所以：第二台机器后来又 `evo import` 了同一个项目，本机记录写的是它自己，但第一轮 tick 就会被远端租约拦住。

## 4. 照做：把项目从 Air 搬到 mini

1. 在 Air 上停掉这个项目（或停掉整个常驻）：`launchctl bootout gui/$(id -u)/com.evoloop.autopilot`，或者等它这一轮跑完、再也不跑这个项目。
2. 在 mini 上导入（如果还没有）：`evo import TB --name 土布 --path ~/code/tubu-platform --github JAY5CXSDMY14/tubu-platform`。
3. 在 mini 上认领：`evo -p TB claim --force`。
   - 远端租约改成 `refs/evo/owner/mini`，别的机器的 ref 删掉。
   - 本机记录写 `owner_host: mini`、`claimed_from: air`、`claimed_at`。
   - 发 `project.claimed` 事件。
   - 推不上去（没网、没权限）就报错退出，什么都不改。
4. 回到 Air：它本机记录还写着 `air`，但远端已经是 `mini`。Air 下一轮会被拒绝，不会再动 TB。要让 Air 上的记录也对上：在 Air 上打开 `config.json`，把 `owner_host` 改成 `mini`；或者直接删掉 Air 上这个项目的目录。

不加 `--force` 的 `claim`：项目没归任何机器，或者已经归本机时直接成功；归别的机器时拒绝，要你确认那台不会再跑它。

`claim` 也是老板的事：外部 Agent（环境里有 `EVO_AGENT`）跑会被拒。

## 5. 模型名：model_prefix 和 aliases

两台机器的 magpie 可能不一样：mini 上的 magpie 把分组发布成 `mini/group/evo-build`，Air 上是 `group/evo-build`。项目和全局配置里**一律写不带前缀的名字**（`group/evo-build`），换机器不用改配置。

- `model_prefix: mini`：派工时 `group/…` 前面自动加 `mini/`（例 `group/evo-build` → `mini/group/evo-build`）。
- `aliases`：某个模型名在本机要换成别的名字，优先于前缀。
- 读 magpie 的 `/v1/models` 时，`mini/group/evo-build` 也能当 `group/evo-build` 用。团队页、成绩统计都用不带前缀的名字。

## 6. 看归属

```bash
evo projects --json        # 顶层 host = 本机；每个项目有 owner_host、here（是不是归本机）
evo -p TB status --json    # owner_host、host
git -C ~/code/tubu-platform ls-remote origin 'refs/evo/owner/*'
```

## 7. 可以改的默认（第十八轮待定项，按推荐默认实现）

**远端租约默认开。** 关掉的办法：

- 全局关：`~/.evoloop/config.json` 写 `"lease_remote": false`。
- 单个项目：项目 `config.json` 写 `"lease_remote": false`（或 `true`）。项目里写的优先于全局。

关掉后只剩本机记录那一道，两台机器各自 import 同一个项目就拦不住了。只在确定只有一台机器跑 evo、或者远端不允许推自定义 ref 时关。

测试：`kit/tests/test_round18.py::test_project_owner_lease_and_claim`、`test_remote_lease_blocks_second_machine`、`test_remote_lease_default_on_global_off`、`test_machine_model_prefix`。

## 8. 只能真机验的

- 真 GitHub 仓库接不接受推 `refs/evo/owner/*`（分支保护规则只管 `refs/heads/*`，一般能推；企业仓库可能有推送规则拦自定义 ref）。
- 两台真 Mac 同时开着时，第二台第一轮 tick 被拒、`claim --force` 后第一台下一轮被拒（测试里用 `EVO_HOST` 模拟两台机器）。
- 国内网络下 `ls-remote` 走项目的 `git_env` 代理是否通（不通时不拦，只是晚一点才发现冲突）。
