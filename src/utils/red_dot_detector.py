#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
红点检测模块

提供通用的红点检测功能，支持在指定区域内检测和定位红点
"""

import cv2
import numpy as np
import logging
from typing import List, Tuple, Optional


class RedDotDetector:
    """红点检测器
    
    提供检测和定位图像中红点的功能
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初始化红点检测器
        
        Args:
            logger: 日志记录器，可选
        """
        self.logger = logger or logging.getLogger(__name__)
        
    def detect_red_dots(self, image: np.ndarray) -> List[Tuple[int, int]]:
        """
        检测图像中的所有红点
        
        Args:
            image: 输入图像 (BGR 格式)
            
        Returns:
            红点坐标列表 [(x1, y1), (x2, y2), ...]
        """
        try:
            if image is None or len(image.shape) < 3:
                return []
            
            # 转换为 HSV 色彩空间
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # 定义红色的 HSV 范围
            # 红色在 HSV 中分为两个范围
            lower_red1 = np.array([0, 150, 150])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([160, 150, 150])
            upper_red2 = np.array([180, 255, 255])
            
            # 创建掩码
            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            red_mask = cv2.bitwise_or(mask1, mask2)
            
            # 形态学操作去除噪声
            kernel = np.ones((3, 3), np.uint8)
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)
            
            # 查找轮廓
            contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 过滤和定位红点
            red_dot_positions = []
            min_contour_area = 50
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area >= min_contour_area:
                    # 计算轮廓的圆度
                    perimeter = cv2.arcLength(contour, True)
                    if perimeter > 0:
                        circularity = 4 * np.pi * area / (perimeter * perimeter)
                        
                        if circularity > 0.5:  # 圆度阈值
                            # 计算轮廓中心
                            M = cv2.moments(contour)
                            if M["m00"] != 0:
                                cx = int(M["m10"] / M["m00"])
                                cy = int(M["m01"] / M["m00"])
                                red_dot_positions.append((cx, cy))
            
            return red_dot_positions
            
        except cv2.error as e:
            self.logger.warning(f"红点检测失败: {e}")
            return []
        except Exception as e:
            self.logger.warning(f"红点检测异常: {e}")
            return []
    
    def detect_red_dot_presence(self, image: np.ndarray, threshold: float = 0.01) -> bool:
        """
        检测图像中是否存在红点
        
        Args:
            image: 输入图像 (BGR 格式)
            threshold: 红色像素比例阈值，默认 0.01 (1%)
            
        Returns:
            是否检测到红点
        """
        try:
            if image is None or len(image.shape) < 3:
                return False
            
            # 转换为 HSV 色彩空间
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # 定义红色的 HSV 范围
            lower_red1 = np.array([0, 100, 100])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([160, 100, 100])
            upper_red2 = np.array([180, 255, 255])
            
            # 创建掩码
            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            red_mask = cv2.bitwise_or(mask1, mask2)
            
            # 形态学操作去除噪声
            kernel = np.ones((3, 3), np.uint8)
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)
            
            # 计算红色像素比例
            red_pixels = np.sum(red_mask > 0)
            total_pixels = red_mask.size
            
            if total_pixels > 0:
                red_ratio = red_pixels / total_pixels
                return red_ratio > threshold
            
            return False
            
        except cv2.error as e:
            self.logger.warning(f"红点存在检测失败: {e}")
            return False
        except Exception as e:
            self.logger.warning(f"红点存在检测异常: {e}")
            return False
    
    def get_red_dot_positions_with_offset(self, image: np.ndarray, offset_x: int, offset_y: int) -> List[Tuple[int, int]]:
        """
        检测图像中的红点并添加偏移量
        
        Args:
            image: 输入图像 (BGR 格式)
            offset_x: X 轴偏移量
            offset_y: Y 轴偏移量
            
        Returns:
            带偏移的红点坐标列表 [(x1, y1), (x2, y2), ...]
        """
        dots = self.detect_red_dots(image)
        # 添加偏移量
        return [(x + offset_x, y + offset_y) for (x, y) in dots]


# 全局红点检测器实例
red_dot_detector = RedDotDetector()


def detect_red_dots(image: np.ndarray) -> List[Tuple[int, int]]:
    """
    检测图像中的红点
    
    Args:
        image: 输入图像 (BGR 格式)
        
    Returns:
        红点坐标列表
    """
    return red_dot_detector.detect_red_dots(image)


def detect_red_dot_presence(image: np.ndarray, threshold: float = 0.01) -> bool:
    """
    检测图像中是否存在红点
    
    Args:
        image: 输入图像 (BGR 格式)
        threshold: 红色像素比例阈值
        
    Returns:
        是否检测到红点
    """
    return red_dot_detector.detect_red_dot_presence(image, threshold)


def get_red_dot_positions_with_offset(image: np.ndarray, offset_x: int, offset_y: int) -> List[Tuple[int, int]]:
    """
    检测图像中的红点并添加偏移量
    
    Args:
        image: 输入图像 (BGR 格式)
        offset_x: X 轴偏移量
        offset_y: Y 轴偏移量
        
    Returns:
        带偏移的红点坐标列表
    """
    return red_dot_detector.get_red_dot_positions_with_offset(image, offset_x, offset_y)
