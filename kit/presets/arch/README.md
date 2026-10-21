# 后端 / 架构预设（第十五轮）

这份预设让施工岗写后端时守同一套规矩：目录怎么放、分几层、依赖往哪个方向走、配置放哪里。它和 UI 预设是同一套做法。

老板原话：

> 去 github 找那种专业的开发文档规则，规矩，
>
> 例如文件夹怎么放啊，架构怎么搭啊之类的，
>
> 这就可以预设到我们后端这部分了

## 原则

前四条沿用 UI 预设的精神：

1. **优先复用成熟库和成熟做法**
2. **统一规范**
3. **严格限制重复依赖**
4. **不重复造轮子**

后三条是架构专属的：

5. **依赖方向单向**：上层可以依赖下层，下层不许依赖上层。
6. **按领域分包**：一个业务领域放一个目录，不把所有接口堆进一个文件夹。
7. **配置走环境变量**：连接串、口令、密钥只在 config 模块读，代码里不写死。

红线：新开目录、新分层、换库，一律先 ask 决策岗。老板批准后，写进项目的 `arch_overrides`，再在 `docs/decisions/` 补一份 ADR。施工岗自己开新目录或新分层，交卷时直接打回。

## 规范从哪来

只收能变成规则或脚本检查的条目。每个来源都打开原文核对过（2026-10-21）。

