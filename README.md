# 无尽冬日 (Wujindongri)

无尽冬日游戏挂机系统 - 基于图像识别的游戏自动化工具

## 功能特点

- **多窗口挖矿**: 支持同时管理多个游戏窗口自动挖矿
- **保护性外壳**: 自动检测并处理war保护机制
- **雪域兵器联赛**: 自动完成雪域兵器联赛活动
- **每日任务**: 自动执行每日任务
- **OCR识别**: 自动识别游戏内资源数量
- **坐标记录**: 可视化记录游戏内点击坐标

## 技术栈

- Python 3.8+
- OpenCV (图像识别)
- tkinter (GUI界面)
- win32gui (窗口管理)
- RapidOCR (文字识别)
- pyautogui (鼠标控制)

## 安装要求

- Python 3.8+
- Windows 操作系统
- 依赖包: `requirements.txt`

## 安装步骤

1. 克隆项目
```bash
git clone <repository-url>
cd wujindongri
```

2. 创建虚拟环境（推荐）
```bash
python -m venv venv
venv\Scripts\activate
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 运行程序
```bash
python run.py
```

## 使用说明

1. 启动程序后，窗口列表会自动刷新显示可用的游戏窗口
2. 选中要操作的游戏窗口，点击相应功能按钮
3. 支持多窗口同时挖矿，自动轮换
4. 所有窗口挖矿完成后自动进入保护性外壳检测模式

## 项目结构

```
wujindongri/
├── src/                          # 源代码
│   ├── __init__.py
│   ├── main.py                   # 主程序入口
│   ├── gui.py                    # GUI界面
│   ├── mining.py                 # 挖矿模块
│   ├── Protective_casing.py      # 保护性外壳
│   ├── snowfield_weapon_league.py # 雪域兵器联赛
│   ├── daily_task.py             # 每日任务
│   ├── window_manager.py         # 窗口管理
│   ├── recording.py              # 坐标记录
│   ├── dashed_line_detector.py   # 虚线检测
│   ├── config.py                 # 配置管理
│   ├── config/
│   │   └── settings.py           # 配置设置
│   └── utils/                    # 工具函数
│       ├── adaptive_matcher.py    # 自适应图像匹配
│       ├── screenshot_cache.py   # 截图缓存
│       ├── window_utils.py        # 窗口工具
│       └── red_dot_detector.py   # 红点检测
├── pic/                          # 图片资源
├── logs/                         # 日志文件
├── docs/                         # 文档
├── tests/                        # 测试文件
├── README.md                     # 项目说明
└── requirements.txt              # 依赖列表
```

## 配置说明

配置文件位于 `src/config/settings.py`，可以修改以下设置:

- 日志级别
- 图像匹配置信度
- 其他应用设置

## 注意事项

- 本工具仅用于学习和研究，请勿用于商业用途
- 使用时请确保游戏窗口可见
- 部分功能可能需要管理员权限

## 许可证

MIT License

## 版本历史

### v1.0.0 (2026-03-19)
- 初始版本发布
- 多窗口挖矿功能
- 保护性外壳自动化
- 雪域兵器联赛
- 每日任务
- OCR文字识别
