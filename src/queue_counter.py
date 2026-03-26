import cv2
import numpy as np
import os
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class AdaptiveMatcher:
    """自适应图片匹配器"""

    BASE_WIDTH = 558
    BASE_HEIGHT = 1021
    FALLBACK_SCALE_MIN = 0.5
    FALLBACK_SCALE_MAX = 2.0
    FALLBACK_STEPS = 20

    def __init__(self, confidence: float = 0.65):
        self.confidence = confidence
        self._template_cache: Dict[str, np.ndarray] = {}
        self._scaled_cache: Dict[tuple, np.ndarray] = {}
        self._last_success_scale: Dict[str, float] = {}

    def load_template(self, image_path: str) -> Optional[np.ndarray]:
        """加载模板图片（带缓存）"""
        if image_path not in self._template_cache:
            if not os.path.exists(image_path):
                return None
            img = cv2.imread(image_path)
            if img is None:
                return None
            self._template_cache[image_path] = img
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
        except Exception:
            pass
        return None

    def match_multi_scale(self, screenshot: np.ndarray, template: np.ndarray,
                          scale_min: float, scale_max: float, steps: int) -> Optional[dict]:
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
        except Exception:
            pass
        return None

    def match(self, screenshot: np.ndarray, image_path: str,
              window_width: int, window_height: int) -> Optional[dict]:
        """主匹配函数"""
        template = self.load_template(image_path)
        if template is None:
            return None
        image_name = os.path.basename(image_path)
        scale = self.get_scale_factor(window_width, window_height)
        scaled_template = self.get_scaled_template(image_path, scale)
        if scaled_template is not None:
            result = self.match_single(screenshot, scaled_template)
            if result:
                result["scale"] = scale
                result["method"] = "window_scale"
                self._last_success_scale[image_path] = scale
                return result
        if image_path in self._last_success_scale:
            last_scale = self._last_success_scale[image_path]
            search_min = max(self.FALLBACK_SCALE_MIN, last_scale - 0.2)
            search_max = min(self.FALLBACK_SCALE_MAX, last_scale + 0.2)
            result = self.match_multi_scale(screenshot, template, search_min, search_max, 10)
            if result:
                result["method"] = "fallback_near_last"
                self._last_success_scale[image_path] = result["scale"]
                return result
        result = self.match_multi_scale(screenshot, template,
                                        self.FALLBACK_SCALE_MIN,
                                        self.FALLBACK_SCALE_MAX,
                                        self.FALLBACK_STEPS)
        if result:
            result["method"] = "fallback_full"
            self._last_success_scale[image_path] = result["scale"]
            return result
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


