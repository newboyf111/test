#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪域兵器联赛 (Snowfield Weapon League) 功能模块
"""

import time
import random
import logging
import json
import os
import threading
import cv2
import numpy as np
from typing import Optional, Dict, Any, Tuple

from src.utils.adaptive_matcher import AdaptiveMatcher
from src.utils.window_utils import set_dpi_aware, capture_window
from src.utils.resource_path import get_pic_path


set_dpi_aware()


class SnowfieldWeaponLeague:
    """雪域兵器联赛功能模块"""
    
    def __init__(self, hwnd: int, window_name: str = "", matcher: Optional[AdaptiveMatcher] = None):
        self.hwnd = hwnd
        self.window_name = window_name or f"Snowfield_{hwnd}"
        self.logger = self._setup_logger()
        
        if matcher is None:
            self.matcher = AdaptiveMatcher(confidence=0.85, logger=self.logger)
        else:
            self.matcher = matcher
        
        self.image_paths = {
            "snowfield": get_pic_path("snowfield.png"),
            "back": get_pic_path("back.png"),
            "back1": get_pic_path("back1.png"),
            "back2": get_pic_path("back2.png"),
            "close": get_pic_path("close.png"),
        }
        
        self.last_window_size = None
        self.frame_data = self._load_frame_data()
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger(f"SnowfieldWeaponLeague_{self.hwnd}")
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.propagate = False
        return logger
    
    def _load_frame_data(self) -> Dict[str, Any]:
        """加载frame_data.json中的画框数据"""
        try:
            json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frame_data.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"加载frame_data.json失败: {e}")
        return {}
    
    def _get_window_size(self) -> Optional[tuple]:
        """获取窗口尺寸"""
        try:
            import win32gui
            rect = win32gui.GetWindowRect(self.hwnd)
            if rect:
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                return (width, height)
        except Exception as e:
            self.logger.warning(f"获取窗口尺寸失败: {e}")
        return None
    
    def _get_window_position(self) -> Optional[tuple]:
        """获取窗口屏幕位置"""
        try:
            import win32gui
            rect = win32gui.GetWindowRect(self.hwnd)
            if rect:
                return (rect[0], rect[1])
        except Exception as e:
            self.logger.warning(f"获取窗口位置失败: {e}")
        return None
    
    def _screenshot(self) -> Optional[Any]:
        """截取窗口截图"""
        try:
            result = capture_window(self.hwnd)
            if result is not None and result[0] is not None:
                return result[0]
        except Exception as e:
            self.logger.warning(f"截取截图失败: {e}")
        return None
    
    def _find(self, name: str, confidence: Optional[float] = None) -> Optional[Tuple[float, float]]:
        """查找图像"""
        try:
            screenshot = self._screenshot()
            if screenshot is None:
                return None
            
            win_w, win_h = self._get_window_size()
            if win_w is None or win_h is None:
                return None
            
            if self.last_window_size != (win_w, win_h):
                self.matcher.clear_cache()
                self.last_window_size = (win_w, win_h)
            
            path = self.image_paths.get(name)
            if path is None:
                self.logger.error(f"未找到图像路径: {name}")
                return None
            
            result = self.matcher.match(screenshot, path, win_w, win_h)
            if result is not None:
                x, y = result.get("location", (0, 0))
                return (float(x), float(y))
            return None
        except Exception as e:
            self.logger.warning(f"查找图像失败: {e}")
            return None
    
    def _click(self, name: str, confidence: Optional[float] = None) -> bool:
        """查找并点击图像"""
        try:
            result = self._find(name, confidence)
            if result is not None:
                x, y = result
                window_pos = self._get_window_position()
                if window_pos is not None:
                    screen_x = window_pos[0] + int(x)
                    screen_y = window_pos[1] + int(y)
                    self.logger.info(f"点击 {name}: 窗口内({x}, {y}), 屏幕({screen_x}, {screen_y})")
                    import pyautogui
                    pyautogui.click(screen_x, screen_y)
                else:
                    self.logger.warning(f"无法获取窗口位置,点击失败")
                    return False
                return True
            return False
        except Exception as e:
            self.logger.warning(f"点击图像失败: {e}")
            return False
    
    def _click_back_sequence(self) -> bool:
        """点击back/back1/back2/close的序列流程"""
        self.logger.info("开始点击back序列流程...")
        
        if self._click("back"):
            self.logger.info("✓ 成功点击back")
            time.sleep(random.uniform(1, 2))
            if self._click("back1"):
                self.logger.info("✓ 成功点击back1")
                time.sleep(random.uniform(1, 2))
                return True
            return False
        
        if self._click("back1"):
            self.logger.info("✓ 成功点击back1")
            time.sleep(random.uniform(1, 2))
            return True
        
        if self._click("back2"):
            self.logger.info("✓ 成功点击back2")
            time.sleep(random.uniform(1, 2))
            return True
        
        if self._click("close"):
            self.logger.info("✓ 成功点击close")
            time.sleep(random.uniform(1, 2))
            return True
        
        self.logger.warning("back/back1/back2/close均未匹配成功")
        return False
    
    def _click_snowfield_with_back_sequence(self) -> bool:
        """点击snowfield,如果不存在则按顺序匹配back/back1/back2/close"""
        self.logger.info("开始点击snowfield...")
        
        for attempt in range(10):
            snowfield_result = self._find("snowfield")
            
            if snowfield_result is not None:
                self.logger.info("✓ 检测到snowfield,不点击,先检测入口区域红点...")
                
                if not self._check_red_dot_in_entry_region():
                    self.logger.warning("入口区域红点检测失败")
                    return False
                
                self.logger.info("✓ 入口区域红点检测通过,点击snowfield...")
                if self._click("snowfield"):
                    self.logger.info("✓ 成功点击snowfield")
                    time.sleep(random.uniform(1, 2))
                    return True
            else:
                self.logger.info("未找到snowfield,尝试点击back/back1/back2/close...")
                
                if self._click_back_sequence():
                    self.logger.info("等待1-2秒后继续搜索snowfield...")
                    time.sleep(random.uniform(1, 2))
                    continue
                else:
                    self.logger.warning("未找到back/back1/back2/close,继续等待...")
                    time.sleep(random.uniform(1, 2))
        
        self.logger.warning("尝试次数过多,点击snowfield失败")
        return False
    
    def _click_red_dot_in_daily_task_region(self) -> bool:
        """在每日任务区域检测并点击红点"""
        self.logger.info("开始检测每日任务区域的红点...")
        
        daily_task_info = self.frame_data.get("雪域兵器联赛", {}).get("每日任务")
        if not daily_task_info:
            self.logger.warning("未找到每日任务的画框数据")
            return False
        
        try:
            screenshot = self._screenshot()
            if screenshot is None:
                return False
            
            win_w, win_h = self._get_window_size()
            if win_w is None or win_h is None:
                return False
            
            if self.last_window_size != (win_w, win_h):
                self.matcher.clear_cache()
                self.last_window_size = (win_w, win_h)
            
            region = daily_task_info.get("region", [0, 0, 0, 0])
            
            x1, y1, width, height = region
            
            abs_x = int(x1)
            abs_y = int(y1)
            abs_width = int(width)
            abs_height = int(height)
            
            if abs_x >= 0 and abs_y >= 0 and abs_x + abs_width <= screenshot.shape[1] and abs_y + abs_height <= screenshot.shape[0]:
                region_screenshot = screenshot[abs_y:abs_y + abs_height, abs_x:abs_x + abs_width]
            else:
                self.logger.warning("指定区域超出截图范围")
                return False
            
            center_x = int(x1 + width / 2)
            center_y = int(y1 + height / 2)
            
            red_dot_found = self._detect_red_dot_in_region(region_screenshot)
            
            if red_dot_found:
                click_x = abs_x + int(width / 2)
                click_y = abs_y + int(height / 2)
                window_pos = self._get_window_position()
                if window_pos is not None:
                    screen_x = window_pos[0] + click_x
                    screen_y = window_pos[1] + click_y
                    self.logger.info(f"✓ 检测到红点,点击区域中心: 窗口内({click_x}, {click_y}), 屏幕({screen_x}, {screen_y})")
                    import pyautogui
                    pyautogui.click(screen_x, screen_y)
                return True
            else:
                self.logger.info("未检测到红点,点击区域中心")
                window_pos = self._get_window_position()
                if window_pos is not None:
                    screen_x = window_pos[0] + center_x
                    screen_y = window_pos[1] + center_y
                    self.logger.info(f"点击区域中心: 窗口内({center_x}, {center_y}), 屏幕({screen_x}, {screen_y})")
                    import pyautogui
                    pyautogui.click(screen_x, screen_y)
                return True
        except Exception as e:
            self.logger.warning(f"检测每日任务红点失败: {e}")
            import traceback
            self.logger.warning(f"详细错误: {traceback.format_exc()}")
            return False
    
    def _check_red_dot_in_entry_region(self) -> bool:
        """检查入口区域是否有红点"""
        self.logger.info("开始检测入口区域的红点...")
        
        entry_info = self.frame_data.get("雪域兵器联赛", {}).get("入口")
        if not entry_info:
            self.logger.warning("未找到入口区域的画框数据")
            return False
        
        try:
            screenshot = self._screenshot()
            if screenshot is None:
                return False
            
            win_w, win_h = self._get_window_size()
            if win_w is None or win_h is None:
                return False
            
            if self.last_window_size != (win_w, win_h):
                self.matcher.clear_cache()
                self.last_window_size = (win_w, win_h)
            
            region = entry_info.get("region", [0, 0, 0, 0])
            
            x1, y1, width, height = region
            
            abs_x = int(x1)
            abs_y = int(y1)
            abs_width = int(width)
            abs_height = int(height)
            
            if abs_x >= 0 and abs_y >= 0 and abs_x + abs_width <= screenshot.shape[1] and abs_y + abs_height <= screenshot.shape[0]:
                region_screenshot = screenshot[abs_y:abs_y + abs_height, abs_x:abs_x + abs_width]
            else:
                self.logger.warning("入口区域超出截图范围")
                return False
            
            red_dot_positions = self._find_all_red_dots(region_screenshot, abs_x, abs_y)
            
            if len(red_dot_positions) == 1:
                self.logger.info(f"✓ 检测到1个红点,继续执行后续逻辑")
                return True
            elif len(red_dot_positions) == 0:
                self.logger.warning(f"未检测到红点(检测到0个),结束雪域兵器联赛完整流程")
                return False
            else:
                self.logger.warning(f"检测到{len(red_dot_positions)}个红点(期望1个),结束流程")
                return False
        except Exception as e:
            self.logger.warning(f"检测入口区域红点失败: {e}")
            import traceback
            self.logger.warning(f"详细错误: {traceback.format_exc()}")
            return False
    
    def _click_red_dot_in_reward_region(self) -> bool:
        """在领奖区域检测并点击红点"""
        self.logger.info("开始检测领奖区域的红点...")
        
        reward_info = self.frame_data.get("雪域兵器联赛", {}).get("领奖")
        if not reward_info:
            self.logger.warning("未找到领奖区域的画框数据")
            return False
        
        try:
            screenshot = self._screenshot()
            if screenshot is None:
                return False
            
            win_w, win_h = self._get_window_size()
            if win_w is None or win_h is None:
                return False
            
            if self.last_window_size != (win_w, win_h):
                self.matcher.clear_cache()
                self.last_window_size = (win_w, win_h)
            
            region = reward_info.get("region", [0, 0, 0, 0])
            
            x1, y1, width, height = region
            
            abs_x = int(x1)
            abs_y = int(y1)
            abs_width = int(width)
            abs_height = int(height)
            
            if abs_x >= 0 and abs_y >= 0 and abs_x + abs_width <= screenshot.shape[1] and abs_y + abs_height <= screenshot.shape[0]:
                region_screenshot = screenshot[abs_y:abs_y + abs_height, abs_x:abs_x + abs_width]
            else:
                self.logger.warning("领奖区域超出截图范围")
                return False
            
            red_dot_positions = self._find_all_red_dots(region_screenshot, abs_x, abs_y)
            
            if not red_dot_positions:
                self.logger.info("领奖区域未检测到红点")
                return False
            
            self.logger.info(f"✓ 检测到 {len(red_dot_positions)} 个红点")
            
            window_pos = self._get_window_position()
            for i, (click_x, click_y) in enumerate(red_dot_positions):
                if window_pos is not None:
                    screen_x = window_pos[0] + click_x
                    screen_y = window_pos[1] + click_y
                    self.logger.info(f"点击第 {i+1} 个红点: 窗口内({click_x}, {click_y}), 屏幕({screen_x}, {screen_y})")
                    import pyautogui
                    pyautogui.click(screen_x, screen_y)
                else:
                    self.logger.warning(f"无法获取窗口位置,点击第 {i+1} 个红点失败")
                if i < len(red_dot_positions) - 1:
                    time.sleep(0.5)
            
            self.logger.info("等待1-2秒...")
            time.sleep(random.uniform(1, 2))
            
            new_screenshot = self._screenshot()
            if new_screenshot is not None:
                new_red_dot_positions = self._find_all_red_dots(new_screenshot, abs_x, abs_y)
                if len(new_red_dot_positions) == 0:
                    self.logger.info("领奖区域红点已全部点击,执行滑动操作...")
                    self._swipe_up_from_center()
            
            return True
        except Exception as e:
            self.logger.warning(f"检测领奖区域红点失败: {e}")
            import traceback
            self.logger.warning(f"详细错误: {traceback.format_exc()}")
            return False
    
    def _swipe_up_from_center(self):
        """从窗口中心向上滑动100像素"""
        try:
            import pyautogui
            window_pos = self._get_window_position()
            window_size = self._get_window_size()
            
            if window_pos is None or window_size is None:
                self.logger.warning("无法获取窗口位置或尺寸,滑动失败")
                return
            
            center_x = window_pos[0] + window_size[0] // 2
            center_y = window_pos[1] + window_size[1] // 2
            
            start_x = center_x
            start_y = center_y
            end_x = center_x
            end_y = center_y - 100
            
            self.logger.info(f"从窗口中心滑动: 起点({start_x}, {start_y}), 终点({end_x}, {end_y})")
            
            pyautogui.moveTo(start_x, start_y)
            pyautogui.dragTo(end_x, end_y, duration=0.5, button='left')
            
            self.logger.info("✓ 滑动完成")
        except Exception as e:
            self.logger.warning(f"滑动操作失败: {e}")
            import traceback
            self.logger.warning(f"详细错误: {traceback.format_exc()}")
    
    def _find_all_red_dots(self, region_screenshot: np.ndarray, offset_x: int, offset_y: int) -> list:
        """在指定区域内查找所有红点
        
        Args:
            region_screenshot: 区域截图
            offset_x: 区域在截图中的x偏移
            offset_y: 区域在截图中的y偏移
            
        Returns:
            红点位置列表 [(x1, y1), (x2, y2), ...]
        """
        try:
            if region_screenshot is None or len(region_screenshot.shape) < 3:
                return []
            
            hsv = cv2.cvtColor(region_screenshot, cv2.COLOR_BGR2HSV)
            
            lower_red1 = np.array([0, 150, 150])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([160, 150, 150])
            upper_red2 = np.array([180, 255, 255])
            
            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            red_mask = cv2.bitwise_or(mask1, mask2)
            
            kernel = np.ones((3, 3), np.uint8)
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)
            
            contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            red_dot_positions = []
            min_contour_area = 50
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area >= min_contour_area:
                    perimeter = cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    
                    if circularity > 0.5:
                        M = cv2.moments(contour)
                        if M["m00"] != 0:
                            cx = int(M["m10"] / M["m00"])
                            cy = int(M["m01"] / M["m00"])
                            abs_x = offset_x + cx
                            abs_y = offset_y + cy
                            red_dot_positions.append((abs_x, abs_y))
            
            return red_dot_positions
        except Exception as e:
            self.logger.warning(f"查找红点失败: {e}")
            return []
    
    def run_full_cycle_async(self, callback=None):
        """异步运行完整流程(在后台线程中执行)
        
        Args:
            callback: 可选的回调函数,接收一个布尔参数表示成功与否
        """
        def run():
            try:
                success = self._run_full_cycle_internal()
                if callback:
                    callback(success)
            except Exception as e:
                self.logger.error(f"异步执行失败: {e}")
                import traceback
                self.logger.error(f"详细错误: {traceback.format_exc()}")
                if callback:
                    callback(False)
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread
    
    def _detect_red_dot_in_region(self, region_screenshot: np.ndarray) -> bool:
        """在指定区域内检测红点
        
        Args:
            region_screenshot: 区域截图
            
        Returns:
            是否检测到红点
        """
        try:
            import numpy as np
            if region_screenshot is None or len(region_screenshot.shape) < 3:
                return False
            
            hsv = cv2.cvtColor(region_screenshot, cv2.COLOR_BGR2HSV)
            
            lower_red1 = np.array([0, 100, 100])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([160, 100, 100])
            upper_red2 = np.array([180, 255, 255])
            
            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            red_mask = cv2.bitwise_or(mask1, mask2)
            
            kernel = np.ones((3, 3), np.uint8)
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)
            
            red_pixels = np.sum(red_mask > 0)
            total_pixels = red_mask.size
            red_ratio = red_pixels / total_pixels
            
            if red_ratio > 0.01:
                return True
            return False
        except Exception as e:
            self.logger.warning(f"检测红点失败: {e}")
            return False
    
    def _run_full_cycle_internal(self) -> bool:
        """内部运行完整流程(不阻塞)"""
        self.logger.info("开始雪域兵器联赛完整流程...")
        
        if not self._click_snowfield_with_back_sequence():
            self.logger.warning("snowfield点击失败")
        
        time.sleep(0.5)
        
        self._click_red_dot_in_reward_region()
        
        self.logger.info("雪域兵器联赛完整流程完成")
        return True
    
    def run_full_cycle(self) -> bool:
        """运行完整流程(同步版本,不推荐用于GUI)"""
        return self._run_full_cycle_internal()
