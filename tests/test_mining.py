#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试挖矿模块
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import threading
import time
import numpy as np
from collections import deque

# 模拟 Windows 特定的库
mock_win32gui = Mock()
mock_win32con = Mock()
mock_win32process = Mock()

# 将模拟对象添加到 sys.modules
import sys
sys.modules['win32gui'] = mock_win32gui
sys.modules['win32con'] = mock_win32con
sys.modules['win32process'] = mock_win32process

# 模拟 pyautogui
mock_pyautogui = Mock()
sys.modules['pyautogui'] = mock_pyautogui

# 模拟 ctypes
mock_ctypes = Mock()
sys.modules['ctypes'] = mock_ctypes

# 导入 mining 模块
from src.mining import SingleWindowMiner, MultiWindowMiningManager


class TestSingleWindowMiner(unittest.TestCase):
    """测试单个窗口挖矿模块"""

    def setUp(self):
        """设置测试环境"""
        # 创建一个模拟的窗口句柄
        self.hwnd = 12345
        self.window_name = "Test Window"
        
        # 创建 SingleWindowMiner 实例
        self.miner = SingleWindowMiner(self.hwnd, self.window_name)
        
        # 模拟 mining_manager
        self.mining_manager = Mock()
        self.miner.mining_manager = self.mining_manager

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.miner.hwnd, self.hwnd)
        self.assertEqual(self.miner.window_name, self.window_name)
        self.assertFalse(self.miner.is_mining)
        self.assertEqual(self.miner.mining_state, 0)
        self.assertTrue(self.miner._need_init)

    @patch('src.mining.win32gui.IsWindow')
    def test_get_screenshot_window_invalid(self, mock_is_window):
        """测试获取截图 - 窗口无效"""
        # 模拟窗口无效
        mock_is_window.return_value = False
        
        screenshot, win_w, win_h = self.miner._get_screenshot()
        self.assertIsNone(screenshot)
        self.assertEqual(win_w, 0)
        self.assertEqual(win_h, 0)

    @patch('src.mining.win32gui.IsWindow')
    @patch('src.mining.capture_window')
    def test_get_screenshot_success(self, mock_capture, mock_is_window):
        """测试获取截图 - 成功"""
        # 模拟窗口有效
        mock_is_window.return_value = True
        
        # 模拟截图
        mock_screenshot = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_capture.return_value = (mock_screenshot, 558, 1021)
        
        screenshot, win_w, win_h = self.miner._get_screenshot()
        self.assertIsNotNone(screenshot)
        self.assertEqual(win_w, 558)
        self.assertEqual(win_h, 1021)

    def test_stop_mining(self):
        """测试停止挖矿"""
        # 模拟挖矿中
        self.miner.is_mining = True
        
        # 测试用户手动停止
        result = self.miner.stop_mining(user_stopped=True)
        self.assertTrue(result)
        self.assertFalse(self.miner.is_mining)
        self.assertTrue(self.miner._user_stopped)
        self.assertEqual(self.miner.mining_state, 2)
        
        # 重置状态
        self.miner.is_mining = True
        self.miner._user_stopped = False
        
        # 测试自动停止
        result = self.miner.stop_mining(user_stopped=False)
        self.assertTrue(result)
        self.assertFalse(self.miner.is_mining)
        self.assertFalse(self.miner._user_stopped)
        self.assertTrue(self.miner.mined)
        self.assertEqual(self.miner.mining_state, 2)

    def test_get_mining_status(self):
        """测试获取挖矿状态"""
        self.assertFalse(self.miner.get_mining_status())
        
        self.miner.is_mining = True
        self.assertTrue(self.miner.get_mining_status())

    def test_get_mining_state(self):
        """测试获取挖矿状态值"""
        self.assertEqual(self.miner.get_mining_state(), 0)  # 未开始
        
        self.miner.mining_state = 1
        self.assertEqual(self.miner.get_mining_state(), 1)  # 挖矿中
        
        self.miner.mining_state = 2
        self.assertEqual(self.miner.get_mining_state(), 2)  # 挖矿结束

    def test_is_user_stopped(self):
        """测试是否是用户手动停止"""
        self.assertFalse(self.miner.is_user_stopped())
        
        self.miner._user_stopped = True
        self.assertTrue(self.miner.is_user_stopped())

    def test_set_timer(self):
        """测试设置倒计时"""
        # 测试小于60秒的情况
        self.miner.set_timer(30)
        self.assertEqual(self.miner.timer_minutes, 1)
        self.assertEqual(self.miner.timer_remaining, 30)
        
        # 测试大于60秒的情况
        self.miner.set_timer(120)
        self.assertEqual(self.miner.timer_minutes, 2)
        self.assertEqual(self.miner.timer_remaining, 120)

    @patch('src.mining.threading.Thread')
    def test_start_timer(self, mock_thread):
        """测试启动倒计时"""
        # 设置倒计时时间
        self.miner.timer_minutes = 1
        self.miner.timer_remaining = 60
        self.miner.timer_running = False
        
        # 启动倒计时
        self.miner.start_timer()
        
        # 验证线程是否启动
        mock_thread.assert_called_once()
        self.assertTrue(self.miner.timer_running)

    def test_stop_timer(self):
        """测试停止倒计时"""
        # 设置倒计时正在运行
        self.miner.timer_running = True
        
        # 停止倒计时
        self.miner.stop_timer()
        
        # 验证状态
        self.assertFalse(self.miner.timer_running)

    def test_get_timer_remaining(self):
        """测试获取倒计时剩余时间"""
        # 测试没有设置倒计时的情况
        self.assertEqual(self.miner.get_timer_remaining(), 0)
        
        # 测试设置了倒计时的情况
        self.miner.timer_remaining = 30
        self.assertEqual(self.miner.get_timer_remaining(), 30)


