#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无尽冬日 (Wujindongri) - 记录模块
"""

import tkinter as tk
from tkinter import ttk, messagebox
import win32gui
import ctypes
from ctypes import wintypes
import threading
import queue
import json
import os
import time
import atexit


# 定义Windows API函数和常量
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# 定义回调函数类型
HOOKPROC = ctypes.CFUNCTYPE(
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_void_p
)

# 定义鼠标消息常量
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202

# 定义钩子类型
WH_MOUSE_LL = 14

# 设置 CallNextHookEx 函数签名
user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_void_p
]
user32.CallNextHookEx.restype = ctypes.c_int

# 定义 MSLLHOOKSTRUCT 结构体
class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long)
    ]

class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

# 全局变量
mouse_hook = None
mouse_callback = None


class RecordingModule:
    """记录模块"""
    
    def __init__(self, gui) -> None:
        """
        初始化记录模块
        
        参数:
            gui: GUI 对象，用于日志输出和窗口引用
        """
        self.gui = gui
        self.is_recording = False
        self.recorded_coordinates = []
        self.selected_hwnds = []  # 存储选中的窗口句柄列表
        self.window_listbox = None
        self.mouse_hook_proc = None
        self.click_queue = None
        self.hook_thread = None
        self.input_dialog = None
        self._atexit_registered = False
        
        # 注册退出时清理资源（防止重复注册）
        if not self._atexit_registered:
            atexit.register(self._cleanup_resources)
            self._atexit_registered = True
    
    def __del__(self) -> None:
        """析构函数，确保资源被清理"""
        self._cleanup_resources()
    
    def _cleanup_resources(self) -> None:
        """清理所有资源"""
        if self.is_recording:
            self.stop_recording()
        
    def set_window_listbox(self, listbox):
        """设置窗口列表框"""
        self.window_listbox = listbox
        
    def set_selected_window(self, hwnd):
        """设置选中的窗口句柄"""
        if hwnd not in self.selected_hwnds:
            self.selected_hwnds.append(hwnd)
        
    def clear_selected_windows(self):
        """清空选中的窗口列表"""
        self.selected_hwnds = []
        
    def start_recording(self):
        """开始记录"""
        if not self.selected_hwnds:
            messagebox.showinfo("提示", "请先选择至少一个游戏窗口")
            return False
        
        self.is_recording = True
        self.recorded_coordinates = []
        self.gui.log(f"开始记录坐标，请点击游戏窗口内需要记录的位置 (共 {len(self.selected_hwnds)} 个窗口)")
        
        # 设置鼠标钩子
        self.set_mouse_hook()
        return True
        
    def stop_recording(self):
        """停止记录"""
        self.is_recording = False
        
        # 移除全局鼠标钩子
        self.remove_mouse_hook()
        
        # 清空选中的窗口列表
        self.selected_hwnds = []
        
        if self.recorded_coordinates:
            self.save_coordinates()
            self.gui.log(f"记录完成，共记录 {len(self.recorded_coordinates)} 个坐标")
            return True
        else:
            self.gui.log("记录已停止，未记录任何坐标")
            return False
    
    def set_mouse_hook(self):
        """设置全局鼠标钩子"""
        global mouse_hook, mouse_callback
        
        try:
            self.gui.log("开始设置鼠标钩子...")
            
            # 使用队列来存储点击事件，避免线程安全问题
            self.click_queue = queue.Queue()
            
            # 定义鼠标钩子回调函数
            def mouse_hook_proc(nCode, wParam, lParam):
                try:
                    if nCode >= 0 and wParam == WM_LBUTTONDOWN:
                        # 获取鼠标位置
                        mouse_struct = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                        x = int(mouse_struct.pt.x)
                        y = int(mouse_struct.pt.y)
                        
                        # 将点击事件放入队列
                        self.click_queue.put((x, y))
                except (OSError, ValueError) as e:
                    self.gui.log(f"鼠标钩子回调错误: {e}")
                
                # 调用下一个钩子
                # CallNextHookEx 的第4个参数应该是 LPARAM 类型
                return user32.CallNextHookEx(None, nCode, wParam, None)
            
            # 保存回调函数引用，防止被垃圾回收
            self.mouse_hook_proc = mouse_hook_proc
            
            # 创建回调函数
            mouse_callback = HOOKPROC(mouse_hook_proc)
            self.gui.log(f"鼠标回调函数已创建: {mouse_callback}")
            
            # 设置钩子 - 直接使用 NULL 作为模块句柄
            self.gui.log(f"准备设置钩子，钩子类型: {WH_MOUSE_LL}")
            mouse_hook = user32.SetWindowsHookExW(
                WH_MOUSE_LL,
                mouse_callback,
                None,
                0
            )
            
            self.gui.log(f"SetWindowsHookExW返回值: {mouse_hook}")
            
            if mouse_hook:
                self.gui.log("全局鼠标钩子已设置")
                
                # 启动消息循环
                self.hook_thread = threading.Thread(target=self.hook_message_loop, daemon=True)
                self.hook_thread.start()
                
                # 启动点击事件处理循环
                self.process_clicks()
            else:
                error_code = kernel32.GetLastError()
                self.gui.log(f"设置鼠标钩子失败，错误代码: {error_code}")
                
                # 提供更详细的错误信息
                error_messages = {
                    5: "拒绝访问 (可能需要管理员权限)",
                    87: "参数错误",
                    1428: "没有可用的钩子槽",
                    6: "句柄无效"
                }
                if error_code in error_messages:
                    self.gui.log(f"错误详情: {error_messages[error_code]}")
        except (OSError, RuntimeError) as e:
            self.gui.log(f"设置鼠标钩子异常: {e}")
            import traceback
            self.gui.log(f"异常堆栈: {traceback.format_exc()}")
    
    def process_clicks(self):
        """处理点击事件队列（定时调度模式）"""
        if not self.is_recording:
            return
        
        try:
            # 处理队列中所有待处理的事件
            while True:
                try:
                    x, y = self.click_queue.get_nowait()
                    self.on_global_mouse_click(x, y)
                except queue.Empty:
                    break  # 队列为空，退出循环
        except (OSError, RuntimeError) as e:
            self.gui.log(f"处理点击事件异常: {e}")
        
        # 如果仍在录制，安排下一次处理
        if self.is_recording:
            self.gui.root.after(10, self.process_clicks)
    
    def hook_message_loop(self):
        """钩子消息循环"""
        try:
            msg = wintypes.MSG()
            while self.is_recording:
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == 0 or result == -1:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except (OSError, RuntimeError) as e:
            self.gui.log(f"钩子消息循环异常: {e}")
        finally:
            self.gui.log("钩子消息循环已结束")
    
    def remove_mouse_hook(self):
        """移除全局鼠标钩子"""
        global mouse_hook
        try:
            if mouse_hook:
                result = user32.UnhookWindowsHookEx(mouse_hook)
                if not result:
                    error_code = ctypes.get_last_error()
                    self.gui.log(f"移除鼠标钩子失败，错误代码: {error_code}")
                else:
                    self.gui.log("全局鼠标钩子已移除")
        except (OSError, RuntimeError) as e:
            self.gui.log(f"移除鼠标钩子异常: {e}")
        finally:
            # 确保即使异常也清理全局变量
            mouse_hook = None
    
    def on_global_mouse_click(self, x, y):
        """全局鼠标点击事件"""
        if not self.is_recording:
            return
        
        # 检查是否有选中的窗口
        if not self.selected_hwnds:
            return
        
        # 遍历所有选中的窗口，检查点击是否在其中
        for hwnd in self.selected_hwnds:
            try:
                # 检查窗口是否有效
                if not win32gui.IsWindow(hwnd):
                    continue
                
                # 获取窗口位置和大小
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                
                # 检查点击是否在窗口内
                if left <= x <= right and top <= y <= bottom:
                    # 计算相对坐标
                    relative_x = x - left
                    relative_y = y - top
                    
                    # 获取窗口标题
                    title = win32gui.GetWindowText(hwnd)
                    
                    # 弹出输入框，输入位置名称
                    self.show_coordinate_input(relative_x, relative_y, x, y, title)
                    return
            except (win32gui.error, OSError) as e:
                self.gui.log(f"检查窗口 {hwnd} 时出错: {e}")
                continue
        
        # 点击不在任何选中的窗口内
        self.gui.log("点击位置不在选中的游戏窗口内，忽略")
    
    def show_coordinate_input(self, relative_x, relative_y, absolute_x, absolute_y, window_title):
        """显示坐标输入框"""
        # 如果已有输入框正在显示，不创建新的
        if self.input_dialog is not None and self.input_dialog.winfo_exists():
            return
        
        # 创建输入对话框
        self.input_dialog = tk.Toplevel(self.gui.root)
        self.input_dialog.title("输入位置名称")
        self.input_dialog.geometry("400x200")
        self.input_dialog.attributes('-topmost', True)
        
        # 设置窗口居中
        self.input_dialog.update_idletasks()
        x = (self.input_dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.input_dialog.winfo_screenheight() // 2) - (200 // 2)
        self.input_dialog.geometry(f"400x200+{x}+{y}")
        
        # 提示信息
        info_label = ttk.Label(
            self.input_dialog,
            text=f"相对坐标: ({relative_x}, {relative_y})\n绝对坐标: ({absolute_x}, {absolute_y})",
            font=("Microsoft YaHei", 9)
        )
        info_label.pack(pady=10)
        
        # 位置名称输入框
        name_label = ttk.Label(self.input_dialog, text="位置名称:", font=("Microsoft YaHei", 9))
        name_label.pack(pady=5)
        
        name_entry = ttk.Entry(self.input_dialog, width=40)
        name_entry.pack(pady=5)
        name_entry.focus_set()
        
        # 确定按钮
        def on_ok():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("提示", "请输入位置名称")
                return
            
            # 检查是否已存在相同名称的坐标
            found = False
            for i, coord in enumerate(self.recorded_coordinates):
                if coord.get('name') == name:
                    # 替换旧数据
                    self.recorded_coordinates[i] = {
                        'window_title': window_title,
                        'relative_x': relative_x,
                        'relative_y': relative_y,
                        'absolute_x': absolute_x,
                        'absolute_y': absolute_y,
                        'name': name
                    }
                    self.gui.log(f"替换坐标: {name} - 相对 ({relative_x}, {relative_y})，绝对 ({absolute_x}, {absolute_y})")
                    found = True
                    break
            
            # 如果不存在相同名称，添加新坐标
            if not found:
                coordinate = {
                    'window_title': window_title,
                    'relative_x': relative_x,
                    'relative_y': relative_y,
                    'absolute_x': absolute_x,
                    'absolute_y': absolute_y,
                    'name': name
                }
                self.recorded_coordinates.append(coordinate)
            self.gui.log(f"记录坐标: {name} - 相对 ({relative_x}, {relative_y})，绝对 ({absolute_x}, {absolute_y})")
            
            self.input_dialog.destroy()
            self.input_dialog = None
        
        button_frame = ttk.Frame(self.input_dialog)
        button_frame.pack(pady=10)
        
        ok_button = ttk.Button(button_frame, text="确定", command=on_ok, width=15)
        ok_button.pack(side="left", padx=5)
        
        cancel_button = ttk.Button(button_frame, text="取消", command=self.input_dialog.destroy, width=15)
        cancel_button.pack(side="left", padx=5)
        
        # 绑定回车键
        self.input_dialog.bind('<Return>', lambda e: on_ok())
    
    def save_coordinates(self):
        """保存坐标到文件"""
        # 创建记录文件
        record_file = "记录.json"
        
        # 读取现有记录
        existing_records = []
        if os.path.exists(record_file):
            try:
                with open(record_file, 'r', encoding='utf-8') as f:
                    existing_records = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        # 获取当前记录的窗口标题列表
        window_titles = []
        for hwnd in self.selected_hwnds:
            try:
                if win32gui.IsWindow(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        window_titles.append(title)
            except (win32gui.error, TypeError):
                pass
        
        current_window = ", ".join(window_titles) if window_titles else "未知"
        
        # 验证坐标数据
        if not self.recorded_coordinates:
            self.gui.log("保存失败：没有记录到坐标数据")
            return
        
        # 检查坐标数据格式
        try:
            for coord in self.recorded_coordinates:
                if not isinstance(coord, dict):
                    self.gui.log("保存失败：坐标数据格式错误（应为字典）")
                    return
                required_keys = ['window_title', 'relative_x', 'relative_y', 'absolute_x', 'absolute_y', 'name']
                for key in required_keys:
                    if key not in coord:
                        self.gui.log(f"保存失败：坐标数据缺少必要字段 '{key}'")
                        return
                    if key not in ['window_title', 'name']:
                        if not isinstance(coord[key], (int, float)):
                            self.gui.log(f"保存失败：字段 '{key}' 的值类型错误（应为数字）")
                            return
        except Exception as e:
            self.gui.log(f"保存失败：坐标数据验证错误: {e}")
            return
        
        # 检查是否已存在相同窗口的记录
        found = False
        for record in existing_records:
            if record.get('window') == current_window:
                # 替换旧记录
                record['timestamp'] = self.get_current_time()
                record['coordinates'] = self.recorded_coordinates
                found = True
                self.gui.log(f"替换窗口 {current_window} 的坐标记录")
                break
        
        # 如果不存在相同窗口的记录，添加新记录
        if not found:
            new_record = {
                'timestamp': self.get_current_time(),
                'window': current_window,
                'coordinates': self.recorded_coordinates
            }
            existing_records.append(new_record)
        
        # 保存到文件
        try:
            with open(record_file, 'w', encoding='utf-8') as f:
                json.dump(existing_records, f, ensure_ascii=False, indent=2)
            self.gui.log(f"坐标已保存到 {record_file}")
        except (IOError, OSError) as e:
            self.gui.log(f"保存坐标失败: {e}")
    
    def get_current_time(self):
        """获取当前时间"""
        return time.strftime('%Y-%m-%d %H:%M:%S')
    
    def get_recording_status(self):
        """获取记录状态"""
        return self.is_recording
    
    def get_recorded_coordinates(self):
        """获取已记录的坐标"""
        return self.recorded_coordinates
