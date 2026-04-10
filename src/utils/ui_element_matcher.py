#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UIElementMatcher - 通用UI元素识别模块
用于识别和点击游戏界面中的各种按钮和元素
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from .adaptive_matcher import AdaptiveMatcher
from .window_utils import set_dpi_aware, capture_window, click_at


set_dpi_aware()


class UIElementMatcher:
    """通用UI元素匹配器"""
    
    def __init__(self, hwnd: int, logger=None):
        """
        初始化UI元素匹配器
        
        Args:
            hwnd: 窗口句柄
            logger: 日志记录器
        """
        self.hwnd = hwnd
        if logger is None:
            self.logger = logging.getLogger(f"ui_matcher_{hwnd}")
            self.logger.propagate = False
        else:
            self.logger = logger
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                f"[UI识别] %(asctime)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
        self.matcher = AdaptiveMatcher(confidence=0.75, logger=self.logger)
        self.config_path = Path(__file__).parent / "ui_elements.json"
        self._ui_config = None
        self._last_window_size = None
    
    def _load_config(self) -> Optional[Dict[str, Any]]:
        """加载UI元素配置文件"""
        try:
            if not self.config_path.exists():
                self.logger.error(f"配置文件不存在: {self.config_path}")
                return None
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._ui_config = json.load(f)
            
            self.logger.info(f"UI元素配置加载成功，界面数量: {len(self._ui_config)}")
            return self._ui_config
        except Exception as e:
            self.logger.error(f"加载UI元素配置失败: {e}")
            return None
    
    def _get_window_size(self) -> tuple:
        """获取窗口尺寸"""
        try:
            import win32gui
            rect = win32gui.GetWindowRect(self.hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            return (width, height)
        except Exception as e:
            self.logger.error(f"获取窗口尺寸失败: {e}")
            return (558, 1021)
    
    def match_button(self, button_name: str, interface_type: str = None) -> Optional[Dict[str, Any]]:
        """
        匹配指定名称的按钮
        
        Args:
            button_name: 按钮名称
            interface_type: 界面类型（可选）
            
        Returns:
            匹配结果字典，包含found、location、confidence等信息
        """
        if self._ui_config is None:
            if self._load_config() is None:
                return None
        
        search_list = []
        
        if interface_type:
            if interface_type in self._ui_config:
                if button_name in self._ui_config[interface_type]:
                    search_list.append((interface_type, button_name))
        
        for iface_name, buttons in self._ui_config.items():
            if button_name in buttons:
                if (interface_type is None) or (iface_name == interface_type):
                    search_list.append((iface_name, button_name))
        
        screenshot = capture_window(self.hwnd)
        if screenshot is None:
            self.logger.error("截图失败")
            return None
        
        window_width, window_height = self._get_window_size()
        
        for iface_name, btn_name in search_list:
            btn_config = self._ui_config[iface_name][btn_name]
            image_path = btn_config.get("image", f"{btn_name}.png")
            confidence = btn_config.get("confidence", 0.75)
            
            self.logger.debug(f"尝试匹配 [{iface_name}] {btn_name}: {image_path}")
            
            result = self.matcher.match(screenshot, image_path, window_width, window_height)
            
            if result and result.get("found"):
                result["interface_type"] = iface_name
                result["button_name"] = btn_name
                result["config"] = btn_config
                self.logger.info(f"匹配成功: [{iface_name}] {btn_name}")
                return result
        
        self.logger.debug(f"未找到按钮: {button_name}")
        return None
    
    def click_button(self, button_name: str, interface_type: str = None, 
                     wait_time: tuple = (1.0, 2.0)) -> bool:
        """
        匹配并点击按钮
        
        Args:
            button_name: 按钮名称
            interface_type: 界面类型（可选）
            wait_time: 点击后等待时间 (min, max)
            
        Returns:
            是否成功点击
        """
        result = self.match_button(button_name, interface_type)
        
        if not result or not result.get("found"):
            self.logger.warning(f"按钮未找到: {button_name}")
            return False
        
        center = self.matcher.get_center(result)
        if not center:
            self.logger.error("无法获取按钮中心点")
            return False
        
        btn_config = result.get("config", {})
        hwnd = btn_config.get("hwnd", self.hwnd)
        
        click_at(hwnd, center[0], center[1])
        
        import time
        import random
        time.sleep(random.uniform(wait_time[0], wait_time[1]))
        
        self.logger.info(f"点击按钮: {button_name} ({center[0]}, {center[1]})")
        return True
    
    def match_all_buttons(self, interface_type: str = None) -> Dict[str, Dict[str, Any]]:
        """
        匹配指定界面的所有按钮
        
        Args:
            interface_type: 界面类型（可选）
            
        Returns:
            匹配结果字典，键为按钮名称，值为匹配结果
        """
        if self._ui_config is None:
            if self._load_config() is None:
                return {}
        
        results = {}
        screenshot = capture_window(self.hwnd)
        if screenshot is None:
            self.logger.error("截图失败")
            return results
        
        window_width, window_height = self._get_window_size()
        
        search_interfaces = []
        if interface_type:
            if interface_type in self._ui_config:
                search_interfaces.append(interface_type)
        else:
            search_interfaces = list(self._ui_config.keys())
        
        for iface_name in search_interfaces:
            if iface_name not in self._ui_config:
                continue
            
            for btn_name, btn_config in self._ui_config[iface_name].items():
                image_path = btn_config.get("image", f"{btn_name}.png")
                confidence = btn_config.get("confidence", 0.75)
                
                self.logger.debug(f"匹配 [{iface_name}] {btn_name}")
                
                result = self.matcher.match(screenshot, image_path, window_width, window_height)
                
                if result and result.get("found"):
                    result["interface_type"] = iface_name
                    result["button_name"] = btn_name
                    result["config"] = btn_config
                    results[btn_name] = result
                    self.logger.info(f"匹配成功: [{iface_name}] {btn_name}")
        
        return results
    
    def get_button_region(self, button_name: str, interface_type: str = None) -> Optional[tuple]:
        """
        获取按钮区域坐标
        
        Args:
            button_name: 按钮名称
            interface_type: 界面类型（可选）
            
        Returns:
            按钮区域 (x, y, width, height) 或 None
        """
        result = self.match_button(button_name, interface_type)
        
        if not result or not result.get("found"):
            return None
        
        location = result.get("location", (0, 0))
        size = result.get("size", (0, 0))
        
        return (location[0], location[1], size[0], size[1])
    
    def clear_cache(self):
        """清除匹配器缓存"""
        self.matcher.clear_cache()
        self.logger.debug("匹配器缓存已清除")
