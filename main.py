#!/usr/bin/env python3
"""
ATSC 客户端钱包 v10.12 - 手机版
- 支持 Android/iOS 触控操作
- 使用 RecycleView 实现列表
- 完整的区域管理功能
"""

import subprocess
import sys
import os
import threading
import time
import json
import hashlib
import base64
import queue
import traceback
from datetime import datetime

# 检测是否在打包环境中
def is_frozen():
    return getattr(sys, 'frozen', False)

def get_resource_path(relative_path):
    if is_frozen():
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# 安装依赖（仅开发环境）
def install_dependencies():
    if is_frozen():
        return False
    
    dependencies = ['requests', 'kivy', 'websocket-client', 'Pillow']
    missing = []
    
    for dep in dependencies:
        try:
            if dep == 'websocket-client':
                __import__('websocket')
            else:
                __import__(dep)
        except ImportError:
            missing.append(dep)
    
    if missing:
        print(f"正在安装缺失的依赖: {missing}")
        for dep in missing:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
        print("依赖安装完成！")
        return True
    return False

#if not is_frozen() and __name__ == '__main__':
#    install_dependencies()

# Kivy 导入
import kivy
kivy.require('2.1.0')
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import StringProperty, ObjectProperty
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, Rectangle

# 设置窗口大小（用于测试，实际手机全屏）
Window.size = (360, 640)

import requests
import websocket
import threading

CURRENT_VERSION = "10.12"

# 颜色定义
COLORS = {
    'bg': '#1a1a2e',
    'card': '#16213e',
    'accent': '#00ff88',
    'warning': '#ff4444',
    'info': '#ffd700',
    'primary': '#4a90e2',
    'text': '#ffffff',
    'text_secondary': '#888888'
}


class RV(RecycleView):
    """自定义RecycleView，正确配置布局管理器"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout_manager = RecycleBoxLayout(
            default_size=(None, dp(50)),
            default_size_hint=(1, None),
            size_hint_y=None,
            height=self.height,
            orientation='vertical'
        )
        self.add_widget(self.layout_manager)
        self.layout_manager.bind(minimum_height=self.layout_manager.setter('height'))


class SelectableRecycleBoxLayout(RecycleBoxLayout):
    """可选择的RecycleBoxLayout"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_item = None
        self.on_select = None
    
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            for child in self.children:
                if child.collide_point(*touch.pos):
                    self.selected_item = child
                    if self.on_select:
                        self.on_select(child.index)
                    return True
        return super().on_touch_down(touch)


class SelectableLabel(RecycleDataViewBehavior, BoxLayout):
    """可选择的列表项"""
    text = StringProperty('')
    index = None
    
    def refresh_view_attrs(self, rv, index, data):
        self.index = index
        self.text = data.get('text', '')
        self.ids.label.text = self.text
        return super().refresh_view_attrs(rv, index, data)
    
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self.parent and hasattr(self.parent, 'selected_item'):
                self.parent.selected_item = self
            if hasattr(self.parent, 'on_select') and self.parent.on_select:
                self.parent.on_select(self.index)
            return True
        return super().on_touch_down(touch)


class SelectableButton(RecycleDataViewBehavior, Button):
    """可选择的按钮列表项"""
    index = None
    on_select_callback = ObjectProperty(None)
    
    def refresh_view_attrs(self, rv, index, data):
        self.index = index
        self.text = data.get('text', '')
        return super().refresh_view_attrs(rv, index, data)
    
    def on_press(self):
        if self.on_select_callback:
            self.on_select_callback(self.index)


