#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试红点检测流程
"""

import cv2
import numpy as np
import pyautogui
import win32gui
import time
from pathlib import Path


def capture_window(hwnd: int):
    """截取窗口内容"""
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        logic_width = right - left
        logic_height = bottom - top

        if logic_width <= 0 or logic_height <= 0:
            return None, 0, 0, 0, 0

        screenshot = pyautogui.screenshot(region=(left, top, logic_width, logic_height))
        img = np.array(screenshot)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        phys_height, phys_width = img_bgr.shape[:2]

        if phys_width != logic_width or phys_height != logic_height:
            img_bgr = cv2.resize(img_bgr, (logic_width, logic_height), interpolation=cv2.INTER_AREA)

        return img_bgr, logic_width, logic_height, left, top
    except Exception as e:
        print(f"截图失败: {e}")
        return None, 0, 0, 0, 0


def detect_red_at_center(image, center_tolerance=100):
    """
    检测图像中心点是否有红色，并返回标记后的图像
    
    Args:
        image: BGR图像
        center_tolerance: 中心点容差（像素）
        
    Returns:
        (has_red, marked_image)
    """
    if image is None:
        return False, None
    
    # 转换到HSV颜色空间
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # 定义红色范围
    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 100, 100])
    upper_red2 = np.array([180, 255, 255])
    
    # 创建掩码
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = cv2.bitwise_or(mask1, mask2)
    
    # 形态学操作
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    # 计算屏幕中心
    screen_center_x = image.shape[1] // 2
    screen_center_y = image.shape[0] // 2
    
    # 检查中心点附近是否有红色
    center_region = mask[
        screen_center_y - center_tolerance:screen_center_y + center_tolerance,
        screen_center_x - center_tolerance:screen_center_x + center_tolerance
    ]
    
    # 检查是否有红色像素
    has_red = np.sum(center_region) > 0
    
    # 创建标记图像
    marked_image = image.copy()
    
    # 在中心区域画框
    x1 = screen_center_x - center_tolerance
    y1 = screen_center_y - center_tolerance
    x2 = screen_center_x + center_tolerance
    y2 = screen_center_y + center_tolerance
    
    # 画矩形框
    color = (0, 255, 0) if has_red else (0, 0, 255)
    cv2.rectangle(marked_image, (x1, y1), (x2, y2), color, 3)
    
    # 画中心点
    cv2.circle(marked_image, (screen_center_x, screen_center_y), 5, color, -1)
    
    # 添加文字
    text = f"Red: {'Yes' if has_red else 'No'}"
    cv2.putText(marked_image, text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    
    return has_red, marked_image


def main():
    # 指定窗口名称
    target_window_name = "MuMu安卓设备"
    
    # 枚举所有窗口，找到目标窗口
    hwnd = None
    
    def enum_window_callback(window_hwnd, window_name_list):
        if win32gui.IsWindow(window_hwnd):
            title = win32gui.GetWindowText(window_hwnd)
            if target_window_name in title:
                window_name_list.append((window_hwnd, title))
    
    window_list = []
    win32gui.EnumWindows(enum_window_callback, window_list)
    
    if window_list:
        # 找到第一个匹配的窗口
        hwnd = window_list[0][0]
        window_name = window_list[0][1]
        print(f"找到窗口: {window_name} (hwnd: {hwnd})")
    else:
        print(f"未找到窗口: {target_window_name}")
        return
    
    # 截取窗口
    result = capture_window(hwnd)
    if result[0] is None:
        print("截图失败")
        return
    
    screenshot, win_w, win_h, left, top = result
    print(f"窗口尺寸: {win_w}x{win_h}")
    
    # 检测红点
    has_red, marked_image = detect_red_at_center(screenshot, center_tolerance=1)
    
    # 显示结果
    print(f"中心检测到红点: {'是' if has_red else '否'}")
    
    # 保存标记后的图像
    output_path = Path("test_red_detection_result.png")
    cv2.imwrite(str(output_path), marked_image)
    print(f"标记后的图像已保存到: {output_path}")
    
    # 显示图像（可选）
    cv2.imshow("Red Detection Result", marked_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
