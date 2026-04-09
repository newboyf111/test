#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资源池管理模块 - 缓存图像资源，提高性能
"""

import cv2
import numpy as np
from typing import Dict, Optional
from .resource_path import get_pic_path


class ResourcePool:
    """资源池管理类"""
    
    def __init__(self):
        """初始化资源池"""
        self.image_cache: Dict[str, np.ndarray] = {}
    
    def get_image(self, image_name: str) -> Optional[np.ndarray]:
        """
        获取图像资源，优先从缓存中读取
        
        Args:
            image_name: 图像文件名
            
        Returns:
            图像数组，如果加载失败返回 None
        """
        # 检查缓存
        if image_name in self.image_cache:
            return self.image_cache[image_name]
        
        # 加载图像
        try:
            image_path = get_pic_path(image_name)
            image = cv2.imread(image_path)
            if image is not None:
                # 缓存图像
                self.image_cache[image_name] = image
                return image
        except Exception:
            pass
        
        return None
    
    def clear_cache(self):
        """清空缓存"""
        self.image_cache.clear()
    
    def get_cache_size(self) -> int:
        """获取缓存大小"""
        return len(self.image_cache)


# 全局资源池实例
resource_pool = ResourcePool()


def get_image(image_name: str) -> Optional[np.ndarray]:
    """
    从资源池获取图像
    
    Args:
        image_name: 图像文件名
        
    Returns:
        图像数组，如果加载失败返回 None
    """
    return resource_pool.get_image(image_name)


def clear_resource_cache():
    """清空资源缓存"""
    resource_pool.clear_cache()


def get_resource_cache_size() -> int:
    """获取资源缓存大小"""
    return resource_pool.get_cache_size()
