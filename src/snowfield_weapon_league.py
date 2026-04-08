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
            
            red_dot_path = get_pic_path("red_dot.png")
            if not os.path.exists(red_dot_path):
                self.logger.warning(f"红点图片不存在: {red_dot_path}")
                center_x = int(x1 + width / 2)
                center_y = int(y1 + height / 2)
                window_pos = self._get_window_position()
                if window_pos is not None:
                    screen_x = window_pos[0] + center_x
                    screen_y = window_pos[1] + center_y
                    self.logger.info(f"未找到红点图片,点击区域中心: 窗口内({center_x}, {center_y}), 屏幕({screen_x}, {screen_y})")
                    import pyautogui
                    pyautogui.click(screen_x, screen_y)
                return True
            
            region_win_w = abs_width
            region_win_h = abs_height
            result = self.matcher.match(region_screenshot, red_dot_path, region_win_w, region_win_h)
            
            if result is not None:
                dx, dy = result.get("location", (0, 0))
                click_x = abs_x + int(dx)
                click_y = abs_y + int(dy)
                window_pos = self._get_window_position()
                if window_pos is not None:
                    screen_x = window_pos[0] + click_x
                    screen_y = window_pos[1] + click_y
                    self.logger.info(f"✓ 检测到红点,点击位置: 窗口内({click_x}, {click_y}), 屏幕({screen_x}, {screen_y})")
                    import pyautogui
                    pyautogui.click(screen_x, screen_y)
                return True
            else:
                self.logger.info("未检测到红点,结束流程")
                return False
        except Exception as e:
            self.logger.warning(f"检测红点失败: {e}")
            import traceback
            self.logger.warning(f"详细错误: {traceback.format_exc()}")
            return False
    
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
    
    def _run_full_cycle_internal(self) -> bool:
        """内部运行完整流程(不阻塞)"""
        self.logger.info("开始雪域兵器联赛完整流程...")
        
        if not self._click_snowfield_with_back_sequence():
            self.logger.warning("snowfield点击失败")
        
        if not self._click_red_dot_in_daily_task_region():
            self.logger.warning("红点检测失败")
        
        self.logger.info("雪域兵器联赛完整流程完成")
        return True
    
    def run_full_cycle(self) -> bool:
        """运行完整流程(同步版本,不推荐用于GUI)"""
        return self._run_full_cycle_internal()
