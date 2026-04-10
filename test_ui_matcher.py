#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试UI元素识别功能
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.ui_element_matcher import UIElementMatcher
from src.utils.window_utils import set_dpi_aware, get_all_windows


def main():
    set_dpi_aware()
    
    print("=" * 60)
    print("UI元素识别功能测试")
    print("=" * 60)
    
    windows = get_all_windows()
    
    if not windows:
        print("未找到任何窗口")
        return
    
    print(f"\n找到 {len(windows)} 个窗口:")
    for hwnd, title in windows:
        print(f"  {hwnd}: {title}")
    
    if not windows:
        return
    
    hwnd = windows[0][0]
    
    print(f"\n测试窗口: {hwnd}")
    
    logger = logging.getLogger("ui_test")
    logger.setLevel(logging.DEBUG)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            f"[UI测试] %(asctime)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    matcher = UIElementMatcher(hwnd, logger=logger)
    
    print("\n" + "=" * 60)
    print("测试1: 匹配特定按钮")
    print("=" * 60)
    
    test_buttons = ["返回", "关闭", "每日任务"]
    
    for btn_name in test_buttons:
        print(f"\n测试按钮: {btn_name}")
        result = matcher.match_button(btn_name)
        
        if result and result.get("found"):
            print(f"  ✓ 匹配成功")
            print(f"    位置: {result.get('location')}")
            print(f"    置信度: {result.get('confidence'):.3f}")
            center = matcher.matcher.get_center(result)
            print(f"    中心点: {center}")
        else:
            print(f"  ✗ 匹配失败")
    
    print("\n" + "=" * 60)
    print("测试2: 匹配所有按钮（主城界面）")
    print("=" * 60)
    
    results = matcher.match_all_buttons("主城界面")
    
    if results:
        print(f"\n找到 {len(results)} 个按钮:")
        for btn_name, result in results.items():
            print(f"  ✓ {btn_name}: {result.get('confidence'):.3f}")
    else:
        print("\n未找到任何按钮")
    
    print("\n" + "=" * 60)
    print("测试3: 点击按钮")
    print("=" * 60)
    
    success = matcher.click_button("返回", wait_time=(0.5, 1.0))
    
    if success:
        print("✓ 点击成功")
    else:
        print("✗ 点击失败")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
