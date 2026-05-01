[app]
# 应用基本信息
title = ATSC Wallet
package.name = atscwallet
package.domain = org.atsc
source.dir = .
source.include_exts = py,png,jpg,kv,atsc
version = 10.12

# 要求的Python版本
osx.python_version = 3.8
android.ndk = 25b
android.sdk = 24
android.api = 33
android.ndk.api = 21
android.build_tools = 33.0.2

# 应用权限
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.arch = arm64-v8a,x86_64  # 支持的CPU架构

# Kivy配置
kivy.version = 2.1.0
android.add_androidx = True
android.gradle_dependencies = 
    androidx.core:core:1.10.1
    com.google.android.material:material:1.11.0

# 依赖配置
requirements = python3,kivy==2.1.0,requests,websocket-client,Pillow

# 构建配置
android.accept_sdk_license = True
android.ndk_path = /usr/local/android-sdk/ndk/25b
android.sdk_path = /usr/local/android-sdk

[buildozer]
log_level = 2
warn_on_root = 1
