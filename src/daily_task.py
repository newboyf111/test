#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DailyTaskModule - 每日任务自动化脚本
用于自动完成游戏中的每日任务
"""

import time
import logging
import threading
import json
import random
from pathlib import Path
from typing import Optional, Callable, Tuple
import win32gui

from src.utils.adaptive_matcher import AdaptiveMatcher
from src.utils.window_utils import set_dpi_aware, capture_window
from src.utils.red_dot_detector import detect_red_dot_presence


set_dpi_aware()


class DailyTaskModule:
    """每日任务自动化脚本"""
    
    def __init__(self, hwnd: int, mining_manager=None, protective_casing=None):
        """
        初始化每日任务模块
        
        Args:
            hwnd: 窗口句柄
            mining_manager: 挖矿管理器，用于检查挖矿状态
            protective_casing: 保护外壳，用于检查和暂停保护状态
        """
        self.hwnd = hwnd
        self.logger = logging.getLogger(f"daily_task_{hwnd}")
        self.logger.setLevel(logging.DEBUG)
        
        # 确保有 handler
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                f"[每日任务] %(asctime)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
        self.matcher = AdaptiveMatcher(confidence=0.75, logger=self.logger)
        self.running = False
        
        # 依赖的管理器
        self.mining_manager = mining_manager
        self.protective_casing = protective_casing
        
        # 每日任务相关图片文件名（AdaptiveMatcher 会自动处理路径）
        self.town_path = "town.png"
        self.wild_path = "wild.png"
        self.back_path = "back.png"
        self.back1_path = "back1.png"
        self.back2_path = "back2.png"
        self.close_path = "close.png"
        
        # 等待时间配置
        self.click_wait = (1.0, 2.0)
        
        # 每日任务入口区域配置（延迟加载，在 run_daily_task 中加载）
        self.daily_task_region = None
    
    def _load_region_config(self) -> Optional[dict]:
        """从 frame_data.json 加载每日任务入口区域配置"""
        try:
            config_path = Path(__file__).parent / "frame_data.json"
            
            self.logger.info(f"尝试加载配置文件: {config_path}")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.logger.info(f"配置文件加载成功，键名: {list(data.keys())}")
            
            if "每日任务" in data and "入口" in data["每日任务"]:
                self.logger.info("找到每日任务入口配置")
                return data["每日任务"]["入口"]
            elif "雪域兵器联赛" in data and "每日任务" in data["雪域兵器联赛"]:
                self.logger.info("找到雪域兵器联赛每日任务入口配置")
                return data["雪域兵器联赛"]["每日任务"]["入口"]
            
            self.logger.warning("未找到每日任务入口配置")
            return None
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
            return None
    
    def _wait(self, min_sec: float = None, max_sec: float = None):
        """统一随机等待"""
        if min_sec is None:
            min_sec = self.click_wait[0]
        if max_sec is None:
            max_sec = self.click_wait[1]
        time.sleep(random.uniform(min_sec, max_sec))
    
    def _get_screenshot(self) -> Optional[Tuple]:
        """获取窗口截图"""
        if not win32gui.IsWindow(self.hwnd):
            self.logger.warning("窗口无效")
            return None
        
        return capture_window(self.hwnd)
    
    def _click_at(self, rel_x: int, rel_y: int, action_name: str = "按钮"):
        """点击指定位置"""
        try:
            # 获取窗口坐标
            left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
            width = right - left
            
            # 计算缩放比例（基准宽度 558）
            scale = width / 558
            abs_x = int(left + rel_x * scale)
            abs_y = int(top + rel_y)
            
            # 激活窗口
            win32gui.ShowWindow(self.hwnd, 5)
            win32gui.SetForegroundWindow(self.hwnd)
            time.sleep(0.1)
            
            # 点击
            import pyautogui
            pyautogui.click(abs_x, abs_y)
            self.logger.info(f"点击 {action_name} @ ({abs_x}, {abs_y})")
            return True
        except Exception as e:
            self.logger.error(f"点击失败: {e}")
            return False
    
    def _check_mining_status(self) -> bool:
        """检查是否在挖矿"""
        if self.mining_manager:
            try:
                return self.mining_manager.get_mining_status()
            except (AttributeError, RuntimeError) as e:
                self.logger.error(f"检查挖矿状态失败: {e}")
                return False
        return False
    
    def _check_mining_state(self) -> int:
        """检查挖矿状态
        
        Returns:
            int: 挖矿状态（0: 未开始, 1: 挖矿中, 2: 挖矿结束）
        """
        if self.mining_manager:
            try:
                states = self.mining_manager.get_all_mining_states()
                if states:
                    return list(states.values())[0]
                return 0
            except (AttributeError, RuntimeError) as e:
                self.logger.error(f"检查挖矿状态失败: {e}")
                return 0
        return 0
    
    def _wait_for_mining_to_end(self, max_wait_time: int = 300):
        """等待挖矿结束
        
        Args:
            max_wait_time: 最大等待时间（秒），默认 300 秒
        """
        self.logger.info("检查挖矿状态...")
        
        elapsed = 0
        while self._check_mining_status():
            if elapsed >= max_wait_time:
                self.logger.warning(f"等待挖矿结束超时 ({max_wait_time} 秒)")
                return False
            
            self.logger.info(f"挖矿进行中，等待挖矿结束... (已等待 {elapsed} 秒)")
            time.sleep(5)
            elapsed += 5
        
        self.logger.info("挖矿已结束")
        return True
    
    def _check_protective_status(self) -> bool:
        """检查保护外壳是否开启"""
        if self.protective_casing:
            try:
                return self.protective_casing.is_protecting()
            except (AttributeError, RuntimeError) as e:
                self.logger.error(f"检查保护外壳状态失败: {e}")
                return False
        return False
    
    def _pause_protective_if_needed(self):
        """如果保护外壳开启，则暂停它"""
        if self._check_protective_status():
            self.logger.info("保护外壳开启中，准备暂停...")
            try:
                self.protective_casing.stop_protection()
                self.logger.info("保护外壳已暂停")
                return True
            except Exception as e:
                self.logger.error(f"暂停保护外壳失败: {e}")
                return False
        return True
    
    def _match_image(self, image_path: str) -> Optional[dict]:
        """匹配图片
        
        Args:
            image_path: 图片路径
            
        Returns:
            匹配结果，包含 location 和 size
        """
        result = self._get_screenshot()
        if result is None:
            return None
        
        screenshot, win_w, win_h = result
        
        match_result = self.matcher.match(screenshot, image_path, win_w, win_h)
        if match_result:
            self.logger.info(f"匹配 {image_path} 成功，置信度: {match_result['confidence']:.3f}")
            return match_result
        
        self.logger.info(f"未匹配到 {image_path}")
        return None
    
    def _extract_region(self, region_config: dict, win_w: int, win_h: int) -> Tuple[int, int, int, int]:
        """从配置中提取区域坐标
        
        Args:
            region_config: 区域配置
            win_w: 窗口宽度
            win_h: 窗口高度
            
        Returns:
            (x, y, w, h) 元组
        """
        if "region" in region_config:
            return region_config["region"]
        elif "relative" in region_config:
            rel = region_config["relative"]
            return (
                int(rel["x"] * win_w),
                int(rel["y"] * win_h),
                int(rel["width"] * win_w),
                int(rel["height"] * win_h)
            )
        else:
            raise ValueError("区域配置格式错误")
    
    def _check_red_dot_in_region(self, region_config: dict) -> bool:
        """检查指定区域是否存在红点
        
        Args:
            region_config: 区域配置
            
        Returns:
            是否检测到红点
        """
        self.logger.info("检查红点...")
        
        result = self._get_screenshot()
        if result is None:
            return False
        
        screenshot, win_w, win_h = result
        
        try:
            x, y, w, h = self._extract_region(region_config, win_w, win_h)
            
            region_image = screenshot[y:y+h, x:x+w]
            
            if region_image.size == 0:
                self.logger.warning("裁剪区域无效")
                return False
            
            has_red = detect_red_dot_presence(region_image)
            
            if has_red:
                self.logger.info(f"在区域 [{x}, {y}, {w}, {h}] 检测到红点")
                return True
            else:
                self.logger.info(f"在区域 [{x}, {y}, {w}, {h}] 未检测到红点")
                return False
                
        except Exception as e:
            self.logger.error(f"检查红点失败: {e}")
            return False
    
    def _click_region_center(self, region_config: dict):
        """点击区域中心
        
        Args:
            region_config: 区域配置
        """
        self.logger.info("点击区域中心...")
        
        result = self._get_screenshot()
        if result is None:
            return False
        
        screenshot, win_w, win_h = result
        
        try:
            x, y, w, h = self._extract_region(region_config, win_w, win_h)
            
            center_x = x + w // 2
            center_y = y + h // 2
            
            return self._click_at(center_x, center_y, "区域中心")
            
        except Exception as e:
            self.logger.error(f"点击区域中心失败: {e}")
            return False
    
    def _try_match_town(self) -> bool:
        """尝试匹配 town，如果存在则检查红点"""
        self.logger.info("尝试匹配 town...")
        
        match_result = self._match_image(self.town_path)
        if match_result:
            self.logger.info("town 匹配成功")
            
            if self.daily_task_region:
                if self._check_red_dot_in_region(self.daily_task_region):
                    self.logger.info("检测到红点，准备点击...")
                    self._click_region_center(self.daily_task_region)
                else:
                    self.logger.info("未检测到红点")
            
            self.logger.info("结束每日任务流程")
            return True
        
        self.logger.info("未匹配到 town")
        return False
    
    def _try_match_wild(self) -> bool:
        """尝试匹配 wild，如果存在则检查红点"""
        self.logger.info("尝试匹配 wild...")
        
        match_result = self._match_image(self.wild_path)
        if match_result:
            self.logger.info("wild 匹配成功")
            
            if self.daily_task_region:
                if self._check_red_dot_in_region(self.daily_task_region):
                    self.logger.info("检测到红点，准备点击...")
                    self._click_region_center(self.daily_task_region)
                else:
                    self.logger.info("未检测到红点")
            
            self.logger.info("结束每日任务流程")
            return True
        
        self.logger.info("未匹配到 wild")
        return False
    
    def _try_match_back(self) -> bool:
        """尝试匹配 back，如果存在则点击"""
        self.logger.info("尝试匹配 back...")
        
        match_result = self._match_image(self.back_path)
        if match_result:
            self.logger.info("back 匹配成功")
            
            # 点击 back
            x, y = match_result["location"]
            w, h = match_result["size"]
            center_x = x + w // 2
            center_y = y + h // 2
            
            if self._click_at(center_x, center_y, "back"):
                self._wait()
                return True
        
        self.logger.info("未匹配到 back")
        return False
    
    def _try_match_back1(self) -> bool:
        """尝试匹配 back1，如果存在则点击"""
        self.logger.info("尝试匹配 back1...")
        
        match_result = self._match_image(self.back1_path)
        if match_result:
            self.logger.info("back1 匹配成功")
            
            # 点击 back1
            x, y = match_result["location"]
            w, h = match_result["size"]
            center_x = x + w // 2
            center_y = y + h // 2
            
            if self._click_at(center_x, center_y, "back1"):
                self._wait()
                return True
        
        self.logger.info("未匹配到 back1")
        return False
    
    def _try_match_back2(self) -> bool:
        """尝试匹配 back2，如果存在则点击"""
        self.logger.info("尝试匹配 back2...")
        
        match_result = self._match_image(self.back2_path)
        if match_result:
            self.logger.info("back2 匹配成功")
            
            # 点击 back2
            x, y = match_result["location"]
            w, h = match_result["size"]
            center_x = x + w // 2
            center_y = y + h // 2
            
            if self._click_at(center_x, center_y, "back2"):
                self._wait()
                return True
        
        self.logger.info("未匹配到 back2")
        return False
    
    def _try_match_close(self) -> bool:
        """尝试匹配 close，如果存在则点击"""
        self.logger.info("尝试匹配 close...")
        
        match_result = self._match_image(self.close_path)
        if match_result:
            self.logger.info("close 匹配成功")
            
            # 点击 close
            x, y = match_result["location"]
            w, h = match_result["size"]
            center_x = x + w // 2
            center_y = y + h // 2
            
            if self._click_at(center_x, center_y, "close"):
                self._wait()
                return True
        
        self.logger.info("未匹配到 close")
        return False
    
    def run_daily_task(self) -> bool:
        """运行每日任务流程"""
        self.logger.info("=" * 50)
        self.logger.info("开始每日任务流程")
        self.logger.info("=" * 50)
        
        try:
            # 0. 延迟加载每日任务入口区域配置
            if self.daily_task_region is None:
                self.logger.info("加载每日任务入口配置...")
                self.daily_task_region = self._load_region_config()
                if self.daily_task_region is None:
                    self.logger.error("无法加载每日任务入口配置")
                    return False
            
            # 1. 检查挖矿状态
            mining_state = self._check_mining_state()
            self.logger.info(f"挖矿状态: {mining_state} (0:未开始, 1:挖矿中, 2:挖矿结束)")
            
            # 如果挖矿正在进行（状态为1），等待挖矿结束
            if mining_state == 1:
                self.logger.info("检测到挖矿进行中")
                if not self._wait_for_mining_to_end():
                    self.logger.warning("等待挖矿结束失败")
                    return False
            elif mining_state == 0:
                self.logger.info("挖矿未开始")
            elif mining_state == 2:
                self.logger.info("挖矿已结束")
            
            # 2. 检查保护外壳，如果开启则暂停
            if not self._pause_protective_if_needed():
                self.logger.warning("暂停保护外壳失败")
                return False
            
            # 3. 尝试匹配 town
            if self._try_match_town():
                return True
            
            # 4. 尝试匹配 wild
            if self._try_match_wild():
                return True
            
            # 5. 尝试匹配 back，如果成功则等待后继续匹配 town 和 wild
            if self._try_match_back():
                if self._try_match_town():
                    return True
                if self._try_match_wild():
                    return True
            
            # 6. 尝试匹配 back1，如果成功则等待后继续匹配 town 和 wild
            if self._try_match_back1():
                if self._try_match_town():
                    return True
                if self._try_match_wild():
                    return True
            
            # 7. 尝试匹配 back2，如果成功则等待后继续匹配 town 和 wild
            if self._try_match_back2():
                if self._try_match_town():
                    return True
                if self._try_match_wild():
                    return True
            
            # 8. 尝试匹配 close，如果成功则等待后继续匹配 town 和 wild
            if self._try_match_close():
                if self._try_match_town():
                    return True
                if self._try_match_wild():
                    return True
            
            self.logger.warning("所有匹配尝试均失败")
            return False
            
        except Exception as e:
            self.logger.error(f"每日任务流程执行异常: {e}")
            import traceback
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def run_daily_task_async(self, callback: Optional[Callable[[bool], None]] = None):
        """异步运行每日任务流程
        
        Args:
            callback: 完成后的回调函数，签名为 callback(success: bool)
        """
        def run():
            success = self.run_daily_task()
            if callback:
                callback(success)
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        self.logger.info("每日任务流程已在后台启动")
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.running
    
    def stop(self):
        """停止运行"""
        self.running = False
        self.logger.info("停止每日任务流程")
