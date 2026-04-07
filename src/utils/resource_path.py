#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资源路径处理模块 - 支持PyInstaller打包后的资源路径
"""

import sys
import os
from pathlib import Path


def get_resource_path(relative_path: str) -> str:
    """
    获取资源文件的绝对路径
    
    在开发环境中，返回项目根目录下的相对路径
    在PyInstaller打包后，返回临时目录中的路径
    
    Args:
        relative_path: 相对于项目根目录的路径
        
    Returns:
        资源文件的绝对路径
    """
    if hasattr(sys, '_MEIPASS'):
        base_path = Path(sys._MEIPASS)
    else:
        # __file__ = src/utils/resource_path.py
        # parent = src/utils/, parent.parent = src/, parent.parent.parent = 项目根目录
        base_path = Path(__file__).parent.parent.parent
    
    return str(base_path / relative_path)


def get_pic_path(image_name: str) -> str:
    """
    获取pic文件夹中图片的路径
    
    Args:
        image_name: 图片文件名
        
    Returns:
        图片的绝对路径
    """
    return get_resource_path(f"pic/{image_name}")
