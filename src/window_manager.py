#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无尽冬日 (Wujindongri) - 窗口管理模块
"""

import win32gui
import win32con
import win32process
import win32api
import psutil
import time


class WindowManager:
    """窗口管理类"""
    
    def __init__(self):
        """初始化窗口管理器"""
        self.window_list = []
    
    def get_window_list(self):
        """获取所有可见窗口列表"""
        self.window_list = []
        
        def callback(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    self.window_list.append((hwnd, title))
        
        win32gui.EnumWindows(callback, None)
        return self.window_list
    
    def get_window_title(self, hwnd):
        """获取窗口标题"""
        return win32gui.GetWindowText(hwnd)
    
    def resize_window(self, hwnd, width, height):
        """调整窗口尺寸（使用 Windows API）"""
        try:
            if not win32gui.IsWindow(hwnd):
                print(f"调整窗口尺寸失败: 窗口句柄无效")
                return False
            
            # 先恢复窗口状态（如果是最小化或最大化状态）
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.1)
            
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            current_width = right - left
            current_height = bottom - top
            
            print(f"当前窗口尺寸: {current_width}x{current_height}")
            print(f"目标窗口尺寸: {width}x{height}")
            
            if current_width == width and current_height == height:
                print("窗口尺寸已匹配，无需调整")
                return True
            
            # 使用 SetWindowPos 调整窗口尺寸
            result = win32gui.SetWindowPos(
                hwnd,
                0,  # hWndInsertAfter (0 = 不改变Z顺序)
                0,  # X (使用 SWP_NOMOVE)
                0,  # Y (使用 SWP_NOMOVE)
                width,
                height,
                win32con.SWP_NOMOVE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
            )
            
            time.sleep(0.2)
            
            # 验证调整结果
            left2, top2, right2, bottom2 = win32gui.GetWindowRect(hwnd)
            new_width = right2 - left2
            new_height = bottom2 - top2
            print(f"调整后窗口尺寸: {new_width}x{new_height}")
            
            if new_width == width and new_height == height:
                print(f"成功调整窗口尺寸为: {width}x{height}")
                return True
            else:
                print(f"SetWindowPos 调整失败，目标尺寸: {width}x{height}，实际尺寸: {new_width}x{new_height}")
                return False
                
        except Exception as e:
            print(f"调整窗口尺寸失败: {e}")
            return False
    
    def activate_window(self, hwnd):
        """激活窗口（增强版）"""
        try:
            # 检查窗口是否有效
            if not win32gui.IsWindow(hwnd):
                print(f"激活窗口失败: 窗口句柄无效")
                return False
            
            # 检查窗口是否可见
            if not win32gui.IsWindowVisible(hwnd):
                print(f"激活窗口失败: 窗口不可见")
                return False
            
            # 方法 1: 标准方法 + SetWindowPos
            try:
                # 显示窗口
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                # 恢复窗口（如果是最小化或最大化状态）
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                # 使用 SetWindowPos 强制置顶并保持置顶状态
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOPMOST,  # 置于最顶层
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
                )
                # 前置窗口
                win32gui.SetForegroundWindow(hwnd)
                print(f"使用 SetWindowPos 方法激活窗口成功（保持置顶）")
                return True
            except Exception as e:
                print(f"SetWindowPos 方法激活失败: {e}")
                
                # 方法 2: 使用 AttachThreadInput 绕过限制
                try:
                    # 获取当前线程ID
                    current_thread_id = win32api.GetCurrentThreadId()
                    # 获取目标窗口线程ID
                    target_thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)
                    
                    # 附加线程输入
                    if current_thread_id != target_thread_id:
                        try:
                            win32process.AttachThreadInput(current_thread_id, target_thread_id, True)
                        except Exception as e:
                            print(f"AttachThreadInput 调用失败: {e}")
                    
                    # 显示窗口
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                    # 恢复窗口
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    # 使用 SetWindowPos 强制置顶并保持置顶状态
                    win32gui.SetWindowPos(
                        hwnd,
                        win32con.HWND_TOPMOST,
                        0, 0, 0, 0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
                    )
                    # 前置窗口
                    win32gui.SetForegroundWindow(hwnd)
                    
                    # 分离线程输入
                    if current_thread_id != target_thread_id:
                        try:
                            win32process.AttachThreadInput(current_thread_id, target_thread_id, False)
                        except Exception as e:
                            print(f"AttachThreadInput 分离失败: {e}")
                    
                    print(f"使用 AttachThreadInput + SetWindowPos 方法激活窗口成功（保持置顶）")
                    return True
                except Exception as e2:
                    print(f"AttachThreadInput 方法激活失败: {e2}")
                    
                    # 方法 3: 模拟 Alt+Tab + 强制置顶
                    try:
                        # 显示窗口
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        # 使用 SetWindowPos 强制置顶并保持置顶状态
                        win32gui.SetWindowPos(
                            hwnd,
                            win32con.HWND_TOPMOST,
                            0, 0, 0, 0,
                            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
                        )
                        # 模拟 Alt+Tab
                        win32api.keybd_event(0x12, 0, 0, 0)  # Alt 键按下
                        win32api.keybd_event(0x09, 0, 0, 0)  # Tab 键按下
                        win32api.keybd_event(0x09, 0, win32con.KEYEVENTF_KEYUP, 0)  # Tab 键释放
                        win32api.keybd_event(0x12, 0, win32con.KEYEVENTF_KEYUP, 0)  # Alt 键释放
                        time.sleep(0.1)
                        # 再次前置
                        win32gui.SetForegroundWindow(hwnd)
                        print(f"使用 Alt+Tab + SetWindowPos 方法激活窗口成功（保持置顶）")
                        return True
                    except Exception as e3:
                        print(f"Alt+Tab 方法激活失败: {e3}")
                        return False
        except Exception as e:
            print(f"激活窗口失败: {e}")
            return False
    
    def get_process_name(self, hwnd):
        """获取窗口所属进程名"""
        try:
            thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(process_id)
            return process.name()
        except Exception as e:
            print(f"获取进程名失败: {e}")
            return "未知进程"
    
    def get_process_id(self, hwnd):
        """获取窗口所属进程ID"""
        try:
            thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
            return process_id
        except Exception as e:
            print(f"获取进程ID失败: {e}")
            return None
    
    def find_window_by_title(self, title):
        """根据标题查找窗口"""
        for hwnd, window_title in self.window_list:
            if title in window_title:
                return hwnd
        return None
    
    def get_activated_windows(self):
        """获取当前被激活的窗口标题列表"""
        activated_titles = []
        
        def callback(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    activated_titles.append(title)
        
        win32gui.EnumWindows(callback, None)
        return activated_titles
