#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自适应图片匹配器 - 统一的模板匹配模块
支持不同屏幕分辨率、窗口大小和DPI的自适应图片匹配
"""

import os
import logging
import cv2
import numpy as np
from typing import Optional, Tuple, Dict
from pathlib import Path


class AdaptiveMatcher:
    """自适应图片匹配器 - 支持不同屏幕分辨率、窗口大小和DPI"""
    
    BASE_WIDTH = 558
    BASE_HEIGHT = 1021
    FALLBACK_SCALE_MIN = 0.5
    FALLBACK_SCALE_MAX = 2.0
    FALLBACK_STEPS = 20
    
    def __init__(self, confidence: float = 0.65, logger=None):
        self.confidence = confidence
        self.logger = logger or logging.getLogger(__name__)
        self._template_cache: Dict[str, np.ndarray] = {}
        self._scaled_cache: Dict[Tuple[str, float], np.ndarray] = {}
        self._last_success_scale: Dict[str, float] = {}
    
    def log(self, level: str, msg: str):
        """记录日志"""
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
            self.log("debug", f"加载模板: {os.path.basename(image_path)} {img.shape[1]}x{img.shape[0]}")
        return self._template_cache.get(image_path)
    
    def get_scale_factor(self, current_width: int, current_height: int) -> float:
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
                          scale_min: float = 0.5, scale_max: float = 2.0, steps: int = 20) -> Optional[dict]:
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
                if max_val > best_score:
                    best_score = max_val
                    best_result = {"location": max_loc, "size": (new_w, new_h), "scale": scale}
            if best_result and best_score >= self.confidence:
                best_result["found"] = True
                best_result["confidence"] = best_score
                return best_result
        except Exception as e:
            self.log("error", f"多尺度匹配错误: {e}")
        return None
    
    def match(self, screenshot: np.ndarray, image_path: str,
              window_width: int, window_height: int) -> Optional[dict]:
        """主匹配函数 - 自适应多尺度匹配"""
        template = self.load_template(image_path)
        if template is None:
            return None
        
        image_name = os.path.basename(image_path)
        scale = self.get_scale_factor(window_width, window_height)
        
        # 方法1：使用计算出的缩放比例
        scaled_template = self.get_scaled_template(image_path, scale)
        if scaled_template is not None:
            result = self.match_single(screenshot, scaled_template)
            if result:
                result["scale"] = scale
                result["method"] = "window_scale"
                self._last_success_scale[image_path] = scale
                self.log("debug", f"[比例匹配] {image_name} scale={scale:.3f} conf={result['confidence']:.3f}")
                return result
        
        self.log("info", f"比例匹配失败，启用备选搜索: {image_name}")
        
        # 方法2：使用上次成功的缩放比例
        if image_path in self._last_success_scale:
            last_scale = self._last_success_scale[image_path]
            search_min = max(self.FALLBACK_SCALE_MIN, last_scale - 0.2)
            search_max = min(self.FALLBACK_SCALE_MAX, last_scale + 0.2)
            result = self.match_multi_scale(screenshot, template, search_min, search_max, 10)
            if result:
                result["method"] = "fallback_near_last"
                self._last_success_scale[image_path] = result["scale"]
                self.log("info", f"[备选-近邻] {image_name} scale={result['scale']:.3f} conf={result['confidence']:.3f}")
                return result
        
        # 方法3：全范围多尺度匹配
        result = self.match_multi_scale(screenshot, template,
                                        self.FALLBACK_SCALE_MIN,
                                        self.FALLBACK_SCALE_MAX,
                                        self.FALLBACK_STEPS)
        if result:
            result["method"] = "fallback_full"
            self._last_success_scale[image_path] = result["scale"]
            self.log("info", f"[备选-全范围] {image_name} scale={result['scale']:.3f} conf={result['confidence']:.3f}")
            return result
        
        self.log("debug", f"未找到: {image_name}")
        return None
    
    def get_center(self, result: dict) -> Optional[Tuple[int, int]]:
        """获取匹配结果的中心点"""
        if not result or not result.get("found"):
            return None
        x, y = result["location"]
        w, h = result["size"]
        return (x + w // 2, y + h // 2)
    
    def clear_cache(self):
        """清除缓存"""
        self._scaled_cache.clear()
