#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动脚本
"""

import sys
import os
import io
from pathlib import Path

# 设置控制台编码为UTF-8
if sys.stdout:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 获取项目根目录
project_root = Path(__file__).parent

# 只在开发环境中添加虚拟环境的site-packages路径
if not hasattr(sys, '_MEIPASS'):
    venv_site_packages = project_root / "venv" / "Lib" / "site-packages"
    if venv_site_packages.exists():
        sys.path.insert(0, str(venv_site_packages))

# 添加 src 目录到路径
if hasattr(sys, '_MEIPASS'):
    sys.path.insert(0, str(Path(sys._MEIPASS) / "src"))
else:
    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(project_root / "src"))

# 导入并运行主程序
from src.main import main

if __name__ == "__main__":
    main()
