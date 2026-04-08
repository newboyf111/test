#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪域兵器联赛 (Snowfield Weapon League) 功能模块
"""

import time
import random
import logging
from typing import Optional, Dict, Any

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
            "daily_task": get_pic_path("雪域兵器联赛/每日任务.png"),
            "weekly_task": get_pic_path("雪域兵器联赛/每周任务.png"),
            "claim_reward": get_pic_path("雪域兵器联赛/领奖.png"),
        }
        
        self.last_window_size = None
        
    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger(f"SnowfieldWeaponLeague_{self.hwnd}")
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
        return logger
    
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
    
    def _find(self, name: str, confidence: Optional[float] = None) -> bool:
        """查找图像"""
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
            
            path = self.image_paths.get(name)
            if path is None:
                self.logger.error(f"未找到图像路径: {name}")
                return False
            
            result = self.matcher.find(path, screenshot, confidence=confidence)
            return result is not None
        except Exception as e:
            self.logger.warning(f"查找图像失败: {e}")
            return False
    
    def _click(self, name: str, confidence: Optional[float] = None) -> bool:
        """查找并点击图像"""
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
            
            path = self.image_paths.get(name)
            if path is None:
                self.logger.error(f"未找到图像路径: {name}")
                return False
            
            result = self.matcher.find(path, screenshot, confidence=confidence)
            if result is not None:
                x, y = result
                self.logger.info(f"点击 {name}: ({x}, {y})")
                return True
            return False
        except Exception as e:
            self.logger.warning(f"点击图像失败: {e}")
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
        
        # 开始每日任务
        if not self.start_daily_task():
            self.logger.warning("每日任务失败")
        
        # 开始每周任务
        if not self.start_weekly_task():
            self.logger.warning("每周任务失败")
        
        self.logger.info("雪域兵器联赛完整流程完成")
        return True
