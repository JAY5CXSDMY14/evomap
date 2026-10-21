# Evo 菜单栏应用：全部命令行，没有 Xcode 工程。见 README.md。
#   make build   编译（release）
#   make test    跑 EvoCore 单元测试
#   make app     组装 build/Evo.app（含整套 kit，ad-hoc 签名）
#   make dmg     打 build/Evo.dmg
#   make run     组装后打开
#   make install 拷到 /Applications
#   make snapshots  用假数据把主要界面画成 PNG（build/snapshots，浅色+深色）
#   make clean
# 可选：SIGN="Developer ID Application: …" 换正式证书；SIGN= 跳过签名；UNIVERSAL=1 出 arm64+x86_64 通用包
VERSION := $(shell tr -d '[:space:]' < VERSION)
# xcode-select 指向 CommandLineTools（没有 SwiftUI 宏插件）时，自动借用装着的 Xcode / Xcode-beta；
# 不改系统设置。自己指定 DEVELOPER_DIR=… 则以你的为准。
ifeq ($(origin DEVELOPER_DIR),undefined)
  _EVO_DEVDIR := $(shell scripts/dev-dir.sh)
  ifneq ($(_EVO_DEVDIR),)
    export DEVELOPER_DIR := $(_EVO_DEVDIR)
    $(info 用 $(_EVO_DEVDIR) 编译（命令行工具里没有 SwiftUI 宏插件）)
  endif
endif
SIGN ?= -
OUT := build
ifeq ($(UNIVERSAL),1)
  ARCHFLAGS := --arch arm64 --arch x86_64
  BINDIR = $(shell swift build -c release $(ARCHFLAGS) --show-bin-path)
else
  ARCHFLAGS :=
  BINDIR = $(shell swift build -c release --show-bin-path)
endif

.PHONY: build test app dmg run install clean version snapshots

build:
	swift build -c release $(ARCHFLAGS)

test:
	swift test

app: build
	scripts/fetch-vendor.sh
	scripts/assemble-app.sh "$(BINDIR)/Evo" $(OUT) "$(SIGN)"

dmg: app
	scripts/make-dmg.sh $(OUT)

run: app
	-pkill -x Evo
	open $(OUT)/Evo.app

install: app
	-pkill -x Evo
	-chmod -R u+w /Applications/Evo.app 2>/dev/null
	rm -rf /Applications/Evo.app
	cp -R $(OUT)/Evo.app /Applications/
	open /Applications/Evo.app

# 界面截图：debug 编译后用 --snapshots 跑一次（不碰 evo，画完就退出）
snapshots:
	scripts/fetch-vendor.sh
	swift build
	rm -rf $(OUT)/snapshots
	"$$(swift build --show-bin-path)/Evo" --snapshots $(OUT)/snapshots
	@ls -1 $(OUT)/snapshots

version:
	@echo $(VERSION)

clean:
	-chmod -R u+w $(OUT) 2>/dev/null
	rm -rf .build $(OUT)
