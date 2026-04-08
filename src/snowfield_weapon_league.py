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
            "close": get_pic_path("close.png"),
            "daily_task": get_pic_path("雪域兵器联赛/每日任务.png"),
            "weekly_task": get_pic_path("雪域兵器联赛/每周任务.png"),
            "claim_reward": get_pic_path("雪域兵器联赛/领奖.png"),
        }
        
        self.last_window_size = None
        self.frame_data = self._load_frame_data()
        
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
    
    def _screenshot(self) -> Optional[Any]:
        """截取窗口截图"""
        try:
            screenshot = capture_window(self.hwnd)
            if screenshot is not None:
                return screenshot
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
            
            result = self.matcher.find(path, screenshot, confidence=confidence)
            return result
        except Exception as e:
            self.logger.warning(f"查找图像失败: {e}")
            return None
    
    def _click(self, name: str, confidence: Optional[float] = None) -> bool:
        """查找并点击图像"""
        try:
            result = self._find(name, confidence)
            if result is not None:
                x, y = result
                self.logger.info(f"点击 {name}: ({x}, {y})")
                return True
            return False
        except Exception as e:
            self.logger.warning(f"点击图像失败: {e}")
            return False
    
    def _click_any_of(self, names: list, confidence: Optional[float] = None) -> Optional[str]:
        """查找并点击多个图像中的任意一个"""
        for name in names:
            if self._click(name, confidence):
                return name
        return None
    
    def _find_any_of(self, names: list, confidence: Optional[float] = None) -> Optional[str]:
        """查找多个图像中的任意一个"""
        for name in names:
            if self._find(name, confidence):
                return name
        return None
    
    def _click_snowfield_with_retry(self) -> bool:
        """点击snowfield,如果不存在则点击back/back1/close"""
        self.logger.info("开始点击snowfield...")
        
        for attempt in range(10):
            snowfield_result = self._find("snowfield")
            
            if snowfield_result is not None:
                if self._click("snowfield"):
                    self.logger.info("✓ 成功点击snowfield")
                    time.sleep(random.uniform(1, 2))
                    return True
            else:
                self.logger.info("未找到snowfield,尝试点击back/back1/close...")
                
                clicked = self._click_any_of(["back", "back1", "close"])
                if clicked:
                    self.logger.info(f"✓ 成功点击{clicked}")
                    time.sleep(random.uniform(1, 2))
                    continue
                else:
                    self.logger.warning(f"未找到back/back1/close,继续等待...")
                    time.sleep(random.uniform(1, 2))
        
        self.logger.warning("尝试次数过多,点击snowfield失败")
        return False
    
    def _click_back1_after_back(self) -> bool:
        """点击back后,搜索back1并点击"""
        self.logger.info("开始点击back后流程...")
        
        if self._click("back"):
            self.logger.info("✓ 成功点击back")
            time.sleep(random.uniform(1, 2))
            
            if self._click("back1"):
                self.logger.info("✓ 成功点击back1")
                time.sleep(random.uniform(1, 2))
                return True
        
        self.logger.warning("back/back1点击失败")
        return False
    
    def _click_daily_task(self) -> bool:
        """点击每日任务按钮"""
        self.logger.info("开始点击每日任务...")
        
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
            relative = daily_task_info.get("relative", {})
            
            x1, y1, width, height = region
            rel_x = relative.get("x", x1 / win_w) if win_w > 0 else 0
            rel_y = relative.get("y", y1 / win_h) if win_h > 0 else 0
            rel_w = relative.get("width", width / win_w) if win_w > 0 else 0
            rel_h = relative.get("height", height / win_h) if win_h > 0 else 0
            
            center_x = int(x1 + width / 2)
            center_y = int(y1 + height / 2)
            
            self.logger.info(f"点击每日任务区域: ({center_x}, {center_y})")
            
            return True
        except Exception as e:
            self.logger.warning(f"点击每日任务失败: {e}")
            return False
    
    def start_daily_task(self) -> bool:
        """开始每日任务"""
        self.logger.info("开始雪域兵器联赛每日任务...")
        
        if not self._find("daily_task"):
            self.logger.warning("未找到每日任务按钮")
            return False
        
        if self._click("daily_task"):
            self.logger.info("点击每日任务成功")
            time.sleep(random.uniform(1, 2))
            return True
        
        return False
    
    def start_weekly_task(self) -> bool:
        """开始每周任务"""
        self.logger.info("开始雪域兵器联赛每周任务...")
        
        if not self._find("weekly_task"):
            self.logger.warning("未找到每周任务按钮")
            return False
        
        if self._click("weekly_task"):
            self.logger.info("点击每周任务成功")
            time.sleep(random.uniform(1, 2))
            return True
        
        return False
    
    def claim_reward(self) -> bool:
        """领取奖励"""
        self.logger.info("开始领取雪域兵器联赛奖励...")
        
        if not self._find("claim_reward"):
            self.logger.warning("未找到领奖按钮")
            return False
        
        if self._click("claim_reward"):
            self.logger.info("点击领奖成功")
            time.sleep(random.uniform(1, 2))
            return True
        
        return False
    
    def run_full_cycle(self) -> bool:
        """运行完整流程"""
        self.logger.info("开始雪域兵器联赛完整流程...")
        
        # 领取奖励
        if not self.claim_reward():
            self.logger.warning("领取奖励失败")
        
        # 点击snowfield,如果不存在则点击back/back1/close
        if not self._click_snowfield_with_retry():
            self.logger.warning("snowfield点击失败")
        
        # 点击back后,搜索back1并点击
        if not self._click_back1_after_back():
            self.logger.warning("back/back1点击失败")
        
        # 点击每日任务
        if not self.start_daily_task():
            self.logger.warning("每日任务失败")
        
        # 开始每周任务
        if not self.start_weekly_task():
            self.logger.warning("每周任务失败")
        
        self.logger.info("雪域兵器联赛完整流程完成")
        return True
