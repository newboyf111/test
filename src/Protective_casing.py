#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Protective_casing - 自动化脚本模块
用于循环查看多个游戏窗口检测 war.png，并自动点击 deploy 按钮
"""

import time
import logging
import cv2
import numpy as np
import pyautogui
import win32gui
import win32con
import ctypes
import random
from pathlib import Path
from typing import Optional, List, Tuple, Dict


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


class AdaptiveMatcher:
    """自适应图片匹配器 - 支持不同屏幕分辨率、窗口大小和DPI"""

    BASE_WIDTH = 558
    BASE_HEIGHT = 1021
    FALLBACK_SCALE_MIN = 0.5
    FALLBACK_SCALE_MAX = 2.0
    FALLBACK_STEPS = 20

    def __init__(self, confidence: float = 0.75, logger=None):
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
            if not Path(image_path).exists():
                self.log("warning", f"图片不存在: {image_path}")
                return None
            img = cv2.imread(image_path)
            if img is None:
                self.log("warning", f"无法读取图片: {image_path}")
                return None
            self._template_cache[image_path] = img
            self.log("debug", f"加载模板: {Path(image_path).name} {img.shape[1]}x{img.shape[0]}")
        return self._template_cache.get(image_path)

    def get_scale_factor(self, current_width: int, current_height: int = None) -> float:
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
                if max_val >= self.confidence and max_val > best_score:
                    best_score = max_val
                    best_result = {
                        "found": True,
                        "location": max_loc,
                        "confidence": max_val,
                        "size": (new_w, new_h),
                        "scale": scale
                    }
            return best_result
        except Exception as e:
            self.log("error", f"多尺度匹配错误: {e}")
        return None

    def match(self, screenshot: np.ndarray, image_path: str, 
              win_w: int, win_h: int) -> Optional[dict]:
        """
        匹配图片 - 自适应多尺度匹配
        
        1. 首先使用计算出的缩放比例进行匹配
        2. 如果失败，尝试使用上次成功的缩放比例
        3. 如果仍然失败，使用多尺度匹配扫描
        """
        template = self.load_template(image_path)
        if template is None:
            return None

        scale = self.get_scale_factor(win_w, win_h)
        
        # 方法1：使用计算出的缩放比例
        scaled_template = self.get_scaled_template(image_path, scale)
        if scaled_template is not None:
            result = self.match_single(screenshot, scaled_template)
            if result:
                result["scale"] = scale
                self._last_success_scale[image_path] = scale
                self.log("debug", f"[{Path(image_path).name}] 匹配成功，缩放: {scale:.3f}，置信度: {result['confidence']:.3f}")
                return result

        # 方法2：使用上次成功的缩放比例
        if image_path in self._last_success_scale:
            last_scale = self._last_success_scale[image_path]
            if abs(last_scale - scale) > 0.01:
                scaled_template = self.get_scaled_template(image_path, last_scale)
                if scaled_template is not None:
                    result = self.match_single(screenshot, scaled_template)
                    if result:
                        result["scale"] = last_scale
                        self.log("debug", f"[{Path(image_path).name}] 使用上次成功缩放: {last_scale:.3f}")
                        return result

        # 方法3：多尺度匹配扫描
        self.log("debug", f"[{Path(image_path).name}] 单一缩放匹配失败，启动多尺度扫描...")
        result = self.match_multi_scale(
            screenshot, template,
            self.FALLBACK_SCALE_MIN, self.FALLBACK_SCALE_MAX, self.FALLBACK_STEPS
        )
        if result:
            self._last_success_scale[image_path] = result.get("scale", scale)
            self.log("debug", f"[{Path(image_path).name}] 多尺度匹配成功，缩放: {result.get('scale', 'N/A'):.3f}")
        return result

    def get_center(self, result: dict) -> Optional[Tuple[int, int]]:
        """获取匹配结果的中心坐标"""
        if not result:
            return None
        x, y = result["location"]
        w, h = result["size"]
        return (x + w // 2, y + h // 2)


class ProtectiveCasing:
    """保护性外壳自动化脚本 - 循环检测 war.png 并点击 deploy"""

    BASE_WIDTH = 558
    BASE_HEIGHT = 1021
    DEPLOY_RELATIVE_X = 28
    DEPLOY_RELATIVE_Y = 94
    BUY_2_RELATIVE_X = 451
    BUY_2_RELATIVE_Y = 423

    def __init__(self, window_list: List[Tuple[int, str]] = None, mining_manager=None):
        """
        初始化
        
        Args:
            window_list: GUI 激活的窗口列表，格式为 [(hwnd, title), ...]
            mining_manager: 挖矿管理器实例，用于检查挖矿状态
        """
        self.logger = logging.getLogger("ProtectiveCasing")
        self.running = False
        self.matcher = AdaptiveMatcher(confidence=0.75, logger=self.logger)
        
        pic_dir = Path(__file__).parent.parent / "pic"
        self.war_image_path = str(pic_dir / "war.png")
        self.shield_image_path = str(pic_dir / "Shield.png")
        self.buy_image_path = str(pic_dir / "buy.png")
        
        self.check_interval = 5  # 检测间隔（秒）
        self.target_windows: List[Tuple[int, str]] = window_list or []  # (hwnd, title)
        self.mining_manager = mining_manager  # 挖矿管理器实例

    def set_windows(self, window_list: List[Tuple[int, str]]):
        """
        设置要检测的窗口列表
        
        Args:
            window_list: GUI 激活的窗口列表，格式为 [(hwnd, title), ...]
        """
        self.target_windows = window_list
        self.logger.info(f"设置检测窗口列表: {len(window_list)} 个窗口")

    def set_mining_manager(self, mining_manager):
        """
        设置挖矿管理器
        
        Args:
            mining_manager: 挖矿管理器实例
        """
        self.mining_manager = mining_manager
        self.logger.info("已设置挖矿管理器")

    def is_mining_active(self) -> bool:
        """
        检查是否有窗口正在挖矿
        
        Returns:
            bool: True 表示有窗口正在挖矿，False 表示所有窗口都已停止挖矿
        """
        if self.mining_manager:
            try:
                return self.mining_manager.get_mining_status()
            except Exception as e:
                self.logger.error(f"获取挖矿状态失败: {e}")
                return False
        return False

    def get_scale_factor(self, current_width: int) -> float:
        """计算窗口缩放比例"""
        if self.BASE_WIDTH == 0:
            return 1.0
        return current_width / self.BASE_WIDTH

    def get_scaled_deploy_coords(self, win_width: int, win_height: int) -> Tuple[int, int]:
        """
        获取缩放后的 deploy 按钮坐标
        
        Args:
            win_width: 窗口宽度
            win_height: 窗口高度
            
        Returns:
            缩放后的相对坐标 (x, y)
        """
        scale = self.get_scale_factor(win_width)
        scaled_x = int(self.DEPLOY_RELATIVE_X * scale)
        scaled_y = int(self.DEPLOY_RELATIVE_Y * scale)
        return scaled_x, scaled_y

    def get_window_screenshot(self, hwnd: int) -> Optional[Tuple[np.ndarray, int, int]]:
        """获取窗口截图"""
        try:
            if not win32gui.IsWindow(hwnd):
                return None
            
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            
            if width <= 0 or height <= 0:
                return None
            
            screenshot = pyautogui.screenshot(region=(left, top, width, height))
            screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
            return screenshot, width, height
        except Exception as e:
            self.logger.error(f"截图失败 (hwnd={hwnd}): {e}")
            return None

    def check_war_in_window(self, hwnd: int, window_name: str) -> bool:
        """检查窗口中是否存在 war.png"""
        result = self.get_window_screenshot(hwnd)
        if result is None:
            return False
        
        screenshot, win_w, win_h = result
        
        match_result = self.matcher.match(screenshot, self.war_image_path, win_w, win_h)
        
        if match_result:
            self.logger.info(f"[{window_name}] 发现 war! 置信度: {match_result['confidence']:.3f}")
            return True
        
        return False

    def click_deploy(self, hwnd: int, window_name: str):
        """
        点击 deploy 按钮
        
        Args:
            hwnd: 窗口句柄
            window_name: 窗口名称
        """
        try:
            if not win32gui.IsWindow(hwnd):
                self.logger.warning(f"窗口无效，无法点击 deploy")
                return
            
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            win_width = right - left
            win_height = bottom - top
            
            # 获取缩放后的 deploy 坐标
            deploy_x, deploy_y = self.get_scaled_deploy_coords(win_width, win_height)
            
            # 计算绝对坐标
            abs_x = left + deploy_x
            abs_y = top + deploy_y
            
            self.logger.info(f"[{window_name}] 点击 deploy 按钮，相对坐标 ({deploy_x}, {deploy_y})，绝对坐标 ({abs_x}, {abs_y})")
            
            # 使用 win32gui 发送点击消息
            lParam = win32con.MAKELONG(deploy_x, deploy_y)
            
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
            time.sleep(0.05)
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lParam)
            
            self.logger.info(f"[{window_name}] 已点击 deploy 按钮")
            
        except Exception as e:
            self.logger.error(f"点击 deploy 失败: {e}")

    def find_and_click_shield(self, hwnd: int, window_name: str, max_attempts: int = 5) -> bool:
        """
        查找并点击 Shield.png
        
        Args:
            hwnd: 窗口句柄
            window_name: 窗口名称
            max_attempts: 最大尝试次数
            
        Returns:
            是否成功点击
        """
        for attempt in range(max_attempts):
            if not self.running or not win32gui.IsWindow(hwnd):
                return False
            
            result = self.get_window_screenshot(hwnd)
            if result is None:
                time.sleep(0.5)
                continue
            
            screenshot, win_w, win_h = result
            
            match_result = self.matcher.match(screenshot, self.shield_image_path, win_w, win_h)
            
            if match_result:
                x, y = match_result["location"]
                w, h = match_result["size"]
                center_x = x + w // 2
                center_y = y + h // 2
                
                self.logger.info(f"[{window_name}] 发现 Shield! 置信度: {match_result['confidence']:.3f}，位置: ({center_x}, {center_y})")
                
                lParam = win32con.MAKELONG(center_x, center_y)
                win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
                time.sleep(0.05)
                win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lParam)
                
                self.logger.info(f"[{window_name}] 已点击 Shield 按钮")
                return True
            
            self.logger.debug(f"[{window_name}] 未找到 Shield，尝试 {attempt + 1}/{max_attempts}")
            time.sleep(0.5)
        
        self.logger.warning(f"[{window_name}] 未找到 Shield 按钮")
        return False

    def get_scaled_buy_2_coords(self, win_width: int, win_height: int) -> Tuple[int, int]:
        """
        获取缩放后的 buy_2 坐标
        
        Args:
            win_width: 窗口宽度
            win_height: 窗口高度
            
        Returns:
            缩放后的相对坐标 (x, y)
        """
        scale = self.get_scale_factor(win_width)
        scaled_x = int(self.BUY_2_RELATIVE_X * scale)
        scaled_y = int(self.BUY_2_RELATIVE_Y * scale)
        return scaled_x, scaled_y

    def click_buy_2(self, hwnd: int, window_name: str):
        """
        点击 buy_2 按钮
        
        Args:
            hwnd: 窗口句柄
            window_name: 窗口名称
        """
        try:
            if not win32gui.IsWindow(hwnd):
                self.logger.warning(f"窗口无效，无法点击 buy_2")
                return
            
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            win_width = right - left
            win_height = bottom - top
            
            # 获取缩放后的 buy_2 坐标
            buy_2_x, buy_2_y = self.get_scaled_buy_2_coords(win_width, win_height)
            
            self.logger.info(f"[{window_name}] 点击 buy_2 按钮，相对坐标 ({buy_2_x}, {buy_2_y})")
            
            # 使用 win32gui 发送点击消息
            lParam = win32con.MAKELONG(buy_2_x, buy_2_y)
            
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
            time.sleep(0.05)
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lParam)
            
            self.logger.info(f"[{window_name}] 已点击 buy_2 按钮")
            
        except Exception as e:
            self.logger.error(f"点击 buy_2 失败: {e}")

    def find_and_click_buy(self, hwnd: int, window_name: str, max_attempts: int = 5) -> bool:
        """
        查找并点击 buy.png
        
        Args:
            hwnd: 窗口句柄
            window_name: 窗口名称
            max_attempts: 最大尝试次数
            
        Returns:
            是否成功点击
        """
        for attempt in range(max_attempts):
            if not self.running or not win32gui.IsWindow(hwnd):
                return False
            
            result = self.get_window_screenshot(hwnd)
            if result is None:
                time.sleep(0.5)
                continue
            
            screenshot, win_w, win_h = result
            
            match_result = self.matcher.match(screenshot, self.buy_image_path, win_w, win_h)
            
            if match_result:
                x, y = match_result["location"]
                w, h = match_result["size"]
                center_x = x + w // 2
                center_y = y + h // 2
                
                self.logger.info(f"[{window_name}] 发现 buy! 置信度: {match_result['confidence']:.3f}，位置: ({center_x}, {center_y})")
                
                lParam = win32con.MAKELONG(center_x, center_y)
                win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
                time.sleep(0.05)
                win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lParam)
                
                self.logger.info(f"[{window_name}] 已点击 buy 按钮")
                return True
            
            self.logger.debug(f"[{window_name}] 未找到 buy，尝试 {attempt + 1}/{max_attempts}")
            time.sleep(0.5)
        
        self.logger.warning(f"[{window_name}] 未找到 buy 按钮")
        return False

    def start(self):
        """启动自动化脚本"""
        self.logger.info("=" * 50)
        self.logger.info("启动保护性外壳自动化脚本")
        self.logger.info(f"检测目标: {self.war_image_path}")
        self.logger.info(f"Shield 目标: {self.shield_image_path}")
        self.logger.info(f"Buy 目标: {self.buy_image_path}")
        self.logger.info(f"Deploy 相对坐标: ({self.DEPLOY_RELATIVE_X}, {self.DEPLOY_RELATIVE_Y})")
        self.logger.info(f"Buy_2 相对坐标: ({self.BUY_2_RELATIVE_X}, {self.BUY_2_RELATIVE_Y})")
        self.logger.info(f"检测间隔: {self.check_interval} 秒")
        self.logger.info(f"检测窗口数: {len(self.target_windows)}")
        self.logger.info("=" * 50)
        
        if not self.target_windows:
            self.logger.warning("未设置检测窗口列表，请先通过 set_windows() 设置窗口")
            return
        
        self.running = True
        
        try:
            while self.running:
                if not self.target_windows:
                    self.logger.warning("检测窗口列表为空")
                    time.sleep(self.check_interval)
                    continue
                
                # 检查是否有窗口正在挖矿
                is_mining = self.is_mining_active()
                
                if is_mining:
                    self.logger.info("检测到挖矿正在进行，暂停 war 检测")
                    # 等待 5 秒后再次检查
                    for _ in range(5):
                        if not self.running:
                            break
                        time.sleep(1)
                    continue
                
                self.logger.info(f"检测 {len(self.target_windows)} 个窗口...")
                
                war_found_windows = []
                
                for hwnd, title in self.target_windows:
                    if not self.running:
                        break
                    
                    # 再次检查挖矿状态（避免在处理过程中挖矿启动）
                    if self.is_mining_active():
                        self.logger.info("检测到挖矿启动，停止当前检测")
                        break
                    
                    # 检查窗口是否有效
                    if not win32gui.IsWindow(hwnd):
                        self.logger.warning(f"窗口无效 [{title}]")
                        continue
                    
                    # 激活窗口
                    try:
                        win32gui.SetForegroundWindow(hwnd)
                        time.sleep(0.3)
                    except Exception as e:
                        self.logger.warning(f"激活窗口失败 [{title}]: {e}")
                    
                    # 检测 war.png
                    if self.check_war_in_window(hwnd, title):
                        war_found_windows.append(title)
                        
                        # 等待 1-2 秒
                        wait_time = random.uniform(1.0, 2.0)
                        self.logger.info(f"[{title}] 等待 {wait_time:.1f} 秒后点击 deploy...")
                        time.sleep(wait_time)
                        
                        # 点击 deploy 按钮
                        self.click_deploy(hwnd, title)
                        
                        # 等待 2-3 秒后点击 Shield
                        wait_time_shield = random.uniform(2.0, 3.0)
                        self.logger.info(f"[{title}] 等待 {wait_time_shield:.1f} 秒后查找 Shield...")
                        time.sleep(wait_time_shield)
                        
                        # 查找并点击 Shield
                        if self.find_and_click_shield(hwnd, title):
                            # 等待 1-2 秒后点击 buy_2
                            wait_time_buy_2 = random.uniform(1.0, 2.0)
                            self.logger.info(f"[{title}] 等待 {wait_time_buy_2:.1f} 秒后点击 buy_2...")
                            time.sleep(wait_time_buy_2)
                            
                            # 点击 buy_2 按钮
                            self.click_buy_2(hwnd, title)
                            
                            # 等待 2-3 秒后点击 buy.png
                            wait_time_buy_1 = random.uniform(2.0, 3.0)
                            self.logger.info(f"[{title}] 等待 {wait_time_buy_1:.1f} 秒后查找 buy...")
                            time.sleep(wait_time_buy_1)
                            
                            # 第一次点击 buy.png
                            if self.find_and_click_buy(hwnd, title):
                                # 等待 2-3 秒后再次点击 buy.png
                                wait_time_buy_2nd = random.uniform(2.0, 3.0)
                                self.logger.info(f"[{title}] 等待 {wait_time_buy_2nd:.1f} 秒后再次点击 buy...")
                                time.sleep(wait_time_buy_2nd)
                                
                                # 第二次点击 buy.png
                                if self.find_and_click_buy(hwnd, title):
                                    # 点击成功后等待 3-4 秒，然后检查下一个窗口
                                    wait_time_next = random.uniform(3.0, 4.0)
                                    self.logger.info(f"[{title}] 操作完成，等待 {wait_time_next:.1f} 秒后检查下一个窗口...")
                                    time.sleep(wait_time_next)
                
                # 汇总结果
                if war_found_windows:
                    self.logger.warning(f"[WAR] 发现 war 的窗口: {', '.join(war_found_windows)}")
                else:
                    self.logger.info("[OK] 所有窗口未发现 war")
                
                # 等待下一次检测
                for _ in range(self.check_interval):
                    if not self.running:
                        break
                    # 检查挖矿状态，如果挖矿开始则提前结束等待
                    if self.is_mining_active():
                        self.logger.info("检测到挖矿启动，提前结束等待")
                        break
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            self.logger.info("用户中断")
        except Exception as e:
            self.logger.error(f"运行异常: {e}", exc_info=True)
        finally:
            self.stop()

    def stop(self):
        """停止自动化脚本"""
        self.logger.info("停止保护性外壳自动化脚本")
        self.running = False


def main():
    """主函数 - 独立运行时的示例"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 示例：手动设置窗口列表
    # 实际使用时，应该从 GUI 获取窗口列表
    script = ProtectiveCasing()
    
    # 查找所有游戏窗口作为示例
    windows = []
    def enum_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and ("MuMu" in title or "无尽冬日" in title):
                windows.append((hwnd, title))
    win32gui.EnumWindows(enum_callback, None)
    
    if windows:
        script.set_windows(windows)
        try:
            script.start()
        except KeyboardInterrupt:
            print("\n用户中断，退出程序")
    else:
        print("未找到游戏窗口")


if __name__ == "__main__":
    main()
