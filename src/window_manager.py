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
import logging
from typing import List, Tuple, Optional, Dict

from src.utils.window_utils import set_dpi_aware


set_dpi_aware()


class WindowManager:
    """窗口管理类"""
    
    def __init__(self) -> None:
        """初始化窗口管理器"""
        self.window_list: List[Tuple[int, str]] = []
        self.logger: logging.Logger = logging.getLogger(__name__)
    
    def get_window_list(self) -> List[Tuple[int, str]]:
        """获取所有可见窗口列表"""
        self.window_list = []
        
        def callback(hwnd: int, extra: None) -> None:
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    self.window_list.append((hwnd, title))
        
        win32gui.EnumWindows(callback, None)
        return self.window_list
    
    def get_window_title(self, hwnd: int) -> str:
        """获取窗口标题"""
        return win32gui.GetWindowText(hwnd)
    
    def get_client_rect(self, hwnd: int) -> Tuple[int, int]:
        """获取窗口客户区尺寸"""
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        return right - left, bottom - top

    def resize_window(self, hwnd, client_width, client_height):
        """
        调整窗口尺寸为指定大小（直接设置窗口尺寸，不是客户区）
        
        直接使用 Windows API 调整窗口大小
        """
        try:
            self.logger.debug(f"[resize_window] 开始调整窗口 (hwnd={hwnd})")
            self.logger.debug(f"[resize_window] 目标窗口尺寸: {client_width}x{client_height}")

            if not win32gui.IsWindow(hwnd):
                self.logger.error(f"[resize_window] 调整窗口尺寸失败: 窗口句柄无效")
                return False

            # 激活并恢复窗口
            self.logger.debug(f"[resize_window] 激活并恢复窗口")
            show_result = win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            self.logger.debug(f"[resize_window] ShowWindow 返回: {show_result}")
            
            try:
                fg_result = win32gui.SetForegroundWindow(hwnd)
                self.logger.debug(f"[resize_window] SetForegroundWindow 返回: {fg_result}")
            except (win32gui.error, OSError) as fg_e:
                self.logger.warning(f"[resize_window] SetForegroundWindow 失败: {fg_e}")
            
            time.sleep(0.2)

            # 获取当前窗口尺寸
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            current_width = right - left
            current_height = bottom - top
            self.logger.debug(f"[resize_window] 当前窗口尺寸: {current_width}x{current_height}")
            self.logger.debug(f"[resize_window] 窗口位置: ({left}, {top}, {right}, {bottom})")

            # 如果尺寸已匹配，无需调整
            if current_width == client_width and current_height == client_height:
                self.logger.info(f"[resize_window] 窗口尺寸已匹配，无需调整")
                return True

            # 检查 win32con 常量值
            self.logger.debug(f"[resize_window] SWP_NOMOVE: {win32con.SWP_NOMOVE}")
            self.logger.debug(f"[resize_window] SWP_NOZORDER: {win32con.SWP_NOZORDER}")
            self.logger.debug(f"[resize_window] SWP_FRAMECHANGED: {win32con.SWP_FRAMECHANGED}")
            flags = win32con.SWP_NOMOVE | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED
            self.logger.debug(f"[resize_window] 组合标志: {flags}")

            # 使用 SetWindowPos 直接设置窗口尺寸
            self.logger.debug(f"[resize_window] 调用 SetWindowPos")
            self.logger.debug(f"[resize_window] 参数: hwnd={hwnd}, hWndInsertAfter=0, x=0, y=0, cx={client_width}, cy={client_height}, uFlags={flags}")
            
            # 尝试不同的 SetWindowPos 调用方式
            try:
                # 方式1: 标准调用
                result = win32gui.SetWindowPos(
                    hwnd,
                    0,
                    0, 0,
                    client_width, client_height,
                    flags
                )
                self.logger.debug(f"[resize_window] SetWindowPos 返回: {result}")
                self.logger.debug(f"[resize_window] SetWindowPos 返回类型: {type(result)}")
                
                # 注意：SetWindowPos 在某些情况下可能返回 None，但窗口调整仍然成功
                # 所以我们不依赖返回值，而是通过后续的尺寸验证来判断
                
            except (win32gui.error, OSError) as swp_e:
                self.logger.error(f"[resize_window] SetWindowPos 异常: {swp_e}")
                import traceback
                self.logger.error(traceback.format_exc())
                # 即使出现异常，也继续尝试验证尺寸
            
            time.sleep(0.3)

            # 验证调整后的尺寸
            try:
                left2, top2, right2, bottom2 = win32gui.GetWindowRect(hwnd)
                new_width = right2 - left2
                new_height = bottom2 - top2
                self.logger.debug(f"[resize_window] 调整后窗口尺寸: {new_width}x{new_height}")
                self.logger.debug(f"[resize_window] 调整后窗口位置: ({left2}, {top2}, {right2}, {bottom2})")
            except (win32gui.error, OSError) as rect_e:
                self.logger.warning(f"[resize_window] GetWindowRect 异常: {rect_e}")
                new_width, new_height = 0, 0

            if new_width == client_width and new_height == client_height:
                self.logger.info(f"[resize_window] 成功!")
                return True

            self.logger.warning(f"[resize_window] 失败: 期望 {client_width}x{client_height}, 实际 {new_width}x{new_height}")
            return False

        except (win32gui.error, OSError) as e:
            self.logger.error(f"[resize_window] 调整窗口尺寸时发生异常: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def resize_window_by_script(self, hwnd, client_width, client_height):
        """调用 resize_window 方法"""
        return self.resize_window(hwnd, client_width, client_height)

    def activate_window(self, hwnd):
        """激活窗口（保持置顶）"""
        try:
            if not win32gui.IsWindow(hwnd):
                self.logger.error(f"激活窗口失败: 窗口句柄无效")
                return False

            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
            )
            self.logger.info(f"使用 SetWindowPos 方法激活窗口成功（保持置顶）")
            return True

        except (win32gui.error, OSError) as e:
            self.logger.error(f"激活窗口失败: {e}")
            return False

    def get_process_name(self, hwnd):
        """获取窗口所属进程名"""
        try:
            _, process_id = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(process_id)
            return process.name()
        except (psutil.NoSuchProcess, OSError) as e:
            self.logger.warning(f"获取进程名失败: {e}")
            return "未知进程"

    def get_process_id(self, hwnd):
        """获取窗口所属进程ID"""
        try:
            _, process_id = win32process.GetWindowThreadProcessId(hwnd)
            return process_id
        except (win32gui.error, OSError) as e:
            self.logger.warning(f"获取进程ID失败: {e}")
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

    def get_window_info(self, hwnd):
        """获取窗口详细信息（用于调试）"""
        info = {}

        info["title"] = win32gui.GetWindowText(hwnd)

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        info["window_rect"] = {
            "left": left, "top": top, "right": right, "bottom": bottom,
            "width": right - left, "height": bottom - top
        }

        cl, ct, cr, cb = win32gui.GetClientRect(hwnd)
        info["client_rect"] = {
            "width": cr - cl, "height": cb - ct
        }

        try:
            _, process_id = win32process.GetWindowThreadProcessId(hwnd)
            info["process_id"] = process_id
            info["process_name"] = psutil.Process(process_id).name()
        except (win32gui.error, OSError, psutil.NoSuchProcess) as e:
            info["process_id"] = None
            info["process_name"] = "未知"

        return info


# ─────────────────────────────────────────────
# 测试代码
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    wm = WindowManager()
    wm.get_window_list()
    wm.logger.info("可用窗口:")
    for hwnd, title in wm.window_list:
        wm.logger.info(f"  {hwnd}: {title}")

    test_title = "MuMu"
    hwnd = wm.find_window_by_title(test_title)

    if hwnd:
        wm.logger.info(f"窗口信息: {test_title} (hwnd={hwnd})")
        info = wm.get_window_info(hwnd)
        wm.logger.info(f"  窗口尺寸: {info['window_rect']['width']}x{info['window_rect']['height']}")
        wm.logger.info(f"  客户区尺寸: {info['client_rect']['width']}x{info['client_rect']['height']}")

        wm.logger.info(f"调整窗口尺寸为 558x1021...")
        wm.resize_window(hwnd, 558, 1021)

        wm.logger.info("调整后:")
        info = wm.get_window_info(hwnd)
        wm.logger.info(f"  窗口尺寸: {info['window_rect']['width']}x{info['window_rect']['height']}")
        wm.logger.info(f"  客户区尺寸: {info['client_rect']['width']}x{info['client_rect']['height']}")
    else:
        wm.logger.warning(f"未找到窗口: {test_title}")
