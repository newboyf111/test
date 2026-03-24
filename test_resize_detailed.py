#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调试窗口尺寸调整"""

import win32gui
import win32con
import time


def test_resize_detailed(hwnd):
    """详细测试窗口尺寸调整"""
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
    
    # 检查窗口是否可见
    is_visible = win32gui.IsWindowVisible(hwnd)
    print(f"窗口可见: {is_visible}")
    
    # 检查窗口是否最小化/最大化
    if win32gui.IsIconic(hwnd):
        print("窗口已最小化")
    elif hasattr(win32gui, 'IsZoomed') and win32gui.IsZoomed(hwnd):
        print("窗口已最大化")
    else:
        print("窗口正常状态")
    
    # 先激活窗口
    print("\n--- 步骤1: 激活窗口 ---")
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
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
    
    # 方法4: 使用 SetWindowPos 改变窗口样式
    print("\n方法4: 先改变窗口样式再调整")
    # 移除 WS_THICKFRAME 样式（可调整大小边框）
    new_style = style & ~win32con.WS_THICKFRAME
    win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, new_style)
    time.sleep(0.1)
    
    result = win32gui.SetWindowPos(
        hwnd,
        0,
        left, top, width, height,
        win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED
    )
    print(f"SetWindowPos 返回: {result}")
    time.sleep(0.3)
    
    left5, top5, right5, bottom5 = win32gui.GetWindowRect(hwnd)
    new_width4 = right5 - left5
    new_height4 = bottom5 - top5
    print(f"调整后尺寸: {new_width4}x{new_height4}")
    
    if new_width4 == width and new_height4 == height:
        print("[OK] 成功!")
        return True
    else:
        print(f"[FAIL] 失败: 期望 {width}x{height}, 实际 {new_width4}x{new_height4}")
    
    print("\n所有方法都失败了")
    return False


if __name__ == "__main__":
    # 查找所有 MuMu 窗口
    def find_game_windows(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "MuMu" in title or "模拟器" in title:
                print(f"\n找到窗口: {title} (hwnd={hwnd})")
                test_resize_detailed(hwnd)
    
    print("查找游戏窗口...")
    win32gui.EnumWindows(find_game_windows, None)
    print("\n测试完成")
