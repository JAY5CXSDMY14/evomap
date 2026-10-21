# 第三方表情引擎 · Third-party expression engines

来源 / Source: https://github.com/sam70361/aora-bot
固定版本 / Pinned commit: `e3b6148c818da4a8e1966f2bc89cdb3cee473b73`（2026-08-25）
作者 / Copyright (c) 2026 sam70361

| 目录 | 内容 | 许可 |
| --- | --- | --- |
| `emotion-ball/js/`（rings.js、emotions.js、ball.js、engine.js） | 调度球（Evo 里的叫法；原作者称 blob 球形角色 / emotion-ball）+ 表情引擎，**Evo 默认角色** | `emotion-ball/LICENSE`、`emotion-ball/NOTICE.md`：引擎与表情数据非商业免费（可另购商业授权，见 `emotion-ball/LICENSE-COMMERCIAL.md`）；**球形角色视觉形象只许个人学习研究，永不商用、永不提供商业授权** |
| `mood-mates/`（src、docs） | 云宝 Nimbo / 亮亮 Twinkle 原创角色 + 引擎（设置里可选） | `mood-mates/LICENSE`（社区许可，禁止商业用途）+ `mood-mates/LICENSE-COMMERCIAL.md`（可购买商业许可） |

## 用法限制（Evo 这边的规矩）

- Evo 是老板自用的本机工具。带着调度球形象（即 emotion-ball 的球形角色）的 Evo **只许个人学习 / 研究、非商业使用**，**不得公开分发**（不发 GitHub Release、不放公开下载、不卖）。
- 哪天要分发或商用：先把角色换成 mood-mates（云宝 / 亮亮）并**向作者购买商业许可**（1251579308@qq.com），或换成我们自己画的角色；调度球（emotion-ball 球形角色）形象无论如何都不能带出去。
- 对原文件的唯一改动：`emotion-ball/js/ball.js` 和 `mood-mates/src/core/render.js` 里睡眠 Z 字母的字体从 `'Space Grotesk', 'Noto Sans SC'` 换成系统字体 `-apple-system, 'PingFang SC'`（不加载任何网络字体）。展示站（index.html、site/、app.js、i18n.js、hero-particles.js、css、图片）没有拷进来——宿主页 `Resources/mate/index.html` 是 Evo 自己写的，不联网。
- 应用图标 `Resources/AppIcon.icns` / `AppIcon.png` 不是这些引擎的东西：是 `scripts/make-icon.py` 用代码画的原创图标（v0.5.0）。

## 公开仓库（2026-10-21 起）

- evomap 仓库公开后，上述第三方文件**不再提交进仓库**：`app/scripts/fetch-vendor.sh` 在构建时从上游 sam70361/aora-bot 固定 commit 下载到 `app/Resources/vendor/`（已 .gitignore），并做上面那处字体改动。
- 带调度球形象的截图同样不进仓库，只留在 CI 构件和本机。
