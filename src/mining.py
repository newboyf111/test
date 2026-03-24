#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无尽冬日 (Wujindongri) - 多窗口自动轮换挖矿模块
核心功能：
- 支持多个游戏窗口独立挖矿
- 每个窗口在独立线程中运行
- 一个窗口出错不影响其他窗口
- 窗口挖矿停止后，自动启动下一个未标记的窗口
- 跨分辨率、跨DPI、跨窗口尺寸自适应图片匹配

基准配置：
- 截图窗口尺寸: 558 x 1021
- 屏幕分辨率: 2560 x 1440
- DPI缩放: 100%
"""

import threading
import time
import random
import logging
import cv2
import numpy as np
import pyautogui
import os
import ctypes
import win32gui
import win32con
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from collections import defaultdict


# ─────────────────────────────────────────────
# DPI 感知设置
# ─────────────────────────────────────────────

def set_dpi_aware():
    """设置进程为DPI感知，确保坐标和像素一致"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


set_dpi_aware()


# ─────────────────────────────────────────────
# 屏幕截图工具
# ─────────────────────────────────────────────

def capture_window(hwnd: int) -> Tuple[Optional[np.ndarray], int, int]:
    """截取窗口内容，返回BGR图像和窗口尺寸"""
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        logic_width = right - left
        logic_height = bottom - top

        if logic_width <= 0 or logic_height <= 0:
            return None, 0, 0

        screenshot = pyautogui.screenshot(region=(left, top, logic_width, logic_height))
        img = np.array(screenshot)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        phys_height, phys_width = img_bgr.shape[:2]

        if phys_width != logic_width or phys_height != logic_height:
            img_bgr = cv2.resize(img_bgr, (logic_width, logic_height),
                                 interpolation=cv2.INTER_AREA)

        return img_bgr, logic_width, logic_height

    except Exception as e:
        logging.getLogger(__name__).error(f"截图失败: {e}")
        return None, 0, 0


# ─────────────────────────────────────────────
# 自适应图片匹配器
# ─────────────────────────────────────────────

