# Sbackup: 智能文件夹备份工具

一个轻量、高效的文件夹备份工具，支持命令行操作，帮助你轻松管理备份策略。

## 📖 目录

- [简介](#简介)
- [功能特性](#功能特性)
- [快速开始](#快速开始)
  - [安装](#安装)
  - [使用方法](#使用方法)
- [配置文件](#配置文件)
- [实现原理](#实现原理)
- [开发指南](#开发指南)
  - [运行测试](#运行测试)
  - [代码结构](#代码结构)
- [常见问题](#常见问题)
- [贡献指南](#贡献指南)
- [许可证](#许可证)
- [作者](#作者)

---

## 简介

Sbackup 是一个轻量级的文件夹备份工具，支持通过命令行添加、删除和查看备份策略。它基于文件夹的最后修改时间来决定是否需要进行备份，确保你的数据始终保持最新状态。

## 功能特性

- ✅ **增量备份**：仅备份已更改的文件夹，节省时间和存储空间
- ✅ **灵活的策略管理**：支持添加、删除和查看备份策略
- ✅ **自定义配置**：支持通过 `config.json` 自定义压缩算法、忽略模式等
- ✅ **轻量高效**：体积小，启动速度快，资源占用低
- ✅ **跨平台支持**：支持 Windows、macOS 和 Linux

## 快速开始

### 安装

#### 使用 pip 安装

```bash
pip install sbackup
```

#### 从源码安装

```bash
git clone https://github.com/yourusername/sbackup.git
cd sbackup
pip install -e .
```

### 使用方法

#### 基本语法

```bash
sbackup <command>
```

#### 可用命令

| 命令 | 描述 |
|------|------|
| `add` | 添加备份策略 |
| `rm` 或 `remove` | 删除备份策略 |
| `all` | 查看所有备份策略 |
| `save` | 执行备份 |
| `version` | 查看版本信息 |
| `help` | 查看帮助信息 |

#### 添加备份策略

```bash
sbackup add
```

运行后，程序会提示你输入：
- **备份文件夹**：需要备份的文件夹路径
- **目标文件夹**：备份文件存放的目标路径
- **需要忽略的文件夹或文件**：用逗号分隔，例如 `.git,__pycache__,node_modules`

#### 删除备份策略

```bash
sbackup rm
```

运行后，程序会提示你输入需要删除备份策略的目标文件夹路径。

#### 查看所有备份策略

```bash
sbackup all
```

显示当前所有已配置的备份策略。

#### 执行备份

```bash
sbackup save
```

根据备份策略，自动备份已更改的文件夹。

#### 查看版本信息

```bash
sbackup version
```

## 配置文件

Sbackup 支持通过 `config.json` 文件进行自定义配置。配置文件应放在项目根目录下。

### 配置项说明

```json
{
  "compression": {
    "algorithm": "ZIP_DEFLATED",
    "level": 6
  },
  "skip_patterns": [".git", "__pycache__"],
  "data_file": "sbackup.json"
}
```

| 配置项 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `compression.algorithm` | string | `"ZIP_DEFLATED"` | 压缩算法，可选值：`ZIP_DEFLATED`, `ZIP_STORED`, `ZIP_BZIP2`, `ZIP_LZMA` |
| `compression.level` | int | `6` | 压缩级别，范围 0-9（0 为不压缩，9 为最高压缩） |
| `skip_patterns` | list | `[".git", "__pycache__"]` | 需要忽略的文件或文件夹模式 |
| `data_file` | string | `"sbackup.json"` | 备份策略数据文件的存放路径 |

### 示例配置

使用 `ZIP_BZIP2` 算法进行压缩：

```json
{
  "compression": {
    "algorithm": "ZIP_BZIP2",
    "level": 9
  },
  "skip_patterns": [".git", "__pycache__", "node_modules", "*.log"],
  "data_file": "backup_strategies.json"
}
```

## 实现原理

Sbackup 通过以下方式实现备份功能：

1. **备份策略存储**：备份策略存储在 `sbackup.json` 文件中，包含文件夹路径、最后修改时间、目标路径和忽略模式。
2. **增量备份**：通过比较文件夹的最后修改时间，仅备份已更改的文件夹。
3. **压缩备份**：使用 Python 内置的 `zipfile` 模块进行压缩，支持多种压缩算法。

### 数据文件格式

```json
{
  "/path/to/source/folder": [
    1719235200.0,  // 最后修改时间戳
    "/path/to/target/folder",  // 目标备份路径
    [".git", "__pycache__"]  // 忽略模式
  ]
}
```

## 开发指南

### 运行测试

```bash
python -m unittest discover -s tests -t .
```

### 代码结构

```
sbackup/
├── main.py              # 程序入口
├── sbackup/
│   ├── __init__.py      # 主模块，处理命令行参数
│   ├── _compression.py  # 压缩功能实现
│   └── auto_save.py     # 备份策略管理
├── tests/
│   └── sbackup/
│       ├── test_auto_save.py   # 备份策略测试
│       ├── test_compression.py # 压缩功能测试
│       └── test_main.py        # 主模块测试
├── config.json          # 配置文件
└── README.md            # 文档
```

### 添加新功能

1. 在 `sbackup/` 目录下创建新的模块文件
2. 在 `sbackup/__init__.py` 中导入新功能的函数
3. 在 `run()` 函数中添加新的命令行命令处理逻辑
4. 在 `tests/` 目录下添加对应的测试文件

## 常见问题

### Q: 备份策略文件被误删了怎么办？

A: 备份策略存储在 `sbackup.json` 文件中。如果误删，可以通过重新运行 `sbackup add` 命令重新添加备份策略。

### Q: 如何修改已添加的备份策略？

A: 目前不支持直接修改备份策略。你可以先使用 `sbackup rm` 删除旧的策略，再使用 `sbackup add` 添加新的策略。

### Q: 支持远程备份吗？

A: 目前仅支持本地备份。远程备份功能正在开发中。

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

### 代码风格

本项目遵循 PEP 8 和 Google Python Style Guide。请确保你的代码：
- 使用类型注解
- 遵循 Google 风格的 docstrings
- 通过所有单元测试

## 许可证

本项目采用 GNU GPL v3.0 许可证。详情请参阅 [LICENSE](LICENSE) 文件。

## 作者

**xiatianxuan** (CodeSeed)

- [Gitee](https://gitee.com/xiatianxuan)
- [个人主页](https://xnors-codeseed.pages.dev/)

## 特别鸣谢

- [Xnors Studio](https://xnors.github.io/)

## 联系我们

如有问题或建议，请发送邮件至：xiatianxuan2025@163.com

---

*最后更新：2026年4月25日*