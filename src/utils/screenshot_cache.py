import time
from typing import Optional, Dict, Tuple
import numpy as np
import logging


class ScreenshotCache:
    """统一的截图缓存管理器"""
    
    def __init__(self, ttl: float = 0.5, enable_stats: bool = False, logger: logging.Logger = None):
        """
        初始化缓存管理器
        
        Args:
            ttl: 缓存过期时间（秒），默认 0.5 秒
            enable_stats: 是否启用缓存统计
            logger: 日志记录器
        """
        self._ttl = ttl
        self._cache: Dict[int, Tuple[np.ndarray, int, int, float]] = {}
        self._enable_stats = enable_stats
        self._logger = logger or logging.getLogger(__name__)
        
        # 缓存统计
        self._stats = {
            'hits': 0,
            'misses': 0,
            'updates': 0
        }
    
    def get(self, hwnd: int, capture_func) -> Optional[Tuple[np.ndarray, int, int]]:
        """
        获取截图（带缓存）
        
        Args:
            hwnd: 窗口句柄
            capture_func: 截图函数，签名为 () -> Tuple[np.ndarray, int, int]
        
        Returns:
            (screenshot, win_w, win_h) 或 None
        """
        current_time = time.time()
        
        # 检查缓存
        if hwnd in self._cache:
            cached = self._cache[hwnd]
            if current_time - cached[3] < self._ttl:
                if self._enable_stats:
                    self._stats['hits'] += 1
                return cached[0], cached[1], cached[2]
            else:
                # 缓存过期，删除
                del self._cache[hwnd]
        
        # 缓存未命中，调用截图函数
        if self._enable_stats:
            self._stats['misses'] += 1
        
        result = capture_func()
        if result is None:
            return None
        
        screenshot, win_w, win_h = result
        self._cache[hwnd] = (screenshot, win_w, win_h, current_time)
        
        if self._enable_stats:
            self._stats['updates'] += 1
        
        return screenshot, win_w, win_h
    
    def invalidate(self, hwnd: int):
        """清除指定窗口的缓存"""
        if hwnd in self._cache:
            del self._cache[hwnd]
    
    def clear_all(self):
        """清除所有缓存"""
        self._cache.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        return self._stats.copy()
    
    def reset_stats(self):
        """重置缓存统计"""
        self._stats = {
            'hits': 0,
            'misses': 0,
            'updates': 0
        }
    
    def set_ttl(self, ttl: float):
        """设置缓存过期时间"""
        self._ttl = ttl