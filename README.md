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
- ✅ **多格式支持**：支持 ZIP、tar、tar.gz、tar.bz2、tar.xz、tar.zst、7z 七种打包格式，全局和条目级均可独立指定
- ✅ **备份还原**：支持从备份文件解压还原到指定目录
- ✅ **备份清理**：自动删除旧备份，仅保留最近 N 个文件
- ✅ **加密备份**：支持 7z 格式密码加密
- ✅ **定时备份**：设置间隔自动执行，实现无人值守
- ✅ **备份历史**：记录每次备份的时间、大小和文件数，方便追溯
- ✅ **灵活的策略管理**：支持添加、删除和查看备份策略
- ✅ **自定义配置**：支持通过 `config.json` 自定义压缩算法、忽略模式等
- ✅ **国际化**：支持中文、英语、法语、西班牙语、俄语、德语、日语、葡萄牙语、韩语九种语言，可随时切换
- ✅ **轻量高效**：体积小，启动速度快，资源占用低
- ✅ **跨平台支持**：支持 Windows、macOS 和 Linux

## 快速开始

### 安装

#### 使用 uv 安装

```bash
uv pip install sbackup
```

#### 从源码安装

```bash
git clone https://gitee.com/xiatianxuan/sbackup.git
cd sbackup
uv sync
```

### 使用方法

#### 基本语法

```bash
uv run python main.py <command> [options]
```

#### 可用命令

| 命令 | 描述 |
|------|------|
| `add` | 添加备份策略 |
| `rm` 或 `remove` | 删除备份策略 |
| `all` | 查看所有备份策略 |
| `save` | 执行备份 |
| `watch` | 定时执行备份 |
| `restore` | 从备份文件还原 |
| `version` | 查看版本信息 |
| `help` | 查看帮助信息 |

#### 全局参数

| 参数 | 描述 |
|------|------|
| `--lang zh_CN` / `en_US` / `fr_FR` / `es_ES` / `ru_RU` / `de_DE` / `ja_JP` / `pt_BR` / `ko_KR` | 设置界面语言（持久化到 config.json） |
| `--format zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z` | 设置打包格式（持久化到 config.json） |
| `--debug` | 开启调试日志 |

#### 添加备份策略

```bash
uv run python main.py add <source> <dest> [-i ignore_patterns]
```

参数说明：
- **source**：需要备份的源文件夹路径
- **dest**：备份文件存放的目标路径
- **-i, --ignore**：需要忽略的文件或文件夹名称，使用逗号分隔（默认：`.git,__pycache__`）
- **--format**：条目级打包格式（仅作用于该备份策略，不指定则使用全局默认）：`zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z`

示例：
```bash
# 使用全局默认格式添加策略
uv run python main.py add F:/my_folder F:/backup -i node_modules,.git

# 为该策略指定 tar.gz 格式（每次备份此文件夹都使用 tar.gz）
uv run python main.py add F:/my_folder F:/backup --format tar.gz

# 指定 7z 格式（仅此文件夹）
uv run python main.py add F:/my_folder F:/backup --format 7z
```

#### 删除备份策略

```bash
uv run python main.py rm <path>
```

参数说明：
- **path**：需要删除备份策略的源文件夹路径

示例：
```bash
uv run python main.py rm F:/my_folder
```

#### 查看所有备份策略

```bash
uv run python main.py all
```

显示当前所有已配置的备份策略。

#### 执行备份

```bash
# 使用默认格式（ZIP）
uv run python main.py save

# 使用 tar.gz 格式
uv run python main.py --format tar.gz save

# 保留最近 5 个备份文件，自动清理旧的
uv run python main.py save --keep 5

# 使用 7z 格式并加密
uv run python main.py --format 7z save --password mysecret

# 英文界面 + tar.xz 格式
uv run python main.py --lang en_US --format tar.xz save
```

**save 命令参数：**

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `--keep N` | `0` | 保留最近 N 个备份文件，0 表示不清理 |
| `--password PASSWORD` | `""` | 加密密码（仅 7z 格式支持） |

根据备份策略，自动备份已更改的文件夹。

#### 定时备份

