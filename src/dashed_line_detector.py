import cv2
import numpy as np

class DashedLineDetector:
    """红色虚线检测器 - 仅检测中心点是否有红色"""
    
    def __init__(self):
        self.image_scale = 1.0
        self.center_tolerance = 1  # 中心点容差（像素）
        
    def set_center_tolerance(self, tolerance: int):
        """
        设置中心点检测容差
        
        Args:
            tolerance: 中心点容差（像素）
        """
        self.center_tolerance = tolerance
    
    def set_image_scale(self, scale: float):
        """
        设置图像缩放比例
        
        Args:
            scale: 图像缩放比例
        """
        self.image_scale = scale
    
    def has_red_at_center(self, image_path: str) -> bool:
        """
        检测图像中心点是否有红色
        
        Args:
            image_path: 图像路径
            
        Returns:
            是否在中心点附近检测到红色
        """
        image = cv2.imread(image_path)
        if image is None:
            return False
        
        if abs(self.image_scale - 1.0) > 0.001:
            new_w = int(image.shape[1] * self.image_scale)
            new_h = int(image.shape[0] * self.image_scale)
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # 转换到HSV颜色空间
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # 定义红色范围
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])
        
        # 创建掩码
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)
        
        # 形态学操作
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # 计算屏幕中心
        screen_center_x = image.shape[1] // 2
        screen_center_y = image.shape[0] // 2
        
        # 检查中心点附近是否有红色
        center_region = mask[screen_center_y - self.center_tolerance:screen_center_y + self.center_tolerance, 
                           screen_center_x - self.center_tolerance:screen_center_x + self.center_tolerance]
        
        # 检查是否有红色像素
        return np.sum(center_region) > 0
