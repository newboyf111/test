#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
招募功能 - OCR 识别并点击"招募"按钮
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


class RecruitOCR:
    """招募 OCR 识别类"""

    def __init__(self, ocr_reader=None):
        self.ocr_reader = ocr_reader
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
        except Exception:
            return None

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

                        corrected_text = str(text).strip()

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

    def _get_hero_recruit_remaining(self, hwnd: int):
        """从 JSON 文件中获取英雄招募的 remaining 值"""
        json_path = os.path.join(output_dir, f"daily_task_{hwnd}.json")
        if not os.path.exists(json_path):
            print(f"  未找到 JSON 文件: {json_path}")
            return None

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for task in data.get('每日任务', []):
                if '英雄招募' in task.get('text', ''):
                    return task.get('task', {}).get('remaining')
        except Exception as e:
            print(f"  读取 JSON 失败: {e}")

        return None

    def find_and_click_recruit(self, hwnd: int) -> bool:
        """查找并点击"招募"按钮

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

        recruit_btn = None
        for result in ocr_results:
            text = result.get('text', '').strip()
            pos = result.get('first_char_pos')

            if text == '招募1次' and pos is not None:
                recruit_btn = {
                    'text': text,
                    'position': pos,
                    'confidence': result.get('confidence', 0)
                }
                break

        if recruit_btn is None:
            print("✗ 未找到'招募1次'按钮")
            return False

        try:
            win32gui.ShowWindow(hwnd, 5)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            import ctypes
            ctypes.windll.user32.SetForegroundWindow(hwnd)

        time.sleep(0.3)

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)

        json_remaining = self._get_hero_recruit_remaining(hwnd)
        if json_remaining is None:
            print("  无法获取招募剩余次数，退出")
            return False

        print(f"  英雄招募剩余次数: {json_remaining}")

        for i in range(json_remaining):
            screenshot = self.get_window_screenshot(hwnd)
            if screenshot is None:
                print(f"  第 {i+1} 次招募: 无法获取窗口截图")
                break

            ocr_results = self.recognize_text(screenshot)

            recruit_1btn = None
            for result in ocr_results:
                text = result.get('text', '').strip()
                pos = result.get('first_char_pos')

                if text == '招募1次' and pos is not None:
                    recruit_1btn = {
                        'text': text,
                        'position': pos,
                    }
                    break

            if recruit_1btn is None:
                print(f"  第 {i+1} 次招募: 未找到'招募1次'按钮")
                break

            rel_x, rel_y = recruit_1btn['position']
            screen_x = left + rel_x
            screen_y = top + rel_y

            print(f"  第 {i+1}/{json_remaining} 次点击 '招募1次' 位置: ({screen_x}, {screen_y})")
            pyautogui.click(screen_x, screen_y)

            self._click_to_exit(hwnd)

            time.sleep(random.uniform(0.8, 1.2))

        print(f"  完成 {json_remaining} 次招募")

        self._click_back1(hwnd)

        return True

    def _click_to_exit(self, hwnd: int):
        """等待识别 text=="点击任意位置退出"，然后点击关闭弹窗"""
        max_wait = 10
        wait_interval = 1

        for _ in range(max_wait):
            screenshot = self.get_window_screenshot(hwnd)
            if screenshot is None:
                time.sleep(wait_interval)
                continue

            ocr_results = self.recognize_text(screenshot)

            exit_btn = None
            for result in ocr_results:
                text = result.get('text', '').strip()
                pos = result.get('first_char_pos')

                if text == '点击任意位置退出' and pos is not None:
                    exit_btn = {
                        'text': text,
                        'position': pos,
                    }
                    break

            if exit_btn:
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                rel_x, rel_y = exit_btn['position']
                screen_x = left + rel_x
                screen_y = top + rel_y

                print(f"  点击 '点击任意位置退出' 位置: ({screen_x}, {screen_y})")
                pyautogui.click(screen_x, screen_y)
                time.sleep(random.uniform(1.0, 2.0))
                return

            time.sleep(wait_interval)

        print(f"  未识别到'点击任意位置退出'")

    def _click_back1(self, hwnd: int):
        """点击 back3.png"""
        back_path = os.path.join(project_root, "pic", "back3.png")
        if not os.path.exists(back_path):
            print(f"  未找到 back3.png: {back_path}")
            return

        for attempt in range(10):
            try:
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)

                screenshot = self.get_window_screenshot(hwnd)
                if screenshot is None:
                    time.sleep(0.5)
                    continue

                back_img = cv2.imread(back_path)
                if back_img is None:
                    print(f"  无法读取 back3.png")
                    return

                result = cv2.matchTemplate(screenshot, back_img, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

                if max_val > 0.8:
                    h, w = back_img.shape[:2]
                    click_x = left + max_loc[0] + w // 2
                    click_y = top + max_loc[1] + h // 2

                    print(f"  点击 back3.png 位置: ({click_x}, {click_y}) 匹配度: {max_val:.2f}")
                    pyautogui.click(click_x, click_y)
                    time.sleep(random.uniform(1.0, 2.0))
                    return
                else:
                    if attempt < 9:
                        time.sleep(0.5)
                    else:
                        print(f"  未找到 back3.png (最大匹配度: {max_val:.2f})")
            except Exception as e:
                if attempt < 9:
                    time.sleep(0.5)
                else:
                    print(f"  点击 back3.png 失败: {e}")


def main():
    """主函数"""
    import win32gui

    def get_window_by_title(title):
        hwnd = win32gui.FindWindow(None, title)
        if hwnd:
            return hwnd

        result = []

        def enum_handler(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    result.append((hwnd, title))

        win32gui.EnumWindows(enum_handler, None)

        for h, t in result:
            if title in t:
                return h

        return None

    windows = []

    def enum_handler(hwnd, ctx):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and ('MuMu' in title or '模拟器' in title):
                windows.append((hwnd, title))

    win32gui.EnumWindows(enum_handler, None)

    if not windows:
        print("✗ 未找到 MuMu 窗口")
        return

    print(f"\n找到 {len(windows)} 个窗口:")
    for i, (hwnd, title) in enumerate(windows):
        print(f"  [{i+1}] {title}")

    if len(windows) == 1:
        hwnd, title = windows[0]
    else:
        print(f"\n请选择窗口 [1-{len(windows)}]: ", end='')
        try:
            choice = int(input().strip())
            if choice < 1 or choice > len(windows):
                print("✗ 无效选择")
                return
            hwnd, title = windows[choice - 1]
        except ValueError:
            print("✗ 输入无效")
            return

    print(f"\n选择窗口: {title} (hwnd={hwnd})")

    recruit = RecruitOCR()

    if not recruit.init_ocr():
        print("✗ OCR 初始化失败")
        return

    success = recruit.find_and_click_recruit(hwnd)
    if success:
        print("\n✓ 招募流程完成")
    else:
        print("\n✗ 招募流程失败")


if __name__ == "__main__":
    main()
