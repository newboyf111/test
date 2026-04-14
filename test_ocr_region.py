"""
测试脚本：截取 OCR 识别区域
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import time
import win32gui
import pyautogui
import numpy as np
import cv2

def find_mumu_window():
    """查找 MuMu 模拟器窗口"""
    windows = []
    
    def enum_callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and "MuMu" in title:
                windows.append((hwnd, title))
    
    win32gui.EnumWindows(enum_callback, None)
    return windows

def capture_window(hwnd):
    """截取窗口内容"""
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top
        
        if width <= 0 or height <= 0:
            return None, 0, 0
        
        screenshot = pyautogui.screenshot(region=(left, top, width, height))
        img = np.array(screenshot)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        
        return img_bgr, width, height
    except Exception as e:
        print(f"截图失败: {e}")
        return None, 0, 0

def get_ocr_region(screenshot, win_w, win_h, ocr_region_base):
    """截取 OCR 区域"""
    if screenshot is None:
        return None
    
    BASE_WIDTH = 558
    
    scale = win_w / BASE_WIDTH
    x1 = int(ocr_region_base[0] * scale)
    y1 = int(ocr_region_base[1] * scale)
    x2 = int(ocr_region_base[2] * scale)
    y2 = int(ocr_region_base[3] * scale)
    
    x1 = max(0, min(x1, screenshot.shape[1]))
    y1 = max(0, min(y1, screenshot.shape[0]))
    x2 = max(0, min(x2, screenshot.shape[1]))
    y2 = max(0, min(y2, screenshot.shape[0]))
    
    if x1 >= x2 or y1 >= y2:
        print("OCR 区域坐标无效")
        return None
    
    ocr_region = screenshot[y1:y2, x1:x2]
    return ocr_region, (x1, y1, x2, y2)

def main():
    print("查找 MuMu 模拟器窗口...")
    windows = find_mumu_window()
    
    if not windows:
        print("未找到 MuMu 模拟器窗口")
        return
    
    print(f"找到 {len(windows)} 个窗口:")
    for i, (hwnd, title) in enumerate(windows):
        print(f"  {i+1}. {title} (hwnd: {hwnd})")
    
    hwnd = windows[0][0]
    title = windows[0][1]
    print(f"\n使用窗口: {title}")
    
    print("\n等待 3 秒，请切换到游戏界面...")
    time.sleep(3)
    
    print("截取窗口...")
    screenshot, win_w, win_h = capture_window(hwnd)
    
    if screenshot is None:
        print("截图失败")
        return
    
    print(f"窗口尺寸: {win_w}x{win_h}")
    
    ocr_region_base = (152, 188, 192, 219)
    result = get_ocr_region(screenshot, win_w, win_h, ocr_region_base)
    
    if result is None:
        print("获取 OCR 区域失败")
        return
    
    ocr_region, coords = result
    x1, y1, x2, y2 = coords
    
    print(f"OCR 区域坐标: ({x1}, {y1}) -> ({x2}, {y2})")
    print(f"OCR 区域大小: {ocr_region.shape[1]}x{ocr_region.shape[0]}")
    
    output_dir = os.path.join(os.path.dirname(__file__), 'test_output')
    os.makedirs(output_dir, exist_ok=True)
    
    full_path = os.path.join(output_dir, 'ocr_full.png')
    cv2.imwrite(full_path, screenshot)
    print(f"全屏截图已保存: {full_path}")
    
    ocr_path = os.path.join(output_dir, 'ocr_region.png')
    cv2.imwrite(ocr_path, ocr_region)
    print(f"OCR 区域已保存: {ocr_path}")
    
    debug_img = screenshot.copy()
    cv2.rectangle(debug_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
    debug_path = os.path.join(output_dir, 'ocr_debug.png')
    cv2.imwrite(debug_path, debug_img)
    print(f"调试图已保存: {debug_path}")
    
    print("\n请查看 test_output 文件夹中的图片")

if __name__ == '__main__':
    main()
