// 入口。界面代码都包在 #if os(macOS) 里，Linux 上（CI 之外的沙盒）只为了让 swift test 能编过。
#if os(macOS)
EvoApp.main()
#else
print("Evo 是 macOS 菜单栏应用；这里只能跑 swift test（EvoCore）。")
#endif
