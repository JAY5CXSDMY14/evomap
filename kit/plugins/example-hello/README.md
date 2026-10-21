# example-hello（evo 示例插件）

一个插件四种贡献点各一个：侧栏页「你好」、输入框 `/hello 名字`、通知渠道（要推的事追加到 `$EVO_PLUGIN_DATA/notify.log`）、件详情页按钮。纯 Python 标准库。

```bash
evo plugin install kit/plugins/example-hello   # 拷到 ~/.evoloop/plugins/example-hello（默认关着）
evo plugin enable example-hello                # 或在 App 设置 → 插件里打开
evo plugin run example-hello sidebar_page hello
evo plugin run example-hello composer_command hello --args 老板
```

写法见 docs/plugins.md。
