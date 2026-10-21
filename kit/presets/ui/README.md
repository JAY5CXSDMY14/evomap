# UI 栈预设（第十三轮）

让施工岗哪怕一次成型，也写出风格统一、依赖干净的界面。老板定的五条原则（原话）：

1. **优先复用成熟库**
2. **组件源代码可控**
3. **统一设计语言**
4. **严格限制重复依赖**
5. **不重复造轮子**（2026-10-21 补）

第五条是红线。已有依赖能正确表达的组件和行为，严禁自行设计实现。先参考业界实现和成熟库。验收发现即不通过。

另一条硬要求是三态必做。会取数据或可能为空的界面，要做空状态、加载中、报错三种样子。Web 用 shadcn Empty、Skeleton、Alert 和 sonner。SwiftUI 用 ContentUnavailableView、ProgressView 和骨架占位。验收要三态截图各一张。


## 审美：taste-skill（Web）

Web 预设带上 taste-skill 的固定副本（MIT，提交 6010f91，在 kit/vendor/taste-skill）。它管「好不好看」，上面的库表管「用什么」，两者不冲突。

施工岗做 Web 界面时先读 SKILL.md。页面（官网、落地页）和应用界面（工作台、后台）走不同流程。应用界面看 references/app-screens.md。

已有品牌的项目保留自己的颜色和字体，只借构图和规矩。只改一个组件时，贴着周围设计做。新页面或整页重做才走完整流程，约 30–45 分钟。

验收岗对改动的前端文件跑 lint.mjs。本机有 Chrome 时，再跑 inspect.mjs。有 FAIL 就不通过。三个宽度的截图放进证据，给看效果门用。

土布注意：土布的靛蓝是品牌色，taste-skill 默认禁靛蓝和紫色。土布按品牌放行，在证据里写明。SwiftUI 不用 taste-skill，继续按系统组件和苹果规范。

## 三种模式

| 项目配置 `ui_preset` | 用在哪 | 说明 |
|---|---|---|
| `web-react` | React 网页 | `web-react.json` |
| `swiftui` | 原生 Mac / iOS | `swiftui.json` |
| `none`（默认） | 保持现状 | 什么都不加：任务书不带 UI 规范，交卷不查依赖 |

设置：`evo new/import … --ui-preset web-react`，或 `evo -p AB ui set web-react | swiftui | none`。查看：`evo -p AB ui`（`--json` 给机器读）；`evo -p AB ui show web-react` 只预览某个预设套到本仓库的结果，不改配置。外部 Agent（设了 `EVO_AGENT`）只能看、不能改。

## web-react：默认栈

| 类别 | 选定 | 包名 | 同类不另加（节选） | 来源 |
|---|---|---|---|---|
| UI 组件 | shadcn/ui（Nova 风格），组件源码复制进 `components/ui/` | `radix-ui` / `@radix-ui/*`、`class-variance-authority`、`clsx`、`tailwind-merge` | MUI、antd、Chakra、Mantine、HeroUI、react-bootstrap、Headless UI、daisyUI… | 老板定 |
| 样式 | Tailwind CSS（设计令牌走 CSS 变量） | `tailwindcss`、`@tailwindcss/*`、`tw-animate-css` | styled-components、Emotion、Stitches、vanilla-extract、UnoCSS、Sass | 老板定 |
| 图标 | Lucide | `lucide-react` | heroicons、react-icons、Font Awesome、Tabler、Phosphor、`@radix-ui/react-icons` | 老板定 |
| 动画 | Motion（motion.dev，原 framer-motion） | `motion`（旧项目的 `framer-motion` 视为同一个库） | react-spring、GSAP、anime.js、react-transition-group、auto-animate | 老板定 |
| 分栏布局 | react-resizable-panels（shadcn Resizable） | `react-resizable-panels` | react-split-pane、allotment、split.js、react-mosaic | 老板定 |
| 拖放 | dnd-kit | `@dnd-kit/*` | react-dnd、react-beautiful-dnd、@hello-pangea/dnd、SortableJS、pragmatic-dnd | 老板定 |
| 状态 | Zustand（服务端数据交给 TanStack Query） | `zustand` | Redux / RTK、Jotai、MobX、Recoil、Valtio | 老板定 |
| 表单与校验 | react-hook-form + zod（shadcn Form） | `react-hook-form`、`@hookform/resolvers`、`zod` | Formik、react-final-form、TanStack Form、yup、valibot、joi | 建议 |
| 数据请求 | TanStack Query | `@tanstack/react-query` | SWR、旧版 `react-query` | 建议 |
| 表格 | TanStack Table + shadcn Data Table | `@tanstack/react-table` | AG Grid、react-table v7、MUI DataGrid、Handsontable | 建议 |
| 轻提示 | sonner（shadcn Sonner） | `sonner` | react-hot-toast、react-toastify、notistack、`@radix-ui/react-toast` | 建议 |
| 图表 | Recharts（shadcn Chart） | `recharts` | Chart.js、ECharts、Nivo、Victory、ApexCharts、Highcharts、visx、Tremor | 建议 |
| 日期 | date-fns（日期选择用 shadcn Calendar / react-day-picker） | `date-fns`、`@date-fns/*`、`react-day-picker` | moment、dayjs、luxon | 建议 |

