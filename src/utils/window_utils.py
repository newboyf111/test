#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
窗口工具模块 - 提供窗口操作和截图的公共函数
"""

import ctypes
import logging
import cv2
import numpy as np
import pyautogui
import win32gui
from typing import Optional, Tuple


def set_dpi_aware():
    """设置进程为DPI感知，确保坐标和像素一致"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def capture_window(hwnd: int) -> Tuple[Optional[np.ndarray], int, int]:
    """截取窗口内容，返回BGR图像和窗口尺寸
    
    Args:
        hwnd: 窗口句柄
        
    Returns:
        (image, width, height) 或 (None, 0, 0) 如果失败
    """
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        logic_width = right - left
        logic_height = bottom - top

        if logic_width <= 0 or logic_height <= 0:
            return None, 0, 0

        screenshot = pyautogui.screenshot(region=(left, top, logic_width, logic_height))
        img = np.array(screenshot)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        phys_height, phys_width = img_bgr.shape[:2]

        if phys_width != logic_width or phys_height != logic_height:
            img_bgr = cv2.resize(img_bgr, (logic_width, logic_height),
                                 interpolation=cv2.INTER_AREA)

        return img_bgr, logic_width, logic_height

    except Exception as e:
        logging.getLogger(__name__).error(f"截图失败: {e}")
        return None, 0, 0


def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    """获取窗口矩形区域
    
    Args:
        hwnd: 窗口句柄
        
    Returns:
        (left, top, right, bottom) 或 None 如果失败
    """
    try:
        return win32gui.GetWindowRect(hwnd)
    except Exception:
        return None


def get_window_size(hwnd: int) -> Optional[Tuple[int, int]]:
    """获取窗口尺寸
    
    Args:
        hwnd: 窗口句柄
        
    Returns:
        (width, height) 或 None 如果失败
    """
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        return (right - left, bottom - top)
    except Exception:
        return None


def is_window_valid(hwnd: int) -> bool:
    """检查窗口是否有效
    
    Args:
        hwnd: 窗口句柄
        
    Returns:
        窗口是否有效
    """
    try:
        return win32gui.IsWindow(hwnd)
    except Exception:
        return False
