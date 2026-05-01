[app]

# 应用基本信息
title = ATSC钱包
package.name = atscwallet
package.domain = org.atsc

# 源码目录
source.dir = .
source.include_exts = py,png,jpg,kv,atsc,txt,json

# 版本（选择一种方式）
# 方式1：固定版本
version = 10.12

# 方式2：从文件读取（如果使用方式2，请注释掉上面的version）
# version.regex = CURRENT_VERSION = "([0-9]+\.[0-9]+)"
# version.filename = main.py

# 需求
requirements = python3==3.9.7,kivy==2.1.0,requests==2.28.1,websocket-client==1.4.2,Pillow==9.4.0

# 允许的权限
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE

# Android API级别
android.api = 30
android.minapi = 21
android.ndk = 23b
android.sdk = 30

# 应用图标（可选）
# icon.filename = %(source.dir)s/icon.png
# presplash.filename = %(source.dir)s/splash.png

# 支持的架构
android.archs = armeabi-v7a, arm64-v8a

# 调试模式
android.release = False
android.debug = True

# 日志级别
log_level = 2

# 忽略的目录
android.exclude_activity_context = True
source.exclude_exts = pyc,pyo,so,git

# 允许下载缓存
buildozer.cache_limit = 2000

# 屏幕方向
orientation = portrait

# 全屏
fullscreen = 0

# 应用类别
android.category = android.intent.category.LAUNCHER

# 应用主题
android.phone.background_style = transparent
android.window_background_color = #1a1a2e

# 编译线程数
buildozer.threads = 4

# 开发模式
android.ignore_setup_os = True

[buildozer]

# 日志级别
log_level = 2

# 警告抑制
warn_on_root = 0
