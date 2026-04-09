#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Protective_casing - 自动化脚本模块
用于循环查看多个游戏窗口检测 war.png，并自动点击 deploy 按钮

修复版：
1. 抽取公共方法，减少冗余代码
2. 修复 deploy 点击逻辑（先点击 deploy，再处理 six）
3. 移除窗口激活检查
4. 修复内部 import
5. 增加截图缓存 TTL
"""

import time
import logging
import cv2
import numpy as np
import pyautogui
import win32gui
import threading
import ctypes
import random
import tempfile
import os
from pathlib import Path
from typing import Optional, List, Tuple, Dict

from src.utils.adaptive_matcher import AdaptiveMatcher
from src.utils.window_utils import set_dpi_aware, capture_window
from src.utils.resource_path import get_pic_path


set_dpi_aware()


class ProtectiveCasing:
    """保护性外壳自动化脚本 - 循环检测 war.png 并点击 deploy"""

    BASE_WIDTH = 558
    BASE_HEIGHT = 1021
    DEPLOY_RELATIVE_X = 28
    DEPLOY_RELATIVE_Y = 94
    BUY_2_RELATIVE_X = 451
    BUY_2_RELATIVE_Y = 423

    def __init__(self, window_list: List[Tuple[int, str]] = None, mining_manager=None):
        self.logger = logging.getLogger("ProtectiveCasing")
        self.running = False
        self.matcher = AdaptiveMatcher(confidence=0.75, logger=self.logger)
        
        self.war_image_path = get_pic_path("war.png")
        self.shield_image_path = get_pic_path("Shield.png")
        self.buy_image_path = get_pic_path("buy.png")
        self.buy1_image_path = get_pic_path("buy1.png")
        self.town_image_path = get_pic_path("town.png")
        self.six_image_path = get_pic_path("six.png")
        self.sure_image_path = get_pic_path("sure.png")
        
        self.check_interval = 5
        self.target_windows: List[Tuple[int, str]] = window_list or []
        self.mining_manager = mining_manager
        self._screenshot_cache: Dict[int, Tuple[np.ndarray, int, int, float]] = {}
        self._screenshot_ttl = 2.0  # 修复：增加截图缓存时间

    def set_windows(self, window_list: List[Tuple[int, str]]):
        self.target_windows = window_list
        self.logger.info(f"设置检测窗口列表: {len(window_list)} 个窗口")

    def set_mining_manager(self, mining_manager):
        self.mining_manager = mining_manager
        self.logger.info("已设置挖矿管理器")

    def is_mining_active(self) -> bool:
        if self.mining_manager:
            try:
                return self.mining_manager.get_mining_status()
            except (AttributeError, RuntimeError) as e:
                self.logger.error(f"获取挖矿状态失败: {e}")
                return False
        return False

    # ==================== 公共方法（减少冗余）====================

    def _get_window_geometry(self, hwnd: int) -> Optional[dict]:
        """获取窗口几何信息"""
        if not win32gui.IsWindow(hwnd):
            return None
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        return {
            'left': left, 'top': top,
            'right': right, 'bottom': bottom,
            'width': right - left,
            'height': bottom - top
        }

    def _ensure_window_active(self, hwnd: int):
        """确保窗口激活"""
        if not win32gui.IsWindow(hwnd):
            return
        try:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.1)
        except (win32gui.error, OSError) as e:
            self.logger.warning(f"激活窗口失败: {e}")

    def _click_at(self, hwnd: int, rel_x: int, rel_y: int, action_name: str = "按钮"):
        """统一点击逻辑"""
        geom = self._get_window_geometry(hwnd)
        if not geom:
            return False
        
        self._ensure_window_active(hwnd)
        # 激活后重新获取窗口坐标
        geom = self._get_window_geometry(hwnd)
        if not geom:
            return False
            
        abs_x = geom['left'] + rel_x
        abs_y = geom['top'] + rel_y
        pyautogui.click(abs_x, abs_y)
        return True

    def _wait(self, min_sec: float = 1.0, max_sec: float = 2.0):
        """统一随机等待"""
        time.sleep(random.uniform(min_sec, max_sec))

    def _get_screenshot(self, hwnd: int) -> Optional[Tuple[np.ndarray, int, int]]:
        """获取窗口截图（带缓存）"""
        current_time = time.time()
        
        if hwnd in self._screenshot_cache:
            cached = self._screenshot_cache[hwnd]
            if current_time - cached[3] < self._screenshot_ttl:
                return cached[0], cached[1], cached[2]
        
        screenshot, win_w, win_h = capture_window(hwnd)
        if screenshot is None:
            return None
        self._screenshot_cache[hwnd] = (screenshot, win_w, win_h, current_time)
        return screenshot, win_w, win_h

    def _invalidate_screenshot(self, hwnd: int):
        """清除截图缓存"""
        if hwnd in self._screenshot_cache:
            del self._screenshot_cache[hwnd]

    # ==================== 业务方法 ====================

    def check_war_in_window(self, hwnd: int, window_name: str) -> bool:
        """检查窗口中是否存在 war.png"""
        result = self._get_screenshot(hwnd)
        if result is None:
            return False
        
        screenshot, win_w, win_h = result
        match_result = self.matcher.match(screenshot, self.war_image_path, win_w, win_h)
        
        if match_result:
            self.logger.info(f"[{window_name}] 发现 war! 置信度: {match_result['confidence']:.3f}")
            return True
        return False

    def check_town_and_six(self, hwnd: int, window_name: str) -> List[dict]:
        """检测 town 和 six，返回 six 的坐标列表"""
        result = self._get_screenshot(hwnd)
        if result is None:
            return []
        
        screenshot, win_w, win_h = result
        
        # 检测 town
        town_result = self.matcher.match(screenshot, self.town_image_path, win_w, win_h)
        if not town_result:
            self.logger.info(f"[{window_name}] 未找到 town，跳过 six 检测")
            return []
        
        # 检测 six
        six_result = self.matcher.match(screenshot, self.six_image_path, win_w, win_h)
        if not six_result:
            self.logger.info(f"[{window_name}] 未找到 six 模板")
            return []
        
        # 找到所有 six 位置
        six_template = self.matcher.load_template(self.six_image_path)
        if six_template is None:
            return []
        
        # 使用 matcher.match_multi_scale 找到最佳匹配位置和缩放比例
        best_match = self.matcher.match_multi_scale(screenshot, six_template, scale_min=0.8, scale_max=1.2, steps=10)
        if not best_match:
            self.logger.info(f"[{window_name}] 未找到 six 模板（多尺度匹配失败）")
            return []
        
        # 使用最佳匹配结果的尺寸
        w, h = best_match["size"]
        
        # 使用 cv2.matchTemplate 在最佳缩放模板下进行全图扫描，获取所有匹配位置
        gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        gray_tmpl = cv2.cvtColor(six_template, cv2.COLOR_BGR2GRAY)
        
        # 缩放模板用于全图匹配
        scaled_tmpl = self.matcher.scale_template(six_template, best_match.get("scale", 1.0))
        gray_scaled = cv2.cvtColor(scaled_tmpl, cv2.COLOR_BGR2GRAY)
        
        result_map = cv2.matchTemplate(gray_screen, gray_scaled, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result_map >= 0.85)
        
        six_positions = []
        for pt in zip(*locations[::-1]):
            x, y = pt
            six_positions.append({
                "x": x, "y": y,
                "w": w, "h": h,
                "center_x": x + w // 2,
                "center_y": y + h // 2,
                "score": result_map[y, x]
            })
        
        # NMS 过滤
        if six_positions:
            original_count = len(six_positions)
            six_positions = self._apply_nms(six_positions, threshold=0.6)
            filtered_count = len(six_positions)
            self.logger.info(f"[{window_name}] NMS 过滤: {original_count} -> {filtered_count} 个 six")
        
        self.logger.info(f"[{window_name}] 检测到 {len(six_positions)} 个 six")
        return six_positions

    def _apply_nms(self, positions: List[dict], threshold: float = 0.5) -> List[dict]:
        """非最大值抑制"""
        if not positions:
            return []
        
        sorted_pos = sorted(positions, key=lambda p: p["score"], reverse=True)
        kept = []
        
        for pos in sorted_pos:
            overlap = False
            for k in kept:
                x_left = max(pos["x"], k["x"])
                y_top = max(pos["y"], k["y"])
                x_right = min(pos["x"] + pos["w"], k["x"] + k["w"])
                y_bottom = min(pos["y"] + pos["h"], k["y"] + k["h"])
                
                if x_right > x_left and y_bottom > y_top:
                    inter = (x_right - x_left) * (y_bottom - y_top)
                    iou = inter / min(pos["w"] * pos["h"], k["w"] * k["h"])
                    if iou > threshold:
                        overlap = True
                        break
            
            if not overlap:
                kept.append(pos)
        
        return kept

    def click_deploy(self, hwnd: int, window_name: str):
        """点击 deploy 按钮"""
        geom = self._get_window_geometry(hwnd)
        if not geom:
            self.logger.warning(f"窗口无效，无法点击 deploy")
            return
        
        scale = geom['width'] / self.BASE_WIDTH
        rel_x = int(self.DEPLOY_RELATIVE_X * scale)
        rel_y = int(self.DEPLOY_RELATIVE_Y * scale)
        
        if self._click_at(hwnd, rel_x, rel_y, "deploy"):
            abs_x = geom['left'] + rel_x
            abs_y = geom['top'] + rel_y
            self.logger.info(f"[{window_name}] 点击 deploy @ ({abs_x}, {abs_y})")

    def click_buy_2(self, hwnd: int, window_name: str):
        """点击 buy_2 按钮"""
        geom = self._get_window_geometry(hwnd)
        if not geom:
            return
        
        scale = geom['width'] / self.BASE_WIDTH
        rel_x = int(self.BUY_2_RELATIVE_X * scale)
        rel_y = int(self.BUY_2_RELATIVE_Y * scale)
        
        if self._click_at(hwnd, rel_x, rel_y, "buy_2"):
            abs_x = geom['left'] + rel_x
            abs_y = geom['top'] + rel_y
            self.logger.info(f"[{window_name}] 点击 buy_2 @ ({abs_x}, {abs_y})")

    def find_and_click(self, hwnd: int, image_path: str, action_name: str, max_attempts: int = 5) -> bool:
        """通用的查找并点击方法"""
        for _ in range(max_attempts):
            if not self.running:
                return False
            
            result = self._get_screenshot(hwnd)
            if result is None:
                self._wait(0.5, 0.5)
                continue
            
            screenshot, win_w, win_h = result
            match_result = self.matcher.match(screenshot, image_path, win_w, win_h)
            
            if match_result:
                x, y = match_result["location"]
                w, h = match_result["size"]
                center_x = x + w // 2
                center_y = y + h // 2
                
                if self._click_at(hwnd, center_x, center_y, action_name):
                    self.logger.info(f"[{hwnd}] 点击 {action_name} @ ({center_x}, {center_y})")
                    return True
            
            self._wait(0.5, 0.5)
        
        return False

    def process_six_with_red_check(self, hwnd: int, window_name: str, six_positions: List[dict]) -> bool:
        """处理 six 的完整流程"""
        detector = DashedLineDetector()
        
        self.logger.info(f"[{window_name}] 开始处理 {len(six_positions)} 个 six...")
        
        for i, six_pos in enumerate(six_positions):
            if not self.running:
                return False
            
            # 计算缩放比例
            geom = self._get_window_geometry(hwnd)
            if not geom:
                continue
            scale = geom['width'] / self.BASE_WIDTH
            offset_x = int(100 * scale)
            
            # 第一次点击 (x-offset_x, y)
            click_x = six_pos["x"] - offset_x
            click_y = six_pos["center_y"]
            
            self._click_at(hwnd, click_x, click_y, f"six #{i+1}")
            self._wait(1.0, 2.0)
            
            # 检测红点
            self._invalidate_screenshot(hwnd)
            screenshot_result = self._get_screenshot(hwnd)
            
            if screenshot_result:
                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        tmp_path = tmp.name
                    
                    cv2.imwrite(tmp_path, screenshot_result[0])
                    has_red = detector.has_red_at_center(tmp_path)
                    
                    if has_red:
                        # 有红心，等待1-2秒后点击 six 原始坐标
                        self._wait(1.0, 2.0)
                        self._click_at(hwnd, six_pos["x"], six_pos["center_y"], f"six #{i+1} 原始")
                        # 等待 sure 出现并点击
                        self.find_and_click(hwnd, self.sure_image_path, "sure")
                    else:
                        # 没有红心，等待2-3秒后点击 six 原始坐标
                        self._wait(2.0, 3.0)
                        self._click_at(hwnd, six_pos["x"], six_pos["center_y"], f"six #{i+1} 原始")
                        # 等待 sure 出现并点击
                        self.find_and_click(hwnd, self.sure_image_path, "sure")
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        os.unlink(tmp_path)
        
        return True

    def start(self):
        """启动自动化脚本"""
        self.logger.info("=" * 50)
        self.logger.info("启动保护性外壳自动化脚本")
        self.logger.info(f"检测目标: {self.war_image_path}")
        self.logger.info("=" * 50)
        
        self.running = True
        
        while self.running:
            try:
                for hwnd, window_name in self.target_windows:
                    if not self.running:
                        break
                    
                    # 移除窗口激活检查，允许后台运行
                    
                    # 检查挖矿状态
                    if self.is_mining_active():
                        self.logger.debug(f"[{window_name}] 挖矿进行中")
                        continue
                    
                    self._invalidate_screenshot(hwnd)
                    
                    # 检测 war
                    if not self.check_war_in_window(hwnd, window_name):
                        continue
                    
                    self.logger.info(f"[{window_name}] 检测到 war，开始处理")
                    
                    # ⚠️ 修复：先点击 deploy，不依赖后续 war 状态
                    self.click_deploy(hwnd, window_name)
                    self._wait()
                    
                    self.find_and_click(hwnd, self.shield_image_path, "Shield")
                    self._wait()
                    
                    self.click_buy_2(hwnd, window_name)
                    self._wait()
                    
                    self.find_and_click(hwnd, self.buy_image_path, "buy")
                    self._wait()
                    
                    # 再处理 six
                    six_positions = self.check_town_and_six(hwnd, window_name)
                    if six_positions:
                        self.logger.info(f"[{window_name}] 检测到 {len(six_positions)} 个 six")
                        self.process_six_with_red_check(hwnd, window_name, six_positions)
                    
                    self._wait(self.check_interval, self.check_interval)
                
                self._wait(1)
                
            except KeyboardInterrupt:
                self.running = False
            except (OSError, RuntimeError) as e:
                self.logger.error(f"运行错误: {e}", exc_info=True)
                self._wait(5)

    def start_deploy_flow(self, hwnd: int, window_name: str):
        """启动 deploy 流程"""
        self.logger.info(f"[{window_name}] 开始 deploy 流程")
        
        # 等待 1-2 秒
        self._wait(1.0, 2.0)
        self.logger.info(f"[{window_name}] 等待后点击 deploy...")
        
        # 点击 deploy 坐标
        self.click_deploy(hwnd, window_name)
        
        # 等待 1-2 秒
        self._wait(1.0, 2.0)
        self.logger.info(f"[{window_name}] 等待后等待 Shield 出现...")
        
        # 等待 Shield 出现后点击
        self.find_and_click(hwnd, self.shield_image_path, "Shield")
        
        # 等待 1-2 秒
        self._wait(1.0, 2.0)
        self.logger.info(f"[{window_name}] 等待后点击 buy_2...")
        
        # 点击 buy_2
        self.click_buy_2(hwnd, window_name)
        
        # 等待 1-2 秒
        self._wait(1.0, 2.0)
        self.logger.info(f"[{window_name}] 等待后等待 buy 出现...")
        
        # 等待 buy 出现后点击
        self.find_and_click(hwnd, self.buy_image_path, "buy")
        
        # 等待 1-2 秒
        self._wait(1.0, 2.0)
        self.logger.info(f"[{window_name}] 等待后等待 buy1 出现...")
        
        # 点击 buy1
        self.find_and_click(hwnd, self.buy1_image_path, "buy1")
        
        # 等待 1-2 秒
        self._wait(1.0, 2.0)
        self.logger.info(f"[{window_name}] 完成 deploy 流程")
    
    def is_protecting(self) -> bool:
        """检查是否正在保护中"""
        return self.running
    
    def stop(self):
        self.running = False
        self.logger.info("停止保护性外壳自动化脚本")
    
    def stop_protection(self):
        """停止保护"""
        self.stop()
    
    def start_protection(self):
        """开始保护"""
        if not self.running:
            self.running = True
            threading.Thread(target=self.start, daemon=True).start()
            self.logger.info("启动保护性外壳自动化脚本")