| 来源 | 星数 | 许可证 | 最近更新 | 取了什么 |
|---|---|---|---|---|
| [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices) | 18.2k | 无许可证，只引用不拷贝 | 2026-08 | 按领域分包和每包固定的文件名；跨领域导入写显式模块名；配置按领域拆；迁移静态可回滚、按日期命名；表名规范；用 ruff |
| [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) | 46.1k | MIT | 2026-10 | `core/config.py` 用 pydantic-settings；Alembic；ruff 规则集；PyJWT 加 pwdlib |
| [seddonym/import-linter](https://github.com/seddonym/import-linter) | 1.2k | BSD-2 | 2026-10 | 用 `layers` 契约强制依赖方向（Python 的机器检查） |
| [astral-sh/ruff](https://github.com/astral-sh/ruff) | 50.2k | MIT | 2026-10 | Python 只用这一个 lint 和格式化工具 |
| [goldbergyoni/nodebestpractices](https://github.com/goldbergyoni/nodebestpractices) | 105.7k | CC-BY-SA-4.0，只引用不拷贝 | 2026-06 | 1.1 按业务组件分；1.2 三层结构，Web 框架不出入口层；1.3 通用代码放 libraries；1.4 配置启动即校验；2.7 用成熟日志库 |
| [sverweij/dependency-cruiser](https://github.com/sverweij/dependency-cruiser) | 7.3k | MIT | 2026-10 | 用 `forbidden` 规则强制依赖方向（Node 的机器检查） |
| [Apple：Organizing your code with local packages](https://developer.apple.com/documentation/xcode/organizing-your-code-with-local-packages) | — | Apple 文档 | — | 可复用的代码拆成本地 Swift 包，由编译器管依赖 |
| [Swift API Design Guidelines](https://www.swift.org/documentation/api-design-guidelines/) | — | swift.org | — | 命名大小写规则；工厂方法用 make 开头；布尔值读起来像断言；写文档注释 |
| [realm/SwiftLint](https://github.com/realm/SwiftLint) | 19.8k | MIT | 2026-10 | Swift 的 lint，只算新增的行 |
| [adr/madr](https://github.com/adr/madr) | 2.6k | MIT 或 CC0 | 2026-08 | ADR 模板，固定副本放在 `kit/vendor/madr`（提交 ba75bb1） |
| [architecture-decision-record](https://github.com/joelparkerhenderson/architecture-decision-record) | 17.3k | 未声明 | 2026-10 | 每个决定一个文件；目录叫 `decisions` 更容易坚持写 |
| [agentsmd/agents.md](https://github.com/agentsmd/agents.md) | 25.0k | MIT | 2026-09 | 目录约定、怎么跑检查写进项目的 AGENTS.md（evo 的项目骨架已经带了） |
| [12factor.net III. Config](https://12factor.net/config) | 3.8k | MIT | 2026-07 | 随部署变化的配置放环境变量 |

## 三种预设加 none

| 项目配置 `arch_preset` | 用在哪 | 文件 |
|---|---|---|
| `python-fastapi` | Python / FastAPI 后端 | `python-fastapi.json` |
| `node-ts` | Node / TypeScript 后端 | `node-ts.json` |
| `swift-app` | SwiftUI 应用（只管目录和分层，界面库看 UI 预设 `swiftui`） | `swift-app.json` |
| `none`（默认） | 保持现状 | 什么都不加 |

设置：`evo new/import … --arch-preset python-fastapi`，或 `evo -p AB arch set python-fastapi`。

查看：`evo -p AB arch`，加 `--json` 给机器读。`evo -p AB arch show node-ts` 只预览，不改配置。

外部 Agent（设了 `EVO_AGENT`）只能看，不能改。

## python-fastapi

推荐的目录（新项目）：

```
src/
  main.py            建 FastAPI 应用
  config.py          全局配置（pydantic-settings 读环境变量）
  database.py        数据库连接
  <领域>/            例 auth/、materials/、search/
    router.py        接口
    schemas.py       Pydantic 模型
    models.py        表模型
    service.py       业务逻辑
    repository.py    数据访问（SQL）
    dependencies.py  路由依赖
    config.py  constants.py  exceptions.py  utils.py
tests/<领域>/
alembic/versions/    迁移文件，命名为「年-月-日_slug.py」
docs/decisions/      ADR
```

分层（只许从上往下依赖）：

| 层 | 认哪些文件（相对源码根） | 额外禁止 |
|---|---|---|
| 入口 | `main.py` | — |
| 接口层 | `*/router.py`、`routers/*`、`routes/*`、`*/dependencies.py` | — |
| 业务层 | `*/service.py`、`services/*`、`*_service.py`、`*/client.py` | — |
| 数据访问层 | `*/repository.py`、`*_repo.py`、`crud.py`、`*/models.py` | 不许 import fastapi、starlette |
| 基础层 | `config.py`、`db.py`、`database.py`、`core/*`、`*/schemas.py`、`*/constants.py`、`*/exceptions.py`、`utils.py` | — |

一个文件对不上任何一层，就不归层，也不查。要让它归层，就用 `arch_overrides` 的 `layers.<层>` 补上文件路径。

依赖（建议，同类不另加）：

| 类别 | 选定 | 同类不另加（节选） |
|---|---|---|
| Web 框架 | FastAPI | Flask、Django、Sanic、Litestar、aiohttp |
| HTTP 客户端 | httpx | requests、aiohttp、urllib3 |
| 配置 | pydantic-settings | python-decouple、dynaconf、environs |
| 数据库 | SQLAlchemy 2 或 SQLModel，加 psycopg 3；原生 SQL 也行 | psycopg2、peewee、tortoise-orm |
| 迁移 | Alembic | yoyo、aerich |
| 令牌和密码 | PyJWT；pwdlib 或 bcrypt | python-jose、passlib |
| 测试 | pytest | nose |
| lint | ruff | flake8、black、isort、pylint |

## node-ts

推荐的目录（nodebestpractices 1.1 和 1.2）：

```
src/apps/<组件>/
  entry-points/api/            控制器：只做协议适配
  entry-points/message-queue/  消费者、定时任务
  domain/                      业务流程、DTO（不认识 HTTP）
  data-access/                 数据库访问（仓储模式）
  test/
src/libraries/<名字>/          跨组件通用：日志、鉴权
src/config/                    启动时用 zod 校验 process.env
```

分层顺序是：入口层 → 业务层 → 数据访问层 → 通用层。业务层和数据访问层不许 import express、fastify 或 koa。

建议的依赖：Fastify、zod（和 web-react 预设用同一个）、pino、原生 fetch、Vitest、ESLint 加 typescript-eslint、dependency-cruiser。

## swift-app

推荐的目录：

```
Sources/<App>/
  App/                  @main、Scene、依赖装配
  Features/<功能>/       View 和该功能的 @Observable 模型
  Services/             URLSession、SwiftData 封装（不 import SwiftUI）
  Domain/  或 Models/    纯数据和规则（只 import Foundation）
  Resources/
Packages/<包名>/         长大后拆出的本地 Swift 包
Tests/
```

分层顺序是：App 入口 → 功能与界面 → 服务与数据（Services、Data、Engine）→ 领域与模型。服务、数据和模型层新加 `import SwiftUI`、`AppKit` 或 `UIKit` 会被打回。拆成本地包后，下层包 import 上层包也会被打回。

建议的依赖用系统框架：URLSession、SwiftData、Codable、os.Logger、async/await。

## 规矩（施工岗照做）

- **只管新代码。** 已有项目不整体迁移。仓库已有自己的结构时，**沿用现有的**，evo 在日志和提醒里各报**一次**，内容变了才再报。常见的四种情况：
  - 源码根不同，例如用 `api/` 而不是 `src/`。
  - 按类型平铺，例如 `routers/` 加 `*_repo.py`。
  - 迁移目录不同。evo 会按现有文件名猜命名规则，例如 `^\d{3}_…\.sql$`。
  - 某类库已经在用别的。
- **按类型平铺的仓库**：新文件放进现有对应目录，照现有命名，**不新开目录**。
- **按领域分包的仓库**：新领域在源码根下建一个包，包里用规范的文件名。
- **依赖方向**：每次新增 import 都想一下它在哪一层、指向哪一层。反方向的依赖，打回。
- **配置**：只在 config 模块读环境变量，别处 import config。新变量同步写进 `.env.example`，只放占位值。
- **迁移**：只加新文件，按项目约定命名，编号不撞。已合并的迁移不再修改。
- **换库、开目录、加分层**：先 `ask` 决策岗。老板批准后写进 `arch_overrides`，再补 ADR：`cp {KIT}/vendor/madr/template/adr-template-minimal.md docs/decisions/NNNN-标题.md`。
- **加新依赖**：先看已选的库能不能做。覆盖不了才加，并在交卷的 `changes` 里写明为什么。

`arch_overrides`（`evo -p AB arch set 键=值`，值留空就清掉）可以设这些键：

| 键 | 例子 | 作用 |
|---|---|---|
| `root` | `api` | 源码根 |
| `layout` | `domain` / `by-type` | 不让 evo 自己猜布局 |
| `allow_dirs` | `api/services,scripts/ops` | 老板批准的新目录 |
| `migrations_dir` / `migrations_pattern` | `migrations` / `^\d{3}_[a-z0-9_]+\.sql$` | 迁移的位置和命名 |
| `layers.<层>` | `layers.service=auth.py,batch_import.py` | 把现有文件归到某一层 |
| `deps.<类别>` | `deps.http=requests` | 老板批准换库：换上的不再禁止，原来选的反而禁止 |
| `checks.<检查>` | `checks.ruff=off` | 关掉某项外部检查 |
| `arch_paths` / `config_modules` | `api/,migrations/` | 哪些路径算后端；哪些文件算 config 模块 |

## 怎么查

施工岗交卷后、送验收前，接棒器自动跑内置检查（不跑外部工具）。验收岗再跑 `evo -p AB arch check`，这一步会把外部工具也跑上。

| 检查 | 结果 |
|---|---|
| 新开了约定外的目录（仓库根、按类型平铺的源码根、领域包里再套目录） | 打回 |
| 新加了反方向的依赖；下层用了 Web 框架或界面框架 | 打回 |
| 新加了禁用库，或者同类的第二个库 | 打回 |
| 新迁移的命名不对，或编号撞了 | 打回 |
| 新增的行里写死了口令、密钥或带密码的连接串（测试目录除外） | 打回 |
| import-linter、dependency-cruiser：改动前后各跑一次，算新出现的违约 | 验收不通过 |
| ruff、SwiftLint：只算新增的行 | 验收不通过 |
| 外部工具没装，或者工具自己报错 | 只警告，并给出安装命令 |
| 新依赖不在规范里又没写理由；在 config 模块外读环境变量；新领域包里的文件名不常规；改了已有迁移；lockfile 里才出现的禁用库 | 只提示（时间线记 `arch_advisory`） |

命令格式是 `evo -p AB arch check [--path 工作区] [--base 提交] [--no-tools] [--json]`。默认对比 `merge-base main HEAD..HEAD`。有不合规，退出码就是 1。

仓库里有 `.importlinter` 或 `.dependency-cruiser.*`，就用仓库自己的规则。没有的话，evo 按本预设的分层生成一份。

安装命令：`pip install import-linter ruff`（或 `uv add --dev import-linter ruff`）；`npm i -D dependency-cruiser`；`brew install swiftlint`。

## 现有项目

- **ST（股票）**：`kit/profiles/st/project.json` 设了 `arch_preset: swift-app` 和 `arch_overrides.root = REASTOCK/Sources/REASTOCK`。REASTOCK 是按类型平铺的（Views、Engine、Data、Core、Models），沿用现有。Engine、Data、Models 新加 `import SwiftUI` 会被打回。Core 不归层。
- **TB（土布）**：配置不动（`none`）。要开的话，先跑 `evo -p TB arch show python-fastapi`，只预览不改配置。对照结论和建议写的 `arch_overrides` 见下一节。

## 土布（TB）对照 python-fastapi

对照 tubu-platform main 分支，提交 78621b4（2026-10-19）。全程只读，没改任何东西。分层检查是把 import-linter 按本预设生成的契约，在本地只读副本上真跑了一遍。

**已经符合的：**

- **配置走环境变量。** `api/config.py` 集中读取 DATABASE_URL、JWT_SECRET、CORS_ORIGINS 等。`.env.example` 只放占位值，`.env` 不入库。它没用 pydantic-settings，而是自己读 .env，但也没有引入第二个配置库，所以不算重复依赖。
- **依赖方向基本单向。** routers 依赖 `*_repo` 和 `*_service`，再往下是 db，再往下是 config。三个 `*_repo.py` 都不 import fastapi。用生成的契约检查，整个 api/ 只有一处向上依赖：`api/schemas.py` 第 27 行在函数里延迟 import 了 `materials_repo.DERIVED_READONLY_FIELDS`，这是故意的，为了不抄第二份清单。老代码不追究。以后要理顺，可以把这个常量挪到基础层的常量模块。
- **依赖没有重复。** fastapi、psycopg 3（没有 psycopg2）、httpx2、pytest、PyJWT、bcrypt 都在预设的选定范围内，也没有用到禁用库。
- **已有 AGENTS.md，测试用 pytest。**

**不同的地方（都沿用现有，不迁移）：**

| 项 | 预设 | 土布现状 |
|---|---|---|
| 源码根 | `src/` | `api/` |
| 布局 | 按领域分包 | 按类型平铺：`api/routers/` 加上 `*_repo.py`、`*_service.py` 和一批工具模块 |
| 迁移 | Alembic，`alembic/versions/年-月-日_slug.py` | 根目录 `migrations/NNN_*.sql`，原生 SQL。已经有两个 004：`004_search_embedding.sqlite.sql` 和 `004_users.sql`。老的不动，新的编号再撞会被打回 |
| lint | ruff，带配置 | 没有 ruff 配置。按 E,W,F,I,B,UP 规则全查约有 23 处提示，但只算新增的行，所以老代码不受影响 |
| ADR | `docs/decisions/` | 还没有，以后的新决定写在这里 |
| 归不了层的模块 | — | auth、batch_import、dictionary、normalize、processing_log、search_*、seed、weave_code、storage/local。不写覆盖的话，这些模块不查分层 |

**建议的 arch_overrides（沿用现有，只约束新代码）：**

```json
"arch_preset": "python-fastapi",
"arch_overrides": {
  "root": "api",
  "layout": "by-type",
  "migrations_dir": "migrations",
  "migrations_pattern": "^\\d{3}_[a-z0-9_]+(\\.sqlite)?\\.sql$",
  "layers.service": ["auth.py", "batch_import.py", "search_*.py", "processing_log.py", "seed.py"],
  "layers.core": ["dictionary.py", "normalize.py", "weave_code.py", "storage/*"],
  "arch_paths": ["api/", "migrations/"]
}
```

前四项 evo 本来也能自动认出来，写明是为了不靠猜。这样配置后，现有代码在生成的契约下只剩上面那一处老违约，不会误伤。

开了以后对新代码的效果：

- 在 `api/` 下新开目录（比如 `api/services/`），打回。
- `*_repo.py` 里新加 `import fastapi`，打回。
- 基础层模块新加对 routers、repo 或 service 的依赖，打回。
- 新迁移不是三位编号，或者编号撞了，打回。
- 新增的行里写死口令，打回。