```bash
# 每 60 分钟执行一次备份
uv run python main.py watch --interval 60

# 每 2 小时备份一次，保留最近 10 个文件
uv run python main.py watch --interval 120 --keep 10

# 定时备份 + 7z 加密
uv run python main.py --format 7z watch --interval 60 --password mysecret
```

**watch 命令参数：**

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `--interval MINUTES` | `60` | 备份间隔（分钟） |
| `--keep N` | `0` | 保留最近 N 个备份文件 |
| `--password PASSWORD` | `""` | 加密密码（仅 7z 格式支持） |

按 `Ctrl+C` 停止定时备份。

#### 还原备份

```bash
uv run python main.py restore <backup_file> <target_dir>
```

参数说明：
- **backup_file**：备份文件路径（支持 .zip / .tar / .tar.gz / .tar.bz2 / .tar.xz / .tar.zst / .7z）
- **target_dir**：还原目标目录

示例：
```bash
uv run python main.py restore F:/backup/my_folder.tar.gz F:/restored
uv run python main.py restore F:/backup/my_folder.7z F:/restored
uv run python main.py restore F:/backup/my_folder.tar.zst F:/restored
```

#### 查看版本信息

```bash
uv run python main.py version
```

## 配置文件

Sbackup 支持通过 `config.json` 文件进行自定义配置。配置文件应放在项目根目录下。

### 配置项说明

```json
{
  "compression_format": "ZIP",
  "compression": {
    "algorithm": "ZIP_DEFLATED",
    "level": 6
  },
  "skip_patterns": [".git", "__pycache__"],
  "data_file": "sbackup.json",
  "lang": "zh_CN",
  "password": ""
}
```

| 配置项 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `compression_format` | string | `"ZIP"` | 打包格式，可选值：`ZIP`, `TAR`, `TAR_GZ`, `TAR_BZ2`, `TAR_XZ`, `TAR_ZST`, `7Z` |
| `compression.algorithm` | string | `"ZIP_DEFLATED"` | ZIP 压缩算法，可选值：`ZIP_DEFLATED`, `ZIP_STORED`, `ZIP_BZIP2`, `ZIP_LZMA` |
| `compression.level` | int | `6` | 压缩级别，范围 0-9（0 为不压缩，9 为最高压缩） |
| `skip_patterns` | list | `[".git", "__pycache__"]` | 需要忽略的文件或文件夹模式（支持 fnmatch 通配符和路径匹配） |
| `data_file` | string | 平台默认路径 | 备份策略数据文件的存放路径 |
| `lang` | string | `"zh_CN"` | 界面语言，可选值：`zh_CN`, `en_US`, `fr_FR`, `es_ES`, `ru_RU`, `de_DE`, `ja_JP`, `pt_BR`, `ko_KR` |
| `password` | string | `""` | 7z 加密密码 |

### 示例配置

使用 tar.bz2 格式进行高压缩率备份：

```json
{
  "compression_format": "TAR_BZ2",
  "compression_level": 9,
  "skip_patterns": [".git", "__pycache__", "node_modules", "*.log"],
  "data_file": "backup_strategies.json",
  "lang": "zh_CN"
}
```

### 打包格式对比

| 格式 | 扩展名 | 压缩率 | 速度 | 依赖 | 适用场景 |
|------|--------|--------|------|------|----------|
| ZIP | .zip | 中 | 快 | 标准库 | 通用，Windows 兼容性最好 |
| tar | .tar | 无 | 极快 | 标准库 | 纯归档，配合外部压缩 |
| tar.gz | .tar.gz | 中 | 快 | 标准库 | Linux/macOS 通用 |
| tar.bz2 | .tar.bz2 | 高 | 中 | 标准库 | 高压缩率归档 |
| tar.xz | .tar.xz | 最高 | 慢 | 标准库 | 长期归档，空间敏感 |
| tar.zst | .tar.zst | 中高 | 极快 | zstandard | 现代场景，速度与压缩率平衡 |
| 7z | .7z | 极高 | 慢 | py7zr | 最高压缩率，支持加密 |

## 实现原理

Sbackup 通过以下方式实现备份功能：