class AdaptiveMatcher:
    """自适应图片匹配器"""

    BASE_WIDTH = 558
    BASE_HEIGHT = 1021
    FALLBACK_SCALE_MIN = 0.5
    FALLBACK_SCALE_MAX = 2.0
    FALLBACK_STEPS = 20

    def __init__(self, confidence: float = 0.65, logger=None):
        self.confidence = confidence
        self.logger = logger or logging.getLogger(__name__)
        self._template_cache: Dict[str, np.ndarray] = {}
        self._scaled_cache: Dict[tuple, np.ndarray] = {}
        self._last_success_scale: Dict[str, float] = {}

    def log(self, level: str, msg: str):
        getattr(self.logger, level)(msg)

    def load_template(self, image_path: str) -> Optional[np.ndarray]:
        """加载模板图片（带缓存）"""
        if image_path not in self._template_cache:
            if not os.path.exists(image_path):
                self.log("warning", f"图片不存在: {image_path}")
                return None
            img = cv2.imread(image_path)
            if img is None:
                self.log("warning", f"无法读取图片: {image_path}")
                return None
            self._template_cache[image_path] = img
            self.log("debug", f"加载模板: {os.path.basename(image_path)} {img.shape[1]}x{img.shape[0]}")
        return self._template_cache.get(image_path)

    def get_scale_factor(self, current_width: int, current_height: int) -> float:
        """计算窗口缩放比例"""
        if self.BASE_WIDTH == 0:
            return 1.0
        return current_width / self.BASE_WIDTH

    def scale_template(self, template: np.ndarray, scale: float) -> np.ndarray:
        """按比例缩放模板图片"""
        if abs(scale - 1.0) < 0.001:
            return template
        h, w = template.shape[:2]
        new_w = max(8, int(w * scale))
        new_h = max(8, int(h * scale))
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        return cv2.resize(template, (new_w, new_h), interpolation=interp)

    def get_scaled_template(self, image_path: str, scale: float) -> Optional[np.ndarray]:
        """获取缩放后的模板（带缓存）"""
        cache_key = (image_path, round(scale, 3))
        if cache_key not in self._scaled_cache:
            template = self.load_template(image_path)
            if template is None:
                return None
            scaled = self.scale_template(template, scale)
            self._scaled_cache[cache_key] = scaled
        return self._scaled_cache.get(cache_key)

    def match_single(self, screenshot: np.ndarray, template: np.ndarray) -> Optional[dict]:
        """单次模板匹配"""
        try:
            gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            gray_tmpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            tmpl_h, tmpl_w = gray_tmpl.shape[:2]
            scr_h, scr_w = gray_screen.shape[:2]
            if tmpl_w > scr_w or tmpl_h > scr_h:
                return None
            result = cv2.matchTemplate(gray_screen, gray_tmpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= self.confidence:
                return {
                    "found": True,
                    "location": max_loc,
                    "confidence": max_val,
                    "size": (tmpl_w, tmpl_h)
                }
        except Exception as e:
            self.log("error", f"匹配错误: {e}")
        return None

    def match_multi_scale(self, screenshot: np.ndarray, template: np.ndarray,
                          scale_min: float, scale_max: float, steps: int) -> Optional[dict]:
        """多尺度匹配（备选方案）"""
        try:
            gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            gray_tmpl_orig = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            orig_h, orig_w = gray_tmpl_orig.shape[:2]
            best_score = 0.0
            best_result = None
            for scale in np.linspace(scale_min, scale_max, steps):
                new_w = int(orig_w * scale)
                new_h = int(orig_h * scale)
                if new_w < 8 or new_h < 8:
                    continue
                if new_w > screenshot.shape[1] or new_h > screenshot.shape[0]:
                    continue
                gray_tmpl = cv2.resize(gray_tmpl_orig, (new_w, new_h),
                                       interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
                result = cv2.matchTemplate(gray_screen, gray_tmpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                if max_val > best_score:
                    best_score = max_val
                    best_result = {"location": max_loc, "size": (new_w, new_h), "scale": scale}
            if best_result and best_score >= self.confidence:
                best_result["found"] = True
                best_result["confidence"] = best_score
                return best_result
        except Exception as e:
            self.log("error", f"多尺度匹配错误: {e}")
        return None

    def match(self, screenshot: np.ndarray, image_path: str,
              window_width: int, window_height: int) -> Optional[dict]:
        """主匹配函数"""
        template = self.load_template(image_path)
        if template is None:
            return None
        image_name = os.path.basename(image_path)
        scale = self.get_scale_factor(window_width, window_height)
        scaled_template = self.get_scaled_template(image_path, scale)
        if scaled_template is not None:
            result = self.match_single(screenshot, scaled_template)
            if result:
                result["scale"] = scale
                result["method"] = "window_scale"
                self._last_success_scale[image_path] = scale
                self.log("debug", f"[比例匹配] {image_name} scale={scale:.3f} conf={result['confidence']:.3f}")
                return result
        self.log("info", f"比例匹配失败，启用备选搜索: {image_name}")
        if image_path in self._last_success_scale:
            last_scale = self._last_success_scale[image_path]
            search_min = max(self.FALLBACK_SCALE_MIN, last_scale - 0.2)
            search_max = min(self.FALLBACK_SCALE_MAX, last_scale + 0.2)
            result = self.match_multi_scale(screenshot, template, search_min, search_max, 10)
            if result:
                result["method"] = "fallback_near_last"
                self._last_success_scale[image_path] = result["scale"]
                self.log("info", f"[备选-近邻] {image_name} scale={result['scale']:.3f} conf={result['confidence']:.3f}")
                return result
        result = self.match_multi_scale(screenshot, template,
                                        self.FALLBACK_SCALE_MIN,
                                        self.FALLBACK_SCALE_MAX,
                                        self.FALLBACK_STEPS)
        if result:
            result["method"] = "fallback_full"
            self._last_success_scale[image_path] = result["scale"]
            self.log("info", f"[备选-全范围] {image_name} scale={result['scale']:.3f} conf={result['confidence']:.3f}")
            return result
        self.log("debug", f"未找到: {image_name}")
        return None

    def get_center(self, result: dict) -> Optional[Tuple[int, int]]:
        """获取匹配结果的中心点"""
        if not result or not result.get("found"):
            return None
        x, y = result["location"]
        w, h = result["size"]
        return (x + w // 2, y + h // 2)

    def clear_cache(self):
        """清除缓存"""
        self._scaled_cache.clear()


# ─────────────────────────────────────────────
# 单窗口挖矿模块
# ─────────────────────────────────────────────

class SingleWindowMiner:
    """单个窗口的挖矿模块"""

    def __init__(self, hwnd: int, window_name: str = ""):
        self.hwnd = hwnd
        self.window_name = window_name or f"Window_{hwnd}"
        self.is_mining = False
        self.mining_thread = None
        self.logger = self._setup_logger()
        self.matcher = AdaptiveMatcher(confidence=0.65, logger=self.logger)

        pic_dir = Path(__file__).parent.parent / "pic"

        self.image_paths = {
            "town":        str(pic_dir / "town.png"),
            "wild":        str(pic_dir / "wild.png"),
            "search":      str(pic_dir / "search.png"),
            "meat":        str(pic_dir / "meat.png"),
            "wood":        str(pic_dir / "wood.png"),
            "coal":        str(pic_dir / "coal mine.png"),
            "iron":        str(pic_dir / "iron.png"),
            "add":         str(pic_dir / "add.png"),
            "search_meat": str(pic_dir / "search_meat.png"),
            "gather":      str(pic_dir / "gather.png"),
            "battle":      str(pic_dir / "battle.png"),
            "team":        str(pic_dir / "team.png"),
            "close":       str(pic_dir / "close.png"),
            "minus":       str(pic_dir / "minus.png"),
            "back":        str(pic_dir / "back.png"),
            "back1":       str(pic_dir / "back1.png"),
        }

        self.resource_order = ["meat", "wood", "coal", "iron"]
        self.resource_index = 0
        self.last_window_size = None
        self.retry_times = 3
        self.retry_delay = 2
        self.completed_cycles = 0
        self.max_cycles = 6

        self._screenshot_cache = None
        self._screenshot_time = 0
        self._screenshot_ttl = 0.5

        self.image_confidence = {
            "back":  0.75,
            "back1": 0.75,
        }

        # 挖矿标记（True 表示已完成挖矿）
        self.mined = False
        
        # 挖矿管理器引用
        self.mining_manager = None

    def _setup_logger(self) -> logging.Logger:
        """为每个窗口创建独立的日志记录器"""
        logger = logging.getLogger(f"mining_{self.hwnd}")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                f"[{self.window_name}] %(asctime)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
        return logger

    def _get_screenshot(self) -> Tuple[Optional[np.ndarray], int, int]:
        """获取截图（带缓存）"""
        current_time = time.time()

        if (self._screenshot_cache is not None and
                current_time - self._screenshot_time < self._screenshot_ttl):
            return self._screenshot_cache, self.last_window_size[0], self.last_window_size[1]

        if not win32gui.IsWindow(self.hwnd):
            self.logger.warning("窗口无效")
            return None, 0, 0

        screenshot, win_w, win_h = capture_window(self.hwnd)
        self._screenshot_cache = screenshot
        self._screenshot_time = current_time
        return screenshot, win_w, win_h

    def _invalidate_screenshot(self):
        """清除截图缓存"""
        self._screenshot_cache = None
        self._screenshot_time = 0

    def _get_window_size(self) -> Optional[Tuple[int, int]]:
        """获取窗口尺寸"""
        try:
            left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
            return (right - left, bottom - top)
        except Exception:
            return None

    def start_mining(self) -> bool:
        """开始挖矿"""
        if not self.is_mining:
            self.is_mining = True
            self.completed_cycles = 0
            size = self._get_window_size()
            if size:
                self.last_window_size = size
            self.logger.info("=" * 50)
            self.logger.info("挖矿开始")
            self.logger.info(f"基准尺寸: {AdaptiveMatcher.BASE_WIDTH}x{AdaptiveMatcher.BASE_HEIGHT}")
            self.logger.info("=" * 50)
            self.mining_thread = threading.Thread(target=self._mining_loop, daemon=True)
            self.mining_thread.start()
            return True
        return False

    def stop_mining(self) -> bool:
        """停止挖矿"""
        if self.is_mining:
            self.is_mining = False
            # 标记窗口为已挖矿
            self.mined = True
            self.logger.info(f"挖矿结束，标记窗口为已挖矿")
            return True
        return False

    def get_mining_status(self) -> bool:
        return self.is_mining
    
    def set_timer(self, seconds: int):
        """设置倒计时（秒）"""
        if hasattr(self, 'timer_running') and self.timer_running:
            self.timer_running = False
        self.timer_minutes = seconds // 60 if seconds >= 60 else 1
        self.timer_remaining = seconds
        self.logger.info(f"设置倒计时: {seconds} 秒")
    
    def start_timer(self):
        """启动倒计时"""
        if not hasattr(self, 'timer_running'):
            self.timer_running = False
        if not hasattr(self, 'timer_minutes'):
            self.timer_minutes = 0
        if not hasattr(self, 'timer_remaining'):
            self.timer_remaining = 0
        
        if self.timer_minutes > 0 and not self.timer_running:
            self.timer_running = True
            self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
            self.timer_thread.start()
            self.logger.info("倒计时启动")
    
    def stop_timer(self):
        """停止倒计时"""
        if hasattr(self, 'timer_running') and self.timer_running:
            self.timer_running = False
            self.logger.info("倒计时停止")
    
    def get_timer_remaining(self) -> int:
        """获取倒计时剩余时间（秒）"""
        if hasattr(self, 'timer_remaining'):
            return self.timer_remaining
        return 0
    
    def _timer_loop(self):
        """倒计时主循环"""
        self.logger.info(f"倒计时循环开始: timer_remaining={self.timer_remaining}, timer_running={self.timer_running}")
        while self.timer_running and self.timer_remaining > 0:
            time.sleep(1)
            self.timer_remaining -= 1
            if self.timer_remaining % 10 == 0:
                self.logger.info(f"倒计时进度: {self.timer_remaining}秒")
        if self.timer_remaining <= 0:
            self.logger.info("倒计时归零，自动开始挖矿")
            if not self.is_mining:
                self.start_mining()
        self.logger.info("倒计时循环结束")

    def _mining_loop(self):
        """挖矿主循环"""
        consecutive_failures = 0
        max_consecutive_failures = 10

        while self.is_mining:
            try:
                self._run_cycle()
                consecutive_failures = 0
            except Exception as e:
                self.logger.error(f"循环异常: {e}", exc_info=True)
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    self.logger.error(f"连续失败 {consecutive_failures} 次，停止挖矿")
                    self.is_mining = False
                    self.mined = True
                    # 通知管理器
                    if self.mining_manager is not None:
                        self.mining_manager._on_window_mining_stopped(self.hwnd)
                    break

            time.sleep(random.uniform(1, 2))

    def _run_cycle(self):
        """执行一轮挖矿流程"""
        if not win32gui.IsWindow(self.hwnd):
            self.logger.warning("窗口已关闭")
            self.is_mining = False
            self.mined = True
            if self.mining_manager is not None:
                self.mining_manager._on_window_mining_stopped(self.hwnd)
            return

        current_size = self._get_window_size()
        if current_size and current_size != self.last_window_size:
            self.logger.info(f"窗口尺寸变化: {self.last_window_size} -> {current_size}")
            self.last_window_size = current_size
            self.matcher.clear_cache()
            self._invalidate_screenshot()

        town_found = self._find("town")
        wild_found = self._find("wild")

        if not town_found and not wild_found:
            self.logger.info("未找到 town 和 wild，执行初始化流程")

            if self._find("back"):
                self.logger.info("找到 back")
                time.sleep(random.uniform(1, 2))
                if not self._click("back"):
                    return
                self.logger.info("点击 back 成功")
                time.sleep(random.uniform(1, 2))

            if self._find("back1"):
                self.logger.info("找到 back1")
                time.sleep(random.uniform(1, 2))
                if not self._click("back1"):
                    return
                self.logger.info("点击 back1 成功")
                time.sleep(random.uniform(1, 2))
            else:
                self.logger.warning("未找到 back1，初始化失败")
                return

        if self._find("town"):
            self.logger.info("找到 town")
            time.sleep(random.uniform(1, 2))
            if not self._click("search"):
                self.logger.warning("未找到 search")
                return
            self.logger.info("点击 search 成功")
            time.sleep(random.uniform(1, 2))
        else:
            self.logger.debug("未找到 town，尝试 wild")
            time.sleep(1)
            if not self._click("wild"):
                self.logger.debug("未找到 wild")
                return
            self.logger.info("点击 wild 成功")
            time.sleep(random.uniform(1, 2))
            if not self._find("town"):
                self.logger.debug("点击 wild 后仍未找到 town")
                return
            self.logger.info("找到 town")

        resource_key = self.resource_order[self.resource_index]
        resource_found = False
        for i in range(self.retry_times):
            if self._click(resource_key):
                self.logger.info(f"点击资源成功: {resource_key}")
                resource_found = True
                break
            if i < self.retry_times - 1:
                self.logger.info(f"资源未找到，{self.retry_delay}s 后重试 ({i+1}/{self.retry_times})")
                time.sleep(self.retry_delay)

        if not resource_found:
            self.logger.warning(f"资源 {resource_key} 多次未找到")
            self.resource_index = (self.resource_index + 1) % len(self.resource_order)
            return

        time.sleep(random.uniform(1, 2))

        if not self._click("add"):
            self.logger.warning("未找到 add")
            self.resource_index = (self.resource_index + 1) % len(self.resource_order)
            return
        self.logger.info("点击 add 成功")
        self._drag(240, 0)
        time.sleep(random.uniform(1, 2))

        if not self._click("search_meat"):
            self.logger.warning("未找到 search_meat")
            self.resource_index = (self.resource_index + 1) % len(self.resource_order)
            return
        self.logger.info("点击 search_meat 成功")
        time.sleep(random.uniform(1, 2))

        if not self._click("gather"):
            self.logger.warning("未找到 gather，查找 minus")
            minus_found = False
            for i in range(5):
                if self._click("minus"):
                    self.logger.info("点击 minus 成功")
                    minus_found = True
                    break
                self.logger.info(f"未找到 minus，{self.retry_delay}s 后重试 ({i+1}/5)")
                time.sleep(self.retry_delay)

            if not minus_found:
                self.logger.warning("多次未找到 minus")
                self.resource_index = (self.resource_index + 1) % len(self.resource_order)
                return

            time.sleep(random.uniform(1, 2))

            if not self._click("search_meat"):
                self.logger.warning("重新查找 search_meat 失败")
                self.resource_index = (self.resource_index + 1) % len(self.resource_order)
                return
            self.logger.info("重新点击 search_meat 成功")
            time.sleep(random.uniform(1, 2))

            if not self._click("gather"):
                self.logger.warning("再次未找到 gather")
                self.resource_index = (self.resource_index + 1) % len(self.resource_order)
                return
            self.logger.info("点击 gather 成功")
        else:
            self.logger.info("点击 gather 成功")

        time.sleep(random.uniform(1, 2))

        # 检查 team（表示队列已满，需要停止）
        if self._find("team"):
            self.logger.info("找到 team，队列已满，停止挖矿")
            time.sleep(random.uniform(1, 2))
            if self._click("close"):
                self.logger.info("点击 close 成功")
            self.is_mining = False
            self.mined = True
            if self.mining_manager is not None:
                self.mining_manager._on_window_mining_stopped(self.hwnd)
            return

        if self._click("battle"):
            self.logger.info("点击 battle 成功，完成一轮")
            self.completed_cycles += 1
            self.logger.info(f"已完成 {self.completed_cycles}/{self.max_cycles} 轮")
            if self.completed_cycles >= self.max_cycles:
                self.logger.info("已完成指定轮数，停止挖矿")
                self.is_mining = False
                self.mined = True
                if self.mining_manager is not None:
                    self.mining_manager._on_window_mining_stopped(self.hwnd)
            else:
                self.resource_index = (self.resource_index + 1) % len(self.resource_order)
        else:
            self.logger.warning("未找到 battle")
            # 再次检查 team
            if self._find("team"):
                self.logger.info("找到 team，停止挖矿")
                time.sleep(random.uniform(1, 2))
                if self._click("close"):
                    self.logger.info("点击 close 成功")
                self.is_mining = False
                self.mined = True
                if self.mining_manager is not None:
                    self.mining_manager._on_window_mining_stopped(self.hwnd)

    def _find(self, image_key: str) -> bool:
        """只查找图片（每次查找前清除缓存，确保使用最新截图）"""
        image_path = self.image_paths.get(image_key)
        if not image_path:
            self.logger.error(f"未知图片key: {image_key}")
            return False

        # 清除截图缓存，确保使用最新截图
        self._invalidate_screenshot()
        
        screenshot, win_w, win_h = self._get_screenshot()
        if screenshot is None:
            return False

        original_confidence = self.matcher.confidence
        if image_key in self.image_confidence:
            self.matcher.confidence = self.image_confidence[image_key]

        result = self.matcher.match(screenshot, image_path, win_w, win_h)
        self.matcher.confidence = original_confidence

        if result:
            self.logger.debug(f"找到 {image_key} [scale={result.get('scale', 1):.3f}]")
            return True
        return False

    def _click(self, image_key: str) -> bool:
        """查找并点击图片（使用 win32gui.PostMessage 发送鼠标点击消息）"""
        image_path = self.image_paths.get(image_key)
        if not image_path:
            self.logger.error(f"未知图片key: {image_key}")
            return False

        # 清除截图缓存，确保使用最新截图
        self._invalidate_screenshot()
        
        screenshot, win_w, win_h = self._get_screenshot()
        if screenshot is None:
            return False

        original_confidence = self.matcher.confidence
        if image_key in self.image_confidence:
            self.matcher.confidence = self.image_confidence[image_key]

        result = self.matcher.match(screenshot, image_path, win_w, win_h)
        self.matcher.confidence = original_confidence

        if not result:
            return False

        center = self.matcher.get_center(result)
        if center is None:
            return False

        left, top, _, _ = win32gui.GetWindowRect(self.hwnd)
        client_x = center[0]
        client_y = center[1]
        screen_x = left + client_x
        screen_y = top + client_y

        self._invalidate_screenshot()
        
        # 激活窗口
        win32gui.SetForegroundWindow(self.hwnd)
        time.sleep(0.1)
        
        # 使用 pyautogui 进行点击（确保点击有效）
        pyautogui.click(screen_x, screen_y)
        
        self.logger.info(f"点击 {image_key}: ({screen_x}, {screen_y}) [scale={result.get('scale', 1):.3f}]")
        return True

    def _drag(self, dx: int, dy: int, duration: float = 0.4):
        """拖动鼠标"""
        try:
            x, y = pyautogui.position()
            pyautogui.mouseDown()
            pyautogui.moveTo(x + dx, y + dy, duration=duration)
            pyautogui.mouseUp()
            self.logger.info(f"拖动: dx={dx}, dy={dy}")
            self._invalidate_screenshot()
        except Exception as e:
            self.logger.error(f"拖动失败: {e}")


# ─────────────────────────────────────────────
# 多窗口挖矿管理器（自动轮换）
# ─────────────────────────────────────────────

class MultiWindowMiningManager:
    """
    多窗口挖矿管理器
    
    功能：
    - 管理多个游戏窗口
    - 一个窗口挖矿停止后，自动启动下一个未标记的窗口
    - 支持窗口按顺序轮换
    """

    def __init__(self):
        self.miners: Dict[int, SingleWindowMiner] = {}
        self.logger = logging.getLogger("MultiWindowManager")
        self._lock = threading.Lock()
        self.window_order: List[int] = []  # 窗口顺序

    def add_window(self, hwnd: int, window_name: str = "") -> bool:
        """添加窗口"""
        with self._lock:
            if hwnd in self.miners:
                self.logger.warning(f"窗口 {hwnd} 已存在")
                return False

            if not win32gui.IsWindow(hwnd):
                self.logger.error(f"窗口 {hwnd} 无效")
                return False

            miner = SingleWindowMiner(hwnd, window_name)
            miner.mining_manager = self
            self.miners[hwnd] = miner
            self.window_order.append(hwnd)
            self.logger.info(f"添加窗口: {window_name} (hwnd={hwnd})")
            return True

    def remove_window(self, hwnd: int) -> bool:
        """移除窗口"""
        with self._lock:
            if hwnd not in self.miners:
                self.logger.warning(f"窗口 {hwnd} 不存在")
                return False

            miner = self.miners[hwnd]
            miner.stop_mining()
            del self.miners[hwnd]
            if hwnd in self.window_order:
                self.window_order.remove(hwnd)
            self.logger.info(f"移除窗口: hwnd={hwnd}")
            return True

    def start_mining(self, hwnd: int) -> bool:
        """开始指定窗口的挖矿"""
        with self._lock:
            if hwnd not in self.miners:
                self.logger.error(f"窗口 {hwnd} 不存在")
                return False
            
            miner = self.miners[hwnd]
            if miner.start_mining():
                self.logger.info(f"启动窗口 {miner.window_name} 挖矿")
                return True
            return False

    def stop_mining(self, hwnd: int) -> bool:
        """停止指定窗口的挖矿"""
        with self._lock:
            if hwnd not in self.miners:
                self.logger.error(f"窗口 {hwnd} 不存在")
                return False
            
            miner = self.miners[hwnd]
            was_mining = miner.is_mining
            if miner.stop_mining():
                self.logger.info(f"停止窗口 {miner.window_name} 挖矿")
                # 如果窗口正在挖矿，尝试启动下一个
                if was_mining:
                    self._try_start_next_window()
                return True
            return False

    def start_first_window(self) -> bool:
        """开始第一个窗口的挖矿"""
        with self._lock:
            if not self.window_order:
                self.logger.warning("没有窗口")
                return False
            
            # 找第一个未标记的窗口
            for hwnd in self.window_order:
                if hwnd in self.miners and not self.miners[hwnd].mined:
                    miner = self.miners[hwnd]
                    if miner.start_mining():
                        self.logger.info(f"启动第一个窗口 {miner.window_name} 挖矿")
                        return True
            self.logger.info("所有窗口都已挖矿")
            return False

    def stop_all_mining(self) -> int:
        """停止所有窗口的挖矿"""
        with self._lock:
            count = 0
            for miner in self.miners.values():
                if miner.stop_mining():
                    count += 1
            self.logger.info(f"已停止 {count} 个窗口的挖矿")
            return count

    def reset_all_mined_flags(self):
        """重置所有窗口的挖矿标记"""
        with self._lock:
            for miner in self.miners.values():
                miner.mined = False
            self.logger.info("已重置所有窗口的挖矿标记")

    def _on_window_mining_stopped(self, hwnd: int):
        """
        窗口挖矿停止的回调
        由 SingleWindowMiner 在挖矿停止时调用
        """
        self.logger.info(f"窗口 {hwnd} 挖矿停止")
        # 尝试启动下一个未标记的窗口
        self._try_start_next_window()

    def _try_start_next_window(self):
        """
        尝试启动下一个未标记的窗口
        
        从 window_order 中按顺序查找第一个未挖矿的窗口并启动
        """
        self.logger.info(f"查找下一个未标记窗口，当前窗口数: {len(self.window_order)}")
        
        for hwnd in self.window_order:
            if hwnd in self.miners:
                miner = self.miners[hwnd]
                self.logger.info(f"检查窗口 {miner.window_name}: mined={miner.mined}, is_mining={miner.is_mining}")
                
                if not miner.mined and not miner.is_mining:
                    if miner.start_mining():
                        self.logger.info(f"自动启动下一个窗口 {miner.window_name} 挖矿")
                        return
        
        # 所有窗口都已挖矿
        all_mined = all(self.miners[h].mined for h in self.window_order if h in self.miners)
        if all_mined:
            self.logger.info("所有窗口都已挖矿完成")
    
    def set_window_timer(self, hwnd: int, seconds: int) -> bool:
        """设置指定窗口的倒计时（秒）"""
        with self._lock:
            if hwnd not in self.miners:
                self.logger.error(f"窗口 {hwnd} 不存在")
                return False
            self.miners[hwnd].set_timer(seconds)
            return True
    
    def start_window_timer(self, hwnd: int) -> bool:
        """启动指定窗口的倒计时"""
        with self._lock:
            if hwnd not in self.miners:
                self.logger.error(f"窗口 {hwnd} 不存在")
                return False
            self.miners[hwnd].start_timer()
            return True
    
    def stop_window_timer(self, hwnd: int) -> bool:
        """停止指定窗口的倒计时"""
        with self._lock:
            if hwnd not in self.miners:
                self.logger.error(f"窗口 {hwnd} 不存在")
                return False
            self.miners[hwnd].stop_timer()
            return True
    
    def get_window_timer_remaining(self, hwnd: int) -> int:
        """获取指定窗口的倒计时剩余时间"""
        with self._lock:
            if hwnd not in self.miners:
                self.logger.error(f"窗口 {hwnd} 不存在")
                return -1
            return self.miners[hwnd].get_timer_remaining()

    def get_status(self) -> Dict[int, dict]:
        """获取所有窗口的状态"""
        with self._lock:
            status = {}
            for hwnd, miner in self.miners.items():
                status[hwnd] = {
                    "name": miner.window_name,
                    "is_mining": miner.is_mining,
                    "mined": miner.mined,
                    "completed_cycles": miner.completed_cycles,
                    "max_cycles": miner.max_cycles,
                    "resource_index": miner.resource_index,
                }
            return status

    def list_windows(self) -> List[Tuple[int, str, bool, bool]]:
        """列出所有窗口"""
        with self._lock:
            return [(hwnd, miner.window_name, miner.is_mining, miner.mined)
                    for hwnd, miner in self.miners.items()]

    def are_all_windows_mined(self) -> bool:
        """检查所有窗口是否都已挖矿"""
        with self._lock:
            for miner in self.miners.values():
                if not miner.mined:
                    return False
            return True
    
    def get_mining_status(self) -> bool:
        """检查是否有窗口正在挖矿"""
        with self._lock:
            for miner in self.miners.values():
                if miner.is_mining:
                    return True
            return False


# ─────────────────────────────────────────────
# 使用示例
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    manager = MultiWindowMiningManager()

    # 添加窗口（示例）
    # hwnd1 = win32gui.FindWindow(None, "无尽冬日 - 窗口1")
    # if hwnd1:
    #     manager.add_window(hwnd1, "Account_1")

    # 启动第一个窗口
    manager.start_first_window()

    # 监控状态
    try:
        while True:
            time.sleep(10)
            status = manager.get_status()
            print("\n当前状态:")
            for hwnd, info in status.items():
                print(f"  {info['name']}: 挖矿={info['is_mining']}, "
                      f"已标记={info['mined']}, 进度={info['completed_cycles']}/{info['max_cycles']}")
            
            if manager.are_all_windows_mined():
                print("\n所有窗口已完成挖矿")
                break
    except KeyboardInterrupt:
        print("\n停止所有挖矿...")
        manager.stop_all_mining()