class TestMultiWindowMiningManager(unittest.TestCase):
    """测试多窗口挖矿管理器"""

    def setUp(self):
        """设置测试环境"""
        self.manager = MultiWindowMiningManager()
        
        # 创建模拟的窗口句柄
        self.hwnd1 = 12345
        self.hwnd2 = 67890
        self.window_name1 = "Window 1"
        self.window_name2 = "Window 2"

    @patch('src.mining.win32gui.IsWindow')
    def test_add_window(self, mock_is_window):
        """测试添加窗口"""
        # 模拟窗口有效
        mock_is_window.return_value = True
        
        # 添加窗口
        result = self.manager.add_window(self.hwnd1, self.window_name1)
        self.assertTrue(result)
        self.assertIn(self.hwnd1, self.manager.miners)
        self.assertIn(self.hwnd1, self.manager.window_order)
        
        # 测试添加已存在的窗口
        result = self.manager.add_window(self.hwnd1, self.window_name1)
        self.assertFalse(result)

    @patch('src.mining.win32gui.IsWindow')
    def test_add_window_invalid(self, mock_is_window):
        """测试添加无效窗口"""
        # 模拟窗口无效
        mock_is_window.return_value = False
        
        # 添加窗口
        result = self.manager.add_window(self.hwnd1, self.window_name1)
        self.assertFalse(result)
        self.assertNotIn(self.hwnd1, self.manager.miners)

    @patch('src.mining.win32gui.IsWindow')
    def test_remove_window(self, mock_is_window):
        """测试移除窗口"""
        # 模拟窗口有效
        mock_is_window.return_value = True
        
        # 添加窗口
        self.manager.add_window(self.hwnd1, self.window_name1)
        
        # 移除窗口
        result = self.manager.remove_window(self.hwnd1)
        self.assertTrue(result)
        self.assertNotIn(self.hwnd1, self.manager.miners)
        self.assertNotIn(self.hwnd1, self.manager.window_order)
        
        # 测试移除不存在的窗口
        result = self.manager.remove_window(self.hwnd1)
        self.assertFalse(result)

    @patch('src.mining.win32gui.IsWindow')
    def test_start_mining(self, mock_is_window):
        """测试开始指定窗口的挖矿"""
        # 模拟窗口有效
        mock_is_window.return_value = True
        
        # 添加窗口
        self.manager.add_window(self.hwnd1, self.window_name1)
        
        # 模拟挖矿开始成功
        self.manager.miners[self.hwnd1].start_mining = Mock(return_value=True)
        
        # 开始挖矿
        result = self.manager.start_mining(self.hwnd1)
        self.assertTrue(result)
        self.manager.miners[self.hwnd1].start_mining.assert_called_once()
        
        # 测试开始不存在窗口的挖矿
        result = self.manager.start_mining(99999)
        self.assertFalse(result)

    @patch('src.mining.win32gui.IsWindow')
    @patch.object(MultiWindowMiningManager, '_try_start_next_window')
    def test_stop_mining(self, mock_try_start_next, mock_is_window):
        """测试停止指定窗口的挖矿"""
        # 模拟窗口有效
        mock_is_window.return_value = True
        
        # 添加窗口
        self.manager.add_window(self.hwnd1, self.window_name1)
        
        # 模拟挖矿正在进行
        self.manager.miners[self.hwnd1].is_mining = True
        self.manager.miners[self.hwnd1].stop_mining = Mock(return_value=True)
        
        # 停止挖矿
        result = self.manager.stop_mining(self.hwnd1, user_stopped=False)
        self.assertTrue(result)
        self.manager.miners[self.hwnd1].stop_mining.assert_called_once_with(user_stopped=False)
        mock_try_start_next.assert_called_once()
        
        # 测试停止不存在窗口的挖矿
        result = self.manager.stop_mining(99999, user_stopped=False)
        self.assertFalse(result)

    @patch('src.mining.win32gui.IsWindow')
    def test_stop_all_mining(self, mock_is_window):
        """测试停止所有窗口的挖矿"""
        # 模拟窗口有效
        mock_is_window.return_value = True
        
        # 添加两个窗口
        self.manager.add_window(self.hwnd1, self.window_name1)
        self.manager.add_window(self.hwnd2, self.window_name2)
        
        # 模拟挖矿正在进行
        self.manager.miners[self.hwnd1].is_mining = True
        self.manager.miners[self.hwnd1].stop_mining = Mock(return_value=True)
        self.manager.miners[self.hwnd2].is_mining = True
        self.manager.miners[self.hwnd2].stop_mining = Mock(return_value=True)
        
        # 停止所有挖矿
        count = self.manager.stop_all_mining()
        self.assertEqual(count, 2)
        self.manager.miners[self.hwnd1].stop_mining.assert_called_once_with(user_stopped=True)
        self.manager.miners[self.hwnd2].stop_mining.assert_called_once_with(user_stopped=True)

    @patch('src.mining.win32gui.IsWindow')
    def test_reset_all_mined_flags(self, mock_is_window):
        """测试重置所有窗口的挖矿标记"""
        # 模拟窗口有效
        mock_is_window.return_value = True
        
        # 添加两个窗口
        self.manager.add_window(self.hwnd1, self.window_name1)
        self.manager.add_window(self.hwnd2, self.window_name2)
        
        # 模拟已挖矿
        self.manager.miners[self.hwnd1].mined = True
        self.manager.miners[self.hwnd2].mined = True
        
        # 重置挖矿标记
        self.manager.reset_all_mined_flags()
        
        # 验证标记已重置
        self.assertFalse(self.manager.miners[self.hwnd1].mined)
        self.assertFalse(self.manager.miners[self.hwnd2].mined)
        self.assertEqual(len(self.manager._mining_queue), 0)

    @patch('src.mining.win32gui.IsWindow')
    @patch('src.mining.win32gui.SetForegroundWindow')
    def test_ensure_window_active(self, mock_set_foreground, mock_is_window):
        """测试确保窗口激活"""
        # 模拟窗口有效
        mock_is_window.return_value = True
        
        # 添加窗口
        self.manager.add_window(self.hwnd1, self.window_name1)
        
        # 测试激活第一个窗口
        self.manager._ensure_window_active(self.hwnd1, self.window_name1)
        self.assertEqual(self.manager._current_active_hwnd, self.hwnd1)
        mock_set_foreground.assert_called_once_with(self.hwnd1)
        
        # 测试激活同一个窗口（应该不调用 SetForegroundWindow）
        mock_set_foreground.reset_mock()
        self.manager._ensure_window_active(self.hwnd1, self.window_name1)
        mock_set_foreground.assert_not_called()


if __name__ == '__main__':
    unittest.main()
