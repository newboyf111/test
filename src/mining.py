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
from collections import defaultdict, deque

from src.utils.adaptive_matcher import AdaptiveMatcher
from src.utils.window_utils import set_dpi_aware, capture_window
from src.utils.resource_path import get_pic_path
from src.utils import ScreenshotCache


set_dpi_aware()


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

        self.image_paths = {
            "town":        "town.png",
            "wild":        "wild.png",
            "search":      "search.png",
            "meat":        "meat.png",
            "wood":        "wood.png",
            "coal":        "coal mine.png",
            "iron":        "iron.png",
            "add":         "add.png",
            "search_meat": "search_meat.png",
            "gather":      "gather.png",
            "battle":      "battle.png",
            "team":        "team.png",
            "close":       "close.png",
            "minus":       "minus.png",
            "back":        "back.png",
            "back1":       "back1.png",
        }

        self.resource_order = ["meat", "wood", "coal", "iron"]
        self.resource_index = 0
        self.last_window_size = None
        self.retry_times = 3
        self.retry_delay = 2
        self.completed_cycles = 0
        self.max_cycles = 6

        # 使用统一的缓存管理器，TTL 保持 0.5 秒
        self._screenshot_cache = ScreenshotCache(ttl=0.5, logger=self.logger)

        self.image_confidence = {
            "back":  0.85,
            "back1": 0.85,
            "gather": 0.85,
            "town": 0.75,  # 提高 town 的阈值，防止误匹配
            "close": 0.85,  # 提高 close 的阈值，防止错误识别
        }

        self.drag_distance = 240

        # 挖矿标记（True 表示已完成挖矿）
        self.mined = False
        
        # 挖矿状态（0: 未开始, 1: 挖矿中, 2: 挖矿结束）
        self.mining_state = 0
        
        # 是否需要执行初始化流程
        self._need_init = True
        
        # 挖矿管理器引用
        self.mining_manager = None
        
        # Level8 坐标（相对于游戏窗口的基准坐标）
        # 这些是基准值，会根据窗口大小自适应缩放
        self.level8_target_base = (339, 844)
        self.level8_tolerance = 1
        
        # 用户手动停止标志
        self._user_stopped = False
        
        # OCR 识别区域（相对于游戏窗口的基准坐标）
        # 区域: (152, 188) -> (192, 219) 大小: 40x31
        self.ocr_region_base = (152, 188, 192, 219)
        self.ocr_enabled = False
        self.ocr_reader = None

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

    def _init_ocr(self):
        """初始化 OCR"""
        if self.ocr_reader is not None:
            return
        
        try:
            # 忽略 PyTorch DataLoader 的 pin_memory 警告
            import warnings
            warnings.filterwarnings("ignore", message="'pin_memory' argument is set as true but no accelerator is found")
            # 忽略 easyocr 的 GPU 检查警告
            warnings.filterwarnings("ignore", message="Neither CUDA nor MPS are available - defaulting to CPU")
            
            import easyocr
            # 禁用 GPU 检查，直接使用 CPU
            self.ocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
            self.ocr_enabled = True
            self.logger.info("OCR 初始化成功")
        except ImportError as e:
            self.ocr_enabled = False
            self.logger.warning(f"easyocr 未安装，跳过 OCR 识别: {e}")
        except Exception as e:
            self.ocr_enabled = False
            self.logger.warning(f"OCR 初始化失败: {type(e).__name__}: {e}")

    def _get_screenshot(self) -> Tuple[Optional[np.ndarray], int, int]:
        """获取截图（带缓存）"""
        if not win32gui.IsWindow(self.hwnd):
            self.logger.warning("窗口无效")
            return None, 0, 0

        def capture_func():
            return capture_window(self.hwnd)

        return self._screenshot_cache.get(self.hwnd, capture_func)
    
    def _screenshot(self) -> Optional[np.ndarray]:
        """获取截图（简化版本，兼容旧代码）"""
        screenshot, _, _ = self._get_screenshot()
        return screenshot

    def _invalidate_screenshot(self):
        """清除截图缓存"""
        self._screenshot_cache.invalidate(self.hwnd)

    def _get_window_size(self) -> Optional[Tuple[int, int]]:
        """获取窗口尺寸"""
        try:
            left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
            return (right - left, bottom - top)
        except (win32gui.error, AttributeError):
            return None

    def _capture_ocr_region(self, screenshot: np.ndarray, win_w: int, win_h: int) -> Optional[np.ndarray]:
        """截取 OCR 识别区域
        
        Args:
            screenshot: 全屏截图
            win_w: 窗口宽度
            win_h: 窗口高度
        
        Returns:
            OCR 区域截图，失败返回 None
        """
        if screenshot is None:
            return None
        
        # 根据窗口大小自适应缩放 OCR 区域
        scale = win_w / AdaptiveMatcher.BASE_WIDTH
        x1 = int(self.ocr_region_base[0] * scale)
        y1 = int(self.ocr_region_base[1] * scale)
        x2 = int(self.ocr_region_base[2] * scale)
        y2 = int(self.ocr_region_base[3] * scale)
        
        # 确保坐标在截图范围内
        x1 = max(0, min(x1, screenshot.shape[1]))
        y1 = max(0, min(y1, screenshot.shape[0]))
        x2 = max(0, min(x2, screenshot.shape[1]))
        y2 = max(0, min(y2, screenshot.shape[0]))
        
        if x1 >= x2 or y1 >= y2:
            self.logger.warning("OCR 区域坐标无效")
            return None
        
        # 截取区域
        ocr_region = screenshot[y1:y2, x1:x2]
        return ocr_region

    def _ocr_recognize(self, region: np.ndarray) -> Optional[str]:
        """使用 OCR 识别区域内容
        
        Args:
            region: OCR 区域截图
        
        Returns:
            识别结果文本，失败返回 None
        """
        if not self.ocr_enabled or self.ocr_reader is None:
            return None
        
        try:
            # 保存 OCR 区域截图用于调试
            debug_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_output', 'ocr_debug')
            os.makedirs(debug_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            debug_path = os.path.join(debug_dir, f"ocr_{timestamp}.png")
            cv2.imwrite(debug_path, region)
            self.logger.debug(f"OCR 区域截图已保存: {debug_path}")
            
            # 转换为灰度图（OpenCV 返回 BGR，所以用 COLOR_BGR2GRAY）
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            
            # OCR 识别
            results = self.ocr_reader.readtext(gray)
            
            if results:
                # 提取识别文本
                text = results[0][1]
                confidence = results[0][2]
                self.logger.info(f"OCR 识别结果: '{text}' (置信度: {confidence:.2f})")
                return text
            
            return None
        except (RuntimeError, ValueError) as e:
            self.logger.warning(f"OCR 识别失败: {e}")
            return None

    def start_mining(self) -> bool:
        """开始挖矿"""
        if not self.is_mining:
            # 清除缓存
            self._screenshot_cache.clear_all()
            self._screenshot_time = 0
            self.matcher.clear_cache()
            
            self.is_mining = True
            self.mining_state = 1  # 设置为挖矿中
            self._user_stopped = False  # 重置用户停止标志
            self.completed_cycles = 0
            self._need_init = True  # 开始时需要执行初始化流程
            size = self._get_window_size()
            if size:
                self.last_window_size = size
            self.logger.info("=" * 50)
            self.logger.info("挖矿开始")
            self.logger.info(f"基准尺寸: {AdaptiveMatcher.BASE_WIDTH}x{AdaptiveMatcher.BASE_HEIGHT}")
            self.logger.info("=" * 50)
            
            # 优先执行 OCR 检查
            if not self._check_ocr_before_mining():
                self.logger.info("OCR 检查未通过，跳过挖矿流程")
                # 注意：_check_ocr_before_mining 已经设置了 mined=True, mining_state=2, 并调用了 _on_window_mining_stopped
                self.is_mining = False
                return False
            
            self.mining_thread = threading.Thread(target=self._mining_loop, daemon=True)
            self.mining_thread.start()
            return True
        return False

    def _check_ocr_before_mining(self) -> bool:
        """开始挖矿前的 OCR 检查
        
        Returns:
            bool: OCR 检查是否通过
        """
        if not self.ocr_enabled or self.ocr_reader is None:
            self.logger.info("OCR 未启用，跳过 OCR 检查")
            return True
        
        self.logger.info("开始执行 OCR 检查...")
        
        # 获取窗口截图
        screenshot = self._screenshot()
        if screenshot is None:
            self.logger.warning("获取截图失败，跳过 OCR 检查")
            return True
        
        win_w, win_h = self._get_window_size()
        if win_w is None or win_h is None:
            self.logger.warning("获取窗口尺寸失败，跳过 OCR 检查")
            return True
        
        # 截取 OCR 区域
        ocr_region = self._capture_ocr_region(screenshot, win_w, win_h)
        if ocr_region is None:
            self.logger.warning("截取 OCR 区域失败，跳过 OCR 检查")
            return True
        
        # OCR 识别
        ocr_text = self._ocr_recognize(ocr_region)
        if ocr_text is None:
            self.logger.info("OCR 识别失败，视为需要挖矿")
            return True
        
        # 解析识别结果
        try:
            if "/" in ocr_text:
                parts = ocr_text.split("/")
                if len(parts) == 2:
                    current = int(parts[0].strip())
                    total = int(parts[1].strip())
                    remaining = total - current
                    
                    self.logger.info(f"OCR 识别结果: {ocr_text} (剩余: {remaining})")
                    
                    if remaining <= 0:
                        self.logger.info("挖矿次数已用完，跳过挖矿流程")
                        self.mined = True
                        self.mining_state = 2
                        if self.mining_manager is not None:
                            self.mining_manager._on_window_mining_stopped(self.hwnd)
                        return False
        except (ValueError, IndexError) as e:
            self.logger.warning(f"解析 OCR 结果失败: {e}")
        
        return True

    def stop_mining(self, user_stopped: bool = False) -> bool:
        """停止挖矿
        
        Args:
            user_stopped: 是否是用户手动停止
        """
        if self.is_mining:
            self.is_mining = False
            self._user_stopped = user_stopped
            # 标记窗口为已挖矿（只有用户手动停止或自然完成时才标记）
            if user_stopped:
                self.logger.info(f"用户手动停止挖矿")
            else:
                self.mined = True
                self.logger.info(f"挖矿结束，标记窗口为已挖矿")
            self.mining_state = 2  # 设置为挖矿结束
            return True
        return False

    def is_user_stopped(self) -> bool:
        """检查是否是用户手动停止"""
        return self._user_stopped

    def get_mining_status(self) -> bool:
        return self.is_mining
    
    def get_mining_state(self) -> int:
        """获取挖矿状态
        
        Returns:
            int: 挖矿状态（0: 未开始, 1: 挖矿中, 2: 挖矿结束）
        """
        return self.mining_state
    
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
            # 重置挖矿状态
            self.mined = False
            self.mining_state = 0
            self.completed_cycles = 0
            self.max_cycles = 0
            if not self.is_mining:
                self.start_mining()
        self.logger.info("倒计时循环结束")

    def _mining_loop(self):
        """挖矿主循环"""
        consecutive_failures = 0
        max_consecutive_failures = 10

        while self.is_mining:
            # 用户手动停止时立即退出，不等待
            if self._user_stopped:
                self.logger.info("用户手动停止，立即退出挖矿线程")
                break
            
            try:
                self._run_cycle()
                consecutive_failures = 0
            except (RuntimeError, OSError) as e:
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
            
            time.sleep(0.1)  # 减少等待时间，快速响应停止请求

    def _init_mining_flow(self) -> bool:
        """
        挖矿初始化流程
        
        步骤1: 搜索 town，发现则开始挖矿流程
        步骤2: 未发现 town，搜索 wild，发现则点击后等待2-3秒，开始挖矿流程
        步骤3: 未发现 town 和 wild，执行 close/back/back1 流程
        
        Returns:
            bool: 初始化是否成功
        """
        self.logger.info("执行挖矿初始化流程...")
        
        # 步骤1: 搜索 town
        if self._find("town"):
            self.logger.info("找到 town，开始挖矿流程")
            return True
        
        # 步骤2: 搜索 wild
        if self._find("wild"):
            self.logger.info("找到 wild")
            if self._user_stopped:
                self.logger.info("用户手动停止，退出挖矿流程")
                return False
            time.sleep(random.uniform(0.5, 1))
            if self._click("wild")[0]:
                self.logger.info("点击 wild 成功，等待2-3秒后开始挖矿流程")
                if self._user_stopped:
                    self.logger.info("用户手动停止，退出挖矿流程")
                    return False
                time.sleep(random.uniform(2, 3))
                return True
            else:
                self.logger.warning("点击 wild 失败")
        
        # 步骤3: 搜索 close
        self.logger.info("未找到 town 和 wild，开始搜索 close 流程")
        if self._find("close"):
            self.logger.info("找到 close")
            if self._user_stopped:
                self.logger.info("用户手动停止，退出挖矿流程")
                return False
            time.sleep(random.uniform(0.5, 1))
            if self._click("close")[0]:
                self.logger.info("点击 close 成功，开始挖矿流程")
                if self._user_stopped:
                    self.logger.info("用户手动停止，退出挖矿流程")
                    return False
                time.sleep(random.uniform(1, 2))
                return True
            else:
                self.logger.warning("点击 close 失败")
        
        # 步骤4: 搜索 back
        if self._find("back"):
            self.logger.info("找到 back")
            if self._user_stopped:
                self.logger.info("用户手动停止，退出挖矿流程")
                return False
            time.sleep(random.uniform(0.5, 1))
            if self._click("back")[0]:
                self.logger.info("点击 back 成功")
                if self._user_stopped:
                    self.logger.info("用户手动停止，退出挖矿流程")
                    return False
                time.sleep(random.uniform(1, 2))
                
                # 搜索 back1
                if self._find("back1"):
                    self.logger.info("找到 back1")
                    if self._user_stopped:
                        self.logger.info("用户手动停止，退出挖矿流程")
                        return False
                    time.sleep(random.uniform(0.5, 1))
                    if self._click("back1")[0]:
                        self.logger.info("点击 back1 成功，开始挖矿流程")
                        if self._user_stopped:
                            self.logger.info("用户手动停止，退出挖矿流程")
                            return False
                        time.sleep(random.uniform(2, 3))
                        return True
                    else:
                        self.logger.warning("点击 back1 失败")
                else:
                    self.logger.warning("未找到 back1")
            else:
                self.logger.warning("点击 back 失败")
        
        # 步骤5: 直接搜索 back1
        if self._find("back1"):
            self.logger.info("找到 back1")
            if self._user_stopped:
                self.logger.info("用户手动停止，退出挖矿流程")
                return False
            time.sleep(random.uniform(0.5, 1))
            if self._click("back1")[0]:
                self.logger.info("点击 back1 成功，开始挖矿流程")
                if self._user_stopped:
                    self.logger.info("用户手动停止，退出挖矿流程")
                    return False
                time.sleep(random.uniform(1, 2))
                return True
            else:
                self.logger.warning("点击 back1 失败")
        
        self.logger.warning("挖矿初始化流程失败")
        return False

    def _run_cycle(self):
        """执行一轮挖矿流程"""
        if not win32gui.IsWindow(self.hwnd):
            self.logger.warning("窗口已关闭")
            self.is_mining = False
            self.mined = True
            if self.mining_manager is not None:
                self.mining_manager._on_window_mining_stopped(self.hwnd)
            return

        # 用户手动停止时立即退出
        if self._user_stopped:
            self.logger.info("用户手动停止，退出挖矿流程")
            return

        # 初始化 OCR（仅在第一次执行时）
        if not hasattr(self, '_ocr_initialized'):
            self._init_ocr()
            self._ocr_initialized = True

        # 优先执行初始化流程
        if self._need_init:
            self.logger.info("开始执行挖矿初始化流程...")
            if self._init_mining_flow():
                self._need_init = False
                self.logger.info("挖矿初始化完成，开始正常挖矿流程")
            else:
                self.logger.warning("挖矿初始化失败，将在下一轮重试")
                return

        # 用户手动停止时立即退出
        if self._user_stopped:
            self.logger.info("用户手动停止，退出挖矿流程")
            return

        current_size = self._get_window_size()
        if current_size and current_size != self.last_window_size:
            self.logger.info(f"窗口尺寸变化: {self.last_window_size} -> {current_size}")
            self.last_window_size = current_size
            self.matcher.clear_cache()
            self._invalidate_screenshot()

        # 获取截图并进行 OCR 识别
        screenshot, win_w, win_h = self._get_screenshot()
        if screenshot is not None and win_w > 0 and win_h > 0:
            # 截取 OCR 区域
            ocr_region = self._capture_ocr_region(screenshot, win_w, win_h)
            if ocr_region is not None:
                # OCR 识别
                ocr_text = self._ocr_recognize(ocr_region)
                if ocr_text:
                    self.logger.info(f"OCR 识别到文本: {ocr_text}")
                    
                    # 解析 OCR 文本，计算差值
                    try:
                        # 提取格式为 "x/y" 的文本
                        if "/" in ocr_text:
                            parts = ocr_text.split("/")
                            if len(parts) == 2:
                                current = int(parts[0].strip())
                                total = int(parts[1].strip())
                                remaining = total - current
                                self.logger.info(f"解析结果: 当前 {current}, 总数 {total}, 剩余 {remaining}")
                                
                                # 如果剩余为0，不需要执行挖矿流程
                                if remaining <= 0:
                                    self.logger.info("剩余次数为0，跳过挖矿流程")
                                    # 开启保护性外壳自动化脚本
                                    if self.mining_manager is not None:
                                        self.logger.info("开启保护性外壳自动化脚本")
                                        self.is_mining = False
                                        self.mined = True
                                        self.mining_state = 2
                                        self.mining_manager._on_window_mining_stopped(self.hwnd)
                                    return
                                # 设置还需要循环的次数
                                self.max_cycles = remaining
                                self.logger.info(f"设置还需要循环的次数为: {self.max_cycles}")
                    except (ValueError, IndexError) as e:
                        self.logger.warning(f"解析 OCR 文本失败: {e}")

        town_found = self._find("town")
        wild_found = self._find("wild")

        if not town_found and not wild_found:
            self.logger.info("未找到 town 和 wild，执行初始化流程")

            if self._find("back"):
                self.logger.info("找到 back")
                if self._user_stopped:
                    self.logger.info("用户手动停止，退出挖矿流程")
                    return
                time.sleep(random.uniform(1, 2))
                if not self._click("back"):
                    return
                self.logger.info("点击 back 成功")
                if self._user_stopped:
                    self.logger.info("用户手动停止，退出挖矿流程")
                    return
                time.sleep(random.uniform(1, 2))

            if self._find("back1"):
                self.logger.info("找到 back1")
                if self._user_stopped:
                    self.logger.info("用户手动停止，退出挖矿流程")
                    return
                time.sleep(random.uniform(1, 2))
                if not self._click("back1"):
                    return
                self.logger.info("点击 back1 成功")
                if self._user_stopped:
                    self.logger.info("用户手动停止，退出挖矿流程")
                    return
                time.sleep(random.uniform(1, 2))
            else:
                self.logger.warning("未找到 back1，初始化失败")
                return

        # 用户手动停止时立即退出
        if self._user_stopped:
            self.logger.info("用户手动停止，退出挖矿流程")
            return

        if self._find("town"):
            self.logger.info("找到 town")
            if self._user_stopped:
                self.logger.info("用户手动停止，退出挖矿流程")
                return
            time.sleep(random.uniform(1, 2))
            if not self._click("search"):
                self.logger.warning("未找到 search，执行挖矿初始化流程")
                if not self._init_mining_flow():
                    return
            else:
                self.logger.info("点击 search 成功")
                if self._user_stopped:
                    self.logger.info("用户手动停止，退出挖矿流程")
                    return
                time.sleep(random.uniform(1, 2))
        else:
            self.logger.debug("未找到 town，尝试 wild")
            if self._user_stopped:
                self.logger.info("用户手动停止，退出挖矿流程")
                return
            time.sleep(1)
            if not self._click("wild"):
                self.logger.debug("未找到 wild")
                return
            self.logger.info("点击 wild 成功")
            if self._user_stopped:
                self.logger.info("用户手动停止，退出挖矿流程")
                return
            time.sleep(random.uniform(1, 2))
            if not self._find("town"):
                self.logger.debug("点击 wild 后仍未找到 town")
                return
            self.logger.info("找到 town")

        resource_key = self.resource_order[self.resource_index]
        resource_found = False
        for i in range(self.retry_times):
            if self._user_stopped:
                self.logger.info("用户手动停止，退出挖矿流程")
                return
            if self._click(resource_key)[0]:
                self.logger.info(f"点击资源成功: {resource_key}")
                resource_found = True
                break
            if i < self.retry_times - 1:
                self.logger.info(f"资源未找到，{self.retry_delay}s 后重试 ({i+1}/{self.retry_times})")
                if self._user_stopped:
                    self.logger.info("用户手动停止，退出挖矿流程")
                    return
                time.sleep(self.retry_delay)

        if not resource_found:
            self.logger.warning(f"资源 {resource_key} 多次未找到")
            self.resource_index = (self.resource_index + 1) % len(self.resource_order)
            return

        if self._user_stopped:
            self.logger.info("用户手动停止，退出挖矿流程")
            return
        time.sleep(random.uniform(1, 2))

        if not self._click_and_align("add", self.level8_target_base, self.level8_tolerance):
            self.logger.warning("未找到 add 或坐标校准失败")
            self.resource_index = (self.resource_index + 1) % len(self.resource_order)
            return
        self.logger.info("点击 add 成功且坐标校准完成")
        if self._user_stopped:
            self.logger.info("用户手动停止，退出挖矿流程")
            return
        time.sleep(random.uniform(1, 2))

        if not self._click("search_meat"):
            self.logger.warning("未找到 search_meat")
            self.resource_index = (self.resource_index + 1) % len(self.resource_order)
            return
        self.logger.info("点击 search_meat 成功")
        if self._user_stopped:
            self.logger.info("用户手动停止，退出挖矿流程")
            return
        time.sleep(random.uniform(1, 2))

        # 用户手动停止时立即退出
        if self._user_stopped:
            self.logger.info("用户手动停止，退出挖矿流程")
            return

        # 循环尝试寻找并点击 gather
        gather_found = False
        
        while True:
            if self._user_stopped:
                self.logger.info("用户手动停止，退出挖矿流程")
                return
            
            # 尝试点击 gather
            self.logger.info("尝试寻找 gather...")
            if self._click("gather")[0]:
                self.logger.info("点击 gather 成功")
                gather_found = True
                break
            
            # 执行备选方案：点击 add，向左拖动，点击 search_meat
            self.logger.info("未找到 gather，执行备选方案")
            if self._user_stopped:
                self.logger.info("用户手动停止，退出挖矿流程")
                return
            time.sleep(random.uniform(1, 2))
            
            # 点击 add
            success, add_pos = self._click("add")
            if success and add_pos:
                self.logger.info(f"点击 add 成功，位置: {add_pos}")
                if self._user_stopped:
                    self.logger.info("用户手动停止，退出挖矿流程")
                    return
                time.sleep(random.uniform(0.5, 1))
                
                # 向左拖动
                window_size = self._get_window_size()
                if window_size:
                    win_w, _ = window_size
                    scale = win_w / 558
                    drag_distance = int(30 * scale)
                else:
                    drag_distance = 30
                self._drag(-drag_distance, 0, 0.05)
                if self._user_stopped:
                    self.logger.info("用户手动停止，退出挖矿流程")
                    return
            else:
                self.logger.warning("未找到 add")
            
            time.sleep(random.uniform(1, 2))
            
            # 点击 search_meat
            if self._click("search_meat")[0]:
                self.logger.info("点击 search_meat 成功")
                if self._user_stopped:
                    self.logger.info("用户手动停止，退出挖矿流程")
                    return
                # 延迟 1-2 秒后再匹配 gather
                time.sleep(random.uniform(1, 2))
            else:
                self.logger.warning("未找到 search_meat")
            # 继续循环尝试找 gather

        time.sleep(random.uniform(1, 2))

        # 用户手动停止时立即退出
        if self._user_stopped:
            self.logger.info("用户手动停止，退出挖矿流程")
            return

        # 再次检查 gather 是否存在（如果存在说明点击失败）
        if self._find("gather"):
            self.logger.info("gather 仍然存在，点击失败，停止挖矿")
            self.is_mining = False
            self.mined = True
            if self.mining_manager is not None:
                self.mining_manager._on_window_mining_stopped(self.hwnd)
            return

        # 检查 team（表示队列已满，需要停止）
        if self._find("team"):
            self.logger.info("找到 team，队列已满，停止挖矿")
            time.sleep(random.uniform(1, 2))
            if self._click("close")[0]:
                self.logger.info("点击 close 成功")
            self.is_mining = False
            self.mined = True
            if self.mining_manager is not None:
                self.mining_manager._on_window_mining_stopped(self.hwnd)
            return

        if self._click("battle")[0]:
            self.logger.info("点击 battle 成功，完成一轮")
            self.completed_cycles += 1
            self.logger.info(f"已完成 {self.completed_cycles} 轮")
            
            # battle 成功后必须执行 OCR 检查
            time.sleep(random.uniform(1, 2))
            if not self._check_ocr_before_mining():
                self.logger.info("OCR 检查未通过，停止挖矿")
                self.is_mining = False
                self.mined = True
                if self.mining_manager is not None:
                    self.mining_manager._on_window_mining_stopped(self.hwnd)
                return
            
            # 切换资源
            self.resource_index = (self.resource_index + 1) % len(self.resource_order)
        else:
            self.logger.warning("未找到 battle")
            # 再次检查 team
            if self._find("team"):
                self.logger.info("找到 team，停止挖矿")
                time.sleep(random.uniform(1, 2))
                if self._click("close")[0]:
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

    def _click(self, image_key: str) -> Tuple[bool, Optional[Tuple[int, int]]]:
        """查找并点击图片（使用 win32gui.PostMessage 发送鼠标点击消息）
        
        Returns:
            Tuple[bool, Optional[Tuple[int, int]]]: (是否成功, 点击的相对坐标)
        """
        image_path = self.image_paths.get(image_key)
        if not image_path:
            self.logger.error(f"未知图片key: {image_key}")
            return False, None

        # 清除截图缓存，确保使用最新截图
        self._invalidate_screenshot()
        
        screenshot, win_w, win_h = self._get_screenshot()
        if screenshot is None:
            return False, None

        original_confidence = self.matcher.confidence
        if image_key in self.image_confidence:
            self.matcher.confidence = self.image_confidence[image_key]

        result = self.matcher.match(screenshot, image_path, win_w, win_h)
        self.matcher.confidence = original_confidence

        if not result:
            return False, None

        center = self.matcher.get_center(result)
        if center is None:
            return False, None

        left, top, _, _ = win32gui.GetWindowRect(self.hwnd)
        client_x = center[0]
        client_y = center[1]
        screen_x = left + client_x
        screen_y = top + client_y

        self._invalidate_screenshot()
        
        # 通过 mining_manager 统一管理窗口激活，避免来回切换
        # 只在窗口切换时激活，不在每次点击时激活
        # if self.mining_manager:
        #     self.mining_manager._ensure_window_active(self.hwnd, self.window_name)
        
        # 使用 pyautogui 进行点击（确保点击有效）
        pyautogui.click(screen_x, screen_y)
        
        self.logger.info(f"点击 {image_key}: ({screen_x}, {screen_y}) [scale={result.get('scale', 1):.3f}]")
        return True, (client_x, client_y)

    def _click_and_align(self, image_key: str, target_pos_base: Tuple[int, int], tolerance: int = 1) -> bool:
        """查找并点击图片，如果坐标不在目标位置则拖动到目标位置
        
        Args:
            image_key: 图片key
            target_pos_base: 目标位置（相对于游戏窗口的基准坐标）
            tolerance: 坐标容差（像素）
        
        Returns:
            bool: 是否成功
        """
        success, pos = self._click(image_key)
        if not success or pos is None:
            return False
        
        current_x, current_y = pos
        target_x_base, target_y_base = target_pos_base
        
        # 根据窗口大小自适应缩放目标坐标
        window_size = self._get_window_size()
        if window_size:
            win_w, _ = window_size
            scale = win_w / 558
            target_x = int(target_x_base * scale)
            target_y = int(target_y_base * scale)
            self.logger.info(f"窗口宽度: {win_w}, 缩放比例: {scale:.3f}, 目标坐标缩放: ({target_x_base}, {target_y_base}) -> ({target_x}, {target_y})")
        else:
            target_x, target_y = target_x_base, target_y_base
            self.logger.warning("无法获取窗口尺寸，使用原始目标坐标")
        
        self.logger.info(f"{image_key} 当前坐标: ({current_x}, {current_y}), 目标坐标: ({target_x}, {target_y})")
        
        if (abs(current_x - target_x) <= tolerance and 
            abs(current_y - target_y) <= tolerance):
            self.logger.info(f"{image_key} 坐标在容差范围内，继续流程")
            return True
        
        dx = target_x - current_x
        dy = target_y - current_y
        
        self.logger.info(f"拖动 {image_key} 到目标位置: dx={dx}, dy={dy}")
        
        try:
            if window_size:
                scale = win_w / 558
                dx_scaled = int(dx * scale)
                dy_scaled = int(dy * scale)
            else:
                dx_scaled = dx
                dy_scaled = dy
                self.logger.debug("无法获取窗口尺寸，使用原始拖动距离")
            
            x, y = pyautogui.position()
            pyautogui.mouseDown()
            pyautogui.moveTo(x + dx_scaled, y + dy_scaled, duration=0.5)
            pyautogui.mouseUp()
            self.logger.info(f"拖动完成: dx={dx_scaled}, dy={dy_scaled} [scale={scale:.3f}]")
            self._invalidate_screenshot()
        except (RuntimeError, OSError) as e:
            self.logger.error(f"拖动失败: {e}")
            return False
        
        return True

    def _drag(self, dx: int, dy: int, duration: float = 0.4):
        """拖动鼠标（根据窗口大小自适应缩放）"""
        try:
            window_size = self._get_window_size()
            if window_size:
                win_w, _ = window_size
                scale = win_w / 558
                dx_scaled = int(dx * scale)
                dy_scaled = int(dy * scale)
            else:
                dx_scaled = dx
                dy_scaled = dy
                self.logger.debug("无法获取窗口尺寸，使用原始拖动距离")
            
            # 通过 mining_manager 统一管理窗口激活，避免来回切换
            # 只在窗口切换时激活，不在每次拖动时激活
            # if self.mining_manager:
            #     self.mining_manager._ensure_window_active(self.hwnd, self.window_name)
            
            x, y = pyautogui.position()
            pyautogui.mouseDown()
            pyautogui.moveTo(x + dx_scaled, y + dy_scaled, duration=duration)
            pyautogui.mouseUp()
            self.logger.info(f"拖动: dx={dx_scaled}, dy={dy_scaled} [scale={scale:.3f}]")
            self._invalidate_screenshot()
        except (RuntimeError, OSError) as e:
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
        self.window_order: List[int] = []  # 窗口顺序（原始顺序）
        self._current_active_hwnd: int = None  # 当前激活的窗口句柄
        
        # 队列管理窗口挖矿
        self._mining_queue: deque = deque()  # 待挖矿窗口队列
        self._mining_scheduler_thread: threading.Thread = None  # 挖矿调度线程
        self._scheduler_running: bool = False  # 调度器是否运行中
        self._scheduler_lock = threading.Lock()  # 调度器锁

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

    def _ensure_window_active(self, hwnd: int, window_name: str):
        """
        确保指定窗口处于激活状态
        统一管理窗口激活，避免多个窗口来回切换
        注意：此方法不获取锁，调用者需要确保线程安全
        """
        if self._current_active_hwnd != hwnd:
            # 需要切换窗口
            if self._current_active_hwnd is not None:
                self.logger.info(f"切换窗口: 从 {self._current_active_hwnd} 到 {hwnd} ({window_name})")
            else:
                self.logger.info(f"激活窗口: {hwnd} ({window_name})")
            
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.1)  # 减少等待时间
            self._current_active_hwnd = hwnd
        # 如果窗口已经是激活状态，不做任何操作

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

    def stop_mining(self, hwnd: int, user_stopped: bool = False) -> bool:
        """停止指定窗口的挖矿
        
        Args:
            user_stopped: 是否是用户手动停止
        """
        with self._lock:
            if hwnd not in self.miners:
                self.logger.error(f"窗口 {hwnd} 不存在")
                return False
            
            miner = self.miners[hwnd]
            was_mining = miner.is_mining
            if miner.stop_mining(user_stopped=user_stopped):
                if user_stopped:
                    self.logger.info(f"用户手动停止窗口 {miner.window_name} 挖矿")
                else:
                    self.logger.info(f"停止窗口 {miner.window_name} 挖矿")
                # 如果窗口正在挖矿，尝试启动下一个（用户手动停止时不启动下一个）
                if was_mining and not user_stopped:
                    self._try_start_next_window()
                return True
            return False

    def start_first_window(self) -> bool:
        """开始第一个窗口的挖矿"""
        first_hwnd = None
        first_window_name = None
        
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
                        # 保存窗口信息用于锁外激活
                        first_hwnd = hwnd
                        first_window_name = miner.window_name
                        break
        
        # 在锁外激活窗口
        if first_hwnd is not None:
            self._ensure_window_active(first_hwnd, first_window_name)
            return True
        
        self.logger.info("所有窗口都已挖矿")
        return False

    def stop_all_mining(self) -> int:
        """停止所有窗口的挖矿"""
        with self._lock:
            count = 0
            for miner in self.miners.values():
                if miner.stop_mining(user_stopped=True):
                    count += 1
            self.logger.info(f"已停止 {count} 个窗口的挖矿")
            return count

    def reset_all_mined_flags(self):
        """重置所有窗口的挖矿标记"""
        with self._lock:
            for miner in self.miners.values():
                miner.mined = False
            self.logger.info("已重置所有窗口的挖矿标记")
        
        # 停止调度器（如果正在运行）
        with self._scheduler_lock:
            if self._scheduler_running:
                self._scheduler_running = False
                self.logger.info("已停止调度器")
            
            # 清空队列
            self._mining_queue.clear()
            self.logger.info("已清空挖矿队列")

    def _on_window_mining_stopped(self, hwnd: int):
        """
        窗口挖矿停止的回调
        由 SingleWindowMiner 在挖矿停止时调用
        """
        self.logger.info(f"窗口 {hwnd} 挖矿停止")
        
        # 如果调度器正在运行，不自动启动下一个窗口（由调度器处理）
        with self._scheduler_lock:
            if not self._scheduler_running:
                # 尝试启动下一个未标记的窗口（非队列模式）
                self._try_start_next_window()

    def _stop_all_mining_threads(self, except_hwnd: int = None):
        """
        停止所有窗口的挖矿线程
        确保在任何时候只有一个窗口在挖矿
        
        Args:
            except_hwnd: 不停止此窗口的挖矿线程（当前正在挖矿的窗口）
        """
        with self._lock:
            for hwnd, miner in self.miners.items():
                if hwnd != except_hwnd and miner.is_mining:
                    self.logger.info(f"停止窗口 {miner.window_name} 的挖矿线程")
                    miner.is_mining = False
                    # 不要在这里设置 mined=True，让正常流程来设置

    def _try_start_next_window(self):
        """
        尝试启动下一个未标记的窗口
        
        从 window_order 中按顺序查找第一个未挖矿的窗口并启动
        确保只有一个窗口在挖矿
        """
        # 检查是否使用队列模式
        with self._scheduler_lock:
            if self._scheduler_running:
                self.logger.info("队列模式运行中，跳过 _try_start_next_window")
                return
        
        next_hwnd = None
        next_window_name = None
        
        # 使用锁防止多个线程同时启动新窗口
        with self._lock:
            self.logger.info(f"查找下一个未标记窗口，当前窗口数: {len(self.window_order)}")
            
            # 查找第一个未标记且未在挖矿的窗口
            for hwnd in self.window_order:
                if hwnd in self.miners:
                    miner = self.miners[hwnd]
                    self.logger.info(f"检查窗口 {miner.window_name}: mined={miner.mined}, is_mining={miner.is_mining}")
                    
                    if not miner.mined and not miner.is_mining:
                        if miner.start_mining():
                            self.logger.info(f"自动启动下一个窗口 {miner.window_name} 挖矿")
                            next_hwnd = hwnd
                            next_window_name = miner.window_name
                            break
            else:
                # 所有窗口都已挖矿
                all_mined = all(self.miners[h].mined for h in self.window_order if h in self.miners)
                if all_mined:
                    self.logger.info("所有窗口都已挖矿完成")
                return
        
        # 在锁外激活新窗口
        if next_hwnd is not None:
            self._ensure_window_active(next_hwnd, next_window_name)
    
    def _mining_scheduler(self):
        """
        挖矿调度器 - 单线程顺序执行窗口挖矿
        
        从队列中依次取出窗口进行挖矿，一个窗口完成后才启动下一个
        避免多窗口同时挖矿导致的鼠标来回切换问题
        """
        self.logger.info("挖矿调度器启动")
        
        while self._scheduler_running:
            try:
                # 从队列中取出一个窗口
                hwnd = None
                with self._scheduler_lock:
                    if self._mining_queue:
                        hwnd = self._mining_queue.popleft()
                
                if hwnd is None:
                    # 队列为空，等待一段时间再检查
                    time.sleep(0.5)
                    continue
                
                # 检查窗口是否有效
                miner = None
                with self._lock:
                    if hwnd not in self.miners:
                        self.logger.warning(f"窗口 {hwnd} 不存在，跳过")
                        continue
                    miner = self.miners[hwnd]
                    
                    # 检查窗口是否已经完成挖矿
                    if miner.mined:
                        self.logger.info(f"窗口 {miner.window_name} 已完成挖矿，跳过")
                        continue
                    
                    # 检查窗口是否已经在挖矿（不应该发生）
                    if miner.is_mining:
                        self.logger.warning(f"窗口 {miner.window_name} 已经在挖矿，跳过")
                        continue
                
                # miner 可能为 None（如果 continue 被执行）
                if miner is None:
                    continue
                
                # 激活窗口并启动挖矿
                self.logger.info(f"调度器启动窗口 {miner.window_name} 挖矿")
                self._ensure_window_active(hwnd, miner.window_name)
                
                # 启动挖矿（这会创建挖矿线程）
                if not miner.start_mining():
                    self.logger.error(f"启动窗口 {miner.window_name} 挖矿失败")
                    continue
                
                # 等待挖矿完成
                self.logger.info(f"等待窗口 {miner.window_name} 挖矿完成...")
                while miner.is_mining and self._scheduler_running:
                    time.sleep(0.5)
                
                self.logger.info(f"窗口 {miner.window_name} 挖矿完成或停止")
                
                # 检查是否所有窗口都已完成
                with self._lock:
                    all_mined = all(m.mined for m in self.miners.values())
                    if all_mined and not self._mining_queue:
                        self.logger.info("所有窗口挖矿完成，调度器结束")
                        break
                
            except (RuntimeError, OSError) as e:
                self.logger.error(f"调度器异常: {e}", exc_info=True)
                time.sleep(1)
        
        self.logger.info("挖矿调度器停止")
        self._scheduler_running = False
        
        # 将所有窗口的挖矿状态设置为 2（挖矿结束）
        with self._lock:
            for miner in self.miners.values():
                if miner.mining_state == 1:
                    miner.mining_state = 2
                    self.logger.info(f"窗口 {miner.window_name} 挖矿状态设置为 2（挖矿结束）")
    
    def start_mining_queue(self) -> bool:
        """
        启动队列挖矿 - 使用调度器单线程顺序执行
        
        将所有未挖矿的窗口加入队列，然后启动调度器
        """
        with self._scheduler_lock:
            # 停止当前运行的调度器（如果有）
            if self._scheduler_running:
                self.logger.info("停止当前运行的调度器")
                self._scheduler_running = False
                # 等待调度器线程结束（最多等待2秒）
                if hasattr(self, '_mining_scheduler_thread') and self._mining_scheduler_thread.is_alive():
                    self.logger.info("等待调度器线程结束...")
                    self._mining_scheduler_thread.join(timeout=2.0)
                    if self._mining_scheduler_thread.is_alive():
                        self.logger.warning("调度器线程未能在2秒内结束")
            
            # 清空队列并重新填充
            self._mining_queue.clear()
            
            with self._lock:
                for hwnd in self.window_order:
                    if hwnd in self.miners:
                        miner = self.miners[hwnd]
                        if not miner.mined:
                            self._mining_queue.append(hwnd)
                            self.logger.info(f"加入挖矿队列: {miner.window_name}")
            
            if not self._mining_queue:
                self.logger.info("没有需要挖矿的窗口")
                return False
            
            # 启动调度器线程
            self._scheduler_running = True
            self._mining_scheduler_thread = threading.Thread(
                target=self._mining_scheduler,
                daemon=True
            )
            self._mining_scheduler_thread.start()
            self.logger.info(f"启动挖矿队列，共 {len(self._mining_queue)} 个窗口")
            return True
    
    def stop_mining_queue(self, user_stopped: bool = False) -> bool:
        """停止队列挖矿
        
        Args:
            user_stopped: 是否是用户手动停止
        """
        with self._scheduler_lock:
            if not self._scheduler_running:
                return False
            
            self._scheduler_running = False
            
            # 停止当前挖矿的窗口
            with self._lock:
                for miner in self.miners.values():
                    if miner.is_mining:
                        miner.stop_mining(user_stopped=user_stopped)
            
            if user_stopped:
                self.logger.info("用户手动停止挖矿队列")
            else:
                self.logger.info("停止挖矿队列")
            return True
    
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
    
    def get_all_mining_states(self) -> Dict[int, int]:
        """获取所有窗口的挖矿状态
        
        Returns:
            Dict[int, int]: 窗口句柄到挖矿状态的映射
        """
        with self._lock:
            return {hwnd: miner.get_mining_state() for hwnd, miner in self.miners.items()}


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
