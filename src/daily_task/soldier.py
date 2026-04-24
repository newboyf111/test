#!/usr/bin/env python3
# -*- coding: utf-8 -*-


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

import cv2
import numpy as np
from datetime import datetime
from src.utils.window_utils import capture_window
from src.utils.adaptive_matcher import AdaptiveMatcher
import time
import re


BASE_WIDTH = 558
BASE_HEIGHT = 1021


class SoldierOCR:
    """资源队列 OCR 识别类"""

    def __init__(self, ocr_reader=None, log_callback=None):
        self.ocr_reader = ocr_reader
        self.log_callback = log_callback
        self.templates = {
            '木头': os.path.join(project_root, "pic", "woodlist.png"),
            '煤炭': os.path.join(project_root, "pic", "coallist.png"),
            '铁矿': os.path.join(project_root, "pic", "ironlist.png"),
            '肉类': os.path.join(project_root, "pic", "meatlist.png"),
            '后撤': os.path.join(project_root, "pic", "backlist.png"),
        }
        self.matcher = AdaptiveMatcher(confidence=0.9)

    def _log(self, message: str):
        """输出日志，支持回调函数"""
        import sys
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)
            sys.stdout.flush()

    def get_window_screenshot(self, hwnd: int):
        """获取窗口截图"""
        result = capture_window(hwnd)
        if result[0] is None:
            return None, 0, 0
        return result[0], result[1], result[2]

    def init_ocr(self):
        """初始化 OCR"""
        if self.ocr_reader is not None:
            return True

        try:
            from rapidocr import RapidOCR
            self.ocr_reader = RapidOCR()
            self._log("✓ RapidOCR 初始化成功")
            return True
        except ImportError as e:
            self._log(f"✗ RapidOCR 未安装: {e}")
            return False
        except Exception as e:
            self._log(f"✗ OCR 初始化失败: {e}")
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

    def recognize_and_print(self, hwnd: int):
        """识别窗口文字并打印所有信息"""
        screenshot, _, _ = self.get_window_screenshot(hwnd)
        if screenshot is None:
            print("✗ 无法获取窗口截图")
            return

        print("\n" + "=" * 50)
        print("开始 OCR 识别...")
        print("=" * 50)

        ocr_results = self.recognize_text(screenshot)

        if not ocr_results:
            print("✗ 未识别到任何文字")
            return

        print(f"\n共识别到 {len(ocr_results)} 个文本区域:\n")

        for i, result in enumerate(ocr_results, 1):
            text = result.get('text', '')
            confidence = result.get('confidence', 0)
            pos = result.get('first_char_pos')
            bbox = result.get('bbox')

            print(f"[{i}] 文字: {text}")
            print(f"    置信度: {confidence:.4f}")
            if pos:
                print(f"    位置(相对坐标): {pos}")
            if bbox is not None:
                print(f"    边界框: {bbox}")
            print()

    def count_queues(self, hwnd: int) -> dict:
        """统计所有资源队列数量
        
        Returns:
            dict: {
                "木头": [{"x": int, "y": int, "timer": "HH:MM:SS" or None, "seconds": int or None}],
                ...
            }
        """
        screenshot, win_w, win_h = self.get_window_screenshot(hwnd)
        if screenshot is None:
            self._log("✗ 无法获取窗口截图")
            return {}

        if not self.init_ocr():
            self._log("✗ OCR 初始化失败")
            return {}

        ocr_results = self.recognize_text(screenshot)
        has_queue_text = False
        for result in ocr_results:
            text = result.get('text', '')
            if '行军' in text:
                has_queue_text = True
                break
        
        if not has_queue_text:
            self._log("  未检测到行军相关文字，跳过资源匹配")
            return {}

        for name, template_path in self.templates.items():
            if not os.path.exists(template_path):
                self._log(f"✗ 未找到模板文件: {template_path}")
                return {}

        all_results = {}

        for resource_name, template_path in self.templates.items():
            self._log(f"正在匹配: {resource_name}...")

            filtered_matches = []
            max_attempts = 50

            for attempt in range(max_attempts):
                result = self.matcher.match(screenshot, template_path, win_w, win_h)

                if not result:
                    break

                x, y = result["location"]
                w, h = result["size"]
                center_x = x + w // 2
                center_y = y + h // 2
                conf = result["confidence"]

                is_duplicate = False
                for match in filtered_matches:
                    if isinstance(match, dict):
                        fx, fy = match["position"]
                    else:
                        fx, fy, _ = match
                    distance = ((center_x - fx) ** 2 + (center_y - fy) ** 2) ** 0.5
                    if distance < 30:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    filtered_matches.append({"position": (center_x, center_y), "confidence": conf})

                cv2.rectangle(screenshot, (x, y), (x + w, y + h), (0, 0, 255), 2)

            count = len(filtered_matches)
            all_results[resource_name] = filtered_matches

            self._log(f"  {resource_name}队列数量: {count}")

        self._log("\n" + "=" * 50)
        self._log("资源队列匹配结果")
        self._log("=" * 50)
        self._log(f"\n窗口尺寸: {win_w}x{win_h}")
        self._log(f"匹配阈值: {self.matcher.confidence}")

        screenshot_for_ocr, _, _ = self.get_window_screenshot(hwnd)
        if screenshot_for_ocr is not None:
            self._log(f"\n各资源队列 OCR 识别结果:")
            for resource_name, matches in all_results.items():
                self._log(f"\n--- {resource_name}队列 ---")
                if not matches:
                    self._log("  无匹配")
                    continue

                for i, match in enumerate(matches, 1):
                    if isinstance(match, dict):
                        x, y = match["position"]
                        conf = match.get("confidence", 0)
                    else:
                        x, y, conf = match

                    roi_x1 = x
                    roi_y1 = max(0, y - 20)
                    roi_x2 = x + 120
                    roi_y2 = y + 20

                    roi = screenshot_for_ocr[roi_y1:roi_y2, roi_x1:roi_x2]

                    timer_info = None
                    seconds_remaining = None

                    if roi.size > 0:
                        ocr_results = self.recognize_text(roi)
                        if ocr_results:
                            texts = [r['text'] for r in ocr_results]
                            combined_text = ', '.join(texts)
                            self._log(f"  [{i}] 位置({x}, {y}): {combined_text}")

                            timer_info, seconds_remaining = self._parse_timer(combined_text)
                            if timer_info:
                                self._log(f"      倒计时: {timer_info} ({seconds_remaining}秒)")
                    else:
                        self._log(f"  [{i}] 位置({x}, {y}): 区域无效")

        total_count = sum(len(matches) for matches in all_results.values())
        self._log(f"\n总计: {total_count} 个资源队列")

        return all_results

    def _parse_timer(self, text: str) -> tuple:
        """解析倒计时文本
        
        Args:
            text: OCR 识别文本，如 "采集中, 06:41:13"
        
        Returns:
            tuple: (timer_text: str, seconds: int) 或 (None, None)
        """
        timer_pattern = re.compile(r'(\d{1,2}:\d{2}:\d{2})')
        match = timer_pattern.search(text)
        
        if match:
            timer_text = match.group(1)
            parts = timer_text.split(':')
            if len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = int(parts[2])
                total_seconds = hours * 3600 + minutes * 60 + seconds
                return timer_text, total_seconds
        
        return None, None

    def _capture_ocr_region(self, screenshot: np.ndarray, win_w: int, win_h: int, region_base: tuple) -> np.ndarray:
        """截取 OCR 识别区域"""
        if screenshot is None:
            return None

        scale = win_w / BASE_WIDTH
        x1 = int(region_base[0] * scale)
        y1 = int(region_base[1] * scale)
        x2 = int(region_base[2] * scale)
        y2 = int(region_base[3] * scale)

        x1 = max(0, min(x1, screenshot.shape[1]))
        y1 = max(0, min(y1, screenshot.shape[0]))
        x2 = max(0, min(x2, screenshot.shape[1]))
        y2 = max(0, min(y2, screenshot.shape[0]))

        if x1 >= x2 or y1 >= y2:
            return None

        return screenshot[y1:y2, x1:x2]

    def _ocr_recognize(self, region: np.ndarray) -> str:
        """OCR 识别区域内容"""
        if self.ocr_reader is None:
            return None

        try:
            ocr_result = self.ocr_reader(region)

            if hasattr(ocr_result, 'txts') and hasattr(ocr_result, 'scores'):
                txts = ocr_result.txts
                scores = ocr_result.scores

                if txts and scores and len(txts) > 0:
                    for text, confidence in zip(txts, scores):
                        cleaned = ''.join(c for c in text if c.isdigit() or c == '/')
                        if '/' in cleaned:
                            return cleaned

                    text = txts[0]
                    cleaned = ''.join(c for c in text if c.isdigit() or c == '/')
                    return cleaned

            return None
        except Exception as e:
            print(f"OCR 识别失败: {e}")
            return None

    def check_mining_remaining(self, hwnd: int) -> dict:
        """检测剩余挖矿次数

        Returns:
            dict: {"ocr_text": "x/y", "current": int, "total": int, "remaining": int}
        """
        screenshot, win_w, win_h = self.get_window_screenshot(hwnd)
        if screenshot is None:
            print("✗ 无法获取窗口截图")
            return {}

        if self.ocr_reader is None:
            if not self.init_ocr():
                return {}

        ocr_region = self._capture_ocr_region(screenshot, win_w, win_h, (156, 184, 194, 220))
        if ocr_region is None:
            print("✗ 截取 OCR 区域失败")
            return {}

        ocr_text = self._ocr_recognize(ocr_region)
        if ocr_text is None:
            print("✗ OCR 识别失败")
            return {}

        try:
            if "/" in ocr_text:
                parts = ocr_text.split("/")
                if len(parts) == 2:
                    current = int(parts[0].strip())
                    total = int(parts[1].strip())
                    remaining = total - current

                    print(f"\n" + "=" * 50)
                    print("挖矿剩余次数检测")
                    print("=" * 50)
                    print(f"OCR 识别: {ocr_text}")
                    print(f"当前/总数: {current}/{total}")
                    print(f"剩余次数: {remaining}")
                    print()

                    return {
                        "ocr_text": ocr_text,
                        "current": current,
                        "total": total,
                        "remaining": remaining
                    }
        except (ValueError, IndexError) as e:
            print(f"解析 OCR 结果失败: {e}")

        return {}

    def monitor_and_check(self, hwnd: int, interval: int = 30):
        """持续监控并检测挖矿倒计时，结束时调用检查

        Args:
            hwnd: 窗口句柄
            interval: 检测间隔（秒）
        """
        print(f"\n开始监控挖矿倒计时 (间隔: {interval}秒)")
        print("按 Ctrl+C 停止监控\n")

        if not self.init_ocr():
            print("✗ OCR 初始化失败")
            return

        queue_timers = {}

        try:
            while True:
                screenshot, win_w, win_h = self.get_window_screenshot(hwnd)
                if screenshot is None:
                    print("✗ 无法获取窗口截图")
                    time.sleep(interval)
                    continue

                queue_status = self._check_all_queues_with_timer(screenshot, win_w, win_h)

                if queue_status:
                    current_time = datetime.now()

                    if not queue_timers:
                        print(f"\n[{current_time.strftime('%H:%M:%S')}] 检测到资源队列:")

                    finished_resources = []

                    for resource_name, queue_list in queue_status.items():
                        for queue_info in queue_list:
                            timer_text = queue_info.get("timer")
                            seconds = queue_info.get("seconds", -1)
                            position = queue_info.get("position")

                            queue_key = f"{resource_name}_{position[0]}_{position[1]}"

                            if timer_text and seconds is not None and seconds > 0:
                                if queue_key not in queue_timers:
                                    queue_timers[queue_key] = {
                                        "resource_name": resource_name,
                                        "start_time": current_time,
                                        "initial_seconds": seconds,
                                        "timer_text": timer_text
                                    }
                                    print(f"  {resource_name}: {timer_text}")

                                elapsed = int((current_time - queue_timers[queue_key]["start_time"]).total_seconds())
                                remaining = queue_timers[queue_key]["initial_seconds"] - elapsed

                                if remaining <= 0:
                                    finished_resources.append(queue_key)
                                    print(f"  ⚠ {resource_name} 挖矿完成!")
                                    del queue_timers[queue_key]
                                else:
                                    hours = remaining // 3600
                                    mins = (remaining % 3600) // 60
                                    secs = remaining % 60
                                    dynamic_timer = f"{hours:02d}:{mins:02d}:{secs:02d}"

                                    prev_timer = queue_timers[queue_key].get("last_display")
                                    if prev_timer != dynamic_timer:
                                        queue_timers[queue_key]["last_display"] = dynamic_timer
                                        print(f"  {resource_name}: {dynamic_timer}")

                            else:
                                if queue_key in queue_timers:
                                    del queue_timers[queue_key]

                    if finished_resources:
                        print(f"\n检测到 {len(finished_resources)} 个挖矿完成，开始检测剩余次数...")
                        mining_result = self.check_mining_remaining(hwnd)
                        if mining_result:
                            print(f"挖矿剩余次数: {mining_result.get('remaining', 'N/A')}")

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n监控已停止")

    def _check_all_queues_with_timer(self, screenshot: np.ndarray, win_w: int, win_h: int) -> dict:
        """检测所有资源队列及其倒计时
        
        基于模板匹配定位资源图标，然后截取 ROI 区域 OCR 识别倒计时
        
        Returns:
            dict: {"木头": [{"position": (x, y), "timer": "HH:MM:SS", "seconds": int}, ...], ...}
        """
        if self.ocr_reader is None:
            return {}

        results = {}

        for resource_name, template_path in self.templates.items():
            if not os.path.exists(template_path):
                continue

            filtered_matches = []
            max_attempts = 100

            # 创建截图副本用于遮蔽已匹配区域
            temp_screenshot = screenshot.copy()

            for attempt in range(max_attempts):
                result = self.matcher.match(temp_screenshot, template_path, win_w, win_h)
                if not result:
                    break

                x, y = result["location"]
                w, h = result["size"]
                center_x = x + w // 2
                center_y = y + h // 2

                # 检查是否与已有结果距离过近（去重）
                is_duplicate = False
                for match in filtered_matches:
                    fx, fy = match["position"]
                    distance = ((center_x - fx) ** 2 + (center_y - fy) ** 2) ** 0.5
                    if distance < 20:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    roi_x1 = center_x
                    roi_y1 = max(0, center_y - 20)
                    roi_x2 = center_x + 120
                    roi_y2 = center_y + 20

                    roi = screenshot[roi_y1:roi_y2, roi_x1:roi_x2]

                    timer_text = None
                    seconds = None
                    full_text = ""

                    if roi.size > 0:
                        ocr_results = self.recognize_text(roi)
                        if ocr_results:
                            texts = [r['text'] for r in ocr_results]
                            full_text = ', '.join(texts)
                            timer_text, seconds = self._parse_timer(full_text)

                    filtered_matches.append({
                        "position": (center_x, center_y),
                        "timer": timer_text,
                        "seconds": seconds,
                        "full_text": full_text
                    })

                    # 遮蔽已匹配区域，让后续匹配找到新的位置
                    # 将匹配区域填充为黑色，避免重复匹配
                    temp_screenshot[y:y+h, x:x+w] = 0

            if filtered_matches:
                results[resource_name] = filtered_matches

        return results


def main(hwnd=None):
    """主函数
    
    Args:
        hwnd: 窗口句柄，如果为 None 则自动选择窗口
    """
    if hwnd is None:
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

    soldier = SoldierOCR()

    print("\n" + "=" * 50)
    print("开始执行: 统计资源队列 -> 监控倒计时 -> 检测剩余次数")
    print("=" * 50 + "\n")

    print("\n[步骤1] 统计资源队列...")
    queue_result = soldier.count_queues(hwnd)

    if not queue_result:
        print("\n没有检测到资源队列，流程结束")
        return

    print("\n[步骤2] 开始监控挖矿倒计时...")
    print("        当倒计时结束时，将自动检测剩余挖矿次数")
    print("        按 Ctrl+C 停止\n")

    soldier.monitor_and_check(hwnd, interval=30)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='资源队列监控')
    parser.add_argument('--hwnd', type=int, help='窗口句柄')
    args = parser.parse_args()
    main(args.hwnd)
