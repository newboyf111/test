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
import numpy as np
import pyautogui
import win32gui
import traceback
from typing import Optional, Dict, Any, Tuple

from src.utils.adaptive_matcher import AdaptiveMatcher
from src.utils.window_utils import set_dpi_aware, capture_window
from src.utils.red_dot_detector import detect_red_dot_presence, get_red_dot_positions_with_offset


set_dpi_aware()


class SnowfieldWeaponLeague:
    """雪域兵器联赛功能模块，实现游戏中该功能的自动化操作"""
    
    def __init__(self, hwnd: int, window_name: str = "", matcher: Optional[AdaptiveMatcher] = None):
        """初始化模块
        
        Args:
            hwnd: 游戏窗口句柄
            window_name: 窗口名称（可选）
            matcher: 自适应匹配器实例（可选）
        """
        self.hwnd = hwnd
        self.window_name = window_name or f"Snowfield_{hwnd}"
        self.logger = self._setup_logger()
        
        # 初始化匹配器
        if matcher is None:
            self.matcher = AdaptiveMatcher(confidence=0.85, logger=self.logger)
        else:
            self.matcher = matcher
        
        # 图像路径配置
        self.image_paths = {
            "snowfield": "snowfield.png",  # 雪域兵器联赛入口
            "back": "back.png",          # 返回按钮1
            "back1": "back1.png",        # 返回按钮2
            "back2": "back2.png",        # 返回按钮3
            "close": "close.png",        # 关闭按钮
        }
        
        self.last_window_size = None  # 窗口大小缓存
        self.frame_data = self._load_frame_data()  # 加载画框数据
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger(f"SnowfieldWeaponLeague_{self.hwnd}")
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.propagate = False  # 防止日志重复传播
        return logger
    
    def _load_frame_data(self) -> Dict[str, Any]:
        """加载画框数据"""
        try:
            json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frame_data.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning(f"加载frame_data.json失败: {e}")
        return {}
    
    def _get_window_size(self) -> Optional[tuple]:
        """获取窗口尺寸"""
        try:
            rect = win32gui.GetWindowRect(self.hwnd)
            if rect:
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                return (width, height)
        except (win32gui.error, TypeError) as e:
            self.logger.warning(f"获取窗口尺寸失败: {e}")
        return None
    
    def _get_window_position(self) -> Optional[tuple]:
        """获取窗口屏幕位置"""
        try:
            rect = win32gui.GetWindowRect(self.hwnd)
            if rect:
                return (rect[0], rect[1])
        except (win32gui.error, TypeError) as e:
            self.logger.warning(f"获取窗口位置失败: {e}")
        return None
    
    def _screenshot(self) -> Optional[Any]:
        """截取窗口截图"""
        try:
            result = capture_window(self.hwnd)
            if result is not None and result[0] is not None:
                return result[0]
        except (OSError, ValueError) as e:
            self.logger.warning(f"截取截图失败: {e}")
        return None
    
    def _find(self, name: str, confidence: Optional[float] = None) -> Optional[Tuple[float, float]]:
        """查找图像
        
        Args:
            name: 图像名称
            confidence: 匹配置信度（可选）
        """
        try:
            screenshot = self._screenshot()
            if screenshot is None:
                return None
            
            window_size = self._get_window_size()
            if window_size is None:
                return None
            win_w, win_h = window_size
            
            # 如果窗口大小改变，清除匹配器缓存
            if self.last_window_size != (win_w, win_h):
                self.matcher.clear_cache()
                self.last_window_size = (win_w, win_h)
            
            # 获取图像路径
            path = self.image_paths.get(name)
            if path is None:
                self.logger.error(f"未找到图像路径: {name}")
                return None
            
            # 使用自适应匹配器查找图像
            result = self.matcher.match(screenshot, path, win_w, win_h)
            if result is not None:
                x, y = result.get("location", (0, 0))
                return (float(x), float(y))
            return None
        except (OSError, ValueError) as e:
            self.logger.warning(f"查找图像失败: {e}")
            return None
    
    def _click(self, name: str, confidence: Optional[float] = None) -> bool:
        """查找并点击图像
        
        Args:
            name: 图像名称
            confidence: 匹配置信度（可选）
        """
        try:
            # 查找图像
            result = self._find(name, confidence)
            if result is not None:
                x, y = result
                # 获取窗口位置
                window_pos = self._get_window_position()
                if window_pos is not None:
                    # 计算屏幕坐标
                    screen_x = window_pos[0] + int(x)
                    screen_y = window_pos[1] + int(y)
                    self.logger.info(f"点击 {name}: 窗口内({x}, {y}), 屏幕({screen_x}, {screen_y})")
                    # 执行点击
                    pyautogui.click(screen_x, screen_y)
                else:
                    self.logger.warning(f"无法获取窗口位置,点击失败")
                    return False
                return True
            return False
        except (OSError, RuntimeError) as e:
            self.logger.warning(f"点击图像失败: {e}")
            return False
    
    def _click_back_sequence(self) -> bool:
        """点击返回按钮序列"""
        self.logger.info("开始点击back序列流程...")
        
        # 尝试点击 back
        if self._click("back"):
            self.logger.info("✓ 成功点击back")
            time.sleep(random.uniform(1, 2))
            # 点击 back 后尝试点击 back1
            if self._click("back1"):
                self.logger.info("✓ 成功点击back1")
                time.sleep(random.uniform(1, 2))
                return True
            return False
        
        # 尝试点击 back1
        if self._click("back1"):
            self.logger.info("✓ 成功点击back1")
            time.sleep(random.uniform(1, 2))
            return True
        
        # 尝试点击 back2
        if self._click("back2"):
            self.logger.info("✓ 成功点击back2")
            time.sleep(random.uniform(1, 2))
            return True
        
        # 尝试点击 close
        if self._click("close"):
            self.logger.info("✓ 成功点击close")
            time.sleep(random.uniform(1, 2))
            return True
        
        self.logger.warning("back/back1/back2/close均未匹配成功")
        return False
    
    def _click_snowfield_with_back_sequence(self) -> bool:
        """点击雪域兵器联赛入口"""
        self.logger.info("开始点击snowfield...")
        
        # 最多尝试10次
        for attempt in range(10):
            # 查找 snowfield 图像
            snowfield_result = self._find("snowfield")
            
            if snowfield_result is not None:
                self.logger.info("✓ 检测到snowfield,不点击,先检测入口区域红点...")
                
                # 检查入口区域红点
                if not self._check_red_dot_in_entry_region():
                    self.logger.warning("入口区域红点检测失败")
                    return False
                
                self.logger.info("✓ 入口区域红点检测通过,点击snowfield...")
                # 点击 snowfield
                if self._click("snowfield"):
                    self.logger.info("✓ 成功点击snowfield")
                    time.sleep(random.uniform(1, 2))
                    return True
            else:
                self.logger.info("未找到snowfield,尝试点击back/back1/back2/close...")
                
                # 尝试点击返回按钮
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
            
            window_size = self._get_window_size()
            if window_size is None:
                return False
            win_w, win_h = window_size
            
            if self.last_window_size != (win_w, win_h):
                self.matcher.clear_cache()
                self.last_window_size = (win_w, win_h)
            
            # 优先使用相对坐标计算区域
            relative = daily_task_info.get("relative")
            if relative:
                rel_x = relative.get("x", 0)
                rel_y = relative.get("y", 0)
                rel_width = relative.get("width", 0)
                rel_height = relative.get("height", 0)
                
                abs_x = int(rel_x * win_w)
                abs_y = int(rel_y * win_h)
                abs_width = int(rel_width * win_w)
                abs_height = int(rel_height * win_h)
            else:
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
            
            center_x = abs_x + int(abs_width / 2)
            center_y = abs_y + int(abs_height / 2)
            
            red_dot_found = self._detect_red_dot_in_region(region_screenshot)
            
            if red_dot_found:
                click_x = abs_x + int(abs_width / 2)
                click_y = abs_y + int(abs_height / 2)
                window_pos = self._get_window_position()
                if window_pos is not None:
                    screen_x = window_pos[0] + click_x
                    screen_y = window_pos[1] + click_y
                    self.logger.info(f"✓ 检测到红点,点击区域中心: 窗口内({click_x}, {click_y}), 屏幕({screen_x}, {screen_y})")
                    pyautogui.click(screen_x, screen_y)
                return True
            else:
                self.logger.info("未检测到红点,点击区域中心")
                window_pos = self._get_window_position()
                if window_pos is not None:
                    screen_x = window_pos[0] + center_x
                    screen_y = window_pos[1] + center_y
                    self.logger.info(f"点击区域中心: 窗口内({center_x}, {center_y}), 屏幕({screen_x}, {screen_y})")
                    pyautogui.click(screen_x, screen_y)
                return True
        except (OSError, ValueError) as e:
            self.logger.warning(f"检测每日任务红点失败: {e}")
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
            
            window_size = self._get_window_size()
            if window_size is None:
                return False
            win_w, win_h = window_size
            
            if self.last_window_size != (win_w, win_h):
                self.matcher.clear_cache()
                self.last_window_size = (win_w, win_h)
            
            # 优先使用相对坐标计算区域
            relative = entry_info.get("relative")
            if relative:
                rel_x = relative.get("x", 0)
                rel_y = relative.get("y", 0)
                rel_width = relative.get("width", 0)
                rel_height = relative.get("height", 0)
                
                abs_x = int(rel_x * win_w)
                abs_y = int(rel_y * win_h)
                abs_width = int(rel_width * win_w)
                abs_height = int(rel_height * win_h)
            else:
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
                self.logger.warning(f"未检测到红点(检测到0个),继续执行后续逻辑(不终止流程)")
                return True
            else:
                self.logger.warning(f"检测到{len(red_dot_positions)}个红点(期望1个),继续执行后续逻辑")
                return True
        except (OSError, ValueError) as e:
            self.logger.warning(f"检测入口区域红点失败: {e}")
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
            
            window_size = self._get_window_size()
            if window_size is None:
                return False
            win_w, win_h = window_size
            
            if self.last_window_size != (win_w, win_h):
                self.matcher.clear_cache()
                self.last_window_size = (win_w, win_h)
            
            # 优先使用相对坐标计算区域
            relative = reward_info.get("relative")
            if relative:
                rel_x = relative.get("x", 0)
                rel_y = relative.get("y", 0)
                rel_width = relative.get("width", 0)
                rel_height = relative.get("height", 0)
                
                abs_x = int(rel_x * win_w)
                abs_y = int(rel_y * win_h)
                abs_width = int(rel_width * win_w)
                abs_height = int(rel_height * win_h)
            else:
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
        except (OSError, ValueError) as e:
            self.logger.warning(f"检测领奖区域红点失败: {e}")
            self.logger.warning(f"详细错误: {traceback.format_exc()}")
            return False
    
    def _swipe_up_from_center(self):
        """从窗口中心向上滑动"""
        try:
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
        except (OSError, ValueError) as e:
            self.logger.warning(f"滑动操作失败: {e}")
            self.logger.warning(f"详细错误: {traceback.format_exc()}")
    
    def _find_all_red_dots(self, region_screenshot: np.ndarray, offset_x: int, offset_y: int) -> list:
        """在指定区域内查找所有红点
        
        Args:
            region_screenshot: 区域截图
            offset_x: 区域在截图中的x偏移
            offset_y: 区域在截图中的y偏移
        """
        try:
            if region_screenshot is None or len(region_screenshot.shape) < 3:
                return []
            
            # 使用红点检测模块获取带偏移的红点位置
            red_dot_positions = get_red_dot_positions_with_offset(region_screenshot, offset_x, offset_y)
            self.logger.debug(f"检测到 {len(red_dot_positions)} 个红点")
            return red_dot_positions
        except Exception as e:
            self.logger.warning(f"查找红点失败: {e}")
            return []
    
    def run_full_cycle_async(self, callback=None):
        """异步运行完整流程
        
        Args:
            callback: 可选的回调函数
        """
        def run():
            try:
                success = self._run_full_cycle_internal()
                if callback:
                    callback(success)
            except (RuntimeError, OSError) as e:
                self.logger.error(f"异步执行失败: {e}")
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
        """
        try:
            if region_screenshot is None or len(region_screenshot.shape) < 3:
                return False
            
            # 使用红点检测模块检测红点存在
            red_dot_found = detect_red_dot_presence(region_screenshot)
            self.logger.debug(f"红点存在检测结果: {red_dot_found}")
            return red_dot_found
        except Exception as e:
            self.logger.warning(f"检测红点失败: {e}")
            return False
    
    def _run_full_cycle_internal(self) -> bool:
        """内部运行完整流程(不阻塞)"""
        self.logger.info("开始雪域兵器联赛完整流程...")
        
        if not self._click_snowfield_with_back_sequence():
            self.logger.warning("snowfield点击失败")
            return False
        
        time.sleep(0.5)
        
        self._click_red_dot_in_reward_region()
        
        self.logger.info("雪域兵器联赛完整流程完成")
        return True
    
    def run_full_cycle(self) -> bool:
        """运行完整流程(同步版本)"""
        return self._run_full_cycle_internal()