1. **备份策略存储**：备份策略存储在 JSON 文件中，包含文件夹路径、最后修改时间、目标路径、忽略模式和条目级打包格式。
2. **增量备份**：通过比较文件夹的最后修改时间，仅备份已更改的文件夹。
3. **多格式压缩**：使用 Python 内置的 `zipfile` 和 `tarfile` 模块，以及 `zstandard` 和 `py7zr` 第三方库，支持 7 种打包格式。
4. **条目级格式**：每个备份策略可指定独立的打包格式（`add --format`），优先于全局 `--format` 设置；未指定时使用全局默认。
5. **备份清理**：备份成功后自动扫描目标目录，按修改时间排序，删除超出保留数量的旧文件。
6. **加密备份**：7z 格式支持 LZMA2 加密，通过 `--password` 参数或 `config.json` 配置。
7. **定时备份**：`watch` 命令在循环中按指定间隔执行备份，`Ctrl+C` 安全退出。
8. **备份历史**：每次备份后记录时间戳、文件大小和文件数量，保留最近 100 条记录。

### 数据文件格式

```json
{
  "/path/to/source/folder": [
    1719235200.0,
    "/path/to/target/folder",
    [".git", "__pycache__"],
    ""
  ],
  "/path/to/another/folder": [
    1719235200.0,
    "/path/to/another/target",
    [".git"],
    "TAR_GZ"
  ],
  "_history": [
    {
      "time": "2026-05-01T12:00:00",
      "source": "/path/to/source/folder",
      "size_mb": 12.5,
      "files_count": 150
    }
  ]
}
```

每个备份策略条目为 4 元素列表：`[mtime, target, skip_patterns, compression_format]`

| 字段 | 说明 |
|------|------|
| `mtime` | 源文件夹最后修改时间（用于增量备份判断） |
| `target` | 备份文件存放的目标路径 |
| `skip_patterns` | 需忽略的文件/文件夹模式列表 |
| `compression_format` | 条目级打包格式（空字符串表示使用全局默认） |

## 开发指南

### 运行测试

```bash
uv run coverage run -m unittest discover -s tests -t . && uv run coverage report -m
```

### 代码结构

```
sbackup/
├── main.py              # 程序入口
├── sbackup/
│   ├── __init__.py      # CLI 参数解析和命令分发
│   ├── __main__.py      # python -m sbackup 入口
│   ├── config.py        # 配置加载、语言持久化、数据路径
│   ├── compression.py   # ZIP / TAR 压缩功能实现
│   ├── auto_save.py     # 备份策略管理 + 备份历史
│   └── i18n.py          # 国际化支持
├── tests/
│   └── sbackup/
│       ├── test_auto_save.py   # 备份策略测试
│       ├── test_compression.py # 压缩功能测试
│       ├── test_config.py      # 配置加载测试
│       ├── test_i18n.py        # 国际化测试
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

A: 备份策略存储在数据文件中。如果误删，可以通过重新运行 `add` 命令重新添加备份策略。

### Q: 如何修改已添加的备份策略？

A: 目前不支持直接修改备份策略。你可以先使用 `rm` 删除旧的策略，再使用 `add` 添加新的策略。

### Q: 支持远程备份吗？

A: 目前仅支持本地备份。远程备份功能正在开发中。

### Q: tar.gz 和 ZIP 有什么区别？

A: tar.gz 在 Linux/macOS 上更常用，压缩率略高；ZIP 在 Windows 上更通用，兼容性最好。tar.bz2 和 tar.xz 提供更高的压缩率但速度较慢。tar.zst 是现代算法，速度极快且压缩率不错。7z 压缩率最高且支持加密。

### Q: 如何加密备份？

A: 使用 7z 格式并设置密码：`uv run python main.py --format 7z save --password yourpassword`。密码也可以写入 `config.json` 的 `password` 字段。

### Q: 如何自动清理旧备份？

A: 使用 `--keep` 参数：`uv run python main.py save --keep 5` 只保留最近 5 个备份文件。定时备份时同样支持：`uv run python main.py watch --interval 60 --keep 10`。

### Q: 如何设置定时备份？

A: 使用 `watch` 命令：`uv run python main.py watch --interval 60` 每 60 分钟备份一次。按 `Ctrl+C` 停止。

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

*最后更新：2026年5月1日*