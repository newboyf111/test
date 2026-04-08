#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打包项目成exe脚本
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def build_exe():
    """打包成exe"""
    project_root = Path(__file__).parent
    src_dir = project_root / "src"
    pic_dir = project_root / "pic"
    venv_python = project_root / "venv" / "Scripts" / "python.exe"
    
    # 检查虚拟环境中的Python
    if not venv_python.exists():
        print(f"错误: 虚拟环境中的Python不存在: {venv_python}")
        print("请先创建虚拟环境并安装依赖")
        return False
    
    # 检查PyInstaller是否安装
    try:
        subprocess.run([str(venv_python), "-m", "pip", "show", "pyinstaller"], 
                      capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("正在安装PyInstaller...")
        subprocess.run([str(venv_python), "-m", "pip", "install", "pyinstaller"], 
                      capture_output=True, check=True)
    
    # 清理旧的构建文件
    build_dir = project_root / "build"
    dist_dir = project_root / "dist"
    
    if build_dir.exists():
        print(f"清理旧的build目录: {build_dir}")
        shutil.rmtree(build_dir)
    
    if dist_dir.exists():
        print(f"清理旧的dist目录: {dist_dir}")
        shutil.rmtree(dist_dir)
    
    # 创建构建命令
    main_script = project_root / "run.py"
    exe_name = "无尽冬日"
    
    # PyInstaller命令
    cmd = [
        str(venv_python),
        "-m", "PyInstaller",
        "--name", exe_name,
        "--windowed",
        "--onefile",
        "--clean",
        "--add-data", f"src{os.pathsep}src",
        "--add-data", f"pic{os.pathsep}pic",
        str(main_script)
    ]
    
    if (pic_dir / "icon.ico").exists():
        cmd.extend(["--icon", str(pic_dir / "icon.ico")])
    
    print(f"开始打包exe...")
    print(f"命令: {' '.join(cmd)}")
    
    # 执行打包
    result = subprocess.run(cmd, cwd=str(project_root), shell=True)
    
    if result.returncode == 0:
        print(f"\n打包成功!")
        print(f"exe文件位置: {dist_dir / f'{exe_name}.exe'}")
        print(f"文件大小: {(dist_dir / f'{exe_name}.exe').stat().st_size / 1024 / 1024:.2f} MB")
        return True
    else:
        print(f"\n打包失败! 退出码: {result.returncode}")
        return False

if __name__ == "__main__":
    success = build_exe()
    sys.exit(0 if success else 1)
