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
from src.mining import MultiWindowMiningManager
from src.window_manager import WindowManager
from src.recording import RecordingModule


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
        except:
            pass
        
        # 初始化模块
        self.mining_manager = MultiWindowMiningManager()
        self.window_manager = WindowManager()
        self.recording_module = RecordingModule(self)
        self.selected_window = None
        self.timer_minutes = 0
        self.countdown_running = False
        self.active_windows_label = None
        self.window_listbox_hwnd_map = {}  # 列表框索引到 hwnd 的映射
        
        # 创建界面
        self.create_widgets()
        
        # 初始化记录模块的窗口列表框
        self.recording_module.set_window_listbox(self.window_listbox)
        
        # 初始化绿色标签显示
        if self.active_windows_label:
            self._update_active_windows_label([])
        
        # 启动状态检查
        self._check_mining_status()
        
    def create_widgets(self):
        """创建界面组件"""
        # 主标题
        title_label = ttk.Label(
            self.root, 
            text="无尽冬日挂机系统", 
            font=("Microsoft YaHei", 16, "bold")
        )
        title_label.pack(pady=20)
        
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
        self.active_windows_label = tk.Text(
            window_frame,
            height=5,
            width=80,
            font=("Microsoft YaHei", 9),
            bg="#f0f0f0",
            relief="flat",
            state="disabled"
        )
        self.active_windows_label.pack(side="top", fill="x", pady=5)
        # 设置绿色文本标签
        self.active_windows_label.tag_config("green", foreground="green")
        
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
            except:
                display_text = title
            self.window_listbox.insert(tk.END, display_text)
            self.window_listbox_hwnd_map[i] = hwnd  # 存储映射
            self.log(f"#{i}: {title} (hwnd={hwnd})")
        
        # 刷新窗口列表后重置绿色标签
        if self.active_windows_label:
            self._update_active_windows_label([])
    
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
            if self.active_windows_label:
                self._update_active_windows_label([])
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
            except:
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
        self._update_active_windows_label(activated_titles)
    
    def resize_selected_window(self):
        """调整所有选中窗口尺寸为558x1021"""
        selected_indices = self.window_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("提示", "请先选择至少一个窗口")
            return
        
        window_list = self.window_manager.get_window_list()
        selected_hwnds = []
        selected_titles = []
        
        for index in selected_indices:
            if index < len(window_list):
                hwnd, title = window_list[index]
                selected_hwnds.append(hwnd)
                selected_titles.append(title)
        
        # 调整所有选中窗口的尺寸
        success_count = 0
        for i, hwnd in enumerate(selected_hwnds):
            try:
                process_id = self.window_manager.get_process_id(hwnd)
                if process_id:
                    full_title = f"{selected_titles[i]} ({process_id})"
                else:
                    full_title = selected_titles[i]
            except:
                full_title = selected_titles[i]
            
            if self.window_manager.resize_window(hwnd, 558, 1021):
                self.log(f"成功调整窗口尺寸: {full_title} -> 558x1021")
                success_count += 1
            else:
                self.log(f"调整窗口尺寸失败: {full_title}")
        
        self.log(f"批量调整完成: {success_count}/{len(selected_hwnds)} 个窗口成功")
        
        # 调整窗口尺寸后重置绿色标签
        if self.active_windows_label:
            self._update_active_windows_label([])
    
    def toggle_recording(self):
        """切换记录状态"""
        if self.recording_module.get_recording_status():
            self.stop_recording()
        else:
            self.start_recording()
            # 开始记录后重置绿色标签
            if self.active_windows_label:
                self._update_active_windows_label([])
            
    def start_recording(self):
        """开始记录"""
        selected_indices = self.window_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("提示", "请先选择至少一个游戏窗口")
            return
        
        window_list = self.window_manager.get_window_list()
        selected_hwnds = []
        
        for index in selected_indices:
            if index < len(window_list):
                hwnd, title = window_list[index]
                selected_hwnds.append(hwnd)
        
        # 设置所有选中的记录窗口
        for hwnd in selected_hwnds:
            self.recording_module.set_selected_window(hwnd)
        
        if self.recording_module.start_recording():
            self.record_button.config(text="停止记录")
            self.record_status.config(text="记录中")
            self.log(f"开始记录坐标，请点击游戏窗口内需要记录的位置 (共 {len(selected_hwnds)} 个窗口)")
            # 开始记录后重置绿色标签
            if self.active_windows_label:
                self._update_active_windows_label([])
        
    def stop_recording(self):
        """停止记录"""
        if self.recording_module.stop_recording():
            self.record_button.config(text="开始记录")
            self.record_status.config(text="未开始")
            # 停止记录后重置绿色标签
            if self.active_windows_label:
                self._update_active_windows_label([])
    
    def toggle_mining(self):
        """切换挖矿状态"""
        if self.mining_manager.get_mining_status():
            self.stop_mining()
        else:
            self.start_mining()
            # 开始挖矿后重置绿色标签
            if self.active_windows_label:
                self._update_active_windows_label([])
            
    def start_mining(self):
        """开始挖矿（支持多窗口）"""
        selected_indices = self.window_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("提示", "请先选择至少一个游戏窗口")
            return
        
        window_list = self.window_manager.get_window_list()
        selected_hwnds = []
        selected_titles = []
        
        for index in selected_indices:
            if index < len(window_list):
                hwnd, title = window_list[index]
                selected_hwnds.append(hwnd)
                selected_titles.append(title)
        
        # 为每个选中的窗口启动挖矿
        success_count = 0
        for i, hwnd in enumerate(selected_hwnds):
            try:
                process_id = self.window_manager.get_process_id(hwnd)
                if process_id:
                    full_title = f"{selected_titles[i]} ({process_id})"
                else:
                    full_title = selected_titles[i]
            except:
                full_title = selected_titles[i]
            
            # 添加窗口到管理器
            self.mining_manager.add_window(hwnd, full_title)
            self.log(f"添加挖矿窗口: {full_title}")
            
            # 启动倒计时（默认5秒）
            self.mining_manager.set_window_timer(hwnd, 5)
            self.mining_manager.start_window_timer(hwnd)
            
            # 只启动第一个窗口的挖矿，其他窗口等待轮流挖矿
            if i == 0:
                if self.mining_manager.start_mining(hwnd):
                    self.log(f"✓ 窗口 {full_title} 开始挖矿")
                    success_count += 1
                else:
                    self.log(f"✗ 窗口 {full_title} 启动挖矿失败")
            else:
                self.log(f"○ 窗口 {full_title} 等待轮流挖矿")
        
        if success_count > 0:
            self.mine_button.config(text="停止挖矿")
            self.mining_status.config(text="挖矿中")
            self.timer_status.config(text="")
            self.mining_countdown.config(text="")
            self.log(f"挖矿开始... (共 {success_count}/{len(selected_hwnds)} 个窗口成功)")
            # 更新绿色标签显示当前被激活的窗口
            if self.active_windows_label:
                current_activated = self.window_manager.get_activated_windows()
                self._update_active_windows_label(current_activated)
        
    def stop_mining(self):
        """停止挖矿（支持多窗口）"""
        if self.mining_manager.stop_all_mining() > 0:
            self.mine_button.config(text="开始挖矿")
            self.mining_status.config(text="未开始")
            self.log("挖矿结束")
            # 停止所有窗口的倒计时
            for hwnd in self.mining_manager.miners.keys():
                self.mining_manager.stop_window_timer(hwnd)
            # 挖矿结束后重置绿色标签
            if self.active_windows_label:
                self._update_active_windows_label([])
    
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
        if not self.mining_manager.get_mining_status():
            if self.mine_button.cget("text") == "停止挖矿":
                self.mine_button.config(text="开始挖矿")
                self.mining_status.config(text="未开始")
                self.mining_countdown.config(text="")
                self.log("挖矿已自动停止")
                
                # 停止倒计时
                self.countdown_running = False
                
                # 如果设置了定时，启动倒计时
                timer_minutes = int(self.timer_slider.get())
                if timer_minutes > 0:
                    self._start_countdown(timer_minutes)
        self.root.after(500, self._check_mining_status)
    
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
                self.mining_manager.stop_all_mining()
                # 关闭前重置绿色标签
                if self.active_windows_label:
                    self._update_active_windows_label([])
                self.root.destroy()
        else:
            # 关闭前重置绿色标签
            if self.active_windows_label:
                self._update_active_windows_label([])
            self.root.destroy()
            
    def _update_active_windows_label(self, titles):
        """更新被激活窗口的绿色标签（每个窗口一行）"""
        if not titles:
            self.active_windows_label.config(state="normal")
            self.active_windows_label.delete("1.0", "end")
            self.active_windows_label.insert("end", "当前被激活的窗口: 无", "green")
            self.active_windows_label.config(state="disabled")
            return
        
        self.active_windows_label.config(state="normal")
        self.active_windows_label.delete("1.0", "end")
        for title in titles:
            self.active_windows_label.insert("end", f"• {title}\n", "green")
        self.active_windows_label.config(state="disabled")
    
    def run(self):
        """运行 GUI"""
        self.root.mainloop()


def main():
    """主函数"""
    gui = WujindongriGUI()
    gui.run()


if __name__ == "__main__":
    main()
