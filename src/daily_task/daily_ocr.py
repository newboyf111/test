#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR 测试脚本 - 识别整个窗口截图的文字信息
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
if hasattr(sys, '_MEIPASS'):
    script_dir = Path(sys._MEIPASS).parent / "src" / "daily_task"
    output_dir = Path(sys.executable).parent / "daily_task_data"
else:
    script_dir = Path(__file__).parent
    output_dir = script_dir

venv_site_packages = project_root / "venv" / "Lib" / "site-packages"
if venv_site_packages.exists():
    sys.path.insert(0, str(venv_site_packages))

sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import win32gui
import cv2
import numpy as np
import json
import re
from datetime import datetime
from src.utils.window_utils import capture_window
import pyautogui
import time
import random


class OCRFullScreenTester:
    """OCR 全屏测试类"""
    
    def __init__(self):
        self.ocr_reader = None
        self.task_pattern = re.compile(r'[（\(]\d+/\d+')
        self.progress_pattern = re.compile(r'[（\(]\d+/\d+[）\)]')
        self.progress_open_pattern = re.compile(r'[（\(]\d+/\d+')
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
        
    def get_window_screenshot(self, hwnd: int):
        """获取窗口截图"""
        result = capture_window(hwnd)
        if result[0] is None:
            return None
        return result[0]
    
    def init_ocr(self):
        """初始化 OCR"""
        try:
            from rapidocr import RapidOCR
            self.ocr_reader = RapidOCR()
            print("✓ RapidOCR 初始化成功")
            return True
        except ImportError as e:
            print(f"✗ RapidOCR 未安装: {e}")
            return False
        except Exception as e:
            print(f"✗ OCR 初始化失败: {e}")
            return False
    
    def get_first_char_position(self, bbox):
        """获取第一个汉字的中心坐标"""
        if bbox is None:
            return None
        
        try:
            if hasattr(bbox, 'tolist'):
                bbox = bbox.tolist()
            
            if len(bbox) < 4:
                return None
            
            pts = bbox[:4]
            x_coords = [p[0] if hasattr(p, '__iter__') else p for p in pts]
            y_coords = [p[1] if hasattr(p, '__iter__') else p for p in pts]
            
            min_x = min(x_coords)
            max_x = max(x_coords)
            min_y = min(y_coords)
            max_y = max(y_coords)
            
            return (int((min_x + max_x) / 2), int((min_y + max_y) / 2))
        except:
            return None
    
    def swipe_up_from_center(self, hwnd: int, pixels: int = 100):
        """从窗口中心向上滑动指定像素"""
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            
            center_x = left + width // 2
            center_y = top + height // 2
            
            try:
                win32gui.ShowWindow(hwnd, 5)
                win32gui.SetForegroundWindow(hwnd)
            except:
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            
            time.sleep(0.3)
            
            pyautogui.moveTo(center_x, center_y)
            time.sleep(0.15)
            pyautogui.mouseDown()
            time.sleep(0.15)
            pyautogui.moveTo(center_x, center_y - pixels, duration=0.4)
            time.sleep(0.1)
            pyautogui.mouseUp()
            
            time.sleep(0.3)
            
            print(f"✓ 滑动: 从 ({center_x}, {center_y}) 向上 {pixels} 像素")
            return True
        except Exception as e:
            print(f"✗ 滑动失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def click_claim_buttons(self, hwnd: int, ocr_results: list) -> int:
        """识别并点击所有"领取"按钮
        
        Args:
            hwnd: 窗口句柄
            ocr_results: OCR识别结果列表
            
        Returns:
            点击的按钮数量
        """
        claim_buttons = []
        one_click_claim = None
        
        for result in ocr_results:
            text = result.get('text', '').strip()
            pos = result.get('first_char_pos')
            if not pos:
                continue
            
            if text == '一键领取':
                one_click_claim = {
                    'text': text,
                    'position': pos,
                    'confidence': result.get('confidence', 0)
                }
            elif text == '领取':
                claim_buttons.append({
                    'text': text,
                    'position': pos,
                    'confidence': result.get('confidence', 0)
                })
        
        if one_click_claim:
            claim_buttons_to_click = [one_click_claim]
            print(f"\n  发现'一键领取'按钮，只点击一键领取")
        elif claim_buttons:
            claim_buttons_to_click = claim_buttons
            print(f"\n  发现 {len(claim_buttons)} 个领取按钮")
        else:
            return 0
        
        try:
            win32gui.ShowWindow(hwnd, 5)
            win32gui.SetForegroundWindow(hwnd)
        except:
            import ctypes
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        
        time.sleep(0.3)
        
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        
        clicked_count = 0
        for i, btn in enumerate(claim_buttons_to_click):
            rel_x, rel_y = btn['position']
            screen_x = left + rel_x
            screen_y = top + rel_y
            print(f"    [{i+1}] 点击 '{btn['text']}' 位置: ({screen_x}, {screen_y})")
            
            pyautogui.click(screen_x, screen_y)
            time.sleep(0.3)
            
            clicked_count += 1
        
        return clicked_count
    
    def parse_task_progress(self, text: str) -> dict:
        """解析任务进度，返回完成状态
        
        例如: "完成联盟捐献20次（5/20）"
        - 目标: 20
        - 当前: 5
        - 差值: 15
        - completed: False
        """
        result = {'target': None, 'current': None, 'remaining': None, 'completed': False}
        
        patterns = [
            r'[（\(](\d+)/(\d+)[）\)]',  # 混合括号
            r'[（\(](\d+)/(\d+)',        # 只有左括号
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                current = int(match.group(1))
                target = int(match.group(2))
                result['current'] = current
                result['target'] = target
                result['remaining'] = target - current
                result['completed'] = (result['remaining'] == 0)
                break
        
        return result
    
    def recognize_text(self, image: np.ndarray) -> list:
        """识别整张图片的文字"""
        if self.ocr_reader is None:
            return []
        
        try:
            result = self.ocr_reader(image)
            if result is None:
                return []
            
            texts = []
            
            if hasattr(result, 'txts') and hasattr(result, 'scores'):
                txts = result.txts
                scores = result.scores
                boxes = getattr(result, 'boxes', None)
                
                if txts and len(txts) > 0:
                    for i, text in enumerate(txts):
                        conf = scores[i] if i < len(scores) else 0
                        
                        bbox = None
                        first_char_pos = None
                        
                        if boxes is not None and i < len(boxes) and boxes[i] is not None:
                            bbox = boxes[i]
                            try:
                                if len(bbox) >= 4:
                                    first_char_pos = self.get_first_char_position(bbox)
                            except:
                                pass
                        
                        texts.append({
                            'text': str(text).strip(),
                            'confidence': conf,
                            'first_char_pos': first_char_pos,
                            'task': self.parse_task_progress(str(text).strip())
                        })
            
            return texts
        except Exception as e:
            print(f"✗ OCR 识别失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def test_window(self, hwnd: int, window_name: str):
        """测试单个窗口 - 循环识别直到获取22条任务"""
        global output_dir
        print(f"\n{'='*50}")
        print(f"测试窗口: {window_name} (hwnd={hwnd})")
        print(f"{'='*50}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        all_daily_tasks = []
        seen_task_names = set()
        max_tasks = 50
        loop_count = 0
        last_task_texts = []
        consecutive_same_count = 0
        
        while len(all_daily_tasks) < max_tasks:
            loop_count += 1
            print(f"\n--- 第 {loop_count} 次识别 (当前任务: {len(all_daily_tasks)}) ---")
            
            screenshot = self.get_window_screenshot(hwnd)
            if screenshot is None:
                print("✗ 无法获取窗口截图")
                break
            
            ocr_results = self.recognize_text(screenshot)
            
            if ocr_results:
                print(f"  OCR 识别 {len(ocr_results)} 项")
            else:
                print("  ✗ 未识别到文字")
            
            claim_clicked = self.click_claim_buttons(hwnd, ocr_results)
            if claim_clicked > 0:
                time.sleep(0.5)
                screenshot = self.get_window_screenshot(hwnd)
                if screenshot is not None:
                    ocr_results = self.recognize_text(screenshot)
                    print(f"  点击领取后重新OCR识别 {len(ocr_results)} 项")
            
            task_pattern = self.task_pattern
            new_tasks = [r for r in ocr_results if task_pattern.search(r['text'])]
            
            for task in new_tasks:
                task_text = task['text']
                task_name_normalized = self.progress_pattern.sub('', task_text).strip()
                task_name_normalized = task_name_normalized.replace(',', '').replace('，', '')
                
                if not task_name_normalized or len(task_name_normalized) < 2:
                    continue
                
                if not self.chinese_pattern.search(task_name_normalized):
                    continue
                
                if task_name_normalized in seen_task_names:
                    continue
                
                all_daily_tasks.append(task)
                seen_task_names.add(task_name_normalized)
            
            current_task_texts = [t['text'] for t in new_tasks]
            
            if current_task_texts == last_task_texts and len(current_task_texts) > 0:
                consecutive_same_count += 1
                print(f"  连续相同: {consecutive_same_count}/2")
                if consecutive_same_count >= 2:
                    print(f"\n✓ 连续两次OCR结果相同，停止识别")
                    break
            else:
                consecutive_same_count = 0
            
            last_task_texts = current_task_texts
            
            print(f"  新增任务: {len(new_tasks)}, 总计: {len(all_daily_tasks)}")
            
            print("\n  向上滑动...")
            self.swipe_up_from_center(hwnd, 80)
            
            wait_time = random.uniform(1.8, 2.5)
            print(f"  等待 {wait_time:.1f} 秒...")
            time.sleep(wait_time)
        
        print(f"\n{'='*50}")
        print(f"识别完成! 共获取 {len(all_daily_tasks)} 条每日任务")
        print(f"{'='*50}")
        
        if all_daily_tasks:
            print("\n任务列表:")
            for i, task in enumerate(all_daily_tasks):
                print(f"  [{i+1}] {task['text']} -> {task['task']}")
        
        json_data = {
            "window_name": window_name,
            "hwnd": hwnd,
            "screenshot_size": {"width": screenshot.shape[1], "height": screenshot.shape[0]} if screenshot is not None else {},
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "每日任务": all_daily_tasks
        }
        
        json_path = os.path.join(output_dir, f"daily_task_{hwnd}.json")
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
            print(f"\n✓ 每日任务结果已保存: {json_path}")
        except Exception as e:
            print(f"✗ JSON 保存失败: {e}")


def list_game_windows():
    """列出所有窗口"""
    windows = []
    
    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and "MuMu" in title:
                windows.append((hwnd, title))
    
    win32gui.EnumWindows(callback, None)
    return windows


def main():
    print("=" * 50)
    print("OCR 全屏识别工具")
    print("=" * 50)
    
    windows = list_game_windows()
    
    if not windows:
        print("✗ 未找到任何窗口")
        return
    
    print(f"\n找到 {len(windows)} 个窗口:")
    for i, (hwnd, title) in enumerate(windows):
        print(f"  [{i+1}] {title}")
    
    if len(windows) == 1:
        hwnd, title = windows[0]
        print(f"\n自动选择唯一窗口: {title}")
    else:
        print("\n请选择 MuMu 窗口进行 OCR 识别:")
        choice = input("> ")
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(windows):
                hwnd, title = windows[choice_idx]
            else:
                print("✗ 无效选择")
                return
        except ValueError:
            print("✗ 输入无效，请输入数字")
            return
    
    tester = OCRFullScreenTester()
    
    if not tester.init_ocr():
        print("✗ OCR 初始化失败")
        return
    
    tester.test_window(hwnd, title)


if __name__ == "__main__":
    main()
