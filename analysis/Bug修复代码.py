# 无尽冬日项目 Bug 修复代码

> 本文件包含所有P0级别bug的修复代码示例
> 使用方法：参考以下代码手动修改源文件，或将修复应用到新版本

---

## 1. 线程安全问题修复

### 修复位置: `src/mining.py`

```python
import threading
from typing import Optional, Dict, Any

class MultiWindowMiningManager:
    """多窗口挖矿管理器 - 线程安全版本"""
    
    def __init__(self, gui=None):
        # ... 其他初始化代码 ...
        
        # ===== 线程安全修复 =====
        self._lock = threading.RLock()  # 可重入锁
        self._current_active_hwnd: Optional[int] = None
        # =========================
        
        self._stop_event = threading.Event()
        self._windows: Dict[int, 'SingleWindowMiner'] = {}
        
    def _ensure_window_active(self, hwnd: int, window_name: str) -> bool:
        """确保窗口处于激活状态 - 线程安全版本"""
        # 使用锁保护共享状态
        with self._lock:
            if self._current_active_hwnd != hwnd:
                if self._current_active_hwnd is not None:
                    self.logger.info(f"切换窗口: {self._current_active_hwnd} -> {hwnd}")
                
                # 窗口激活操作（可添加超时保护）
                try:
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.1)
                    self._current_active_hwnd = hwnd
                except Exception as e:
                    self.logger.error(f"窗口激活失败: {e}")
                    return False
        return True
    
    def get_active_hwnd(self) -> Optional[int]:
        """获取当前活跃窗口句柄 - 线程安全"""
        with self._lock:
            return self._current_active_hwnd


class SingleWindowMiner:
    """单窗口挖矿器 - 添加线程安全的状态访问"""
    
    def __init__(self, hwnd: int, gui=None):
        # ... 其他初始化 ...
        
        # ===== 线程安全修复 =====
        self._state_lock = threading.Lock()
        self._is_mining = False
        self._mined = 0
        # =========================
        
    @property
    def is_mining(self) -> bool:
        """线程安全的状态读取"""
        with self._state_lock:
            return self._is_mining
    
    @is_mining.setter
    def is_mining(self, value: bool):
        """线程安全的状态写入"""
        with self._state_lock:
            self._is_mining = value
    
    def start_mining(self):
        """开始挖矿 - 线程安全"""
        with self._state_lock:
            if self._is_mining:
                return
            self._is_mining = True
        
        # 启动挖矿线程
        self._mining_thread = threading.Thread(target=self._mining_loop)
        self._mining_thread.daemon = True
        self._mining_thread.start()
```

---

## 2. 资源泄漏风险修复

### 修复位置: `src/recording.py`

```python
import atexit
import threading
from ctypes import windll, byref, c_int, POINTER

class MouseRecorder:
    """鼠标录制器 - 带资源安全管理的版本"""
    
    def __init__(self, gui=None):
        self.hook_id = None
        self.mouse_callback = None
        self.hook_thread = None
        self._running = False
        
        # ===== 修复：注册退出时的清理函数 =====
        atexit.register(self.cleanup)
        # =====================================
        
    def start_recording(self):
        """开始录制 - 带异常保护"""
        if self._running:
            return
            
        try:
            # 设置鼠标钩子
            self.mouse_callback = self._mouse_proc
            self.hook_id = user32.SetWindowsHookExW(
                WH_MOUSE_LL,
                self.mouse_callback,
                None,
                0
            )
            
            if not self.hook_id:
                raise RuntimeError("鼠标钩子设置失败")
            
            self._running = True
            
            # 启动消息循环线程
            self.hook_thread = threading.Thread(target=self._run_message_loop)
            self.hook_thread.daemon = True  # 修复：使用daemon线程
            self.hook_thread.start()
            
        except Exception as e:
            self.cleanup()  # 异常时清理资源
            raise
    
    def cleanup(self):
        """清理所有资源 - 保证调用"""
        self._running = False
        
        # 清理钩子
        if self.hook_id:
            try:
                user32.UnhookWindowsHookEx(self.hook_id)
            except Exception:
                pass  # 忽略清理时的异常
            self.hook_id = None
        
        # 终止钩子线程
        if self.hook_thread and self.hook_thread.is_alive():
            # 使用事件通知线程退出
            # 注意：这里需要一个退出事件机制
            pass
            
    # ===== 修复：添加析构方法 =====
    def __del__(self):
        """析构时确保清理资源"""
        self.cleanup()
    # ===============================
```

---

## 3. 异常处理改进

### 修复位置: `src/mining.py`

```python
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class SingleWindowMiner:
    """单窗口挖矿器 - 改进异常处理"""
    
    def find_and_click(self, image_name: str, confidence: float = 0.8) -> bool:
        """查找并点击图片 - 改进版
        
        Returns:
            bool: 点击成功返回True，未找到返回False
        """
        try:
            # 尝试查找图片
            pos = self.matcher.find_image(
                image_name,
                self.screenshot,
                confidence
            )
            
            if pos:
                self.click_at(pos[0], pos[1])
                logger.info(f"成功点击: {image_name}")
                return True
            else:
                logger.debug(f"未找到图片: {image_name}")
                return False
                
        except cv2.error as e:
            # ===== 修复：具体异常具体处理 =====
            logger.error(f"OpenCV错误(图片:{image_name}): {e}")
            return False
        except Exception as e:
            logger.critical(f"未知错误(图片:{image_name}): {e}", exc_info=True)
            return False
        # =====================================
    
    def _mining_loop(self):
        """挖矿循环 - 改进异常处理"""
        try:
            while self.is_mining and not self._stop_event.is_set():
                # 挖矿逻辑...
                pass
                
        except KeyboardInterrupt:
            logger.info("挖矿被用户中断")
        except Exception as e:
            # ===== 修复：记录完整堆栈 =====
            logger.critical(f"挖矿循环异常: {e}", exc_info=True)
            # ==============================
        finally:
            # ===== 修复：确保状态重置 =====
            self.is_mining = False
            # ==============================
```

