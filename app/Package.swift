// swift-tools-version:5.9
// Evo 菜单栏应用：纯命令行维护（swift build / swift test / make app），没有 Xcode 工程。
import PackageDescription

let package = Package(
    name: "Evo",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "Evo", targets: ["Evo"]),
        .library(name: "EvoCore", targets: ["EvoCore"]),
    ],
    targets: [
        // 纯逻辑：status JSON 解码、角标计数、通知去重、免打扰、心跳、找 python3。不碰 AppKit，Linux 上也能 swift test。
        .target(name: "EvoCore"),
        // 菜单栏外壳：SwiftUI + AppKit + WebKit + UserNotifications + ServiceManagement（只在 macOS 编进去）。
        .executableTarget(name: "Evo", dependencies: ["EvoCore"]),
        .testTarget(name: "EvoCoreTests", dependencies: ["EvoCore"], resources: [.copy("Fixtures")]),
    ]
)
