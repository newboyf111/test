#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Protective_casing - 自动化脚本模块
用于循环查看多个游戏窗口检测 war.png，并自动点击 deploy 按钮

流程：
1. 循环检测所有目标窗口
2. 检测 war.png，发现后执行完整流程
3. 包括 town/six 检测和 Shield 流程
"""

import time
import logging
import cv2
import numpy as np
import pyautogui
import win32gui
import threading
import random
import tempfile
import os
from typing import Optional, List, Tuple, Dict

from src.utils.adaptive_matcher import AdaptiveMatcher
from src.utils.window_utils import set_dpi_aware, capture_window
from src.utils import ScreenshotCache
from src.dashed_line_detector import DashedLineDetector


set_dpi_aware()


class ProtectiveCasing:
    """保护性外壳自动化脚本 - 循环检测 war.png 并点击 deploy"""

    BASE_WIDTH = 558
    BASE_HEIGHT = 1021
    DEPLOY_RELATIVE_X = 33
    DEPLOY_RELATIVE_Y = 132
    BUY_2_RELATIVE_X = 461
    BUY_2_RELATIVE_Y = 464
    SIX_SEARCH_X1 = 149
    SIX_SEARCH_Y1 = 222
    SIX_SEARCH_X2 = 195
    SIX_SEARCH_Y2 = 563

    def __init__(self, window_list: List[Tuple[int, str]] = None, mining_manager=None):
        self.logger = logging.getLogger("ProtectiveCasing")
        self.running = False
        self.matcher = AdaptiveMatcher(confidence=0.75, logger=self.logger)
        
        self.war_image_name = "war.png"
        self.shield_image_name = "Shield.png"
        self.buy_image_name = "buy.png"
        self.buy1_image_name = "buy1.png"
        self.town_image_name = "town.png"
        self.six_image_name = "six.png"
        self.sure_image_name = "sure.png"
        
        self.check_interval = 5
        self.target_windows: List[Tuple[int, str]] = window_list or []
        self.mining_manager = mining_manager
        self._screenshot_cache = ScreenshotCache(ttl=0.5, logger=self.logger)
        self.last_screenshot: Dict[int, np.ndarray] = {}

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

    def _get_window_geometry(self, hwnd: int) -> Optional[dict]:
        """获取窗口几何信息"""
        if not win32gui.IsWindow(hwnd):
            return None
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            return {
                'left': left, 'top': top,
                'right': right, 'bottom': bottom,
                'width': right - left,
                'height': bottom - top
            }
        except (win32gui.error, OSError) as e:
            self.logger.warning(f"获取窗口几何信息失败: {e}")
            return None

    def _activate_window(self, hwnd: int):
        """激活窗口为前台"""
        if not win32gui.IsWindow(hwnd):
            return
        try:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.3)
        except (win32gui.error, OSError) as e:
            self.logger.warning(f"激活窗口失败: {e}")

    def _click_at(self, hwnd: int, rel_x: int, rel_y: int, action_name: str = "按钮"):
        """统一点击逻辑"""
        geom = self._get_window_geometry(hwnd)
        if not geom:
            return False
        
        self._activate_window(hwnd)
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
        def capture_func():
            return capture_window(hwnd)
        
        return self._screenshot_cache.get(hwnd, capture_func)

    def _get_window_screenshot(self, hwnd: int) -> Optional[np.ndarray]:
        """获取窗口截图（保存到内存）"""
        result = capture_window(hwnd)
        if result:
            screenshot, _, _ = result
            self.last_screenshot[hwnd] = screenshot
            return screenshot
        return None

    def _invalidate_screenshot(self, hwnd: int):
        """清除截图缓存"""
        self._screenshot_cache.invalidate(hwnd)

    def check_war_in_window(self, hwnd: int, window_name: str) -> bool:
        """检测窗口中是否存在 war.png"""
        result = self._get_screenshot(hwnd)
        if result is None:
            return False
        
        screenshot, win_w, win_h = result
        match_result = self.matcher.match(screenshot, self.war_image_name, win_w, win_h)
        
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
        
        town_result = self.matcher.match(screenshot, self.town_image_name, win_w, win_h)
        if not town_result:
            self.logger.info(f"[{window_name}] 未找到 town，跳过 six 检测")
            return []
        
        six_result = self.matcher.match(screenshot, self.six_image_name, win_w, win_h)
        if not six_result:
            self.logger.info(f"[{window_name}] 未找到 six 模板")
            return []
        
        six_template = self.matcher.load_template(self.six_image_name)
        if six_template is None:
            return []
        
        scale = win_w / self.BASE_WIDTH
        region_x1 = int(self.SIX_SEARCH_X1 * scale)
        region_y1 = int(self.SIX_SEARCH_Y1 * scale)
        region_x2 = int(self.SIX_SEARCH_X2 * scale)
        region_y2 = int(self.SIX_SEARCH_Y2 * scale)
        
        search_region = screenshot[region_y1:region_y2, region_x1:region_x2]
        
        best_match = self.matcher.match_multi_scale(search_region, six_template, scale_min=0.8, scale_max=1.2, steps=10)
        if not best_match:
            self.logger.info(f"[{window_name}] 未找到 six 模板（多尺度匹配失败）")
            return []
        
        w, h = best_match["size"]
        gray_region = cv2.cvtColor(search_region, cv2.COLOR_BGR2GRAY)
        scaled_tmpl = self.matcher.scale_template(six_template, best_match.get("scale", 1.0))
        gray_scaled = cv2.cvtColor(scaled_tmpl, cv2.COLOR_BGR2GRAY)
        
        result_map = cv2.matchTemplate(gray_region, gray_scaled, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result_map >= 0.85)
        
        six_positions = []
        for pt in zip(*locations[::-1]):
            x, y = pt
            abs_x = x + region_x1
            abs_y = y + region_y1
            six_positions.append({
                "x": abs_x, "y": abs_y,
                "w": w, "h": h,
                "center_x": abs_x + w // 2,
                "center_y": abs_y + h // 2,
                "score": result_map[y, x]
            })
        
        if six_positions:
            original_count = len(six_positions)
            six_positions = self._apply_nms(six_positions, threshold=0.6)
            self.logger.info(f"[{window_name}] NMS 过滤: {original_count} -> {len(six_positions)} 个 six")
        
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
            self.logger.info(f"[{window_name}] 点击 deploy")

    def click_buy_2(self, hwnd: int, window_name: str):
        """点击 buy_2 按钮"""
        geom = self._get_window_geometry(hwnd)
        if not geom:
            return
        
        scale = geom['width'] / self.BASE_WIDTH
        rel_x = int(self.BUY_2_RELATIVE_X * scale)
        rel_y = int(self.BUY_2_RELATIVE_Y * scale)
        
        if self._click_at(hwnd, rel_x, rel_y, "buy_2"):
            self.logger.info(f"[{window_name}] 点击 buy_2")

    def find_and_click(self, hwnd: int, image_name: str, action_name: str, max_attempts: int = 5) -> bool:
        """通用的查找并点击方法"""
        for attempt in range(max_attempts):
            if not self.running:
                return False
            
            result = self._get_screenshot(hwnd)
            if result is None:
                self._wait(0.5, 0.5)
                continue
            
            screenshot, win_w, win_h = result
            match_result = self.matcher.match(screenshot, image_name, win_w, win_h)
            
            if match_result:
                x, y = match_result["location"]
                w, h = match_result["size"]
                center_x = x + w // 2
                center_y = y + h // 2
                
                if self._click_at(hwnd, center_x, center_y, action_name):
                    self.logger.info(f"[{hwnd}] 点击 {action_name}")
                    return True
            
            self._wait(0.5, 0.5)
        
        return False

    def find_and_click_sure(self, hwnd: int, window_name: str) -> bool:
        """查找并点击 sure.png"""
        return self.find_and_click(hwnd, self.sure_image_name, "sure", max_attempts=3)

    def find_and_click_shield(self, hwnd: int, window_name: str) -> bool:
        """查找并点击 Shield"""
        return self.find_and_click(hwnd, self.shield_image_name, "Shield", max_attempts=5)

    def process_six(self, hwnd: int, window_name: str, six_positions: List[dict], detector: DashedLineDetector):
        """处理单个 six"""
        geom = self._get_window_geometry(hwnd)
        if not geom:
            return
        
        scale = geom['width'] / self.BASE_WIDTH
        offset_x = int(100 * scale)
        
        for i, six_pos in enumerate(six_positions):
            if not self.running:
                return
            
            click_x = six_pos["x"] - offset_x
            click_y = six_pos["center_y"]
            
            self._click_at(hwnd, click_x, click_y, f"six #{i+1}")
            self._wait(1.0, 2.0)
            
            screenshot = self._get_window_screenshot(hwnd)
            
            if screenshot is not None:
                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        tmp_path = tmp.name
                    
                    cv2.imwrite(tmp_path, screenshot)
                    has_red = detector.has_red_at_center(tmp_path)
                    
                    if has_red:
                        self._wait(1.0, 2.0)
                        self._click_at(hwnd, six_pos["x"], six_pos["center_y"], f"six #{i+1} 原始")
                        self.find_and_click_sure(hwnd, window_name)
                    else:
                        self.logger.info(f"[{window_name}] six #{i+1} 未检测到红点，跳过")
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        os.unlink(tmp_path)

    def process_shield_flow(self, hwnd: int, window_name: str):
        """执行 Shield 流程"""
        self.logger.info(f"[{window_name}] 开始 Shield 流程")
        
        self._wait(1.0, 2.0)
        self.click_deploy(hwnd, window_name)
        
        self._wait(2.0, 3.0)
        self.find_and_click_shield(hwnd, window_name)
        
        self._wait(1.0, 2.0)
        self.click_buy_2(hwnd, window_name)
        
        self._wait(2.0, 3.0)
        self.find_and_click(hwnd, self.buy_image_name, "buy")
        
        self._wait(2.0, 3.0)
        self.find_and_click(hwnd, self.buy_image_name, "buy")
        
        self._wait(3.0, 4.0)

    def start(self):
        """启动自动化脚本 - 主流程"""
        self.logger.info("=" * 50)
        self.logger.info("启动保护性外壳自动化脚本")
        self.logger.info("=" * 50)
        
        self.running = True
        detector = DashedLineDetector()
        
        while self.running:
            war_windows = []
            
            if self.is_mining_active():
                self.logger.debug("挖矿进行中，暂停 war 检测")
                self._wait(1, 1)
                continue
            
            for hwnd, window_name in self.target_windows:
                if not self.running:
                    break
                
                self._activate_window(hwnd)
                self._invalidate_screenshot(hwnd)
                
                if not self.check_war_in_window(hwnd, window_name):
                    continue
                
                war_windows.append((hwnd, window_name))
                
                six_positions = self.check_town_and_six(hwnd, window_name)
                
                if six_positions:
                    self.process_six(hwnd, window_name, six_positions, detector)
                
                self._invalidate_screenshot(hwnd)
                
                if self.check_war_in_window(hwnd, window_name):
                    self.process_shield_flow(hwnd, window_name)
            
            if war_windows:
                self.logger.info(f"本轮发现 war 的窗口: {[w[1] for w in war_windows]}")
            else:
                self.logger.info("所有窗口未发现 war")
            
            wait_count = 0
            while wait_count < self.check_interval and self.running:
                if self.is_mining_active():
                    self.logger.info("挖矿启动，结束等待")
                    break
                time.sleep(1)
                wait_count += 1
        
        self.logger.info("保护性外壳自动化脚本结束")

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
    
    def should_start_after_mining(self) -> bool:
        """检查是否应该在挖矿结束后启动"""
        if not self.mining_manager:
            return False
        
        try:
            if self.mining_manager.get_mining_status():
                return False
            
            states = self.mining_manager.get_all_mining_states()
            if not states:
                return False
            
            return all(state == 2 for state in states.values())
        except (AttributeError, RuntimeError) as e:
            self.logger.error(f"检查挖矿状态失败: {e}")
            return False

    def process_six_with_red_check(self, hwnd: int, window_name: str, six_positions: List[dict]):
        """处理 six 的完整流程（GUI调用）"""
        detector = DashedLineDetector()
        self.process_six(hwnd, window_name, six_positions, detector)

    def start_deploy_flow(self, hwnd: int, window_name: str):
        """启动 deploy 流程（GUI调用）"""
        self.process_shield_flow(hwnd, window_name)
