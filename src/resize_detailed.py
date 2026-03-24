#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试窗口尺寸调整 - 详细测试版本

此模块用于调试窗口尺寸调整功能，可以接收 GUI 传进来的窗口句柄
"""

import win32gui
import win32con
import time


def test_resize_detailed(hwnd):
    """
    详细测试窗口尺寸调整
    
    参数:
        hwnd: 窗口句柄（由 GUI 传入）
    """
    print(f"\n{'='*60}")
    print(f"测试窗口: {hwnd}")
    print(f"{'='*60}")
    
    # 获取窗口标题
    title = win32gui.GetWindowText(hwnd)
    print(f"窗口标题: {title}")
    
    # 检查窗口状态
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    print(f"窗口样式: {hex(style)}")
    print(f"扩展样式: {hex(ex_style)}")
    
    # 检查窗口是否可见 - 使用 IsWindowVisible 激活窗口
    is_visible = win32gui.IsWindowVisible(hwnd)
    print(f"窗口可见: {is_visible}")
    
    # 检查窗口是否最小化/最大化
    if win32gui.IsIconic(hwnd):
        print("窗口已最小化")
    elif hasattr(win32gui, 'IsZoomed') and win32gui.IsZoomed(hwnd):
        print("窗口已最大化")
    else:
        print("窗口正常状态")
    
    # 先激活窗口 - 使用 IsWindowVisible 检查
    print("\n--- 步骤1: 激活窗口 ---")
    if not is_visible:
        print("窗口不可见，尝试恢复")
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.2)
    
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    
    # 获取调整前的尺寸
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    current_width = right - left
    current_height = bottom - top
    print(f"调整前尺寸: {current_width}x{current_height}")
    
    # 尝试调整尺寸
    width, height = 558, 1021
    print(f"\n--- 步骤2: 调整窗口尺寸 ---")
    print(f"目标尺寸: {width}x{height}")
    
    # 方法1: SetWindowPos
    print("\n方法1: SetWindowPos")
    result = win32gui.SetWindowPos(
        hwnd,
        0,
        0, 0, width, height,
        win32con.SWP_NOMOVE | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED
    )
    print(f"SetWindowPos 返回: {result}")
    time.sleep(0.3)
    
    left2, top2, right2, bottom2 = win32gui.GetWindowRect(hwnd)
    new_width = right2 - left2
    new_height = bottom2 - top2
    print(f"调整后尺寸: {new_width}x{new_height}")
    
    if new_width == width and new_height == height:
        print("[OK] 成功!")
        return True
    else:
        print(f"[FAIL] 失败: 期望 {width}x{height}, 实际 {new_width}x{new_height}")
    
    # 方法2: MoveWindow
    print("\n方法2: MoveWindow")
    result = win32gui.MoveWindow(
        hwnd,
        left, top, width, height,
        True  # repaint=True
    )
    print(f"MoveWindow 返回: {result}")
    time.sleep(0.3)
    
    left3, top3, right3, bottom3 = win32gui.GetWindowRect(hwnd)
    new_width2 = right3 - left3
    new_height2 = bottom3 - top3
    print(f"调整后尺寸: {new_width2}x{new_height2}")
    
    if new_width2 == width and new_height2 == height:
        print("[OK] 成功!")
        return True
    else:
        print(f"[FAIL] 失败: 期望 {width}x{height}, 实际 {new_width2}x{new_height2}")
    
    # 方法3: SetWindowPos with SWP_SHOWWINDOW
    print("\n方法3: SetWindowPos with SWP_SHOWWINDOW")
    result = win32gui.SetWindowPos(
        hwnd,
        0,
        left, top, width, height,
        win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW
    )
    print(f"SetWindowPos 返回: {result}")
    time.sleep(0.3)
    
    left4, top4, right4, bottom4 = win32gui.GetWindowRect(hwnd)
    new_width3 = right4 - left4
    new_height3 = bottom4 - top4
    print(f"调整后尺寸: {new_width3}x{new_height3}")
    
    if new_width3 == width and new_height3 == height:
        print("[OK] 成功!")
        return True
    else:
        print(f"[FAIL] 失败: 期望 {width}x{height}, 实际 {new_width3}x{new_height3}")
    
    return False


def resize_window_by_gui(hwnd):
    """
    由 GUI 调用的窗口调整函数
    
    参数:
        hwnd: 窗口句柄（由 GUI 传入）
    
    返回:
        bool: 调整是否成功
    """
    print(f"\n[GUI] 调整窗口 (hwnd={hwnd})")
    
    # 先激活窗口 - 使用 IsWindowVisible 检查
    is_visible = win32gui.IsWindowVisible(hwnd)
    print(f"[GUI] 窗口可见: {is_visible}")
    
    if not is_visible:
        print(f"[GUI] 窗口不可见，尝试恢复")
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.2)
    
    print(f"[GUI] 激活窗口")
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.2)
    
    # 获取当前尺寸
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    current_width = right - left
    current_height = bottom - top
    print(f"[GUI] 当前尺寸: {current_width}x{current_height}")
    
    # 目标尺寸
    target_width, target_height = 558, 1021
    print(f"[GUI] 目标尺寸: {target_width}x{target_height}")
    
    # 如果尺寸已匹配，无需调整
    if current_width == target_width and current_height == target_height:
        print("[GUI] 尺寸已匹配，无需调整")
        return True
    
    # 使用 SetWindowPos 调整窗口大小
    print(f"[GUI] 调整窗口尺寸")
    result = win32gui.SetWindowPos(
        hwnd,
        0,
        0, 0,
        target_width, target_height,
        win32con.SWP_NOMOVE | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED
    )
    print(f"[GUI] SetWindowPos 返回: {result}")
    time.sleep(0.3)
    
    # 验证调整后的尺寸
    left2, top2, right2, bottom2 = win32gui.GetWindowRect(hwnd)
    new_width = right2 - left2
    new_height = bottom2 - top2
    print(f"[GUI] 调整后尺寸: {new_width}x{new_height}")
    
    if new_width == target_width and new_height == target_height:
        print("[GUI] 成功!")
        return True
    
    print(f"[GUI] 失败: 期望 {target_width}x{target_height}, 实际 {new_width}x{new_height}")
    return False


if __name__ == "__main__":
    # 仅用于独立测试
    print("此模块主要用于 GUI 调用，不建议单独运行")
    print("如需测试，请使用 test_resize_detailed(hwnd) 函数")