class QueueCounter:
    """队列数量检测器 - 使用自适应模板匹配统计相同形状的对象"""
    
    def __init__(self):
        self.template = None
        self.template_path = None
        self.window_offset = (0, 0)
        self.window_size = (558, 1021)
        self.matcher = AdaptiveMatcher(confidence=0.65)
        self.scale_range = (0.5, 2.0)
        self.scale_steps = 30
        self.rotation_range = (-15, 15)
        self.rotation_steps = 7
        
    def load_template(self, template_path: str):
        """
        加载模板图像
        
        Args:
            template_path: 模板图像路径
        """
        template = cv2.imread(template_path)
        if template is None:
            raise ValueError(f"无法读取模板图像: {template_path}")
        
        self.template_path = template_path
        self.template = template
        
    def set_window_offset(self, x: int, y: int):
        """
        设置窗口偏移量（窗口左上角相对于屏幕的坐标）
        
        Args:
            x: 窗口左上角的X坐标
            y: 窗口左上角的Y坐标
        """
        self.window_offset = (x, y)
        
    def set_window_size(self, width: int, height: int):
        """
        设置窗口尺寸
        
        Args:
            width: 窗口宽度
            height: 窗口高度
        """
        self.window_size = (width, height)
        
    def set_adaptive_params(self, scale_range: Tuple[float, float] = None, 
                           scale_steps: int = None,
                           rotation_range: Tuple[float, float] = None,
                           rotation_steps: int = None):
        """
        设置自适应匹配参数
        
        Args:
            scale_range: 缩放比例范围 (min, max)
            scale_steps: 缩放步数
            rotation_range: 旋转角度范围 (min, max)
            rotation_steps: 旋转步数
        """
        if scale_range is not None:
            self.scale_range = scale_range
        if scale_steps is not None:
            self.scale_steps = scale_steps
        if rotation_range is not None:
            self.rotation_range = rotation_range
        if rotation_steps is not None:
            self.rotation_steps = rotation_steps
        
    def extract_template_color(self, template: np.ndarray) -> np.ndarray:
        """
        提取模板的平均颜色
        
        Args:
            template: 模板图像
            
        Returns:
            平均颜色 [B, G, R]
        """
        avg_color = np.mean(template, axis=(0, 1))
        return avg_color
    
    def filter_by_color(self, image: np.ndarray, rectangles: List[Dict], template_color: np.ndarray, tolerance: float = 50) -> List[Dict]:
        """
        根据颜色过滤矩形
        
        Args:
            image: 原始图像
            rectangles: 矩形列表
            template_color: 模板颜色
            tolerance: 颜色容差
            
        Returns:
            过滤后的矩形列表
        """
        filtered = []
        for rect in rectangles:
            x, y, w, h = rect["x"], rect["y"], rect["w"], rect["h"]
            roi = image[y:y+h, x:x+w]
            avg_color = np.mean(roi, axis=(0, 1))
            
            diff = np.abs(avg_color - template_color)
            if np.all(diff < tolerance):
                filtered.append(rect)
        
        return filtered
    
    def match_multi_positions(self, screenshot: np.ndarray, template: np.ndarray, 
                              threshold: float = 0.8, max_count: int = 10) -> List[Dict]:
        """
        匹配多个位置
        
        Args:
            screenshot: 截图
            template: 模板
            threshold: 匹配阈值
            max_count: 最大匹配数量
            
        Returns:
            匹配位置列表
        """
        gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        gray_tmpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        tmpl_h, tmpl_w = gray_tmpl.shape[:2]
        scr_h, scr_w = gray_screen.shape[:2]
        
        if tmpl_w > scr_w or tmpl_h > scr_h:
            return []
        
        result = cv2.matchTemplate(gray_screen, gray_tmpl, cv2.TM_CCOEFF_NORMED)
        
        locations = np.where(result >= threshold)
        
        rectangles = []
        for pt in zip(*locations[::-1]):
            rectangles.append({
                "x": pt[0],
                "y": pt[1],
                "w": tmpl_w,
                "h": tmpl_h,
                "center_x": pt[0] + tmpl_w // 2,
                "center_y": pt[1] + tmpl_h // 2,
                "screen_x": pt[0] + self.window_offset[0],
                "screen_y": pt[1] + self.window_offset[1],
                "center_screen_x": pt[0] + tmpl_w // 2 + self.window_offset[0],
                "center_screen_y": pt[1] + tmpl_h // 2 + self.window_offset[1]
            })
        
        if len(rectangles) == 0:
            return []
        
        # 使用 groupRectangles 过滤重叠的矩形
        rect_list = [[r["x"], r["y"], r["w"], r["h"]] for r in rectangles]
        rect_list, weights = cv2.groupRectangles(rect_list, groupThreshold=1, eps=0.2)
        
        filtered = []
        for i, rect in enumerate(rect_list):
            if i >= max_count:
                break
            x, y, w, h = rect
            filtered.append({
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "center_x": x + w // 2,
                "center_y": y + h // 2,
                "screen_x": x + self.window_offset[0],
                "screen_y": y + self.window_offset[1],
                "center_screen_x": x + w // 2 + self.window_offset[0],
                "center_screen_y": y + h // 2 + self.window_offset[1]
            })
        
        return filtered
    
    def match_multi_scale_rotations(self, screenshot: np.ndarray, template: np.ndarray,
                                    threshold: float = 0.8, max_count: int = 10) -> List[Dict]:
        """
        多尺度多角度匹配
        
        Args:
            screenshot: 截图
            template: 模板
            threshold: 匹配阈值
            max_count: 最大匹配数量
            
        Returns:
            匹配位置列表
        """
        gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        gray_tmpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        tmpl_h, tmpl_w = gray_tmpl.shape[:2]
        scr_h, scr_w = gray_screen.shape[:2]
        
        all_rectangles = []
        
        for scale in np.linspace(self.scale_range[0], self.scale_range[1], self.scale_steps):
            new_w = max(8, int(tmpl_w * scale))
            new_h = max(8, int(tmpl_h * scale))
            
            if new_w > scr_w or new_h > scr_h:
                continue
            
            scaled_tmpl = cv2.resize(gray_tmpl, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            for rotation in np.linspace(self.rotation_range[0], self.rotation_range[1], self.rotation_steps):
                if abs(rotation) < 0.1:
                    rotated_tmpl = scaled_tmpl
                else:
                    center = (new_w // 2, new_h // 2)
                    M = cv2.getRotationMatrix2D(center, rotation, 1.0)
                    rotated_tmpl = cv2.warpAffine(scaled_tmpl, M, (new_w, new_h), flags=cv2.INTER_LINEAR, 
                                                  borderMode=cv2.BORDER_CONSTANT, borderValue=0)
                
                if rotated_tmpl.shape[1] > scr_w or rotated_tmpl.shape[0] > scr_h:
                    continue
                
                result = cv2.matchTemplate(gray_screen, rotated_tmpl, cv2.TM_CCOEFF_NORMED)
                
                locations = np.where(result >= threshold)
                
                for pt in zip(*locations[::-1]):
                    all_rectangles.append({
                        "x": pt[0],
                        "y": pt[1],
                        "w": rotated_tmpl.shape[1],
                        "h": rotated_tmpl.shape[0],
                        "scale": scale,
                        "rotation": rotation,
                        "center_x": pt[0] + rotated_tmpl.shape[1] // 2,
                        "center_y": pt[1] + rotated_tmpl.shape[0] // 2,
                        "screen_x": pt[0] + self.window_offset[0],
                        "screen_y": pt[1] + self.window_offset[1],
                        "center_screen_x": pt[0] + rotated_tmpl.shape[1] // 2 + self.window_offset[0],
                        "center_screen_y": pt[1] + rotated_tmpl.shape[0] // 2 + self.window_offset[1]
                    })
        
        if len(all_rectangles) == 0:
            return []
        
        rect_list = [[r["x"], r["y"], r["w"], r["h"]] for r in all_rectangles]
        rect_list, weights = cv2.groupRectangles(rect_list, groupThreshold=1, eps=0.2)
        
        filtered = []
        for i, rect in enumerate(rect_list):
            if i >= max_count:
                break
            x, y, w, h = rect
            filtered.append({
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "center_x": x + w // 2,
                "center_y": y + h // 2,
                "screen_x": x + self.window_offset[0],
                "screen_y": y + self.window_offset[1],
                "center_screen_x": x + w // 2 + self.window_offset[0],
                "center_screen_y": y + h // 2 + self.window_offset[1]
            })
        
        return filtered
    
    def detect_template_count(self, image_path: str, threshold: float = 0.8) -> Dict:
        """
        检测模板在图像中的数量
        
        Args:
            image_path: 待检测图像路径
            threshold: 匹配阈值
            
        Returns:
            包含检测结果的字典
        """
        if self.template is None:
            return {"status": "error", "message": "未加载模板图像"}
        
        image = cv2.imread(image_path)
        if image is None:
            return {"status": "error", "message": f"无法读取图像: {image_path}"}
        
        # 使用自适应匹配器获取匹配位置
        result = self.matcher.match(image, self.template_path, self.window_size[0], self.window_size[1])
        
        if result is None or not result.get("found"):
            return {"status": "error", "message": "未检测到匹配对象"}
        
        # 获取匹配的模板
        template = self.matcher.load_template(self.template_path)
        if template is None:
            return {"status": "error", "message": "无法加载模板"}
        
        # 获取缩放比例
        scale = result.get("scale", 1.0)
        
        # 缩放模板
        h, w = template.shape[:2]
        new_w = max(8, int(w * scale))
        new_h = max(8, int(h * scale))
        scaled_template = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # 匹配多个位置（使用自适应多尺度多角度匹配）
        rectangles = self.match_multi_scale_rotations(image, scaled_template, threshold=threshold, max_count=10)
        
        if len(rectangles) == 0:
            return {"status": "error", "message": "未检测到匹配对象"}
        
        # 提取模板颜色并过滤
        template_color = self.extract_template_color(self.template)
        filtered_rectangles = self.filter_by_color(image, rectangles, template_color)
        
        count = len(filtered_rectangles)
        
        # 获取检测区域的位置
        if len(filtered_rectangles) > 0:
            all_x = [r["x"] for r in filtered_rectangles]
            all_y = [r["y"] for r in filtered_rectangles]
            all_w = [r["w"] for r in filtered_rectangles]
            all_h = [r["h"] for r in filtered_rectangles]
            
            min_x = min(all_x)
            min_y = min(all_y)
            max_x = max([all_x[i] + all_w[i] for i in range(len(all_x))])
            max_y = max([all_y[i] + all_h[i] for i in range(len(all_y))])
            
            box_x = min_x
            box_y = min_y
            box_w = max_x - min_x
            box_h = max_y - min_y
        else:
            box_x, box_y, box_w, box_h = 0, 0, 0, 0
        
        return {
            "status": "success",
            "count": count,
            "box_position": [box_x, box_y, box_w, box_h],
            "rectangles": filtered_rectangles
        }
    
    def draw_detection(self, image_path: str, output_path: str, threshold: float = 0.8) -> bool:
        """
        绘制检测结果
        
        Args:
            image_path: 待检测图像路径
            output_path: 输出图像路径
            threshold: 匹配阈值
            
        Returns:
            是否成功
        """
        if self.template is None:
            return False
        
        image = cv2.imread(image_path)
        if image is None:
            return False
        
        result = self.detect_template_count(image_path, threshold)
        
        if result["status"] != "success":
            return False
        
        rectangles = result["rectangles"]
        
        for i, rect in enumerate(rectangles):
            x, y, w, h = rect["x"], rect["y"], rect["w"], rect["h"]
            cv2.rectangle(image, (x, y), (x + w, y + h), (0, 0, 255), 2)
            cv2.putText(image, str(i + 1), (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        cv2.imwrite(output_path, image)
        return True
    
    def count_in_image(self, image_path: str, threshold: float = 0.8) -> Dict:
        """
        在图像中计数模板
        
        Args:
            image_path: 待检测图像路径
            threshold: 匹配阈值
            
        Returns:
            包含检测结果的字典
        """
        if self.template is None:
            return {"status": "error", "message": "未加载模板图像"}
        
        try:
            result = self.detect_template_count(image_path, threshold)
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    counter = QueueCounter()
    
    template_image = "pic/six.png"
    test_image = "pic/092057.png"
    
    counter.load_template(template_image)
    
    result = counter.count_in_image(test_image)
    
    print("检测结果:")
    print(f"数量: {result.get('count')}")
    print(f"状态: {result.get('status')}")
    print(f"框体位置: {result.get('box_position')}")
    
    print("\n每个匹配位置的坐标:")
    for i, rect in enumerate(result.get("rectangles", [])):
        print(f"  位置 {i+1}:")
        print(f"    图像坐标: ({rect['x']}, {rect['y']})")
        print(f"    中心点: ({rect['center_x']}, {rect['center_y']})")
        print(f"    屏幕坐标: ({rect['screen_x']}, {rect['screen_y']})")
        print(f"    屏幕中心点: ({rect['center_screen_x']}, {rect['center_screen_y']})")
    
    output_image = "pic/test_092057_result.png"
    success = counter.draw_detection(test_image, output_image)
    if success:
        print(f"\n检测结果已保存到: {output_image}")