class MessagePopup(Popup):
    """消息弹窗"""
    def __init__(self, title, message, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.size_hint = (0.8, None)
        self.height = dp(150)
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(Label(text=message, color=get_color_from_hex(COLORS['text'])))
        btn = Button(text='确定', size_hint_y=None, height=dp(40), 
                     background_normal='', background_color=get_color_from_hex(COLORS['primary']))
        btn.bind(on_press=self.dismiss)
        content.add_widget(btn)
        self.content = content


class InputDialog(Popup):
    """输入弹窗"""
    def __init__(self, title, hint, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.title = title
        self.size_hint = (0.9, None)
        self.height = dp(150)
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        self.text_input = TextInput(hint_text=hint, multiline=False, size_hint_y=None, height=dp(40))
        content.add_widget(self.text_input)
        btn_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
        cancel_btn = Button(text='取消', background_normal='', 
                           background_color=get_color_from_hex(COLORS['warning']))
        confirm_btn = Button(text='确认', background_normal='', 
                            background_color=get_color_from_hex(COLORS['accent']))
        cancel_btn.bind(on_press=self.dismiss)
        confirm_btn.bind(on_press=self.confirm)
        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(confirm_btn)
        content.add_widget(btn_layout)
        self.content = content
    
    def confirm(self, instance):
        self.callback(self.text_input.text)
        self.dismiss()


class ChatClient:
    def __init__(self, app):
        self.app = app
        self.websocket = None
        self.running = False
        self.thread = None
        self.ws_url = None
        self.reconnect_delay = 1
        self.max_reconnect_delay = 30
        self.address = None
        self.token = None
    
    def connect(self, address, token):
        if self.running:
            self.disconnect()
        self.address = address
        self.token = token
        self.ws_url = f"ws://{self.app.cloud_host}:8765"
        self.running = True
        self.reconnect_delay = 1
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def _run(self):
        while self.running:
            try:
                ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                ws.run_forever()
            except Exception as e:
                if self.running:
                    Clock.schedule_once(lambda dt: self.app.log(f"⚠️ WebSocket连接失败，{self.reconnect_delay}秒后重连..."), 0)
                    time.sleep(self.reconnect_delay)
                    self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
    
    def _on_open(self, ws):
        ws.send(json.dumps({'type': 'auth', 'token': self.token}))
    
    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            Clock.schedule_once(lambda dt, d=data: self.app.on_websocket_message(d), 0)
        except:
            pass
    
    def _on_error(self, ws, error):
        pass
    
    def _on_close(self, ws, close_status_code, close_msg):
        if self.running:
            Clock.schedule_once(lambda dt: self.app.log(f"⚠️ WebSocket连接断开"), 0)
            Clock.schedule_once(lambda dt: setattr(self.app.online_label, 'text', "🔴 离线"), 0)
    
    def disconnect(self):
        self.running = False


class ATSCWalletApp(App):
    """主应用程序"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config_file = "atsc_client_config.json"
        self.wallets_dir = "atsc_wallets"
        os.makedirs(self.wallets_dir, exist_ok=True)
        
        self.load_config()
        
        self.current_address = None
        self.current_name = None
        self.current_token = None
        self.current_role = 'user'
        self.current_region = 'default'
        self.managed_region = None
        self.current_chat_friend = None
        self.running = True
        
        self.chat_client = ChatClient(self)
        
        self.cache = {'balance': 0, 'rate': 1.0, 'transactions': [], 'regions': []}
        self.friends = []
        self.friend_requests = []
        
        self.start_task_worker()
    
    def build(self):
        """构建UI"""
        self.root = BoxLayout(orientation='vertical', padding=dp(5), spacing=dp(5))
        
        # 标题栏
        title_bar = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        title = Label(text="⚛️ ATSC钱包", font_size=sp(20), size_hint_x=0.7,
                      color=get_color_from_hex(COLORS['accent']))
        title_bar.add_widget(title)
        
        settings_btn = Button(text="⚙️", size_hint_x=0.15, background_normal='',
                              background_color=get_color_from_hex(COLORS['primary']))
        settings_btn.bind(on_press=self.show_settings)
        title_bar.add_widget(settings_btn)
        
        self.root.add_widget(title_bar)
        
        # 状态栏
        status_bar = GridLayout(cols=2, size_hint_y=None, height=dp(40), spacing=dp(5))
        self.status_label = Label(text="● 未连接", color=get_color_from_hex(COLORS['warning']),
                                  size_hint_x=0.5)
        self.rate_label = Label(text="1 ATSC = 1.00元", color=get_color_from_hex(COLORS['info']),
                                size_hint_x=0.5)
        status_bar.add_widget(self.status_label)
        status_bar.add_widget(self.rate_label)
        self.root.add_widget(status_bar)
        
        # 第二行状态
        status_bar2 = GridLayout(cols=2, size_hint_y=None, height=dp(40), spacing=dp(5))
        self.role_label = Label(text="身份: 普通用户", color=get_color_from_hex(COLORS['text']),
                                size_hint_x=0.5, font_size=sp(12))
        self.online_label = Label(text="🔴 离线", color=get_color_from_hex(COLORS['warning']),
                                  size_hint_x=0.5, font_size=sp(12))
        status_bar2.add_widget(self.role_label)
        status_bar2.add_widget(self.online_label)
        self.root.add_widget(status_bar2)
        
        # 钱包信息卡片
        wallet_card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(180),
                                padding=dp(10), spacing=dp(5))
        with wallet_card.canvas.before:
            Color(*get_color_from_hex(COLORS['card']))
            self.wallet_rect = Rectangle(pos=wallet_card.pos, size=wallet_card.size)
        wallet_card.bind(pos=self._update_wallet_rect, size=self._update_wallet_rect)
        
        self.name_label = Label(text="钱包: 未登录", color=get_color_from_hex(COLORS['text']),
                                font_size=sp(14), halign='left')
        self.name_label.bind(size=self.name_label.setter('text_size'))
        wallet_card.add_widget(self.name_label)
        
        self.address_label = Label(text="地址: 未登录", color=get_color_from_hex(COLORS['text_secondary']),
                                   font_size=sp(10), halign='left', text_size=(Window.width - dp(20), None))
        self.address_label.bind(size=self.address_label.setter('text_size'))
        wallet_card.add_widget(self.address_label)
        
        self.balance_label = Label(text="余额: 0 ATSC", color=get_color_from_hex(COLORS['accent']),
                                   font_size=sp(20), bold=True)
        wallet_card.add_widget(self.balance_label)
        
        self.user_region_label = Label(text="区域: 未登录", color=get_color_from_hex(COLORS['info']),
                                       font_size=sp(12))
        wallet_card.add_widget(self.user_region_label)
        
        self.root.add_widget(wallet_card)
        
        # 按钮行
        button_row = GridLayout(cols=4, size_hint_y=None, height=dp(50), spacing=dp(5))
        
        register_btn = Button(text="注册", background_normal='',
                              background_color=get_color_from_hex(COLORS['accent']))
        register_btn.bind(on_press=self.register_dialog)
        button_row.add_widget(register_btn)
        
        login_btn = Button(text="登录", background_normal='',
                           background_color=get_color_from_hex(COLORS['info']))
        login_btn.bind(on_press=self.login_dialog)
        button_row.add_widget(login_btn)
        
        load_btn = Button(text="加载", background_normal='',
                          background_color=get_color_from_hex(COLORS['primary']))
        load_btn.bind(on_press=self.load_wallet_dialog)
        button_row.add_widget(load_btn)
        
        refresh_btn = Button(text="刷新", background_normal='',
                             background_color=get_color_from_hex(COLORS['primary']))
        refresh_btn.bind(on_press=self.refresh_all)
        button_row.add_widget(refresh_btn)
        
        self.root.add_widget(button_row)
        
        # 标签页
        self.tab_panel = TabbedPanel(size_hint_y=1, do_default_tab=False)
        
        # 区域信息标签页
        region_tab = TabbedPanelItem(text="🌍 区域")
        self.setup_region_tab(region_tab)
        self.tab_panel.add_widget(region_tab)
        
        # 钱包标签页
        wallet_tab = TabbedPanelItem(text="💳 钱包")
        self.setup_wallet_tab(wallet_tab)
        self.tab_panel.add_widget(wallet_tab)
        
        # 商场标签页
        mall_tab = TabbedPanelItem(text="🛒 商场")
        self.setup_mall_tab(mall_tab)
        self.tab_panel.add_widget(mall_tab)
        
        # 订单标签页
        order_tab = TabbedPanelItem(text="📦 订单")
        self.setup_order_tab(order_tab)
        self.tab_panel.add_widget(order_tab)
        
        # 商户标签页
        merchant_tab = TabbedPanelItem(text="🏪 商户")
        self.setup_merchant_tab(merchant_tab)
        self.tab_panel.add_widget(merchant_tab)
        
        # 区域管理标签页（仅区域管理员可见，初始隐藏）
        self.region_mgr_tab = TabbedPanelItem(text="👑 区域管理")
        self.setup_region_mgr_tab(self.region_mgr_tab)
        
        # 聊天标签页
        chat_tab = TabbedPanelItem(text="💬 聊天")
        self.setup_chat_tab(chat_tab)
        self.tab_panel.add_widget(chat_tab)
        
        self.root.add_widget(self.tab_panel)
        
        # 日志区域
        log_scroll = ScrollView(size_hint_y=None, height=dp(100))
        self.log_text = Label(text="", color=get_color_from_hex(COLORS['accent']),
                              font_size=sp(10), halign='left', valign='top',
                              text_size=(Window.width - dp(10), None))
        self.log_text.bind(size=self.log_text.setter('text_size'))
        log_scroll.add_widget(self.log_text)
        self.root.add_widget(log_scroll)
        
        # 启动后台任务
        Clock.schedule_once(lambda dt: self.check_connection(), 1)
        Clock.schedule_interval(lambda dt: self.auto_refresh(), 15)
        
        return self.root
    
    def _update_wallet_rect(self, instance, value):
        self.wallet_rect.pos = instance.pos
        self.wallet_rect.size = instance.size
    
    def setup_region_tab(self, tab):
        """区域信息标签页"""
        layout = BoxLayout(orientation='vertical', padding=dp(5), spacing=dp(5))
        
        refresh_btn = Button(text="🔄 刷新区域列表", size_hint_y=None, height=dp(40),
                             background_normal='', background_color=get_color_from_hex(COLORS['primary']))
        refresh_btn.bind(on_press=lambda x: self.load_regions())
        layout.add_widget(refresh_btn)
        
        self.region_rv = RV()
        self.region_rv.viewclass = 'SelectableLabel'
        self.region_rv.data = []
        layout.add_widget(self.region_rv)
        
        tab.add_widget(layout)
    
    def setup_wallet_tab(self, tab):
        """钱包功能标签页"""
        layout = BoxLayout(orientation='vertical', padding=dp(5), spacing=dp(10))
        
        # 转账区域
        transfer_box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(150),
                                  padding=dp(10), spacing=dp(5))
        
        transfer_box.add_widget(Label(text="转账", font_size=sp(14), color=get_color_from_hex(COLORS['info'])))
        
        self.to_address_input = TextInput(hint_text="接收方地址", multiline=False, size_hint_y=None, height=dp(40))
        transfer_box.add_widget(self.to_address_input)
        
        self.amount_input = TextInput(hint_text="金额(ATSC)", multiline=False, size_hint_y=None, height=dp(40),
                                      input_filter='float')
        transfer_box.add_widget(self.amount_input)
        
        transfer_btn = Button(text="确认转账", size_hint_y=None, height=dp(40),
                              background_normal='', background_color=get_color_from_hex(COLORS['accent']))
        transfer_btn.bind(on_press=self.do_transfer)
        transfer_box.add_widget(transfer_btn)
        
        layout.add_widget(transfer_box)
        
        # 收款区域
        receive_box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(120),
                                padding=dp(10), spacing=dp(5))
        
        receive_box.add_widget(Label(text="收款", font_size=sp(14), color=get_color_from_hex(COLORS['info'])))
        
        self.address_display = Label(text="", color=get_color_from_hex(COLORS['accent']),
                                     font_size=sp(10), halign='left')
        self.address_display.bind(size=self.address_display.setter('text_size'))
        receive_box.add_widget(self.address_display)
        
        copy_btn = Button(text="复制地址", size_hint_y=None, height=dp(40),
                          background_normal='', background_color=get_color_from_hex(COLORS['primary']))
        copy_btn.bind(on_press=self.copy_address)
        receive_box.add_widget(copy_btn)
        
        layout.add_widget(receive_box)
        
        # 兑换区域
        exchange_box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(150),
                                 padding=dp(10), spacing=dp(5))
        
        exchange_box.add_widget(Label(text="兑换ATSC", font_size=sp(14), color=get_color_from_hex(COLORS['info'])))
        
        self.exchange_amount_input = TextInput(hint_text="兑换数量", multiline=False, size_hint_y=None, height=dp(40),
                                               input_filter='float')
        exchange_box.add_widget(self.exchange_amount_input)
        
        self.exchange_preview = Label(text="可获得: 0.00 元", color=get_color_from_hex(COLORS['accent']))
        exchange_box.add_widget(self.exchange_preview)
        
        exchange_btn = Button(text="申请兑换", size_hint_y=None, height=dp(40),
                              background_normal='', background_color=get_color_from_hex(COLORS['primary']))
        exchange_btn.bind(on_press=self.request_exchange)
        exchange_box.add_widget(exchange_btn)
        
        layout.add_widget(exchange_box)
        
        # 交易记录区域
        history_box = BoxLayout(orientation='vertical', padding=dp(5), spacing=dp(5))
        history_box.add_widget(Label(text="交易记录", font_size=sp(14), color=get_color_from_hex(COLORS['info']),
                                     size_hint_y=None, height=dp(30)))
        
        self.history_rv = RV()
        self.history_rv.viewclass = 'SelectableLabel'
        self.history_rv.data = []
        history_box.add_widget(self.history_rv)
        
        layout.add_widget(history_box)
        
        scroll = ScrollView()
        scroll.add_widget(layout)
        tab.add_widget(scroll)
    
    def setup_mall_tab(self, tab):
        """商场标签页"""
        layout = BoxLayout(orientation='vertical', padding=dp(5), spacing=dp(5))
        
        filter_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
        filter_box.add_widget(Label(text="范围:", color=get_color_from_hex(COLORS['text']), size_hint_x=0.2))
        
        self.scope_filter = 'all'
        
        all_btn = Button(text="全部", size_hint_x=0.27, background_normal='',
                         background_color=get_color_from_hex(COLORS['primary']))
        public_btn = Button(text="公共", size_hint_x=0.27, background_normal='',
                            background_color=get_color_from_hex(COLORS['primary']))
        region_btn = Button(text="本区域", size_hint_x=0.27, background_normal='',
                            background_color=get_color_from_hex(COLORS['primary']))
        
        all_btn.bind(on_press=lambda x: self.set_scope_filter('all'))
        public_btn.bind(on_press=lambda x: self.set_scope_filter('public'))
        region_btn.bind(on_press=lambda x: self.set_scope_filter('region'))
        
        filter_box.add_widget(all_btn)
        filter_box.add_widget(public_btn)
        filter_box.add_widget(region_btn)
        layout.add_widget(filter_box)
        
        refresh_btn = Button(text="🔄 刷新商品", size_hint_y=None, height=dp(40),
                             background_normal='', background_color=get_color_from_hex(COLORS['primary']))
        refresh_btn.bind(on_press=lambda x: self.load_products())
        layout.add_widget(refresh_btn)
        
        self.product_rv = RV()
        self.product_rv.viewclass = 'SelectableButton'
        self.product_rv.data = []
        layout.add_widget(self.product_rv)
        
        scroll = ScrollView()
        scroll.add_widget(layout)
        tab.add_widget(scroll)
    
    def setup_order_tab(self, tab):
        """订单标签页"""
        layout = BoxLayout(orientation='vertical', padding=dp(5), spacing=dp(5))
        
        refresh_btn = Button(text="🔄 刷新订单", size_hint_y=None, height=dp(40),
                             background_normal='', background_color=get_color_from_hex(COLORS['primary']))
        refresh_btn.bind(on_press=lambda x: self.load_orders())
        layout.add_widget(refresh_btn)
        
        self.order_rv = RV()
        self.order_rv.viewclass = 'SelectableLabel'
        self.order_rv.data = []
        layout.add_widget(self.order_rv)
        
        tab.add_widget(layout)
    
    def setup_merchant_tab(self, tab):
        """商户标签页"""
        layout = BoxLayout(orientation='vertical', padding=dp(5), spacing=dp(10))
        
        # 商户申请区域
        apply_box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(150),
                              padding=dp(10), spacing=dp(5))
        
        apply_box.add_widget(Label(text="申请成为商户", font_size=sp(14), color=get_color_from_hex(COLORS['info'])))
        
        type_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
        self.merchant_type = 'cloud'
        cloud_btn = Button(text="云端商户", size_hint_x=0.5, background_normal='',
                           background_color=get_color_from_hex(COLORS['primary']))
        region_btn = Button(text="区域商户", size_hint_x=0.5, background_normal='',
                            background_color=get_color_from_hex(COLORS['primary']))
        cloud_btn.bind(on_press=lambda x: self.set_merchant_type('cloud'))
        region_btn.bind(on_press=lambda x: self.set_merchant_type('region'))
        type_box.add_widget(cloud_btn)
        type_box.add_widget(region_btn)
        apply_box.add_widget(type_box)
        
        apply_btn = Button(text="申请成为商户", size_hint_y=None, height=dp(40),
                           background_normal='', background_color=get_color_from_hex(COLORS['accent']))
        apply_btn.bind(on_press=self.apply_merchant)
        apply_box.add_widget(apply_btn)
        
        layout.add_widget(apply_box)
        
        # 添加商品区域
        add_product_box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(250),
                                    padding=dp(10), spacing=dp(5))
        
        add_product_box.add_widget(Label(text="添加商品", font_size=sp(14), color=get_color_from_hex(COLORS['info'])))
        
        self.product_name_input = TextInput(hint_text="商品名称", multiline=False, size_hint_y=None, height=dp(35))
        add_product_box.add_widget(self.product_name_input)
        
        self.product_desc_input = TextInput(hint_text="商品简介", multiline=False, size_hint_y=None, height=dp(35))
        add_product_box.add_widget(self.product_desc_input)
        
        self.product_price_input = TextInput(hint_text="价格(ATSC)", multiline=False, size_hint_y=None, height=dp(35),
                                             input_filter='float')
        add_product_box.add_widget(self.product_price_input)
        
        self.product_type_input = TextInput(hint_text="类型(程序/实物)", multiline=False, size_hint_y=None, height=dp(35))
        add_product_box.add_widget(self.product_type_input)
        
        add_btn = Button(text="提交审核", size_hint_y=None, height=dp(40),
                         background_normal='', background_color=get_color_from_hex(COLORS['primary']))
        add_btn.bind(on_press=self.add_product)
        add_product_box.add_widget(add_btn)
        
        layout.add_widget(add_product_box)
        
        # 我的商品列表
        my_products_box = BoxLayout(orientation='vertical', padding=dp(5), spacing=dp(5))
        my_products_box.add_widget(Label(text="我的商品", font_size=sp(14), color=get_color_from_hex(COLORS['info']),
                                         size_hint_y=None, height=dp(30)))
        
        self.my_products_rv = RV()
        self.my_products_rv.viewclass = 'SelectableLabel'
        self.my_products_rv.data = []
        my_products_box.add_widget(self.my_products_rv)
        
        layout.add_widget(my_products_box)
        
        scroll = ScrollView()
        scroll.add_widget(layout)
        tab.add_widget(scroll)
    
    def setup_region_mgr_tab(self, tab):
        """区域管理标签页"""
        layout = BoxLayout(orientation='vertical', padding=dp(5), spacing=dp(10))
        
        # 区域设置
        settings_box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(200),
                                 padding=dp(10), spacing=dp(5))
        
        settings_box.add_widget(Label(text="区域设置", font_size=sp(14), color=get_color_from_hex(COLORS['info'])))
        
        fee_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
        fee_box.add_widget(Label(text="入驻费:", size_hint_x=0.3))
        self.region_fee_input = TextInput(text="0", multiline=False, size_hint_x=0.4, input_filter='float')
        fee_btn = Button(text="设置", size_hint_x=0.3, background_normal='',
                         background_color=get_color_from_hex(COLORS['primary']))
        fee_btn.bind(on_press=self.set_region_fee)
        fee_box.add_widget(self.region_fee_input)
        fee_box.add_widget(fee_btn)
        settings_box.add_widget(fee_box)
        
        tax_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
        tax_box.add_widget(Label(text="税率(%):", size_hint_x=0.3))
        self.region_tax_input = TextInput(text="5.0", multiline=False, size_hint_x=0.4, input_filter='float')
        tax_btn = Button(text="设置", size_hint_x=0.3, background_normal='',
                         background_color=get_color_from_hex(COLORS['primary']))
        tax_btn.bind(on_press=self.set_region_tax)
        tax_box.add_widget(self.region_tax_input)
        tax_box.add_widget(tax_btn)
        settings_box.add_widget(tax_box)
        
        rate_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
        rate_box.add_widget(Label(text="汇率:", size_hint_x=0.3))
        self.region_rate_input = TextInput(text="1.0", multiline=False, size_hint_x=0.4, input_filter='float')
        rate_btn = Button(text="设置", size_hint_x=0.3, background_normal='',
                          background_color=get_color_from_hex(COLORS['primary']))
        rate_btn.bind(on_press=self.set_region_rate)
        rate_box.add_widget(self.region_rate_input)
        rate_box.add_widget(rate_btn)
        settings_box.add_widget(rate_box)
        
        layout.add_widget(settings_box)
        
        refresh_btn = Button(text="🔄 刷新管理数据", size_hint_y=None, height=dp(40),
                             background_normal='', background_color=get_color_from_hex(COLORS['primary']))
        refresh_btn.bind(on_press=lambda x: self.load_region_management_data())
        layout.add_widget(refresh_btn)
        
        layout.add_widget(Label(text="区域用户", font_size=sp(14), color=get_color_from_hex(COLORS['info']),
                                size_hint_y=None, height=dp(30)))
        self.region_users_rv = RV()
        self.region_users_rv.viewclass = 'SelectableLabel'
        self.region_users_rv.data = []
        layout.add_widget(self.region_users_rv)
        
        layout.add_widget(Label(text="商户申请", font_size=sp(14), color=get_color_from_hex(COLORS['info']),
                                size_hint_y=None, height=dp(30)))
        self.merchant_apps_rv = RV()
        self.merchant_apps_rv.viewclass = 'SelectableButton'
        self.merchant_apps_rv.data = []
        layout.add_widget(self.merchant_apps_rv)
        
        layout.add_widget(Label(text="待审核商品", font_size=sp(14), color=get_color_from_hex(COLORS['info']),
                                size_hint_y=None, height=dp(30)))
        self.pending_products_rv = RV()
        self.pending_products_rv.viewclass = 'SelectableButton'
        self.pending_products_rv.data = []
        layout.add_widget(self.pending_products_rv)
        
        scroll = ScrollView()
        scroll.add_widget(layout)
        tab.add_widget(scroll)
    
    def setup_chat_tab(self, tab):
        """聊天标签页"""
        layout = BoxLayout(orientation='vertical', padding=dp(5), spacing=dp(5))
        
        layout.add_widget(Label(text="好友列表", font_size=sp(14), color=get_color_from_hex(COLORS['info']),
                                size_hint_y=None, height=dp(30)))
        
        self.friends_rv = RV()
        self.friends_rv.viewclass = 'SelectableButton'
        self.friends_rv.data = []
        layout.add_widget(self.friends_rv)
        
        add_friend_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
        self.add_friend_input = TextInput(hint_text="对方用户名", multiline=False)
        add_btn = Button(text="添加好友", background_normal='', size_hint_x=0.3,
                         background_color=get_color_from_hex(COLORS['primary']))
        add_btn.bind(on_press=self.send_friend_request)
        add_friend_box.add_widget(self.add_friend_input)
        add_friend_box.add_widget(add_btn)
        layout.add_widget(add_friend_box)
        
        layout.add_widget(Label(text="好友请求", font_size=sp(12), color=get_color_from_hex(COLORS['info']),
                                size_hint_y=None, height=dp(25)))
        
        self.friend_requests_rv = RV()
        self.friend_requests_rv.viewclass = 'SelectableButton'
        self.friend_requests_rv.data = []
        layout.add_widget(self.friend_requests_rv)
        
        layout.add_widget(Label(text="聊天", font_size=sp(14), color=get_color_from_hex(COLORS['info']),
                                size_hint_y=None, height=dp(30)))
        
        self.chat_display = Label(text="选择好友开始聊天", color=get_color_from_hex(COLORS['text_secondary']),
                                  font_size=sp(12), halign='left', valign='top', size_hint_y=0.4)
        self.chat_display.bind(size=self.chat_display.setter('text_size'))
        layout.add_widget(self.chat_display)
        
        chat_input_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
        self.chat_input = TextInput(hint_text="输入消息", multiline=False)
        send_btn = Button(text="发送", background_normal='', size_hint_x=0.2,
                          background_color=get_color_from_hex(COLORS['accent']))
        send_btn.bind(on_press=self.send_chat_message)
        chat_input_box.add_widget(self.chat_input)
        chat_input_box.add_widget(send_btn)
        layout.add_widget(chat_input_box)
        
        tab.add_widget(layout)
    
    # ==================== 辅助方法 ====================
    
    def set_scope_filter(self, scope):
        self.scope_filter = scope
        self.load_products()
    
    def set_merchant_type(self, mtype):
        self.merchant_type = mtype
    
    def start_task_worker(self):
        def worker():
            while self.running:
                try:
                    task = self.task_queue.get(timeout=0.5)
                    if task:
                        func, args, kwargs = task
                        try:
                            func(*args, **kwargs)
                        except:
                            pass
                except:
                    pass
        self.task_queue = queue.Queue()
        threading.Thread(target=worker, daemon=True).start()
    
    def async_task(self, func, *args, **kwargs):
        self.task_queue.put((func, args, kwargs))
    
    def load_config(self):
        default_config = {
            'cloud_host': '127.0.0.1',
            'wallet_port': 1256,
            'chat_port': 4567,
            'update_port': 2100,
            'business_port': 3000
        }
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.cloud_host = config.get('cloud_host', default_config['cloud_host'])
                    self.wallet_port = config.get('wallet_port', default_config['wallet_port'])
                    self.chat_port = config.get('chat_port', default_config['chat_port'])
                    self.update_port = config.get('update_port', default_config['update_port'])
                    self.business_port = config.get('business_port', default_config['business_port'])
            else:
                self.cloud_host = default_config['cloud_host']
                self.wallet_port = default_config['wallet_port']
                self.chat_port = default_config['chat_port']
                self.update_port = default_config['update_port']
                self.business_port = default_config['business_port']
                self.save_config()
        except:
            self.cloud_host = default_config['cloud_host']
            self.wallet_port = default_config['wallet_port']
            self.chat_port = default_config['chat_port']
            self.update_port = default_config['update_port']
            self.business_port = default_config['business_port']
        
        self.wallet_api = f"http://{self.cloud_host}:{self.wallet_port}/api"
        self.chat_api = f"http://{self.cloud_host}:{self.chat_port}/api"
        self.update_api = f"http://{self.cloud_host}:{self.update_port}/api"
        self.business_api = f"http://{self.cloud_host}:{self.business_port}/api"
    
    def save_config(self):
        config = {
            'cloud_host': self.cloud_host,
            'wallet_port': self.wallet_port,
            'chat_port': self.chat_port,
            'update_port': self.update_port,
            'business_port': self.business_port
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except:
            pass
    
    def get_headers(self):
        if self.current_token:
            return {'Authorization': f'Bearer {self.current_token}'}
        return {}
    
    def save_wallet_to_file(self, address, name, token):
        wallet_data = {'address': address, 'name': name, 'token': token, 'created_at': datetime.now().isoformat()}
        filename = os.path.join(self.wallets_dir, f"wallet_{address[:8]}.atsc")
        try:
            with open(filename, 'w') as f:
                json.dump(wallet_data, f, indent=2)
        except:
            pass
        return filename
    
    def load_wallet_from_file(self, filename):
        with open(filename, 'r') as f:
            return json.load(f)
    
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        current_text = self.log_text.text
        new_text = f"[{timestamp}] {message}\n" + current_text
        if len(new_text) > 5000:
            new_text = new_text[:5000]
        Clock.schedule_once(lambda dt: setattr(self.log_text, 'text', new_text), 0)
    
    def show_message(self, title, message, is_error=False):
        popup = MessagePopup(title, message)
        Clock.schedule_once(lambda dt: popup.open(), 0)
    
    def show_input_dialog(self, title, hint, callback):
        dialog = InputDialog(title, hint, callback)
        Clock.schedule_once(lambda dt: dialog.open(), 0)
    
    def update_user_info(self, data):
        if data.get('role'):
            self.current_role = data.get('role')
            role_text = {'user': '普通用户', 'merchant': '商户', 'region_manager': '区域管理员'}.get(self.current_role, self.current_role)
            Clock.schedule_once(lambda dt: setattr(self.role_label, 'text', f"身份: {role_text}"), 0)
            if self.current_role == 'region_manager':
                self.show_region_management_tab(True)
                self.load_managed_region()
            else:
                self.show_region_management_tab(False)
        if data.get('region'):
            self.current_region = data.get('region')
            Clock.schedule_once(lambda dt: setattr(self.user_region_label, 'text', f"区域: {self.current_region}"), 0)
        if data.get('balance') is not None:
            self.cache['balance'] = data['balance']
            Clock.schedule_once(lambda dt: setattr(self.balance_label, 'text', f"余额: {data['balance']:.6f} ATSC"), 0)
    
    def show_region_management_tab(self, show):
        if show:
            if self.region_mgr_tab not in self.tab_panel.tab_list:
                self.tab_panel.add_widget(self.region_mgr_tab)
                self.load_region_management_data()
        else:
            if self.region_mgr_tab in self.tab_panel.tab_list:
                self.tab_panel.remove_widget(self.region_mgr_tab)
    
    def load_managed_region(self):
        if not self.current_address or self.current_role != 'region_manager':
            return
        def do_load():
            try:
                response = requests.get(f"{self.wallet_api}/get_region_by_manager", 
                                       headers=self.get_headers(), timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result and result.get('name'):
                        self.managed_region = result
                        self.log(f"🌍 您是 {result.get('display_name')} 的区域管理员")
                        self.load_region_management_data()
            except Exception as e:
                self.log(f"❌ 加载管理区域失败: {e}")
        threading.Thread(target=do_load).start()
    
    def load_region_management_data(self):
        self.refresh_region_users()
        self.refresh_merchant_apps()
        self.refresh_pending_products()
        self.load_region_settings()
    
    def load_region_settings(self):
        if not self.managed_region:
            return
        def do_load():
            try:
                response = requests.get(f"{self.wallet_api}/get_region_settings", 
                                       params={'region': self.managed_region['name']},
                                       headers=self.get_headers(), timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    Clock.schedule_once(lambda dt: self.update_region_settings_display(result), 0)
            except:
                pass
        threading.Thread(target=do_load).start()
    
    def update_region_settings_display(self, settings):
        self.region_fee_input.text = str(settings.get('merchant_fee', 0))
        self.region_tax_input.text = str(settings.get('tax_rate', 5.0))
        self.region_rate_input.text = str(settings.get('atsc_rate', 1.0))
    
    def refresh_region_users(self):
        def do_load():
            try:
                response = requests.get(f"{self.wallet_api}/get_users", 
                                       headers=self.get_headers(), timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    users = result.get('users', [])
                    data = [{'text': f"{u[1]} | {u[2]} | {u[4]:.2f} ATSC"} for u in users[:20]]
                    Clock.schedule_once(lambda dt: setattr(self.region_users_rv, 'data', data), 0)
            except:
                pass
        threading.Thread(target=do_load).start()
    
    def refresh_merchant_apps(self):
        def do_load():
            try:
                response = requests.get(f"{self.wallet_api}/get_merchant_applications", 
                                       headers=self.get_headers(), timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    apps = result.get('applications', [])
                    data = [{'text': f"{app['user_name']} (QQ:{app['qq']}) - 待审核"} for app in apps]
                    Clock.schedule_once(lambda dt: setattr(self.merchant_apps_rv, 'data', data), 0)
            except:
                pass
        threading.Thread(target=do_load).start()
    
    def refresh_pending_products(self):
        def do_load():
            try:
                response = requests.get(f"{self.wallet_api}/get_pending_products", 
                                       headers=self.get_headers(), timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    products = result.get('products', [])
                    data = [{'text': f"{p['merchant_name']}: {p['name']} - {p['price']} ATSC"} for p in products]
                    Clock.schedule_once(lambda dt: setattr(self.pending_products_rv, 'data', data), 0)
            except:
                pass
        threading.Thread(target=do_load).start()
    
    def set_region_fee(self, instance):
        if not self.managed_region:
            self.show_message("警告", "您不是任何区域的管理员")
            return
        try:
            fee = float(self.region_fee_input.text)
        except:
            self.show_message("错误", "请输入有效数字")
            return
        def do_set():
            try:
                response = requests.post(f"{self.wallet_api}/set_region_merchant_fee", 
                                        json={'region': self.managed_region['name'], 'fee': fee},
                                        headers=self.get_headers(), timeout=10)
                if response.json().get('success'):
                    self.log(f"✅ 入驻费已设置为 {fee} ATSC")
                    self.show_message("成功", f"入驻费已设置为 {fee} ATSC")
            except:
                pass
        threading.Thread(target=do_set).start()
    
    def set_region_tax(self, instance):
        if not self.managed_region:
            self.show_message("警告", "您不是任何区域的管理员")
            return
        try:
            tax_rate = float(self.region_tax_input.text)
        except:
            self.show_message("错误", "请输入有效数字")
            return
        def do_set():
            try:
                response = requests.post(f"{self.wallet_api}/set_region_tax_rate", 
                                        json={'region': self.managed_region['name'], 'tax_rate': tax_rate},
                                        headers=self.get_headers(), timeout=10)
                if response.json().get('success'):
                    self.log(f"✅ 税率已设置为 {tax_rate}%")
                    self.show_message("成功", f"税率已设置为 {tax_rate}%")
            except:
                pass
        threading.Thread(target=do_set).start()
    
    def set_region_rate(self, instance):
        if not self.managed_region:
            self.show_message("警告", "您不是任何区域的管理员")
            return
        try:
            atsc_rate = float(self.region_rate_input.text)
        except:
            self.show_message("错误", "请输入有效数字")
            return
        def do_set():
            try:
                response = requests.post(f"{self.wallet_api}/set_region_atsc_rate", 
                                        json={'region': self.managed_region['name'], 'atsc_rate': atsc_rate},
                                        headers=self.get_headers(), timeout=10)
                if response.json().get('success'):
                    self.log(f"✅ 汇率已设置为 1 ATSC = {atsc_rate} 元")
                    self.show_message("成功", f"汇率已设置为 1 ATSC = {atsc_rate} 元")
            except:
                pass
        threading.Thread(target=do_set).start()
    
    def load_regions(self):
        def do_load():
            try:
                response = requests.get(f"{self.wallet_api}/get_regions", timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        regions = result.get('regions', [])
                        data = [{'text': f"{r['display_name']} | 区长:{r.get('manager_name', '无')} | {r['user_count']}人"} for r in regions]
                        Clock.schedule_once(lambda dt: setattr(self.region_rv, 'data', data), 0)
                        self.log(f"✅ 成功加载 {len(regions)} 个区域")
            except Exception as e:
                self.log(f"❌ 加载区域失败: {e}")
        threading.Thread(target=do_load).start()
    
    def load_products(self):
        if not self.current_address:
            return
        def do_load():
            try:
                response = requests.get(f"{self.wallet_api}/get_products", 
                                       headers=self.get_headers(), timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        products = result.get('products', [])
                        data = []
                        for p in products:
                            if p.get('status') == 'approved':
                                if self.scope_filter == 'public' and p.get('scope') != 'public':
                                    continue
                                if self.scope_filter == 'region' and p.get('scope') != 'region':
                                    continue
                                data.append({'text': f"{p['name']} | {p['price']} ATSC | {p['merchant_name']}"})
                        Clock.schedule_once(lambda dt: setattr(self.product_rv, 'data', data), 0)
                        self.log(f"✅ 加载 {len(data)} 个商品")
            except Exception as e:
                self.log(f"❌ 加载商品失败: {e}")
        threading.Thread(target=do_load).start()
    
    def load_orders(self):
        if not self.current_address:
            return
        def do_load():
            try:
                response = requests.get(f"{self.wallet_api}/get_orders", 
                                       params={'role': 'buyer'},
                                       headers=self.get_headers(), timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        orders = result.get('orders', [])
                        status_text = {'pending': '待处理', 'accepted': '已接受', 'rejected': '已拒绝'}
                        data = [{'text': f"{o['product_name']} | {o['amount']} ATSC | {status_text.get(o['status'], o['status'])}"} for o in orders]
                        Clock.schedule_once(lambda dt: setattr(self.order_rv, 'data', data), 0)
                        self.log(f"✅ 加载 {len(orders)} 个订单")
            except Exception as e:
                self.log(f"❌ 加载订单失败: {e}")
        threading.Thread(target=do_load).start()
    
    def load_my_products(self):
        if not self.current_address:
            return
        def do_load():
            try:
                response = requests.get(f"{self.wallet_api}/get_my_products", 
                                       headers=self.get_headers(), timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        products = result.get('products', [])
                        status_text = {'pending': '审核中', 'approved': '已上架', 'rejected': '已拒绝'}
                        data = [{'text': f"{p['name']} | {p['price']} ATSC | {status_text.get(p['status'], p['status'])}"} for p in products]
                        Clock.schedule_once(lambda dt: setattr(self.my_products_rv, 'data', data), 0)
            except Exception as e:
                self.log(f"❌ 加载我的商品失败: {e}")
        threading.Thread(target=do_load).start()
    
    def load_friends(self):
        if not self.current_address:
            return
        def do_load():
            try:
                response = requests.get(f"{self.chat_api}/get_friends", 
                                       headers=self.get_headers(), timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        self.friends = result.get('friends', [])
                        data = [{'text': f"{'🟢' if f.get('online') else '⚫'} {f['name']}"} for f in self.friends]
                        Clock.schedule_once(lambda dt: setattr(self.friends_rv, 'data', data), 0)
            except:
                pass
        threading.Thread(target=do_load).start()
    
    def load_friend_requests(self):
        if not self.current_address:
            return
        def do_load():
            try:
                response = requests.get(f"{self.chat_api}/get_friend_requests",
                                       headers=self.get_headers(), timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        requests_list = result.get('requests', [])
                        data = [{'text': f"📨 {r['name']} (QQ:{r.get('qq', '未知')})"} for r in requests_list]
                        Clock.schedule_once(lambda dt: setattr(self.friend_requests_rv, 'data', data), 0)
            except:
                pass
        threading.Thread(target=do_load).start()
    
    def send_friend_request(self, instance):
        if not self.current_address:
            self.show_message("警告", "请先登录")
            return
        to_name = self.add_friend_input.text.strip()
        if not to_name:
            self.show_message("错误", "请输入对方用户名")
            return
        def do_send():
            try:
                response = requests.post(f"{self.chat_api}/send_friend_request",
                                        json={'to_name': to_name},
                                        headers=self.get_headers(), timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        self.log(f"✅ {result.get('message')}")
                        self.show_message("成功", result.get('message', '好友请求已发送'))
                        Clock.schedule_once(lambda dt: setattr(self.add_friend_input, 'text', ''), 0)
                    else:
                        self.show_message("错误", result.get('message', '发送失败'))
            except Exception as e:
                self.show_message("错误", f"发送失败: {e}")
        threading.Thread(target=do_send).start()
    
    def send_chat_message(self, instance):
        if not self.current_chat_friend:
            self.show_message("警告", "请先选择聊天对象")
            return
        message = self.chat_input.text.strip()
        if not message:
            return
        Clock.schedule_once(lambda dt: setattr(self.chat_input, 'text', ''), 0)
        current_text = self.chat_display.text
        new_text = f"[我] {datetime.now().strftime('%H:%M:%S')}\n{message}\n\n" + current_text
        Clock.schedule_once(lambda dt: setattr(self.chat_display, 'text', new_text), 0)
        def do_send():
            try:
                response = requests.post(f"{self.chat_api}/send_message",
                                        json={'to': self.current_chat_friend['address'], 'message': message},
                                        headers=self.get_headers(), timeout=10)
            except:
                pass
        threading.Thread(target=do_send).start()
    
    def on_websocket_message(self, data):
        msg_type = data.get('type')
        if msg_type == 'chat':
            from_name = data.get('from_name', '未知')
            message = data.get('message', '')
            current_text = self.chat_display.text
            new_text = f"[{from_name}] {datetime.now().strftime('%H:%M:%S')}\n{message}\n\n" + current_text
            Clock.schedule_once(lambda dt: setattr(self.chat_display, 'text', new_text), 0)
            self.log(f"💬 收到 {from_name} 的消息")
        elif msg_type == 'role_update':
            new_role = data.get('role')
            role_text = {'user': '普通用户', 'merchant': '商户', 'region_manager': '区域管理员'}.get(new_role, new_role)
            Clock.schedule_once(lambda dt: setattr(self.role_label, 'text', f"身份: {role_text}"), 0)
            self.current_role = new_role
            self.log(f"🔔 身份已更新为: {role_text}")
            if new_role == 'region_manager':
                self.show_region_management_tab(True)
                self.load_managed_region()
            else:
                self.show_region_management_tab(False)
        elif msg_type == 'balance_update':
            new_balance = data.get('balance')
            if new_balance is not None:
                self.cache['balance'] = new_balance
                Clock.schedule_once(lambda dt: setattr(self.balance_label, 'text', f"余额: {new_balance:.6f} ATSC"), 0)
                self.log(f"💰 余额已更新: {new_balance:.6f} ATSC")
        elif msg_type == 'auth_success':
            self.log(f"✅ WebSocket认证成功")
            Clock.schedule_once(lambda dt: setattr(self.online_label, 'text', "🟢 在线"), 0)
            if data.get('role'):
                self.update_user_info(data)
            self.load_friends()
            self.load_friend_requests()
    
    def refresh_all(self, instance):
        self.refresh_balance()
        self.refresh_rate()
        self.refresh_transactions()
        self.load_regions()
        self.load_products()
        self.load_orders()
        self.load_my_products()
        self.load_friends()
        self.load_friend_requests()
    
    def refresh_balance(self):
        if not self.current_address:
            return
        def task():
            try:
                response = requests.get(f"{self.wallet_api}/get_balance", 
                                       headers=self.get_headers(), timeout=5)
                if response.status_code == 200:
                    result = response.json()
                    balance = result.get('balance', 0)
                    self.cache['balance'] = balance
                    Clock.schedule_once(lambda dt: setattr(self.balance_label, 'text', f"余额: {balance:.6f} ATSC"), 0)
            except:
                pass
        threading.Thread(target=task).start()
    
    def refresh_rate(self):
        def task():
            try:
                response = requests.get(f"{self.wallet_api}/get_rate", timeout=5)
                if response.status_code == 200:
                    rate = response.json().get('rate', 1.0)
                    self.cache['rate'] = rate
                    Clock.schedule_once(lambda dt: setattr(self.rate_label, 'text', f"1 ATSC = {rate:.2f}元"), 0)
            except:
                pass
        threading.Thread(target=task).start()
    
    def refresh_transactions(self):
        if not self.current_address:
            return
        def task():
            try:
                response = requests.get(f"{self.wallet_api}/get_transactions", 
                                       headers=self.get_headers(), timeout=5)
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        txs = result.get('transactions', [])
                        data = []
                        for tx in txs[:20]:
                            if tx.get('from') == self.current_address:
                                amount = f"-{tx.get('amount', 0):.4f}"
                            else:
                                amount = f"+{tx.get('amount', 0):.4f}"
                            data.append({'text': f"{tx.get('time', '')[:16]} {amount}"})
                        Clock.schedule_once(lambda dt: setattr(self.history_rv, 'data', data), 0)
            except:
                pass
        threading.Thread(target=task).start()
    
    def do_transfer(self, instance):
        if not self.current_address:
            self.show_message("警告", "请先登录")
            return
        to_addr = self.to_address_input.text.strip()
        try:
            amount = float(self.amount_input.text)
        except:
            self.show_message("错误", "请输入有效金额")
            return
        if not to_addr:
            self.show_message("错误", "请输入接收地址")
            return
        
        def task():
            try:
                response = requests.post(f"{self.wallet_api}/send", json={
                    'to': to_addr, 'amount': amount
                }, headers=self.get_headers(), timeout=10)
                result = response.json()
                if result.get('success'):
                    self.log(f"✅ 转账成功: {amount} ATSC")
                    Clock.schedule_once(lambda dt: setattr(self.to_address_input, 'text', ''), 0)
                    Clock.schedule_once(lambda dt: setattr(self.amount_input, 'text', ''), 0)
                    self.refresh_balance()
                    self.refresh_transactions()
                    self.show_message("成功", "转账成功！")
                else:
                    self.show_message("错误", result.get('message', '转账失败'))
            except Exception as e:
                self.show_message("错误", f"转账失败: {e}")
        threading.Thread(target=task).start()
    
    def request_exchange(self, instance):
        if not self.current_address:
            self.show_message("警告", "请先登录")
            return
        try:
            amount = float(self.exchange_amount_input.text)
            if amount <= 0:
                self.show_message("错误", "请输入有效数量")
                return
        except:
            self.show_message("错误", "请输入有效数量")
            return
        
        def do_request():
            try:
                response = requests.post(f"{self.wallet_api}/request_exchange", json={
                    'atsc_amount': amount
                }, headers=self.get_headers(), timeout=10)
                result = response.json()
                if result.get('success'):
                    self.log(f"✅ 兑换申请已提交: {amount} ATSC")
                    Clock.schedule_once(lambda dt: setattr(self.exchange_amount_input, 'text', ''), 0)
                    self.refresh_balance()
                    self.show_message("成功", "兑换申请已提交")
                else:
                    self.show_message("错误", result.get('message', '申请失败'))
            except Exception as e:
                self.show_message("错误", f"申请失败: {e}")
        threading.Thread(target=do_request).start()
    
    def apply_merchant(self, instance):
        if not self.current_address:
            self.show_message("警告", "请先登录")
            return
        region = None if self.merchant_type == 'cloud' else self.current_region
        
        def do_apply():
            try:
                response = requests.post(f"{self.wallet_api}/apply_merchant", json={
                    'fee_paid': True, 'region': region
                }, headers=self.get_headers(), timeout=10)
                result = response.json()
                if result.get('success'):
                    self.log(f"✅ 商户申请已提交")
                    self.show_message("成功", "商户申请已提交，等待审核")
                else:
                    self.show_message("错误", result.get('message', '申请失败'))
            except Exception as e:
                self.show_message("错误", f"申请失败: {e}")
        threading.Thread(target=do_apply).start()
    
    def add_product(self, instance):
        if not self.current_address:
            self.show_message("警告", "请先登录")
            return
        name = self.product_name_input.text.strip()
        desc = self.product_desc_input.text.strip()
        try:
            price = float(self.product_price_input.text)
        except:
            self.show_message("错误", "请输入有效价格")
            return
        ptype = self.product_type_input.text.strip()
        
        if not name or not desc or not ptype:
            self.show_message("错误", "请填写完整信息")
            return
        
        def do_add():
            try:
                data = {
                    'name': name,
                    'description': desc,
                    'price': price,
                    'type': ptype,
                    'scope': 'region',
                    'region': self.current_region,
                    'address': '',
                    'phone': ''
                }
                response = requests.post(f"{self.wallet_api}/add_product", data=data, 
                                        headers=self.get_headers(), timeout=30)
                result = response.json()
                if result.get('success'):
                    self.log(f"✅ 商品已提交审核: {name}")
                    Clock.schedule_once(lambda dt: setattr(self.product_name_input, 'text', ''), 0)
                    Clock.schedule_once(lambda dt: setattr(self.product_desc_input, 'text', ''), 0)
                    Clock.schedule_once(lambda dt: setattr(self.product_price_input, 'text', ''), 0)
                    Clock.schedule_once(lambda dt: setattr(self.product_type_input, 'text', ''), 0)
                    self.show_message("成功", "商品已提交审核")
                else:
                    self.show_message("错误", result.get('message', '添加失败'))
            except Exception as e:
                self.show_message("错误", f"添加失败: {e}")
        threading.Thread(target=do_add).start()
    
    def copy_address(self, instance):
        if self.current_address:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(self.current_address)
            self.log("📋 地址已复制")
            self.show_message("成功", "地址已复制")
    
    def register_dialog(self, instance):
        self.show_input_dialog("注册", "用户名", self.register_step2)
    
    def register_step2(self, username):
        if not username:
            return
        self.temp_username = username
        self.show_input_dialog("注册", "QQ号", self.register_step3)
    
    def register_step3(self, qq):
        if not qq:
            return
        self.temp_qq = qq
        self.show_input_dialog("注册", "密码", self.register_step4)
    
    def register_step4(self, password):
        if not password:
            return
        self.temp_password = password
        self.show_input_dialog("注册", "微信号", self.register_step5)
    
    def register_step5(self, wechat):
        if not wechat:
            return
        self.temp_wechat = wechat
        self.show_input_dialog("注册", "选择区域(default)", self.register_step6)
    
    def register_step6(self, region):
        region = region or 'default'
        
        def do_register():
            try:
                response = requests.post(f"{self.wallet_api}/register", json={
                    'name': self.temp_username, 'qq': self.temp_qq, 'password': self.temp_password,
                    'wechat_id': self.temp_wechat, 'wechat_qrcode': '', 'region': region
                }, timeout=10)
                result = response.json()
                if result.get('success'):
                    self.current_address = result['address']
                    self.current_name = self.temp_username
                    self.current_region = region
                    self.current_token = result.get('token')
                    
                    self.save_wallet_to_file(self.current_address, self.temp_username, self.current_token)
                    
                    Clock.schedule_once(lambda dt: setattr(self.name_label, 'text', f"钱包: {self.temp_username}"), 0)
                    Clock.schedule_once(lambda dt: setattr(self.address_label, 'text', f"地址: {self.current_address[:16]}..."), 0)
                    Clock.schedule_once(lambda dt: setattr(self.address_display, 'text', self.current_address), 0)
                    Clock.schedule_once(lambda dt: setattr(self.user_region_label, 'text', f"区域: {region}"), 0)
                    
                    self.chat_client.connect(self.current_address, self.current_token)
                    
                    self.log(f"✅ 注册成功: {self.temp_username}")
                    self.show_message("成功", f"注册成功！\n地址: {self.current_address}")
                    self.refresh_balance()
                    self.refresh_rate()
                else:
                    self.show_message("错误", result.get('message', '注册失败'))
            except Exception as e:
                self.show_message("错误", f"注册失败: {e}")
        
        threading.Thread(target=do_register).start()
    
    def login_dialog(self, instance):
        self.show_input_dialog("登录", "用户名", self.login_step2)
    
    def login_step2(self, username):
        if not username:
            return
        self.temp_username = username
        self.show_input_dialog("登录", "密码", self.login_step3)
    
    def login_step3(self, password):
        if not password:
            return
        
        def do_login():
            try:
                response = requests.post(f"{self.wallet_api}/login", json={
                    'name': self.temp_username, 'password': password
                }, timeout=10)
                result = response.json()
                if result.get('success'):
                    self.current_address = result['address']
                    self.current_name = self.temp_username
                    self.current_region = result.get('region', 'default')
                    self.current_role = result.get('role', 'user')
                    self.current_token = result.get('token')
                    
                    self.save_wallet_to_file(self.current_address, self.temp_username, self.current_token)
                    
                    role_text = {'user': '普通用户', 'merchant': '商户', 'region_manager': '区域管理员'}.get(self.current_role, self.current_role)
                    
                    Clock.schedule_once(lambda dt: setattr(self.name_label, 'text', f"钱包: {self.temp_username}"), 0)
                    Clock.schedule_once(lambda dt: setattr(self.address_label, 'text', f"地址: {self.current_address[:16]}..."), 0)
                    Clock.schedule_once(lambda dt: setattr(self.address_display, 'text', self.current_address), 0)
                    Clock.schedule_once(lambda dt: setattr(self.user_region_label, 'text', f"区域: {self.current_region}"), 0)
                    Clock.schedule_once(lambda dt: setattr(self.role_label, 'text', f"身份: {role_text}"), 0)
                    
                    self.chat_client.connect(self.current_address, self.current_token)
                    
                    self.log(f"✅ 登录成功: {self.temp_username}")
                    self.show_message("成功", f"登录成功！")
                    
                    self.refresh_balance()
                    self.refresh_rate()
                    self.refresh_transactions()
                    self.load_regions()
                    self.load_products()
                    self.load_orders()
                    self.load_my_products()
                    self.load_friends()
                    self.load_friend_requests()
                    
                    if self.current_role == 'region_manager':
                        self.show_region_management_tab(True)
                        self.load_managed_region()
                    else:
                        self.show_region_management_tab(False)
                else:
                    self.show_message("错误", result.get('message', '登录失败'))
            except Exception as e:
                self.show_message("错误", f"登录失败: {e}")
        
        threading.Thread(target=do_login).start()
    
    def load_wallet_dialog(self, instance):
        def select_file():
            files = os.listdir(self.wallets_dir)
            if files:
                filename = os.path.join(self.wallets_dir, files[0])
                self.load_wallet_from_file_and_login(filename)
            else:
                self.show_message("提示", "没有找到本地钱包文件，请先注册或登录")
        
        threading.Thread(target=select_file).start()
    
    def load_wallet_from_file_and_login(self, filename):
        try:
            data = self.load_wallet_from_file(filename)
            self.current_address = data['address']
            self.current_name = data['name']
            self.current_token = data.get('token')
            
            try:
                response = requests.get(f"{self.wallet_api}/verify", headers=self.get_headers(), timeout=5)
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        user_info = result.get('user', {})
                        self.current_role = user_info.get('role', 'user')
                        self.current_region = user_info.get('region', 'default')
                    else:
                        self.login_dialog(None)
                        return
                else:
                    self.login_dialog(None)
                    return
            except:
                self.login_dialog(None)
                return
            
            role_text = {'user': '普通用户', 'merchant': '商户', 'region_manager': '区域管理员'}.get(self.current_role, self.current_role)
            
            Clock.schedule_once(lambda dt: setattr(self.name_label, 'text', f"钱包: {self.current_name}"), 0)
            Clock.schedule_once(lambda dt: setattr(self.address_label, 'text', f"地址: {self.current_address[:16]}..."), 0)
            Clock.schedule_once(lambda dt: setattr(self.address_display, 'text', self.current_address), 0)
            Clock.schedule_once(lambda dt: setattr(self.user_region_label, 'text', f"区域: {self.current_region}"), 0)
            Clock.schedule_once(lambda dt: setattr(self.role_label, 'text', f"身份: {role_text}"), 0)
            
            self.chat_client.connect(self.current_address, self.current_token)
            
            self.refresh_balance()
            self.refresh_rate()
            self.refresh_transactions()
            self.load_regions()
            self.load_products()
            self.load_orders()
            self.load_my_products()
            self.load_friends()
            self.load_friend_requests()
            self.log(f"✅ 登录成功: {self.current_name}")
            self.show_message("成功", f"登录成功！")
            
            if self.current_role == 'region_manager':
                self.show_region_management_tab(True)
                self.load_managed_region()
            else:
                self.show_region_management_tab(False)
        except Exception as e:
            self.show_message("错误", f"加载钱包失败: {e}")
    
    def show_settings(self, instance):
        self.show_input_dialog("云平台设置", "IP地址", self.set_cloud_host)
    
    def set_cloud_host(self, host):
        if host:
            self.cloud_host = host
            self.wallet_api = f"http://{self.cloud_host}:{self.wallet_port}/api"
            self.chat_api = f"http://{self.cloud_host}:{self.chat_port}/api"
            self.update_api = f"http://{self.cloud_host}:{self.update_port}/api"
            self.business_api = f"http://{self.cloud_host}:{self.business_port}/api"
            self.save_config()
            self.log(f"✅ 设置已更新: {self.cloud_host}")
            self.show_message("成功", "设置已保存")
            self.check_connection()
    
    def check_connection(self):
        try:
            response = requests.get(f"{self.wallet_api}/get_rate", timeout=2)
            if response.status_code == 200:
                Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', f"● 已连接 {self.cloud_host}"), 0)
                self.log(f"✅ 已连接到云平台")
                self.refresh_rate()
                self.load_regions()
            else:
                Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', "● 连接失败"), 0)
        except:
            Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', "● 连接失败"), 0)
    
    def auto_refresh(self):
        if self.current_address:
            self.refresh_balance()
            self.refresh_transactions()
            self.load_orders()
            self.load_my_products()
            self.load_friends()


def main():
    ATSCWalletApp().run()


if __name__ == "__main__":
    main()