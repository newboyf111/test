#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无尽冬日 (Wujindongri) - GUI 界面
"""

import tkinter as tk
from tkinter import ttk, messagebox
import win32gui
import threading
import time
import random
from src.mining import MultiWindowMiningManager
from src.window_manager import WindowManager
from src.recording import RecordingModule
from src.Protective_casing import ProtectiveCasing
from src.snowfield_weapon_league import SnowfieldWeaponLeague
from src.daily_task import DailyTaskModule

try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None


class WujindongriGUI:
    """无尽冬日 GUI 界面类"""
    
    def __init__(self):
        """初始化 GUI"""
        self.root = tk.Tk()
        self.root.title("无尽冬日 - 挂机系统")
        self.root.geometry("800x1100")
        self.root.resizable(True, True)
        # 设置窗口置顶
        self.root.attributes('-topmost', True)
        
        # 设置窗口图标（可选）
        try:
            self.root.iconbitmap(default='icon.ico')
        except tk.TclError:
            # 图标文件不存在时静默忽略
            pass
        
        # 初始化模块
        self.mining_manager = MultiWindowMiningManager()
        self.window_manager = WindowManager()
        self.recording_module = RecordingModule(self)
        self.protective_casing = ProtectiveCasing(mining_manager=self.mining_manager)
        self.snowfield_league = None  # 雪域兵器联赛模块
        self.daily_task_module = None  # 每日任务模块
        self.selected_window = None
        self.timer_minutes = 0
        self.countdown_running = False
        self.active_windows_label = None
        self.active_windows_label_activated = None
        self.active_windows_label_mining = None
        self.active_windows_label_recording = None
        self.active_windows_label_shield = None
        self.active_windows_label_snowfield = None
        self.active_windows_label_daily_task = None
        self.window_listbox_hwnd_map = {}  # 列表框索引到 hwnd 的映射
        self.ocr_loaded = False  # OCR 是否加载完成
        self.current_mining_hwnd = None  # 当前挖矿窗口句柄
        
        # 创建启动进度条界面
        self._create_loading_screen()
        
        # 在后台线程中初始化 OCR
        threading.Thread(target=self._init_ocr_in_background, daemon=True).start()
        
    def create_widgets(self):
        """创建界面组件"""
        # 主标题
        self.title_label = ttk.Label(
            self.root, 
            text="无尽冬日挂机系统", 
            font=("Microsoft YaHei", 16, "bold")
        )
        self.title_label.pack(pady=20)
        
        # 窗口选择区域
        window_frame = ttk.LabelFrame(self.root, text="窗口管理", padding=10)
        window_frame.pack(fill="x", padx=20, pady=10)
        
        # 窗口列表
        list_frame = ttk.Frame(window_frame)
        list_frame.pack(fill="x", pady=10)
        
        self.window_listbox = tk.Listbox(
            list_frame,
            width=80,
            height=8,
            font=("Microsoft YaHei", 9),
            selectmode="multiple"  # 允许多选
        )
        self.window_listbox.pack(side="left", fill="both", expand=True)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.window_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.window_listbox.config(yscrollcommand=scrollbar.set)
        
        # 绑定列表框事件
        self.window_listbox.bind("<<ListboxSelect>>", self.on_window_select)
        
        # 按钮区域
        button_row_frame = ttk.Frame(window_frame)
        button_row_frame.pack(fill="x", pady=5)
        
        # 刷新按钮
        refresh_button = ttk.Button(
            button_row_frame,
            text="刷新窗口列表",
            command=self.refresh_window_list
        )
        refresh_button.pack(side="left", padx=5)
        
        # 激活按钮
        activate_button = ttk.Button(
            button_row_frame,
            text="激活选中窗口",
            command=self.activate_selected_window
        )
        activate_button.pack(side="left", padx=5)
        
        # 调整窗口尺寸按钮
        resize_button = ttk.Button(
            button_row_frame,
            text="调整窗口尺寸",
            command=self.resize_selected_window
        )
        resize_button.pack(side="left", padx=5)
        
        # 当前被激活的窗口信息区域（绿色）- 放在按钮下方
        self.active_windows_label_activated = tk.Text(
            window_frame,
            height=3,
            width=80,
            font=("Microsoft YaHei", 9),
            bg="#e8f5e9",
            relief="flat",
            state="disabled"
        )
        self.active_windows_label_activated.pack(side="top", fill="x", pady=2)
        self.active_windows_label_activated.tag_config("green", foreground="green")
        
        # 当前挖矿窗口信息区域（蓝色）
        self.active_windows_label_mining = tk.Text(
            window_frame,
            height=3,
            width=80,
            font=("Microsoft YaHei", 9),
            bg="#e3f2fd",
            relief="flat",
            state="disabled"
        )
        self.active_windows_label_mining.pack(side="top", fill="x", pady=2)
        self.active_windows_label_mining.tag_config("blue", foreground="blue")
        
        # 当前记录窗口信息区域（橙色）
        self.active_windows_label_recording = tk.Text(
            window_frame,
            height=3,
            width=80,
            font=("Microsoft YaHei", 9),
            bg="#fff3e0",
            relief="flat",
            state="disabled"
        )
        self.active_windows_label_recording.pack(side="top", fill="x", pady=2)
        self.active_windows_label_recording.tag_config("orange", foreground="orange")
        
        # 功能区域
        function_frame = ttk.LabelFrame(self.root, text="挂机功能", padding=10)
        function_frame.pack(fill="x", padx=20, pady=10)
        
        # 挖矿功能
        mining_frame = ttk.Frame(function_frame)
        mining_frame.pack(fill="x", pady=5)
        
        mining_label = ttk.Label(mining_frame, text="挖矿:", width=10, font=("Microsoft YaHei", 10))
        mining_label.pack(side="left")
        
        self.mine_button = ttk.Button(
            mining_frame,
            text="开始挖矿",
            command=self.toggle_mining,
            width=15
        )
        self.mine_button.pack(side="left", padx=5)
        
        self.mining_status = ttk.Label(
            mining_frame, 
            text="未开始", 
            font=("Microsoft YaHei", 10)
        )
        self.mining_status.pack(side="left", padx=10)
        
        # 挖矿倒计时显示
        self.mining_countdown = ttk.Label(
            mining_frame,
            text="",
            font=("Microsoft YaHei", 10),
            width=15
        )
        self.mining_countdown.pack(side="left", padx=10)
        
        # 停止自动挖矿按钮
        self.stop_auto_mining_button = ttk.Button(
            mining_frame,
            text="停止自动挖矿",
            command=self.stop_auto_mining,
            width=12
        )
        self.stop_auto_mining_button.pack(side="left", padx=5)
        
        # 开盾按钮
        self.shield_button = ttk.Button(
            mining_frame,
            text="开盾",
            command=self.start_shield_process,
            width=10
        )
        self.shield_button.pack(side="left", padx=5)
        
        # 定时自动挖矿
        timer_frame = ttk.Frame(function_frame)
        timer_frame.pack(fill="x", pady=5)
        
        timer_label = ttk.Label(timer_frame, text="定时挖矿:", width=10, font=("Microsoft YaHei", 10))
        timer_label.pack(side="left")
        
        self.timer_slider = ttk.Scale(
            timer_frame,
            from_=0,
            to=120,
            orient="horizontal",
            length=200,
            command=self._on_timer_slider_change
        )
        self.timer_slider.set(0)
        self.timer_slider.pack(side="left", padx=5)
        
        self.timer_label = ttk.Label(
            timer_frame,
            text="0 分钟",
            font=("Microsoft YaHei", 10),
            width=10
        )
        self.timer_label.pack(side="left", padx=5)
        
        self.timer_status = ttk.Label(
            timer_frame,
            text="",
            font=("Microsoft YaHei", 10)
        )
        self.timer_status.pack(side="left", padx=10)
        
        # 记录功能
        record_frame = ttk.Frame(function_frame)
        record_frame.pack(fill="x", pady=5)
        
        record_label = ttk.Label(record_frame, text="记录:", width=10, font=("Microsoft YaHei", 10))
        record_label.pack(side="left")
        
        self.record_button = ttk.Button(
            record_frame,
            text="开始记录",
            command=self.toggle_recording,
            width=15
        )
        self.record_button.pack(side="left", padx=5)
        
        self.record_status = ttk.Label(
            record_frame, 
            text="未开始", 
            font=("Microsoft YaHei", 10)
        )
        self.record_status.pack(side="left", padx=10)
        
        # 其他功能（预留）
        other_frame = ttk.Frame(function_frame)
        other_frame.pack(fill="x", pady=5)
        
        other_label = ttk.Label(other_frame, text="其他功能:", width=10, font=("Microsoft YaHei", 10))
        other_label.pack(side="left")
        
        # 画框按钮
        self.draw_frame_button = ttk.Button(
            other_frame,
            text="画框",
            command=self.draw_frame,
            width=10
        )
        self.draw_frame_button.pack(side="left", padx=5)
        
        # 雪域兵器联赛按钮
        self.snowfield_button = ttk.Button(
            other_frame,
            text="雪域兵器联赛",
            command=self.start_snowfield_league,
            width=15
        )
        self.snowfield_button.pack(side="left", padx=5)
        
        # 每日任务按钮
        self.daily_task_button = ttk.Button(
            other_frame,
            text="每日任务",
            command=self.start_daily_task,
            width=12
        )
        self.daily_task_button.pack(side="left", padx=5)
        
        # 画框结果显示
        self.draw_frame_result = ttk.Label(
            other_frame,
            text="",
            font=("Microsoft YaHei", 10),
            foreground="blue"
        )
        self.draw_frame_result.pack(side="left", padx=10)
        
        ttk.Label(other_frame, text="开发中...", font=("Microsoft YaHei", 10)).pack(side="left")
        
        # 操作按钮
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=20)
        
        exit_button = ttk.Button(
            button_frame,
            text="退出",
            command=self.on_closing,
            width=20
        )
        exit_button.pack()
        
        # 日志区域
        log_frame = ttk.LabelFrame(self.root, text="系统日志", padding=10)
        log_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.log_text = tk.Text(
            log_frame,
            height=15,
            state="disabled",
            font=("Microsoft YaHei", 9)
        )
        self.log_text.pack(fill="both", expand=True)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(self.log_text)
        scrollbar.pack(side="right", fill="y")
        scrollbar.config(command=self.log_text.yview)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 初始化窗口列表
        self.refresh_window_list()
        
        # 设置挖矿回调
        self.mining_manager.set_mining_callbacks(
            self._on_mining_started,
            self._on_mining_stopped
        )
        
    def refresh_window_list(self):
        """刷新窗口列表"""
        self.log("=== 刷新窗口列表 ===")
        self.window_listbox.delete(0, tk.END)
        self.window_listbox_hwnd_map.clear()  # 清空映射
        
        window_list = self.window_manager.get_window_list()
        self.log(f"找到 {len(window_list)} 个窗口")
        for i, (hwnd, title) in enumerate(window_list):
            try:
                process_id = self.window_manager.get_process_id(hwnd)
                if process_id:
                    display_text = f"{title} ({process_id})"
                else:
                    display_text = title
            except (AttributeError, TypeError):
                display_text = title
            self.window_listbox.insert(tk.END, display_text)
            self.window_listbox_hwnd_map[i] = hwnd  # 存储映射
            self.log(f"#{i}: {title} (hwnd={hwnd})")
        
        # 刷新窗口列表后重置绿色标签
        if self.active_windows_label_activated:
            self._update_active_windows_label_activated([])
        if self.active_windows_label_mining:
            self._update_active_windows_label_mining([])
        if self.active_windows_label_recording:
            self._update_active_windows_label_recording([])
    
    def on_window_select(self, event):
        """窗口选择事件"""
        selection = self.window_listbox.curselection()
        if selection:
            self.selected_window = selection[0]  # 保存第一个选中的窗口索引
            selected_titles = []
            for index in selection:
                window_text = self.window_listbox.get(index)
                selected_titles.append(window_text)
            self.log(f"=== 窗口选择事件 ===")
            self.log(f"选中窗口数量: {len(selection)}")
            for i, index in enumerate(selection):
                window_text = self.window_listbox.get(index)
                self.log(f"#{i}: {window_text}")
            # 窗口选择后重置绿色标签
            if self.active_windows_label_activated:
                self._update_active_windows_label_activated([])
            if self.active_windows_label_mining:
                self._update_active_windows_label_mining([])
            if self.active_windows_label_recording:
                self._update_active_windows_label_recording([])
        else:
            self.log(f"=== 窗口选择事件 ===")
            self.log(f"没有选中任何窗口")
    
    def activate_selected_window(self):
        """激活所有选中窗口"""
        selected_indices = self.window_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("提示", "请先选择至少一个窗口")
            return
        
        self.log(f"=== 选中窗口信息 ===")
        self.log(f"选中窗口索引: {selected_indices}")
        
        # 直接从列表框获取选中的窗口信息
        selected_hwnds = []
        selected_titles = []
        
        self.log(f"=== 从列表框获取选中窗口 ===")
        for index in selected_indices:
            window_text = self.window_listbox.get(index)
            self.log(f"索引 {index}: {window_text}")
            
            # 从映射中获取 hwnd
            if index in self.window_listbox_hwnd_map:
                hwnd = self.window_listbox_hwnd_map[index]
                # 从窗口文本中提取标题
                if "(" in window_text and ")" in window_text:
                    start = window_text.rfind("(")
                    title = window_text[:start].strip()
                else:
                    title = window_text
                selected_hwnds.append(hwnd)
                selected_titles.append(title)
                self.log(f"索引 {index} -> {title} (hwnd={hwnd})")
            else:
                self.log(f"索引不在映射中: {index}")
        
        self.log(f"=== 待激活窗口列表 ===")
        self.log(f"待激活窗口数量: {len(selected_hwnds)}")
        for i, (hwnd, title) in enumerate(zip(selected_hwnds, selected_titles)):
            self.log(f"#{i}: {title} (hwnd={hwnd})")
        
        # 激活所有选中的窗口
        success_count = 0
        activated_titles = []
        for i, hwnd in enumerate(selected_hwnds):
            try:
                process_id = self.window_manager.get_process_id(hwnd)
                if process_id:
                    full_title = f"{selected_titles[i]} ({process_id})"
                else:
                    full_title = selected_titles[i]
            except (AttributeError, TypeError):
                full_title = selected_titles[i]
            
            if self.window_manager.activate_window(hwnd):
                self.log(f"✓ 成功激活窗口: {full_title}")
                success_count += 1
                activated_titles.append(full_title)
            else:
                self.log(f"✗ 激活窗口失败: {full_title}")
        
        self.log(f"=== 激活完成 ===")
        self.log(f"批量激活完成: {success_count}/{len(selected_hwnds)} 个窗口成功")
        
        # 更新绿色标签显示当前被激活的窗口（每个窗口一行）
        if self.active_windows_label_activated:
            self._update_active_windows_label_activated(activated_titles)
        if self.active_windows_label_mining:
            self._update_active_windows_label_mining([])
    
    def resize_selected_window(self):
        """调整所有选中窗口尺寸为558x1021"""
        selected_indices = self.window_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("提示", "请先选择至少一个窗口")
            return
        
        self.log(f"=== 选中窗口信息 ===")
        self.log(f"选中窗口索引: {selected_indices}")
        
        # 直接从列表框获取选中的窗口信息
        selected_hwnds = []
        selected_titles = []
        
        self.log(f"=== 从列表框获取选中窗口 ===")
        for index in selected_indices:
            window_text = self.window_listbox.get(index)
            self.log(f"索引 {index}: {window_text}")
            
            # 从映射中获取 hwnd
            if index in self.window_listbox_hwnd_map:
                hwnd = self.window_listbox_hwnd_map[index]
                # 从窗口文本中提取标题
                if "(" in window_text and ")" in window_text:
                    start = window_text.rfind("(")
                    title = window_text[:start].strip()
                else:
                    title = window_text
                selected_hwnds.append(hwnd)
                selected_titles.append(title)
                self.log(f"索引 {index} -> {title} (hwnd={hwnd})")
            else:
                self.log(f"索引不在映射中: {index}")
        
        self.log(f"=== 待调整窗口列表 ===")
        self.log(f"待调整窗口数量: {len(selected_hwnds)}")
        for i, (hwnd, title) in enumerate(zip(selected_hwnds, selected_titles)):
            self.log(f"#{i}: {title} (hwnd={hwnd})")
        
        # 调整所有选中窗口的尺寸
        success_count = 0
        for i, hwnd in enumerate(selected_hwnds):
            try:
                process_id = self.window_manager.get_process_id(hwnd)
                if process_id:
                    full_title = f"{selected_titles[i]} ({process_id})"
                else:
                    full_title = selected_titles[i]
            except (AttributeError, TypeError):
                full_title = selected_titles[i]
            
            if self.window_manager.resize_window_by_script(hwnd, 558, 1021):
                self.log(f"成功调整窗口尺寸: {full_title} -> 558x1021")
                success_count += 1
            else:
                self.log(f"调整窗口尺寸失败: {full_title}")
        
        self.log(f"批量调整完成: {success_count}/{len(selected_hwnds)} 个窗口成功")
        
        # 调整窗口尺寸后重置绿色标签
        if self.active_windows_label_activated:
            self._update_active_windows_label_activated([])
        if self.active_windows_label_mining:
            self._update_active_windows_label_mining([])
    
    def toggle_recording(self):
        """切换记录状态"""
        if self.recording_module.get_recording_status():
            self.stop_recording()
        else:
            self.start_recording()
            # 开始记录后重置绿色标签
            if self.active_windows_label_activated:
                self._update_active_windows_label_activated([])
            if self.active_windows_label_mining:
                self._update_active_windows_label_mining([])
            if self.active_windows_label_recording:
                self._update_active_windows_label_recording([])
            
    def start_recording(self):
        """开始记录"""
        selected_indices = self.window_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("提示", "请先选择至少一个游戏窗口")
            return
        
        selected_hwnds = []
        
        for index in selected_indices:
            if index in self.window_listbox_hwnd_map:
                hwnd = self.window_listbox_hwnd_map[index]
                selected_hwnds.append(hwnd)
        
        # 清空之前的窗口列表并设置新的选中窗口
        self.recording_module.clear_selected_windows()
        for hwnd in selected_hwnds:
            self.recording_module.set_selected_window(hwnd)
        
        if self.recording_module.start_recording():
            self.record_button.config(text="停止记录")
            self.record_status.config(text="记录中")
            self.log(f"开始记录坐标，请点击游戏窗口内需要记录的位置 (共 {len(selected_hwnds)} 个窗口)")
            # 开始记录后重置绿色标签
            if self.active_windows_label_activated:
                self._update_active_windows_label_activated([])
            if self.active_windows_label_mining:
                self._update_active_windows_label_mining([])
            if self.active_windows_label_recording:
                self._update_active_windows_label_recording([])
        
    def stop_recording(self):
        """停止记录"""
        if self.recording_module.stop_recording():
            self.record_button.config(text="开始记录")
            self.record_status.config(text="未开始")
            # 停止记录后重置绿色标签
            if self.active_windows_label_activated:
                self._update_active_windows_label_activated([])
            if self.active_windows_label_mining:
                self._update_active_windows_label_mining([])
            if self.active_windows_label_recording:
                self._update_active_windows_label_recording([])
    
    def toggle_mining(self):
        """切换挖矿状态"""
        if self.mining_manager.get_mining_status():
            self.stop_mining()
        else:
            self.start_mining()
            # 开始挖矿后重置记录标签
            if self.active_windows_label_recording:
                self._update_active_windows_label_recording([])
            
    def start_mining(self):
        """开始挖矿（支持多窗口队列模式）"""
        selected_indices = self.window_listbox.curselection()
        selected_hwnds = []
        selected_titles = []
        
        if not selected_indices:
            # 自动挖矿时，使用所有可用窗口
            self.log("未选择窗口，使用所有可用窗口")
            window_list = self.window_manager.get_window_list()
            for hwnd, title in window_list:
                selected_hwnds.append(hwnd)
                selected_titles.append(title)
        else:
            # 使用映射获取选中的窗口
            for index in selected_indices:
                if index in self.window_listbox_hwnd_map:
                    hwnd = self.window_listbox_hwnd_map[index]
                    window_text = self.window_listbox.get(index)
                    if "(" in window_text and ")" in window_text:
                        start = window_text.rfind("(")
                        title = window_text[:start].strip()
                    else:
                        title = window_text
                    selected_hwnds.append(hwnd)
                    selected_titles.append(title)
        
        # 检查是否有窗口
        if not selected_hwnds:
            messagebox.showinfo("提示", "没有可用的游戏窗口")
            return
        
        # 重置所有窗口的挖矿标记
        self.mining_manager.reset_all_mined_flags()
        self.log("已重置所有窗口的挖矿标记")
        
        # 添加所有选中的窗口到管理器
        for i, hwnd in enumerate(selected_hwnds):
            try:
                process_id = self.window_manager.get_process_id(hwnd)
                if process_id:
                    full_title = f"{selected_titles[i]} ({process_id})"
                else:
                    full_title = selected_titles[i]
            except (AttributeError, TypeError):
                full_title = selected_titles[i]
            
            # 添加窗口到管理器
            self.mining_manager.add_window(hwnd, full_title)
            self.log(f"添加挖矿窗口: {full_title}")
        
        # 使用队列模式启动挖矿（单线程顺序执行）
        if self.mining_manager.start_mining_queue():
            self.log(f"✓ 启动挖矿队列，共 {len(selected_hwnds)} 个窗口")
            self.mine_button.config(text="停止挖矿")
            self.mining_status.config(text="挖矿中")
            self.timer_status.config(text="")
            self.mining_countdown.config(text="")
            # 挖矿开始时，暂停保护性外壳检测
            if hasattr(self, 'protective_casing') and self.protective_casing:
                self.protective_casing.stop()
                self.log("已暂停保护性外壳检测")
        
        # 更新绿色标签显示当前被激活的窗口
        if self.active_windows_label:
            current_activated = self.window_manager.get_activated_windows()
            self._update_active_windows_label(current_activated)
        
    def stop_mining(self):
        """停止挖矿（支持多窗口队列模式）"""
        # 停止挖矿队列（用户手动停止）
        stopped = self.mining_manager.stop_mining_queue(user_stopped=True)
        if stopped:
            self.mine_button.config(text="开始挖矿")
            self.mining_status.config(text="未开始")
            self.log("挖矿结束")
        # 挖矿结束后重置绿色标签
        if self.active_windows_label:
            self._update_active_windows_label([])
    
    def start_shield_process(self):
        """开始开盾流程（直接检测 war 并处理）"""
        # 获取当前选中的窗口列表（使用映射获取正确的窗口）
        selected_indices = self.window_listbox.curselection()
        selected_windows = []
        
        if not selected_indices:
            # 使用所有可用窗口
            window_list = self.window_manager.get_window_list()
            selected_windows = window_list
            self.log("未选择窗口，使用所有可用窗口进行开盾流程")
        else:
            # 使用映射获取选中的窗口
            for index in selected_indices:
                if index in self.window_listbox_hwnd_map:
                    hwnd = self.window_listbox_hwnd_map[index]
                    window_text = self.window_listbox.get(index)
                    if "(" in window_text and ")" in window_text:
                        start = window_text.rfind("(")
                        title = window_text[:start].strip()
                    else:
                        title = window_text
                    selected_windows.append((hwnd, title))
            self.log(f"选择 {len(selected_windows)} 个窗口进行开盾流程")
        
        if not selected_windows:
            messagebox.showinfo("提示", "没有可用的游戏窗口")
            return
        
        # 暂停挖矿（如果正在挖矿）
        if self.mining_manager.get_mining_status():
            self.stop_mining()
        
        # 设置保护性外壳窗口
        self.protective_casing.set_windows(selected_windows)
        
        # 启动保护性外壳检测（单次扫描模式）
        def run_shield_scan():
            self.log("开始开盾流程...")
            self.protective_casing.running = True
            
            try:
                for hwnd, window_name in selected_windows:
                    if not self.protective_casing.running:
                        break
                    
                    if not win32gui.IsWindow(hwnd):
                        self.log(f"窗口无效: {window_name} ({hwnd})")
                        continue
                    
                    # 清除截图缓存
                    self.protective_casing._invalidate_screenshot(hwnd)
                    
                    # 检测 war
                    if self.protective_casing.check_war_in_window(hwnd, window_name):
                        self.log(f"[{window_name}] 检测到 war，开始处理流程")
                        
                        # 检测 town 和 six
                        self.log(f"[{window_name}] 开始检测 town 和 six...")
                        six_positions = self.protective_casing.check_town_and_six(hwnd, window_name)
                        self.log(f"[{window_name}] 检测到 {len(six_positions)} 个 six")
                        if len(six_positions) > 0:
                            self.log(f"[{window_name}] 检测到 {len(six_positions)} 个 six，开始处理")
                            self.protective_casing.process_six_with_red_check(hwnd, window_name, six_positions)
                        else:
                            self.log(f"[{window_name}] 未检测到 six，跳过处理")
                        
                        # 检查 war 是否仍然存在
                        if self.protective_casing.check_war_in_window(hwnd, window_name):
                            self.log(f"[{window_name}] war 仍然存在，开始 deploy 流程")
                            self.protective_casing.start_deploy_flow(hwnd, window_name)
                        else:
                            self.log(f"[{window_name}] war 已消失")
                    else:
                        self.log(f"[{window_name}] 未检测到 war")
                
                self.log("开盾流程完成")
            except (RuntimeError, OSError) as e:
                self.log(f"开盾流程错误: {e}")
            finally:
                self.protective_casing.running = False
                # 开盾流程结束后，启动保护性外壳检测
                if hasattr(self, 'protective_casing') and self.protective_casing:
                    threading.Thread(target=self.protective_casing.start, daemon=True).start()
                    self.log("开盾流程结束，已启动保护性外壳检测")
        
        # 在新线程中运行
        threading.Thread(target=run_shield_scan, daemon=True).start()
        
        # 更新绿色标签
        if self.active_windows_label:
            current_activated = self.window_manager.get_activated_windows()
            self._update_active_windows_label(current_activated)
    
    def stop_auto_mining(self):
        """停止自动挖矿"""
        # 设置定时挖矿时间为0
        self.timer_slider.set(0)
        self.timer_label.config(text="0 分钟")
        
        # 停止倒计时
        self.countdown_running = False
        self.mining_countdown.config(text="")
        self.timer_status.config(text="")
        
        # 停止挖矿（如果正在挖矿）
        if self.mining_manager.get_mining_status():
            self.stop_mining()
        
        self.log("自动挖矿已停止")
        
    def log(self, message):
        """添加日志"""
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        
    def _check_mining_status(self):
        """定时检查挖矿状态，更新按钮"""
        if self.mining_manager.are_all_windows_mined():
            if self.mine_button.cget("text") == "停止挖矿":
                self.mine_button.config(text="开始挖矿")
                self.mining_status.config(text="未开始")
                self.mining_countdown.config(text="")
                self.log("所有窗口都已挖矿")
                
                # 停止倒计时
                self.countdown_running = False
                
                # 检查是否有窗口是用户手动停止的
                user_stopped_windows = []
                auto_stopped_windows = []
                for miner in self.mining_manager.miners.values():
                    if miner.is_user_stopped():
                        user_stopped_windows.append(miner.window_name)
                    else:
                        auto_stopped_windows.append(miner.window_name)
                
                # 只有在所有窗口都是自动停止（自然完成）时才启动保护性外壳
                if user_stopped_windows:
                    self.log(f"检测到用户手动停止了 {len(user_stopped_windows)} 个窗口，不启动保护性外壳检测")
                elif auto_stopped_windows:
                    self.log(f"检测到 {len(auto_stopped_windows)} 个窗口自动挖矿完成，准备启动保护性外壳检测")
                    
                    # 挖矿结束后，启动保护性外壳检测
                    if hasattr(self, 'protective_casing') and self.protective_casing:
                        # 检查是否已经在运行
                        if not self.protective_casing.running:
                            # 获取当前选中的窗口列表（使用映射获取正确的窗口）
                            selected_indices = self.window_listbox.curselection()
                            selected_windows = []
                            
                            if not selected_indices:
                                # 使用所有可用窗口
                                window_list = self.window_manager.get_window_list()
                                selected_windows = window_list
                            else:
                                # 使用映射获取选中的窗口
                                for index in selected_indices:
                                    if index in self.window_listbox_hwnd_map:
                                        hwnd = self.window_listbox_hwnd_map[index]
                                        window_text = self.window_listbox.get(index)
                                        if "(" in window_text and ")" in window_text:
                                            start = window_text.rfind("(")
                                            title = window_text[:start].strip()
                                        else:
                                            title = window_text
                                        selected_windows.append((hwnd, title))
                            
                            if selected_windows:
                                self.protective_casing.set_windows(selected_windows)
                                # 启动保护性外壳检测
                                threading.Thread(target=self.protective_casing.start, daemon=True).start()
                                self.log(f"已启动保护性外壳检测，监控 {len(selected_windows)} 个窗口")
                            else:
                                self.log("无窗口可监控，保护性外壳检测未启动")
                
                # 如果设置了定时，启动倒计时
                timer_minutes = int(self.timer_slider.get())
                self.log(f"滑动条值: {timer_minutes} 分钟")
                if timer_minutes > 0:
                    self._start_countdown(timer_minutes)
        self.root.after(1000, self._check_mining_status)
    
    def _start_countdown(self, minutes):
        """启动倒计时"""
        self.countdown_running = True
        remaining = minutes * 60
        
        def countdown_loop():
            nonlocal remaining
            while remaining > 0 and self.countdown_running:
                if not self.root.winfo_exists():
                    return
                mins = remaining // 60
                secs = remaining % 60
                self.root.after(0, lambda m=mins, s=secs: 
                    self.mining_countdown.config(text=f"{m:02d}分{s:02d}秒"))
                time.sleep(1)
                remaining -= 1
            
            if remaining <= 0 and self.countdown_running:
                # 检查滑动条值，只有 > 0 时才自动开始挖矿
                timer_minutes = int(self.timer_slider.get())
                if timer_minutes > 0:
                    self.root.after(0, self._auto_start_mining)
                self.mining_countdown.config(text="")
        
        threading.Thread(target=countdown_loop, daemon=True).start()
    
    def _on_timer_slider_change(self, value):
        """滑动条值变化时更新标签"""
        if hasattr(self, 'timer_label'):
            minutes = int(float(value))
            self.timer_label.config(text=f"{minutes} 分钟")
    
    def _auto_start_mining(self):
        """自动开始挖矿"""
        if not self.mining_manager.get_mining_status():
            self.timer_status.config(text="正在启动...")
            self.start_mining()
            self.timer_status.config(text="已启动")
            self.log("定时挖矿已自动启动")
        
    def on_closing(self):
        """窗口关闭事件"""
        if self.recording_module.get_recording_status():
            self.stop_recording()
        
        if self.mining_manager.get_mining_status():
            if messagebox.askokcancel("退出", "挖矿正在进行中，确定要退出吗？"):
                self.mining_manager.stop_mining_queue()
                # 关闭前重置绿色标签
                if self.active_windows_label:
                    self._update_active_windows_label([])
                self.root.destroy()
        else:
            # 关闭前重置绿色标签
            if self.active_windows_label:
                self._update_active_windows_label([])
            self.root.destroy()
    
    def _pause_other_systems(self):
        """暂停其他正在运行的系统，返回状态字典"""
        status = {
            'mining': self.mining_manager.get_mining_status(),
            'protective': self.protective_casing.is_protecting(),
            'recording': self.recording_module.get_recording_status(),
            'daily_task': self.daily_task_module is not None and self.daily_task_module.is_running()
        }
        
        if any(status.values()):
            self.log("检测到其他系统运行中，暂停其他系统...")
            
            if status['mining']:
                self.mining_manager.stop_mining_queue()
                self.log("已暂停挖矿系统")
            
            if status['protective']:
                self.protective_casing.stop_protection()
                self.log("已暂停外壳保护系统")
            
            if status['recording']:
                self.stop_recording()
                self.log("已暂停录制系统")
            
            if status['daily_task']:
                if self.daily_task_module:
                    self.daily_task_module.stop()
                self.log("已暂停每日任务系统")
            
            time.sleep(1)
        
        return status
    
    def _resume_systems(self, status: dict):
        """恢复之前暂停的系统"""
        if status['mining']:
            self.log("恢复挖矿系统...")
            self.mining_manager.start_mining_queue()
        
        if status['protective']:
            self.log("恢复外壳保护系统...")
            self.protective_casing.start_protection()
        
        if status['recording']:
            self.log("恢复录制系统...")
            self.toggle_recording()
        
        if status['daily_task']:
            self.log("每日任务系统已在后台运行，无需恢复")
    
    def start_snowfield_league(self):
        """启动雪域兵器联赛模块"""
        selected_indices = self.window_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("警告", "请先选择一个窗口")
            return
        
        index = selected_indices[0]
        if index not in self.window_listbox_hwnd_map:
            messagebox.showwarning("警告", "无法获取窗口信息")
            return
        
        hwnd = self.window_listbox_hwnd_map[index]
        
        # 获取窗口信息
        window_info = self.window_manager.get_window_info(hwnd)
        if not window_info:
            messagebox.showwarning("警告", "无法获取窗口信息")
            return
        
        window_title = window_info['title']
        self.log(f"选择窗口: {window_title}")
        
        # 激活窗口
        win32gui.ShowWindow(hwnd, 5)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        
        # 暂停其他系统
        system_status = self._pause_other_systems()
        
        # 初始化雪域兵器联赛模块
        self.log(f"开始初始化雪域兵器联赛模块...")
        
        try:
            self.snowfield_league = SnowfieldWeaponLeague(hwnd=hwnd)
            self.log(f"✓ 雪域兵器联赛模块初始化成功")
            
            # 运行雪域联赛流程(异步,不阻塞GUI)
            self.log(f"开始执行雪域兵器联赛完整流程...")
            
            def on_league_complete(success):
                """流程完成后的回调"""
                if success:
                    self.log(f"✓ 雪域兵器联赛流程执行完成")
                else:
                    self.log(f"✗ 雪域兵器联赛流程执行失败")
                
                self._resume_systems(system_status)
            
            self.snowfield_league.run_full_cycle_async(callback=on_league_complete)

        except (RuntimeError, OSError) as e:
            self.log(f"✗ 雪域兵器联赛初始化失败: {e}")
            import traceback
            self.log(f"详细错误: {traceback.format_exc()}")
            
            self._resume_systems(system_status)
    
    def start_daily_task(self):
        """启动每日任务模块"""
        selected_indices = self.window_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("警告", "请先选择一个窗口")
            return
        
        index = selected_indices[0]
        if index not in self.window_listbox_hwnd_map:
            messagebox.showwarning("警告", "无法获取窗口信息")
            return
        
        hwnd = self.window_listbox_hwnd_map[index]
        
        # 获取窗口信息
        window_info = self.window_manager.get_window_info(hwnd)
        if not window_info:
            messagebox.showwarning("警告", "无法获取窗口信息")
            return
        
        window_title = window_info['title']
        self.log(f"选择窗口: {window_title}")
        
        # 检查挖矿状态
        if self.mining_manager:
            try:
                mining_states = self.mining_manager.get_all_mining_states()
                if mining_states:
                    first_state = list(mining_states.values())[0]
                    if first_state == 1:
                        messagebox.showwarning("警告", "挖矿正在进行中，请等待挖矿彻底结束后再执行每日任务")
                        self.log("✗ 挖矿进行中，拒绝启动每日任务")
                        return
            except (AttributeError, RuntimeError) as e:
                self.log(f"检查挖矿状态失败: {e}")
        
        # 激活窗口
        win32gui.ShowWindow(hwnd, 5)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        
        # 暂停其他系统
        system_status = self._pause_other_systems()
        
        # 初始化每日任务模块
        self.log(f"开始初始化每日任务模块...")
        
        try:
            self.daily_task_module = DailyTaskModule(hwnd=hwnd, mining_manager=self.mining_manager, protective_casing=self.protective_casing)
            self.log(f"✓ 每日任务模块初始化成功")
            
            # 运行每日任务流程(异步,不阻塞GUI)
            self.log(f"开始执行每日任务流程...")
            
            def on_task_complete(success):
                """流程完成后的回调"""
                if success:
                    self.log(f"✓ 每日任务流程执行完成")
                else:
                    self.log(f"✗ 每日任务流程执行失败")
                
                self._resume_systems(system_status)
            
            self.daily_task_module.run_daily_task_async(callback=on_task_complete)

        except (RuntimeError, OSError) as e:
            self.log(f"✗ 每日任务模块初始化失败: {e}")
            import traceback
            self.log(f"详细错误: {traceback.format_exc()}")
            
            self._resume_systems(system_status)
    
    def draw_frame(self):
        """画框功能：让用户在激活的窗口中框选区域，并显示相对位置"""
        # 获取选中的窗口
        selected_indices = self.window_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("警告", "请先选择一个窗口")
            return
        
        # 获取第一个选中的窗口
        index = selected_indices[0]
        if index not in self.window_listbox_hwnd_map:
            messagebox.showwarning("警告", "无法获取窗口信息")
            return
        
        hwnd = self.window_listbox_hwnd_map[index]
        
        # 获取窗口信息
        window_info = self.window_manager.get_window_info(hwnd)
        if not window_info:
            messagebox.showwarning("警告", "无法获取窗口信息")
            return
        
        window_title = window_info['title']
        window_rect = window_info['window_rect']
        window_width = window_rect['width']
        window_height = window_rect['height']
        
        self.log(f"选择窗口: {window_title} ({window_width}x{window_height})")
        
        # 激活窗口
        win32gui.ShowWindow(hwnd, 5)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        
        # 创建画框窗口
        self._create_draw_window(hwnd, window_width, window_height, window_rect)
        
    def _create_draw_window(self, hwnd, window_width, window_height, window_rect):
        """创建画框覆盖窗口"""
        try:
            import pyautogui
        except ImportError:
            messagebox.showwarning("警告", "请先安装 pyautogui: pip install pyautogui")
            return
        
        draw_window = tk.Toplevel(self.root)
        draw_window.title("画框 - 请框选区域")
        draw_window.attributes('-topmost', True)
        draw_window.overrideredirect(True)
        
        # 获取窗口在屏幕上的位置
        win_x = window_rect['left']
        win_y = window_rect['top']
        
        # 设置画框窗口大小和位置
        draw_window.geometry(f"{window_width}x{window_height}+{win_x}+{win_y}")
        
        # 截取游戏窗口的屏幕截图
        try:
            screenshot = pyautogui.screenshot(region=(win_x, win_y, window_width, window_height))
        except (OSError, ValueError) as e:
            messagebox.showwarning("警告", f"无法截取屏幕: {e}")
            draw_window.destroy()
            return
        
        # 创建画布
        canvas = tk.Canvas(draw_window, width=window_width, height=window_height, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        
        # 检查 PIL 是否可用
        if ImageTk is None:
            messagebox.showwarning("警告", "请先安装 Pillow: pip install Pillow")
            draw_window.destroy()
            return
        
        # 将截图转换为 PhotoImage 并显示
        try:
            photo = ImageTk.PhotoImage(image=screenshot)
            canvas.create_image(0, 0, anchor="nw", image=photo)
        except (tk.TclError, ValueError) as e:
            messagebox.showwarning("警告", f"无法显示截图: {e}")
            draw_window.destroy()
            return
        
        # 保存 photo 引用，防止被垃圾回收
        canvas.image = photo
        
        # 绘制半透明遮罩
        canvas.create_rectangle(0, 0, window_width, window_height, fill='black', stipple='gray25', outline='')
        
        # 画框变量
        start_x = tk.IntVar()
        start_y = tk.IntVar()
        end_x = tk.IntVar()
        end_y = tk.IntVar()
        rect_id = [None]
        
        # 鼠标按下事件
        def on_mouse_down(event):
            start_x.set(event.x)
            start_y.set(event.y)
            end_x.set(event.x)
            end_y.set(event.y)
            if rect_id[0]:
                canvas.delete(rect_id[0])
            rect_id[0] = canvas.create_rectangle(
                start_x.get(), start_y.get(), end_x.get(), end_y.get(),
                outline='red', width=2
            )
        
        # 鼠标移动事件
        def on_mouse_move(event):
            end_x.set(event.x)
            end_y.set(event.y)
            if rect_id[0]:
                canvas.coords(rect_id[0], start_x.get(), start_y.get(), end_x.get(), end_y.get())
        
        # 鼠标释放事件
        def on_mouse_up(event):
            end_x.set(event.x)
            end_y.set(event.y)
            if rect_id[0]:
                canvas.coords(rect_id[0], start_x.get(), start_y.get(), end_x.get(), end_y.get())
            
            # 计算相对位置
            x1 = start_x.get()
            y1 = start_y.get()
            x2 = end_x.get()
            y2 = end_y.get()
            
            # 确保 x1 < x2, y1 < y2
            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1
            
            width = x2 - x1
            height = y2 - y1
            
            # 计算相对于窗口左上角的相对位置
            rel_x = x1 / window_width
            rel_y = y1 / window_height
            rel_width = width / window_width
            rel_height = height / window_height
            
            # 显示结果
            result_text = f"区域: ({x1}, {y1}) -> ({x2}, {y2})\n" \
                         f"大小: {width}x{height}\n" \
                         f"相对位置: x={rel_x:.4f}, y={rel_y:.4f}, w={rel_width:.4f}, h={rel_height:.4f}"
            
            self.draw_frame_result.config(text=result_text)
            self.log(f"画框完成: {result_text.replace(chr(10), ' ')}")
            
            # 弹出输入框让用户输入模块名和功能名
            self._show_input_dialog(hwnd, x1, y1, width, height, rel_x, rel_y, rel_width, rel_height, window_width, window_height)
            
            # 2秒后关闭画框窗口
            draw_window.after(2000, draw_window.destroy)
        
        # 绑定鼠标事件
        canvas.bind("<Button-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_move)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)
        
        # 提示标签
        label = tk.Label(draw_window, text="请在窗口中框选区域", fg='white', bg='black', font=('Microsoft YaHei', 12))
        label.place(relx=0.5, rely=0.5, anchor='center')
        
        self.log("画框窗口已打开，请在窗口中框选区域")
    
    def _show_input_dialog(self, hwnd, x1, y1, width, height, rel_x, rel_y, rel_width, rel_height, window_width, window_height):
        """显示输入对话框，让用户输入模块名和功能名
        
        Args:
            hwnd: 窗口句柄
            x1, y1: 区域左上角坐标
            width, height: 区域大小
            rel_x, rel_y: 相对位置 x, y
            rel_width, rel_height: 相对宽度和高度
            window_width, window_height: 窗口大小
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("保存画框信息")
        dialog.geometry("400x320")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 模块名输入
        ttk.Label(dialog, text="模块名:", font=("Microsoft YaHei", 10)).pack(pady=10)
        module_entry = ttk.Entry(dialog, width=30)
        module_entry.pack(pady=5)
        
        # 功能名输入
        ttk.Label(dialog, text="功能名:", font=("Microsoft YaHei", 10)).pack(pady=10)
        function_entry = ttk.Entry(dialog, width=30)
        function_entry.pack(pady=5)
        
        # 信息显示
        info_text = f"窗口: {hwnd}\n区域: ({x1}, {y1}) -> ({x1+width}, {y1+height})\n大小: {width}x{height}\n相对位置: x={rel_x:.4f}, y={rel_y:.4f}, w={rel_width:.4f}, h={rel_height:.4f}"
        info_label = ttk.Label(dialog, text=info_text, font=("Microsoft YaHei", 8), foreground="gray")
        info_label.pack(pady=10)
        
        # 按钮框架
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        def save_and_close():
            module_name = module_entry.get().strip()
            function_name = function_entry.get().strip()
            
            if not module_name or not function_name:
                messagebox.showwarning("警告", "请输入模块名和功能名")
                return
            
            # 保存到 JSON
            frame_info = {
                "hwnd": hwnd,
                "window_size": [window_width, window_height],
                "region": [x1, y1, width, height],
                "relative": {
                    "x": round(rel_x, 4),
                    "y": round(rel_y, 4),
                    "width": round(rel_width, 4),
                    "height": round(rel_height, 4)
                }
            }
            
            self._save_frame_info(module_name, function_name, frame_info)
            
            dialog.destroy()
            messagebox.showinfo("成功", f"已保存: {module_name} - {function_name}")
        
        def cancel():
            dialog.destroy()
        
        save_button = ttk.Button(button_frame, text="保存", command=save_and_close)
        save_button.pack(side="left", padx=10)
        
        cancel_button = ttk.Button(button_frame, text="取消", command=cancel)
        cancel_button.pack(side="left", padx=10)
    
    def _save_frame_info(self, module_name, function_name, frame_info):
        """保存画框信息到 JSON 文件
        
        Args:
            module_name: 模块名
            function_name: 功能名
            frame_info: 画框信息
        """
        import json
        import os
        
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frame_data.json")
        
        # 读取现有数据
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError):
                data = {}
        else:
            data = {}
        
        # 添加新数据
        if module_name not in data:
            data[module_name] = {}
        data[module_name][function_name] = frame_info
        
        # 保存回文件
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log(f"✓ 已保存画框信息: {module_name} -> {function_name}")
        except (IOError, OSError) as e:
            self.log(f"✗ 保存画框信息失败: {e}")
    
    def _update_active_windows_label_activated(self, titles):
        """更新被激活窗口的绿色标签（每个窗口一行）"""
        if not titles:
            self.active_windows_label_activated.config(state="normal")
            self.active_windows_label_activated.delete("1.0", "end")
            self.active_windows_label_activated.insert("end", "当前被激活的窗口: 无", "green")
            self.active_windows_label_activated.config(state="disabled")
            return
        
        self.active_windows_label_activated.config(state="normal")
        self.active_windows_label_activated.delete("1.0", "end")
        for title in titles:
            self.active_windows_label_activated.insert("end", f"• {title}\n", "green")
        self.active_windows_label_activated.config(state="disabled")
    
    def _update_active_windows_label_mining(self, titles):
        """更新正在挖矿窗口的蓝色标签（每个窗口一行）"""
        if not titles:
            self.active_windows_label_mining.config(state="normal")
            self.active_windows_label_mining.delete("1.0", "end")
            self.active_windows_label_mining.insert("end", "当前正在挖矿的窗口: 无", "blue")
            self.active_windows_label_mining.config(state="disabled")
            return
        
        self.active_windows_label_mining.config(state="normal")
        self.active_windows_label_mining.delete("1.0", "end")
        for title in titles:
            self.active_windows_label_mining.insert("end", f"• {title}\n", "blue")
        self.active_windows_label_mining.config(state="disabled")
    
    def _update_active_windows_label_recording(self, titles):
        """更新正在记录窗口的橙色标签（每个窗口一行）"""
        if not titles:
            if self.active_windows_label_recording:
                self.active_windows_label_recording.config(state="normal")
                self.active_windows_label_recording.delete("1.0", "end")
                self.active_windows_label_recording.insert("end", "当前正在记录的窗口: 无", "orange")
                self.active_windows_label_recording.config(state="disabled")
            return
        
        if self.active_windows_label_recording:
            self.active_windows_label_recording.config(state="normal")
            self.active_windows_label_recording.delete("1.0", "end")
            for title in titles:
                self.active_windows_label_recording.insert("end", f"• {title}\n", "orange")
            self.active_windows_label_recording.config(state="disabled")
    
    def _on_mining_started(self, hwnd, window_name):
        """挖矿开始回调"""
        self.current_mining_hwnd = hwnd
        # 更新挖矿窗口标签
        self._update_active_windows_label_mining([window_name])
        self.log(f"挖矿开始: {window_name} (hwnd={hwnd})")
    
    def _on_mining_stopped(self, hwnd, window_name):
        """挖矿停止回调"""
        if self.current_mining_hwnd == hwnd:
            self.current_mining_hwnd = None
        # 更新挖矿窗口标签
        self._update_active_windows_label_mining([])
        self.log(f"挖矿停止: {window_name} (hwnd={hwnd})")
    
    def _pre_init_ocr(self):
        """提前初始化OCR（在GUI启动时）"""
        self.log("正在提前初始化OCR...")
        try:
            import warnings
            warnings.filterwarnings("ignore", message="'pin_memory' argument is set as true but no accelerator is found")
            warnings.filterwarnings("ignore", message="Neither CUDA nor MPS are available - defaulting to CPU")
            
            import easyocr
            ocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
            self.log("✓ OCR 提前初始化完成")
        except ImportError:
            self.log("⚠ easyocr 未安装，跳过 OCR 初始化")
        except (RuntimeError, OSError) as e:
            self.log(f"⚠ OCR 初始化失败: {e}")
    
    def _create_loading_screen(self):
        """创建启动进度条界面"""
        # 清空根窗口
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # 创建加载界面框架
        loading_frame = ttk.Frame(self.root)
        loading_frame.pack(expand=True)
        
        # 标题
        self.title_label = ttk.Label(
            loading_frame,
            text="无尽冬日挂机系统",
            font=("Microsoft YaHei", 16, "bold")
        )
        self.title_label.pack(pady=20)
        
        # 副标题
        self.subtitle_label = ttk.Label(
            loading_frame,
            text="正在初始化...",
            font=("Microsoft YaHei", 10)
        )
        self.subtitle_label.pack(pady=10)
        
        # 进度条
        self.loading_progress = ttk.Progressbar(
            loading_frame,
            mode='determinate',
            maximum=100,
            length=300
        )
        self.loading_progress.pack(pady=20)
        self.loading_progress['value'] = 0
        
        # 进度文本标签
        self.loading_text_label = ttk.Label(
            loading_frame,
            text="0%",
            font=("Microsoft YaHei", 9)
        )
        self.loading_text_label.pack(pady=5)
        
        # 状态标签
        self.loading_status = ttk.Label(
            loading_frame,
            text="正在加载 OCR 模型...",
            font=("Microsoft YaHei", 9)
        )
        self.loading_status.pack(pady=10)
        
        # 窗口居中
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = 800
        window_height = 1100
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    def _init_ocr_in_background(self):
        """后台初始化 OCR"""
        # 启动进度条动画线程
        animation_thread = threading.Thread(target=self._animate_loading_progress, daemon=True)
        animation_thread.start()
        
        try:
            import warnings
            warnings.filterwarnings("ignore", message="'pin_memory' argument is set as true but no accelerator is found")
            warnings.filterwarnings("ignore", message="Neither CUDA nor MPS are available - defaulting to CPU")
            
            import easyocr
            ocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
            
            # OCR 加载完成，更新进度为 100%
            self.root.after(0, lambda: self.update_loading_progress(100, "OCR 加载完成"))
            
            # OCR 加载完成，更新界面
            self.root.after(0, self._on_ocr_loaded)
        except ImportError:
            self.root.after(0, lambda: self.update_loading_progress(100, "easyocr 未安装"))
            self.root.after(0, self._on_ocr_loaded)
        except (RuntimeError, OSError) as e:
            self.root.after(0, lambda: self.update_loading_progress(100, f"OCR 加载失败: {e}"))
            self.root.after(0, self._on_ocr_loaded)
    
    def _animate_loading_progress(self):
        """动画线程：模拟加载进度到 95%"""
        for i in range(1, 96):
            time.sleep(0.03)  # 模拟加载时间
            self.root.after(0, lambda value=i: self.update_loading_progress(value, "正在加载 OCR 模型..."))
    
    def update_loading_progress(self, value, text):
        """更新加载进度
        
        Args:
            value: 进度值 (0-100)
            text: 进度文本
        """
        if hasattr(self, 'loading_progress'):
            self.loading_progress['value'] = value
        if hasattr(self, 'loading_text_label'):
            self.loading_text_label.config(text=f"{value}%")
        if hasattr(self, 'loading_status'):
            self.loading_status.config(text=text)
    
    def _on_ocr_loaded(self):
        """OCR 加载完成后的回调"""
        # 更新进度为 100%
        self.update_loading_progress(100, "OCR 加载完成")
        
        # 更新状态
        if hasattr(self, 'loading_status'):
            self.loading_status.config(text="初始化完成，正在加载主界面...")
        
        # 创建主界面
        self.create_widgets()
        
        # 初始化记录模块的窗口列表框
        self.recording_module.set_window_listbox(self.window_listbox)
        
        # 初始化绿色标签显示
        if self.active_windows_label:
            self._update_active_windows_label([])
        
        # 标记 OCR 已加载
        self.ocr_loaded = True
        
        # 隐藏加载进度条和标题
        if hasattr(self, 'loading_progress'):
            self.loading_progress.pack_forget()
        if hasattr(self, 'loading_text_label'):
            self.loading_text_label.pack_forget()
        if hasattr(self, 'loading_status'):
            self.loading_status.pack_forget()
        if hasattr(self, 'subtitle_label'):
            self.subtitle_label.pack_forget()
        if hasattr(self, 'title_label') and self.title_label.cget("text") == "无尽冬日挂机系统":
            # 这是加载界面的标题，需要隐藏
            self.title_label.pack_forget()
        
        # 启动状态检查
        self._check_mining_status()
    
    def run(self):
        """运行 GUI"""
        self.root.mainloop()


def main():
    """主函数"""
    gui = WujindongriGUI()
    gui.run()


if __name__ == "__main__":
    main()
