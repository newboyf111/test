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
        self.task_pattern = re.compile(r'[（\(]\s*\d+\s*/\s*\d+')
        self.progress_pattern = re.compile(r'[（\(]\s*\d+\s*/\s*\d+\s*[）\)]')
        self.progress_open_pattern = re.compile(r'[（\(]\s*\d+\s*/\s*\d+')
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

    def _check_and_click_exit(self, hwnd: int):
        """检查并点击'点击任意位置退出'弹窗"""
        screenshot = self.get_window_screenshot(hwnd)
        if screenshot is None:
            return False

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
            return True

        return False

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
            except Exception:
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
    
    def _find_and_click_dailyquest(self, hwnd: int, max_retries: int = 7) -> bool:
        """查找并点击每日任务入口
        
        Args:
            hwnd: 窗口句柄
            max_retries: 最大重试次数
            
        Returns:
            是否成功点击
        """
        dailyquest_path = os.path.join(project_root, "pic", "dailyquest.png")
        if not os.path.exists(dailyquest_path):
            print(f"  未找到 dailyquest.png: {dailyquest_path}")
            return False
        
        for attempt in range(max_retries):
            try:
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                
                screenshot = self.get_window_screenshot(hwnd)
                if screenshot is None:
                    time.sleep(0.5)
                    continue
                
                dailyquest_img = cv2.imread(dailyquest_path)
                if dailyquest_img is None:
                    print(f"  无法读取 dailyquest.png")
                    return False
                
                result = cv2.matchTemplate(screenshot, dailyquest_img, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                
                if max_val > 0.8:
                    h, w = dailyquest_img.shape[:2]
                    click_x = left + max_loc[0] + w // 2
                    click_y = top + max_loc[1] + h // 2
                    
                    print(f"  点击 dailyquest.png 位置: ({click_x}, {click_y}) 匹配度: {max_val:.2f}")
                    pyautogui.click(click_x, click_y)
                    
                    time.sleep(random.uniform(1.0, 2.0))
                    
                    screenshot = self.get_window_screenshot(hwnd)
                    if screenshot is not None:
                        ocr_results = self.recognize_text(screenshot)
                        for r in ocr_results:
                            text = r.get('text', '').strip()
                            pos = r.get('first_char_pos')
                            if text == '每日任务' and pos is not None:
                                rel_x, rel_y = pos
                                screen_x = left + rel_x
                                screen_y = top + rel_y
                                print(f"  点击'每日任务'位置: ({screen_x}, {screen_y})")
                                pyautogui.click(screen_x, screen_y)
                                time.sleep(random.uniform(1.0, 2.0))
                                return True
                    
                    return True
                else:
                    if attempt < max_retries - 1:
                        print(f"  未找到 dailyquest.png (匹配度: {max_val:.2f})，重试 {attempt + 1}/{max_retries}")
                        time.sleep(0.5)
                    else:
                        print(f"  未找到 dailyquest.png (最大匹配度: {max_val:.2f})")
                        return False
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  查找每日任务入口失败: {e}，重试 {attempt + 1}/{max_retries}")
                    time.sleep(0.5)
                else:
                    print(f"  查找每日任务入口失败: {e}")
                    return False
        
        return False
    
    def click_claim_buttons(self, hwnd: int, ocr_results: list) -> int:
        """识别并点击所有"领取"按钮
        
        Args:
            hwnd: 窗口句柄
            ocr_results: OCR识别结果列表
            
        Returns:
            点击的按钮数量
        """
        def find_claim_buttons(results):
            claim_buttons = []
            one_click_claim = None
            
            for result in results:
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
                return [one_click_claim]
            return claim_buttons
        
        claim_buttons_to_click = find_claim_buttons(ocr_results)
        
        if not claim_buttons_to_click:
            return 0
        
        if claim_buttons_to_click[0]['text'] == '一键领取':
            print(f"\n  发现'一键领取'按钮，只点击一键领取")
        else:
            print(f"\n  发现 {len(claim_buttons_to_click)} 个领取按钮")
        
        try:
            win32gui.ShowWindow(hwnd, 5)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            import ctypes
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        
        time.sleep(0.3)
        
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        
        clicked_count = 0
        while claim_buttons_to_click:
            btn = claim_buttons_to_click[0]
            rel_x, rel_y = btn['position']
            screen_x = left + rel_x
            screen_y = top + rel_y
            print(f"    [{clicked_count+1}] 点击 '{btn['text']}' 位置: ({screen_x}, {screen_y})")
            
            pyautogui.click(screen_x, screen_y)
            time.sleep(0.8)
            
            screenshot = self.get_window_screenshot(hwnd)
            if screenshot is not None:
                ocr_results = self.recognize_text(screenshot)
                claim_buttons_to_click = find_claim_buttons(ocr_results)
                if not claim_buttons_to_click:
                    print(f"  所有领取按钮已点击完毕")
                    return clicked_count + 1
            
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
            r'[（\(]\s*(\d+)\s*/\s*(\d+)\s*[）\)]',  # 混合括号
            r'[（\(]\s*(\d+)\s*/\s*(\d+)',            # 只有左括号
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
    
    def _correct_ocr_text(self, text: str) -> str:
        """OCR 文本纠错"""
        corrections = {
            '伤斤': '伤兵',
            '每口登寻': '每日登录',
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
                            'task': self.parse_task_progress(corrected_text)
                        })
            
            return texts
        except Exception as e:
            print(f"✗ OCR 识别失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _find_go_to_button(self, task_pos, task_y, ocr_results, next_task_y=None, y_tolerance=30):
        """查找任务行下方、下一个任务上方的"前往"按钮坐标
        
        Args:
            task_pos: 任务的第一个字符位置 (x, y)
            task_y: 任务的 y 坐标
            ocr_results: OCR识别结果列表
            next_task_y: 下一个任务的 y 坐标（用于确定搜索范围上界）
            y_tolerance: y坐标容差
            
        Returns:
            (x, y) 坐标或 None
        """
        if task_pos is None:
            return None
        
        task_x, _ = task_pos
        
        for result in ocr_results:
            text = result.get('text', '').strip()
            pos = result.get('first_char_pos')
            
            if '前往' not in text:
                continue
            
            if pos is None:
                bbox = result.get('bbox')
                if bbox is not None:
                    try:
                        if hasattr(bbox, 'tolist'):
                            bbox = bbox.tolist()
                        if len(bbox) >= 4:
                            pts = bbox[:4]
                            x_coords = [p[0] if hasattr(p, '__iter__') else p for p in pts]
                            y_coords = [p[1] if hasattr(p, '__iter__') else p for p in pts]
                            pos = (int((min(x_coords) + max(x_coords)) / 2), int((min(y_coords) + max(y_coords)) / 2))
                    except Exception:
                        pass
            
            if pos is None:
                continue
            
            btn_x, btn_y = pos
            
            if btn_x <= task_x:
                continue
            
            if btn_y <= task_y + y_tolerance:
                continue
            
            if next_task_y is not None and btn_y >= next_task_y - y_tolerance:
                continue
            
            return (btn_x, btn_y)
        
        return None

    def test_window(self, hwnd: int, window_name: str):
        """测试单个窗口 - 循环识别直到获取22条任务"""
        global output_dir
        print(f"\n{'='*50}")
        print(f"测试窗口: {window_name} (hwnd={hwnd})")
        print(f"{'='*50}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        if not self._find_and_click_dailyquest(hwnd):
            print("  未找到每日任务入口，跳过")
        
        all_daily_tasks = []
        seen_task_names = set()
        restart_count = 0
        
        self._run_recognition_loop(hwnd, window_name, all_daily_tasks, seen_task_names, restart_count)
    
    def _run_recognition_loop(self, hwnd: int, window_name: str, all_daily_tasks: list, seen_task_names: set, restart_count: int = 0, max_loops: int = 50, max_restarts: int = 10):
        """执行识别循环，可以被重复调用继续执行
        
        Args:
            hwnd: 窗口句柄
            window_name: 窗口名称
            all_daily_tasks: 已识别的任务列表（会被修改）
            seen_task_names: 已见过的任务名称集合（会被修改）
            restart_count: 已重启次数
            max_loops: 最大循环次数
            max_restarts: 最大重启次数（防止无限循环）
        """
        if restart_count >= max_restarts:
            print(f"\n✓ 已达到最大重启次数 ({max_restarts})，停止流程")
            return
        
        loop_count = 0
        last_task_texts = []
        consecutive_same_count = 0
        
        while len(all_daily_tasks) < max_loops:
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
            
            while True:
                claim_clicked = self.click_claim_buttons(hwnd, ocr_results)
                if claim_clicked == 0:
                    break
                time.sleep(0.5)
                screenshot = self.get_window_screenshot(hwnd)
                if screenshot is not None:
                    ocr_results = self.recognize_text(screenshot)
                    print(f"  点击领取后重新OCR识别 {len(ocr_results)} 项")
            
            task_pattern = self.task_pattern
            new_tasks = [r for r in ocr_results if task_pattern.search(r['text'])]
            
            all_texts = [r['text'] for r in ocr_results]
            for t in all_texts:
                if '采集' in t:
                    print(f"  [DEBUG] 发现包含'采集'的文本: '{t}' -> 匹配: {bool(task_pattern.search(t))}")
            
            valid_tasks = []
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
                
                valid_tasks.append((task, task_name_normalized))
            
            valid_tasks.sort(key=lambda x: x[0].get('first_char_pos', (0, 0))[1])

            found_go_to = False
            alliance_in_cooldown = False

            for idx, (task, task_name_normalized) in enumerate(valid_tasks):
                next_task_y = None
                if idx + 1 < len(valid_tasks):
                    next_pos = valid_tasks[idx + 1][0].get('first_char_pos')
                    if next_pos:
                        next_task_y = next_pos[1]

                task_pos = task.get('first_char_pos')
                task_y = task_pos[1] if task_pos else 0
                go_to_pos = self._find_go_to_button(task_pos, task_y, ocr_results, next_task_y)

                if go_to_pos is not None and '联盟捐献' in task_name_normalized:
                    try:
                        import importlib.util
                        alliance_script = os.path.join(script_dir, "alliance.py")
                        spec = importlib.util.spec_from_file_location("alliance", alliance_script)
                        alliance_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(alliance_module)

                        alliance = alliance_module.AllianceOCR(ocr_reader=self.ocr_reader)

                        if alliance.check_alliance_skip():
                            print(f"  联盟捐献在冷却期内，跳过")
                            alliance_in_cooldown = True
                            continue
                    except Exception as e:
                        print(f"  检查联盟捐献冷却失败: {e}")

                task['go_to_position'] = go_to_pos

                all_daily_tasks.append(task)
                seen_task_names.add(task_name_normalized)

                if go_to_pos is not None:
                    found_go_to = True
                    print(f"\n  发现'{task_name_normalized}'任务有前往按钮，停止循环")
                    break

            if found_go_to:
                break
            
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

            self._check_and_click_exit(hwnd)

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
        
        self._process_go_to_tasks(hwnd, all_daily_tasks, restart_count)
    
    def _process_go_to_tasks(self, hwnd: int, all_daily_tasks: list, restart_count: int = 0):
        """处理有"前往"按钮的任务
        
        Args:
            hwnd: 窗口句柄
            all_daily_tasks: 任务列表
            restart_count: 已重启次数
        """
        task_with_go = None
        skip_alliance = False
        
        for task in all_daily_tasks:
            if task.get('go_to_position') is not None:
                task_text = task.get('text', '')
                print(f"  检查任务: {task_text[:20]}...")
                
                if '联盟捐献' in task_text:
                    try:
                        import importlib.util
                        alliance_script = os.path.join(script_dir, "alliance.py")
                        spec = importlib.util.spec_from_file_location("alliance", alliance_script)
                        alliance_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(alliance_module)
                        
                        alliance = alliance_module.AllianceOCR(ocr_reader=self.ocr_reader)
                        
                        if alliance.check_alliance_skip():
                            print(f"  联盟捐献在冷却期内，跳过")
                            skip_alliance = True
                            continue
                    except Exception as e:
                        print(f"  检查联盟捐献冷却失败: {e}")
                
                task_with_go = task
                break
        
        if skip_alliance and task_with_go is None:
            print("  所有有前往的任务均已跳过，重新开始")
            self._restart_from_dailyquest(hwnd, restart_count)
            return
        
        if task_with_go is not None:
            task_text = task_with_go.get('text', '')
            print(f"  处理任务: {task_text[:20]}...")
            
            go_to_pos = task_with_go['go_to_position']
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            rel_x, rel_y = go_to_pos
            screen_x = left + rel_x
            screen_y = top + rel_y
            
            print(f"\n  点击'前往'位置: ({screen_x}, {screen_y})")
            pyautogui.click(screen_x, screen_y)
            
            time.sleep(random.uniform(1.0, 2.0))
            
            if '联盟捐献' in task_text:
                try:
                    import importlib.util
                    alliance_script = os.path.join(script_dir, "alliance.py")
                    spec = importlib.util.spec_from_file_location("alliance", alliance_script)
                    alliance_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(alliance_module)
                    
                    alliance = alliance_module.AllianceOCR(ocr_reader=self.ocr_reader)
                    
                    if alliance.check_alliance_skip():
                        print("  联盟捐献在冷却期内，跳过")
                        self._restart_from_dailyquest(hwnd, restart_count)
                    else:
                        success = alliance.run_alliance_flow(hwnd)
                        if success:
                            self._restart_from_dailyquest(hwnd, restart_count)
                except Exception as e:
                    print(f"  启动联盟流程失败: {e}")
                    import traceback
                    traceback.print_exc()
            elif '英雄招募' in task_text:
                try:
                    import importlib.util
                    recruit_script = os.path.join(script_dir, "recruit.py")
                    spec = importlib.util.spec_from_file_location("recruit", recruit_script)
                    recruit_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(recruit_module)
                    
                    recruit = recruit_module.RecruitOCR(ocr_reader=self.ocr_reader)
                    
                    success = recruit.find_and_click_recruit(hwnd)
                    if success:
                        time.sleep(random.uniform(1.0, 2.0))
                        self._restart_from_dailyquest(hwnd, restart_count)
                except Exception as e:
                    print(f"  启动招募流程失败: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("  非联盟捐献/英雄招募任务，继续识别剩余任务")
                self._restart_from_dailyquest(hwnd, restart_count)
    
    def _restart_from_dailyquest(self, hwnd: int, restart_count: int = 0):
        """alliance流程结束后，重新从匹配 dailyquest.png 开始
        
        Args:
            hwnd: 窗口句柄
            restart_count: 已重启次数
        """
        print("\n" + "="*50)
        print(f"重新开始流程... (第{restart_count + 1}次)")
        print("="*50)
        
        if not self._find_and_click_dailyquest(hwnd):
            print("  未找到每日任务入口，跳过")
        
        all_daily_tasks = []
        seen_task_names = set()
        
        self._run_recognition_loop(hwnd, "MuMu", all_daily_tasks, seen_task_names, restart_count + 1)
    
    def _continue_recognition(self, hwnd: int, all_daily_tasks: list):
        """alliance流程结束后继续识别任务
        
        Args:
            hwnd: 窗口句柄
            all_daily_tasks: 已识别的任务列表
        """
        print("\n" + "="*50)
        print("继续识别剩余任务...")
        print("="*50)
        
        screenshot = self.get_window_screenshot(hwnd)
        if screenshot is None:
            print("✗ 无法获取窗口截图")
            return
        
        time.sleep(random.uniform(1.0, 2.0))
        
        ocr_results = self.recognize_text(screenshot)
        
        if ocr_results:
            print(f"  OCR 识别 {len(ocr_results)} 项")
        
        task_pattern = self.task_pattern
        new_tasks = [r for r in ocr_results if task_pattern.search(r['text'])]
        
        seen_task_names = set(t.get('text', '') for t in all_daily_tasks)
        
        valid_tasks = []
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
            
            valid_tasks.append((task, task_name_normalized))
        
        valid_tasks.sort(key=lambda x: x[0].get('first_char_pos', (0, 0))[1])
        
        found_go_to = False
        for idx, (task, task_name_normalized) in enumerate(valid_tasks):
            next_task_y = None
            if idx + 1 < len(valid_tasks):
                next_pos = valid_tasks[idx + 1][0].get('first_char_pos')
                if next_pos:
                    next_task_y = next_pos[1]
            
            task_pos = task.get('first_char_pos')
            task_y = task_pos[1] if task_pos else 0
            go_to_pos = self._find_go_to_button(task_pos, task_y, ocr_results, next_task_y)
            
            task['go_to_position'] = go_to_pos
            
            all_daily_tasks.append(task)
            seen_task_names.add(task_name_normalized)
            
            if go_to_pos is not None:
                found_go_to = True
                print(f"\n  发现'{task_name_normalized}'任务有前往按钮，继续处理")
                break
        
        if found_go_to:
            self._process_go_to_tasks(hwnd, all_daily_tasks, restart_count)
        else:
            print("\n✓ 所有有'前往'的任务已处理完成")
            self._restart_from_dailyquest(hwnd, restart_count)


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
