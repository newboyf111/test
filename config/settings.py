"""
无尽冬日 (Wujindongri) - 配置文件
"""

# 版本信息
VERSION = "1.0.0"
AUTHOR = "YourName"

# 应用设置
APP_NAME = "无尽冬日"
APP_TITLE = "无尽冬日管理系统"

# 日志设置
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 数据库设置
DATABASE = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "wujindongri"
}

# 服务器设置
SERVER = {
    "host": "0.0.0.0",
    "port": 8080
}

# 其他配置
CONFIG = {
    "debug": False,
    "max_connections": 100,
    "timeout": 30
}
