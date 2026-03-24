# 无尽冬日 (Wujindongri)

无尽冬日管理系统 - 一个用于五金行业的综合管理系统

## 功能特点

- 项目管理
- 库存管理
- 销售管理
- 客户管理
- 报表统计

## 安装要求

- Python 3.8+
- 依赖包: `requirements.txt`

## 安装步骤

1. 克隆项目
```bash
git clone <repository-url>
cd wujindongri
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 运行程序
```bash
python -m src
```

## 项目结构

```
wujindongri/
├── src/              # 源代码
│   ├── __init__.py
│   ├── main.py       # 主程序入口
│   └── core.py       # 核心模块
├── config/           # 配置文件
│   ├── __init__.py
│   └── settings.py   # 配置设置
├── docs/             # 文档
├── tests/            # 测试文件
├── logs/             # 日志文件
├── README.md         # 项目说明
└── requirements.txt  # 依赖列表
```

## 配置说明

配置文件位于 `config/settings.py`，可以修改以下设置:

- 数据库连接
- 服务器端口
- 日志级别
- 其他应用设置

## 许可证

MIT License

## 作者

YourName

## 版本历史

### v1.0.0 (2026-03-19)
- 初始版本发布