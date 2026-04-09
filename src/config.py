"""
无尽冬日 (Wujindongri) - 配置文件
"""

from typing import Any, Dict, Optional


VERSION = "1.0.0"


class Settings:
    """配置类"""
    
    def __init__(self) -> None:
        self.VERSION: str = VERSION
        self.LOG_LEVEL: str = "INFO"
        self.IMAGE_MATCH_CONFIDENCE: float = 0.65
        self.CLICK_DELAY_MIN: float = 0.1
        self.CLICK_DELAY_MAX: float = 0.3
        self.WINDOW_ACTIVATE_TIMEOUT: float = 1.0


settings = Settings()
