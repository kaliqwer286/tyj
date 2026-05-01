[app]

# 应用基本信息
title = ATSC钱包
package.name = atscwallet
package.domain = org.atsc

# 源码目录
source.dir = .
source.include_exts = py,png,jpg,kv,atsc,txt,json

# 版本
version = 10.12

# 需求
requirements = python3==3.9.7,kivy==2.1.0,requests==2.28.1,websocket-client==1.4.2,Pillow==9.4.0

# Android SDK 配置 - 注意：注释不能和配置在同一行！
android.accept_sdk_license = True
android.ndk = 23b
android.sdk = 30
android.api = 30
android.minapi = 21
android.sdk_build_tools = 30.0.3
android.ndk_version = 23b

# 权限
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE

# 架构
android.archs = armeabi-v7a, arm64-v8a

# 调试
android.release = False
android.debug = True

# 日志
log_level = 2

# 忽略
android.exclude_activity_context = True
source.exclude_exts = pyc,pyo,so,git

# 缓存
buildozer.cache_limit = 2000

# 屏幕方向
orientation = portrait
fullscreen = 0

# 编译
buildozer.threads = 4
android.ignore_setup_os = True

[buildozer]

log_level = 2
warn_on_root = 0