新项目起步：`npx shadcn@latest create --preset nova`（Nova：紧凑间距，默认 Lucide 图标 + Geist 字体）；已有项目 `npx shadcn@latest init`，`components.json` 的 style 用 `radix-nova`。加组件一律 `npx shadcn@latest add <组件>`，源码进仓库再按需改。

## swiftui：原生 Mac / iOS

| 类别 | 选定 | 同类不另加（要老板批准） | 来源 |
|---|---|---|---|
| UI 组件 | 系统组件优先（NavigationSplitView、List、Table、Form、Inspector、Toolbar、Settings…） | SwiftUIX、Material Components、swiftui-introspect、Eureka、SkeletonView… | 老板定 |
| 图标 | SF Symbols | FontAwesome.swift、SwiftIcons、Iconic | 老板定 |
| 动画 | 原生弹簧（`.spring` / `.snappy` / `.bouncy`）、PhaseAnimator、KeyframeAnimator、matchedGeometryEffect | lottie-ios / lottie-spm、Pow、Spring、Hero | 老板定 |
| 布局 | NavigationSplitView / HSplitView、Grid、ViewThatFits、Layout 协议 | SnapKit、PureLayout、Stevia | 老板定 |
| 拖放 | `.draggable` / `.dropDestination` + Transferable | — | 建议 |
| 状态 | Observation（`@Observable`）+ SwiftData / `@AppStorage` | TCA、RxSwift、ReactiveSwift、ReSwift | 建议 |
| 图表 | Swift Charts | Charts / DGCharts、SwiftUICharts | 建议 |
| 日期 | Foundation（Date.FormatStyle、Calendar） | SwiftDate、DateToolsSwift | 建议 |

Swift 依赖按包仓库名比对（URL 最后一段去掉 `.git`），读 `Package.swift` 和 Xcode 工程里的包引用。

## 规矩

- **只管新代码**。已有项目不整体迁移。evo 读 `package.json` / `Package.swift` / Xcode 包引用。某一类仓库已在用别的库时，**现有的赢**：这一类沿用旧库，预设选定那个反倒算重复。evo 在日志和提醒里各报**一次**，冲突内容变了才再报。仓库里两种都有时，新代码用预设选定那个，旧库不再新增。
- **加新依赖**：先看各类已选的库能不能做，覆盖不了才加，并在交卷 `changes` 里写明为什么。
- **换库**：先 `ask` 决策岗，老板批准后写进项目 `ui_overrides`（`evo -p AB ui set icons=react-icons`，`icons=` 清掉）。换上的库不再禁，原来选的变成禁用。`ui_overrides` 的值可以是包名、包名列表，或 `{"choice": "说明", "packages": [...]}`。
- 碰界面的件：打了 look，或 scope 落在预设的 `ui_paths`（项目可用 `ui_paths` 覆盖）。施工任务书在「项目目标」那行后面加一段「UI 规范」。验收任务书加「UI 规范检查」。

## 怎么查

| 检查 | 谁做 | 结果 |
|---|---|---|
| 清单（package.json / Package.swift / Xcode 包引用）里**新加**了禁用库或同类第二个库 | 接棒器在施工交卷后、送验收前自动查；验收岗再跑 `evo -p AB ui check` | 直接打回返工（算一轮），原因写明哪一类、已定什么、加了什么 |
| lockfile（package-lock / pnpm-lock / yarn.lock / Package.resolved）里才新出现的禁用库 | 同上 | 只提示（可能是传递依赖），时间线 `ui_advisory` |
| 新依赖不属于任何一类、交卷里又没提到它 | 同上 | 接棒器只提示；验收岗按清单判不通过 |
| 新文件名和预设已有组件撞了（如自己写 `Modal.tsx`、`Button.tsx`），又不在 `components/ui/` | 同上 | 只提示，验收岗写进「建议另开 issue」 |

`evo -p AB ui check [--path 工作区] [--base 提交] [--json]`：默认对比 `merge-base main HEAD..HEAD`，有不合规退出码 1。

## 现有项目

- **ST（股票）**：`kit/profiles/st/project.json` 已设 `ui_preset: swiftui`（REASTOCK 是原生 SwiftUI）。
- **TB（土布）**：配置不动（`none`）。土布的 web 想用 `web-react`，先跑 `evo -p TB ui show web-react`（只预览、不改配置），看「仓库现有栈」那几行冲突在哪、能不能接受，再 `evo -p TB ui set web-react`。