---

## 4. 配置文件增强

### 修复位置: `src/config.py`

```python
import json
from pathlib import Path
from typing import Any, Dict, Optional

class Settings:
    """配置管理类 - 增强版"""
    
    DEFAULT_CONFIG = {
        "window": {
            "target_width": 800,
            "target_height": 600,
            "minimize_on_start": False
        },
        "mining": {
            "retry_times": 3,
            "retry_delay": 2,
            "screenshot_interval": 0.1,
            "level8_target_base": (339, 844),
            "level8_tolerance": 1,
            "resource_order": ["meat", "wood", "coal", "iron"]
        },
        "protective_casing": {
            "base_width": 558,
            "base_height": 1021,
            "deploy_relative_x": 33,
            "deploy_relative_y": 132
        },
        "logging": {
            "level": "INFO",
            "file": "logs/mining.log",
            "max_bytes": 10 * 1024 * 1024,
            "backup_count": 5
        },
        "ocr": {
            "enabled": True,
            "confidence_threshold": 0.65
        }
    }
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self._config: Dict[str, Any] = {}
        self._load_config()
        
    def _load_config(self):
        """加载配置文件"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                # 合并默认配置和用户配置
                self._config = self._merge_config(
                    self.DEFAULT_CONFIG, 
                    user_config
                )
            except json.JSONDecodeError as e:
                print(f"配置文件格式错误: {e}, 使用默认配置")
                self._config = self.DEFAULT_CONFIG.copy()
        else:
            # 使用默认配置并保存
            self._config = self.DEFAULT_CONFIG.copy()
            self._save_config()
    
    def _merge_config(self, default: Dict, user: Dict) -> Dict:
        """递归合并配置"""
        result = default.copy()
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """获取配置值，支持点分隔路径
        
        Example:
            settings.get('mining.retry_times')  # 返回 3
        """
        keys = key_path.split('.')
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        return value
    
    def set(self, key_path: str, value: Any):
        """设置配置值"""
        keys = key_path.split('.')
        config = self._config
        for key in keys[:-1]:
            config = config.setdefault(key, {})
        config[keys[-1]] = value
    
    def _save_config(self):
        """保存配置到文件"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=4, ensure_ascii=False)


# 全局配置实例
settings = Settings()
```

---

## 5. 日志管理统一

### 新建文件: `src/utils/logger.py`

```python
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class LoggerManager:
    """统一的日志管理器"""
    
    _instance: Optional['LoggerManager'] = None
    _loggers = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # 配置根日志器
        self._setup_root_logger()
    
    def _setup_root_logger(self):
        """配置根日志器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # 清除已有的处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(self._get_formatter("console"))
        
        # 文件处理器（带轮转）
        file_handler = RotatingFileHandler(
            self.log_dir / "app.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(self._get_formatter("file"))
        
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
    
    def _get_formatter(self, handler_type: str) -> logging.Formatter:
        """获取格式化器"""
        if handler_type == "console":
            return logging.Formatter(
                '%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%H:%M:%S'
            )
        else:
            return logging.Formatter(
                '%(asctime)s [%(name)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
    
    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志器"""
        if name not in self._loggers:
            self._loggers[name] = logging.getLogger(name)
        return self._loggers[name]


# 全局日志管理器
logger_manager = LoggerManager()


def get_logger(name: str) -> logging.Logger:
    """获取日志器的便捷函数"""
    return logger_manager.get_logger(name)
```

---

## 6. GUI日志方法改进

### 修复位置: `src/gui.py`

```python
import logging
from utils.logger import get_logger

class GameAutomationGUI:
    """GUI主类 - 改进日志输出"""
    
    def __init__(self):
        # ... 其他初始化 ...
        
        # ===== 使用统一的日志管理器 =====
        self.logger = get_logger("gui")
        # =================================
        
        # 保留GUI特有的日志显示到Text控件
        self.gui_log_callback = None
        
    def log(self, message: str, level: str = "info"):
        """输出日志 - 同时输出到GUI和控制台
        
        Args:
            message: 日志消息
            level: 日志级别 (debug/info/warning/error/critical)
        """
        # 控制台/文件日志
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message)
        
        # GUI显示
        if hasattr(self, 'log_text') and self.log_text.winfo_exists():
            timestamp = time.strftime('%H:%M:%S')
            self.log_text.insert("end", f"[{timestamp}] {message}\n")
            self.log_text.see("end")
        
        # 回调（用于测试）
        if self.gui_log_callback:
            self.gui_log_callback(message, level)
```

---

## 使用说明

1. **线程安全问题**：在 `mining.py` 中添加 `threading.RLock()` 保护共享状态
2. **资源泄漏**：在 `recording.py` 中使用 `atexit.register()` 确保清理
3. **异常处理**：为每个异常处理添加具体异常类型和堆栈记录
4. **配置管理**：用 `config.py` 的增强版替代原配置
5. **日志统一**：使用 `utils/logger.py` 统一日志输出

---

**注意**: 这些修复代码需要您手动应用到源文件中，或者创建新版本替换旧代码。