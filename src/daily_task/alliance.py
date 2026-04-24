#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
联盟功能 - OCR 识别并点击"联盟"按钮
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


class AllianceOCR:
    """联盟 OCR 识别类"""
    
    def __init__(self, ocr_reader=None):
        self.ocr_reader = ocr_reader
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
        self.progress_pattern = re.compile(r'\d+\s*/\s*\d+')
        self.progress_extract = re.compile(r'(\d+)\s*/\s*(\d+)')
        self.count_pattern = re.compile(r'次数[：:]\s*(\d+)\s*/\s*(\d+)')
        
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
        except Exception:
            return None
    
    def _correct_ocr_text(self, text: str) -> str:
        """OCR 文本纠错"""
        corrections = {
            '伤斤': '伤兵',
            '每口登寻': '每日登录',
            '盟科技': '联盟科技',
            '天联盟科技': '联盟科技',
        }
        for wrong, correct in corrections.items():
            text = text.replace(wrong, correct)
        return text
    
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
                        
                        corrected_text = self._correct_ocr_text(str(text).strip())
                        
                        bbox = None
                        first_char_pos = None
                        
                        if boxes is not None and i < len(boxes) and boxes[i] is not None:
                            bbox = boxes[i]
                            try:
                                if len(bbox) >= 4:
                                    first_char_pos = self.get_first_char_position(bbox)
                            except Exception:
                                pass
                        
                        texts.append({
                            'text': corrected_text,
                            'confidence': conf,
                            'first_char_pos': first_char_pos,
                            'bbox': bbox
                        })
            
            return texts
        except Exception as e:
            print(f"✗ OCR 识别失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def find_and_click_alliance(self, hwnd: int) -> bool:
        """查找并点击"联盟"按钮，然后点击"联盟科技"
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            是否成功点击
        """
        screenshot = self.get_window_screenshot(hwnd)
        if screenshot is None:
            print("✗ 无法获取窗口截图")
            return False
        
        ocr_results = self.recognize_text(screenshot)
        
        if not ocr_results:
            print("✗ 未识别到文字")
            return False
        
        alliance_btn = None
        for result in ocr_results:
            text = result.get('text', '').strip()
            pos = result.get('first_char_pos')
            
            if text == '联盟' and pos is not None:
                alliance_btn = {
                    'text': text,
                    'position': pos,
                    'confidence': result.get('confidence', 0)
                }
                break
        
        if alliance_btn is None:
            print("✗ 未找到'联盟'按钮")
            return False
        
        try:
            win32gui.ShowWindow(hwnd, 5)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            import ctypes
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        
        time.sleep(0.3)
        
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        rel_x, rel_y = alliance_btn['position']
        screen_x = left + rel_x
        screen_y = top + rel_y
        
        print(f"  点击 '联盟' 位置: ({screen_x}, {screen_y})")
        pyautogui.click(screen_x, screen_y)
        
        wait_time = random.uniform(1.0, 2.0)
        print(f"  等待 {wait_time:.1f} 秒...")
        time.sleep(wait_time)
        
        screenshot = self.get_window_screenshot(hwnd)
        if screenshot is None:
            print("✗ 无法获取窗口截图")
            return False
        
        ocr_results = self.recognize_text(screenshot)
        
        tech_btn = None
        for result in ocr_results:
            text = result.get('text', '').strip()
            pos = result.get('first_char_pos')
            
            if '联盟科技' in text and pos is not None:
                tech_btn = {
                    'text': text,
                    'position': pos,
                    'confidence': result.get('confidence', 0)
                }
                break
        
        if tech_btn is None:
            print("✗ 未找到'联盟科技'按钮")
            return False
        
        rel_x, rel_y = tech_btn['position']
        screen_x = left + rel_x
        screen_y = top + rel_y
        
        print(f"  点击 '{tech_btn['text']}' 位置: ({screen_x}, {screen_y})")
        pyautogui.click(screen_x, screen_y)
        
        time.sleep(random.uniform(1.0, 2.0))
        
        screenshot = self.get_window_screenshot(hwnd)
        if screenshot is not None:
            ocr_results = self.recognize_text(screenshot)
            
            for result in ocr_results:
                text = result.get('text', '').strip()
                pos = result.get('first_char_pos')
                
                if pos is None:
                    continue
                
                match = self.progress_pattern.search(text)
                if match and self.progress_extract.search(text):
                    extract = self.progress_extract.search(text)
                    current = int(extract.group(1))
                    target = int(extract.group(2))
                    if target - current != 0:
                        rel_x, rel_y = pos
                        screen_x = left + rel_x
                        screen_y = top + rel_y
                        
                        print(f"  点击未完成进度 '{text}' (剩余{target - current}) 位置: ({screen_x}, {screen_y})")
                        pyautogui.click(screen_x, screen_y)
                        
                        time.sleep(random.uniform(1.0, 2.0))
                        
                        screenshot = self.get_window_screenshot(hwnd)
                        if screenshot is not None:
                            ocr_results = self.recognize_text(screenshot)
                            
                            count_match = None
                            for r in ocr_results:
                                t = r.get('text', '').strip()
                                m = self.count_pattern.search(t)
                                if m:
                                    count_match = m
                                    break
                            
                            if count_match:
                                remaining = int(count_match.group(1))
                                print(f"  检测到次数: 剩余 {remaining}")
                                
                                json_remaining = self._get_alliance_donate_remaining(hwnd)
                                
                                if json_remaining is not None and remaining >= json_remaining:
                                    print(f"  剩余次数({remaining}) >= JSON联盟捐献remaining({json_remaining}), 执行捐献")
                                    self._click_donate(hwnd, json_remaining)
                                elif json_remaining is not None and remaining < json_remaining:
                                    print(f"  剩余次数({remaining}) < JSON联盟捐献remaining({json_remaining}), 不执行捐献")
                                    self.skip_alliance_donate()
                            
                            self._click_close(hwnd)
                        
                        break
            else:
                print("  所有任务已完成")
                self._click_close(hwnd)
        
        return True
    
    def _get_alliance_donate_remaining(self, hwnd: int):
        """从 JSON 文件中获取联盟捐献的 remaining 值"""
        json_path = os.path.join(output_dir, f"daily_task_{hwnd}.json")
        if not os.path.exists(json_path):
            print(f"  未找到 JSON 文件: {json_path}")
            return None
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for task in data.get('每日任务', []):
                if '联盟捐献' in task.get('text', ''):
                    return task.get('task', {}).get('remaining')
        except Exception as e:
            print(f"  读取 JSON 失败: {e}")
        
        return None
    
    def _click_donate(self, hwnd: int, count: int):
        """点击捐献按钮指定次数"""
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        
        for i in range(count):
            screenshot = self.get_window_screenshot(hwnd)
            if screenshot is None:
                break
            
            ocr_results = self.recognize_text(screenshot)
            
            donate_btn = None
            for result in ocr_results:
                text = result.get('text', '').strip()
                pos = result.get('first_char_pos')
                
                if text == '捐献' and pos is not None:
                    donate_btn = {
                        'text': text,
                        'position': pos,
                    }
            
            if donate_btn is None:
                print(f"  第 {i+1} 次捐献: 未找到'捐献'按钮")
                break
            
            rel_x, rel_y = donate_btn['position']
            screen_x = left + rel_x
            screen_y = top + rel_y
            
            print(f"  第 {i+1}/{count} 次捐献: 点击 '{donate_btn['text']}' 位置: ({screen_x}, {screen_y})")
            pyautogui.click(screen_x, screen_y)
            
            if i < count - 1:
                time.sleep(0.5)
    
    def _click_close(self, hwnd: int):
        """点击 close.png 关闭，然后连续点击两次 back1.png"""
        close_path = os.path.join(project_root, "pic", "close.png")
        if not os.path.exists(close_path):
            print(f"  未找到 close.png: {close_path}")
            return
        
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            
            screenshot = self.get_window_screenshot(hwnd)
            if screenshot is None:
                return
            
            close_img = cv2.imread(close_path)
            if close_img is None:
                print(f"  无法读取 close.png")
                return
            
            result = cv2.matchTemplate(screenshot, close_img, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val > 0.8:
                h, w = close_img.shape[:2]
                click_x = left + max_loc[0] + w // 2
                click_y = top + max_loc[1] + h // 2
                
                print(f"  点击 close.png 位置: ({click_x}, {click_y}) 匹配度: {max_val:.2f}")
                pyautogui.click(click_x, click_y)
                
                time.sleep(random.uniform(1.0, 2.0))
                
                self._click_back1(hwnd)
                
                time.sleep(random.uniform(1.0, 2.0))
                
                self._click_back1(hwnd)
            else:
                print(f"  未找到 close.png (最大匹配度: {max_val:.2f})")
        except Exception as e:
            print(f"  点击 close.png 失败: {e}")
    
    def _click_back1(self, hwnd: int):
        """点击 back1.png"""
        back_path = os.path.join(project_root, "pic", "back1.png")
        if not os.path.exists(back_path):
            print(f"  未找到 back1.png: {back_path}")
            return
        
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            
            screenshot = self.get_window_screenshot(hwnd)
            if screenshot is None:
                return
            
            back_img = cv2.imread(back_path)
            if back_img is None:
                print(f"  无法读取 back1.png")
                return
            
            result = cv2.matchTemplate(screenshot, back_img, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val > 0.8:
                h, w = back_img.shape[:2]
                click_x = left + max_loc[0] + w // 2
                click_y = top + max_loc[1] + h // 2
                
                print(f"  点击 back1.png 位置: ({click_x}, {click_y}) 匹配度: {max_val:.2f}")
                pyautogui.click(click_x, click_y)
            else:
                print(f"  未找到 back1.png (最大匹配度: {max_val:.2f})")
        except Exception as e:
            print(f"  点击 back1.png 失败: {e}")
    
    def run_alliance_flow(self, hwnd: int) -> bool:
        """执行完整的联盟流程：点击联盟 -> 联盟科技 -> 进度 -> 捐献 -> 关闭
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            是否成功完成
        """
        if self.ocr_reader is None:
            if not self.init_ocr():
                return False
        
        success = self.find_and_click_alliance(hwnd)
        if success:
            print("✓ 联盟流程完成")
            return True
        else:
            print("✗ 联盟流程失败")
            return False
    
    def skip_alliance_donate(self):
        """记录联盟捐献冷却时间（1分钟）"""
        skip_file = os.path.join(output_dir, "alliance_skip.txt")
        import datetime
        skip_time = datetime.datetime.now()
        with open(skip_file, 'w', encoding='utf-8') as f:
            f.write(skip_time.strftime("%Y-%m-%d %H:%M:%S"))
        print(f"  已记录联盟捐献冷却时间: {skip_time.strftime('%H:%M:%S')}")
    
    def check_alliance_skip(self) -> bool:
        """检查是否在联盟捐献冷却期内
        
        Returns:
            True 在冷却期内应跳过，False 可以执行
        """
        skip_file = os.path.join(output_dir, "alliance_skip.txt")
        if not os.path.exists(skip_file):
            return False
        
        try:
            with open(skip_file, 'r', encoding='utf-8') as f:
                skip_time_str = f.read().strip()
            
            import datetime
            skip_time = datetime.datetime.strptime(skip_time_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.datetime.now()
            
            elapsed = (now - skip_time).total_seconds()
            if elapsed < 60:
                print(f"  联盟捐献冷却期内 ({int(60 - elapsed)}秒)，跳过")
                return True
            
            os.remove(skip_file)
            return False
        except Exception:
            return False
    
    def run(self, window_name: str = None):
        """运行联盟识别"""
        if not self.init_ocr():
            return
        
        if window_name is None:
            windows = []
            def enum_callback(hwnd, lst):
                lst.append(hwnd)
                return True
            win32gui.EnumWindows(enum_callback, windows)
            for h in windows:
                try:
                    name = win32gui.GetWindowText(h)
                    if name and win32gui.IsWindowVisible(h):
                        print(f"  找到窗口: {name} (hwnd={h})")
                except Exception:
                    pass
            return
        
        hwnd = win32gui.FindWindow(None, window_name)
        if hwnd == 0:
            print(f"✗ 未找到窗口: {window_name}")
            return
        
        print(f"\n{'='*50}")
        print(f"联盟识别: {window_name} (hwnd={hwnd})")
        print(f"{'='*50}")
        
        success = self.find_and_click_alliance(hwnd)
        if success:
            print("✓ 成功点击'联盟'按钮")
        else:
            print("✗ 未能点击'联盟'按钮")


def list_game_windows():
    """列出所有游戏窗口"""
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
    print("联盟 OCR 识别工具")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        hwnd = int(sys.argv[1])
        title = win32gui.GetWindowText(hwnd)
        print(f"\n使用指定窗口: {title} (hwnd={hwnd})")
    else:
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
            print("\n请选择 MuMu 窗口进行联盟识别:")
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
    
    tester = AllianceOCR()
    
    if not tester.init_ocr():
        print("✗ OCR 初始化失败")
        return
    
    print(f"\n{'='*50}")
    print(f"联盟识别: {title} (hwnd={hwnd})")
    print(f"{'='*50}")
    
    success = tester.find_and_click_alliance(hwnd)
    if success:
        print("✓ 成功点击'联盟'按钮")
    else:
        print("✗ 未能点击'联盟'按钮")


if __name__ == "__main__":
    main()
