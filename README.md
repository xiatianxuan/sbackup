# Sbackup

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0-green)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/sbackup-cli?color=blue)](https://pypi.org/project/sbackup-cli/)
[![Tests](https://img.shields.io/badge/tests-940%20passed-brightgreen)](.github/workflows/ci.yml)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

> A lightweight, efficient folder backup tool with CLI support for managing backup strategies.

[English](README.md) | [Deutsch](docs/readme/README_de.md) | [Espanol](docs/readme/README_es.md) | [Francais](docs/readme/README_fr.md) | [Portugues](docs/readme/README_pt.md) | [Pycckuu](docs/readme/README_ru.md) | [日本語](docs/readme/README_ja.md) | [한국어](docs/readme/README_ko.md) | [中文](docs/readme/README_zh.md)

- [Introduction](#introduction)
- [Features](#features)
- [Getting Started](#getting-started)
  - [Installation](#installation)
  - [Usage](#usage)
- [Configuration](#configuration)
  - [Example Configuration](#example-configuration)
- [SFTP Remote Backup](#sftp-remote-backup)
- [WebDAV Remote Backup](#webdav-remote-backup)
- [How It Works](#how-it-works)
- [Development Guide](#development-guide)
  - [Running Tests](#running-tests)
  - [Code Structure](#code-structure)
- [FAQ](#faq)
- [Contributing](#contributing)
- [License](#license)
- [Author](#author)

---

## Introduction

Sbackup is a lightweight folder backup tool that lets you add, remove, and manage backup strategies from the command line. It uses each folder's last-modified timestamp to determine whether a backup is needed, keeping your data up to date.

## Features

- **Incremental backup** -- only folders that have changed are backed up, saving time and storage
- **Multi-format support** -- ZIP, tar, tar.gz, tar.bz2, tar.xz, tar.zst, 7z; both global and per-entry format overrides
- **SFTP remote backup** -- built on paramiko with password/SSH key authentication and auto-detection of default keys
- **WebDAV remote backup** -- uses Python's standard library urllib with zero extra dependencies; works with Jianguoyun, NextCloud, and Synology
- **S3 cloud storage** -- powered by minio, supports all S3-compatible backends (AWS, MinIO, Alibaba Cloud OSS, etc.)
- **Multi-destination parallel backup** -- back up to local and multiple remote targets simultaneously
- **Restore** -- extract backups to a target directory with optional selective recovery
- **Backup cleanup** -- automatically delete old backups by count, age, or daily retention policy
- **Encrypted backup** -- 7z password encryption plus PBKDF2 encryption for all formats
- **Scheduled backup** -- run backups on a fixed interval or monitor the filesystem in real time with watchdog
- **Backup history** -- timestamps, file sizes, and SHA256 checksums recorded for every backup
- **Audit log** -- audit events for all backup and restore operations
- **Pre/Post hooks** -- run custom commands before or after backups
- **Configuration profiles** -- save, switch, import, and export multiple configuration profiles
- **Cross-archive search** -- search for matching filenames across multiple backup archives
- **Data integrity** -- SHA256 checksum generation and verification, Reed-Solomon error correction codes
- **Config validation** -- automatic validation of configuration parameters with tamper detection
- **Task queue** -- manage backup tasks with add, execute, and cancel operations
- **Compression benchmark** -- compare compression performance across formats and levels
- **Disk space estimation** -- estimate backup size by file type and check destination space
- **Internationalization** -- nine languages: Chinese, English, French, Spanish, Russian, German, Japanese, Portuguese, Korean
- **Shell completion** -- auto-completion for bash, zsh, fish, and PowerShell
- **Lightweight and efficient** -- small footprint, fast startup, low resource usage
- **Cross-platform** -- Windows, macOS, and Linux

## Getting Started

### Installation

#### Install with pip

```bash
pip install sbackup-cli
```

After installation, use the `sbackup` command (PyPI package name is `sbackup-cli`, CLI command is `sbackup`).

#### Install from source

```bash
git clone https://github.com/xiatianxuan/sbackup.git
cd sbackup
uv sync
```

### Usage

#### Basic syntax

```bash
uv run python main.py <command> [options]
```

#### Available commands

| Command | Description |
|---------|-------------|
| `add` | Add a backup strategy |
| `rm` / `remove` | Remove a backup strategy |
| `edit` | Edit an existing backup strategy |
| `all` | List all backup strategies |
| `save` | Run backup |
| `watch` | Run backup on a schedule |
| `restore` | Restore from a backup file |
| `info` | View backup file details |
| `diff` | Compare source directory against backup |
| `verify` | Verify backup file integrity |
| `search` | Search for files inside a backup |
| `xsearch` | Search across multiple backup archives |
| `versions` | View backup version history |
| `sftp` | SFTP remote backup management |
| `webdav` | WebDAV remote backup management |
| `remote` | Remote file management (list/rm) |
| `task` | Backup task queue management |
| `audit` | Audit log queries |
| `hooks` | Manually run Pre/Post hooks |
| `profile` | Configuration profile management |
| `rotate` | Backup rotation cleanup |
| `clean` | Clean old backups |
| `diskcheck` | Disk space estimation |
| `benchmark` | Compression format benchmark |
| `integrity` | Backup directory integrity check |
| `dry-run` | Preview backup file selection |
| `export` / `import` | Export/import backup strategies |
| `ignore` | Generate .sbackupignore file |
| `schedule` | Export scheduled task configuration |
| `webhook` | Configure webhook presets |
| `config` | Configuration encryption/validation |
| `report` | Generate backup report |
| `completion` | Generate shell completion scripts |
| `wizard` | Interactive configuration wizard |
| `status` | Backup status dashboard |
| `version` | Show version information |
| `help` | Show help information |

#### Global options

| Option | Description |
|--------|-------------|
| `--lang zh_CN` / `en_US` / `fr_FR` / `es_ES` / `ru_RU` / `de_DE` / `ja_JP` / `pt_BR` / `ko_KR` | Set UI language (persisted in config.json) |
| `--format zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z` | Set archive format (persisted in config.json) |
| `--debug` | Enable debug logging |

#### Adding a backup strategy

```bash
uv run python main.py add <source> <dest> [-i ignore_patterns]
```

Parameters:
- **source** -- path to the folder to back up
- **dest** -- path where backup files are stored
- **-i, --ignore** -- comma-separated names of files or folders to skip (default: `.git,__pycache__`)
- **--format** -- per-entry archive format (overrides the global default for this strategy only): `zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z`

Examples:
```bash
# Add strategy using the global default format
uv run python main.py add F:/my_folder F:/backup -i node_modules,.git

# Specify tar.gz for this strategy (every backup of this folder uses tar.gz)
uv run python main.py add F:/my_folder F:/backup --format tar.gz

# Specify 7z for this folder only
uv run python main.py add F:/my_folder F:/backup --format 7z
```

#### Removing a backup strategy

```bash
uv run python main.py rm <path>
```

Parameters:
- **path** -- source folder path of the strategy to remove

Example:
```bash
uv run python main.py rm F:/my_folder
```

#### Listing all backup strategies

```bash
uv run python main.py all
```

Displays all currently configured backup strategies.

#### Running a backup

```bash
# Use default format (ZIP)
uv run python main.py save

# Use tar.gz format
uv run python main.py --format tar.gz save

# Keep only the 5 most recent backups, auto-clean old ones
uv run python main.py save --keep 5

# Use 7z format with encryption
uv run python main.py --format 7z save --password mysecret

# English UI + tar.xz format
uv run python main.py --lang en_US --format tar.xz save
```

**save options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--keep N` | `0` | Keep the N most recent backup files; 0 means no cleanup |
| `--password PASSWORD` | `""` | Encryption password (7z format only) |
| `--sftp` | `false` | Upload to SFTP server after backup |
| `--webdav` | `false` | Upload to WebDAV server after backup |

Backs up changed folders automatically according to the configured strategies.

#### Scheduled backup

```bash
# Back up every 60 minutes
uv run python main.py watch --interval 60

# Back up every 2 hours, keep the 10 most recent files
uv run python main.py watch --interval 120 --keep 10

# Scheduled backup + 7z encryption
uv run python main.py --format 7z watch --interval 60 --password mysecret
```

**watch options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--interval MINUTES` | `60` | Backup interval in minutes |
| `--keep N` | `0` | Keep the N most recent backup files |
| `--password PASSWORD` | `""` | Encryption password (7z format only) |
| `--sftp` | `false` | Upload to SFTP server after each backup |
| `--webdav` | `false` | Upload to WebDAV server after each backup |

Press `Ctrl+C` to stop scheduled backup.

#### Restoring a backup

```bash
uv run python main.py restore <backup_file> <target_dir>
```

Parameters:
- **backup_file** -- path to the backup file (supports .zip / .tar / .tar.gz / .tar.bz2 / .tar.xz / .tar.zst / .7z)
- **target_dir** -- directory to restore into

Examples:
```bash
uv run python main.py restore F:/backup/my_folder.tar.gz F:/restored
uv run python main.py restore F:/backup/my_folder.7z F:/restored
uv run python main.py restore F:/backup/my_folder.tar.zst F:/restored
```

#### SFTP remote backup

```bash
# ============ Quick start (recommended) ============
# 1. Configure SFTP (auto-detects SSH private key, no manual setup needed)
sbackup sftp config --host 192.168.1.100 --user admin --remote-path /backups

# 2. Test connection
sbackup sftp test

# 3. Run backup and upload
sbackup save --sftp

# ============ Authentication methods ============

# Method 1: Auto-detect private key (recommended)
# Automatically tries ~/.ssh/id_ed25519 -> id_rsa -> id_ecdsa
sbackup sftp config --host 192.168.1.100 --user admin

# Method 2: Password authentication
sbackup sftp config --host 192.168.1.100 --user admin --password secret

# Method 3: Specify private key
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa

# Method 4: Private key + passphrase (interactive input)
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa

# Method 5: Private key + passphrase (command line)
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa --key-passphrase mykeypass

# ============ Use cases ============

# One-time backup with upload
sbackup save --sftp

# Scheduled backup with auto-upload (every 60 minutes)
sbackup watch --interval 60 --sftp

# Specify format + upload
sbackup --format tar.gz save --sftp

# Encrypted backup + upload
sbackup --format 7z save --password mysecret --sftp

# Keep 5 most recent backups + upload
sbackup save --keep 5 --sftp

# ============ Advanced usage ============

# Interactive configuration (step-by-step input)
sbackup sftp config

# Non-interactive configuration (all parameters on command line)
sbackup sftp config --host 192.168.1.100 --port 22 --user admin --password secret --remote-path /backups

# Test connection with verbose logging
sbackup --debug sftp test
```

**sftp subcommands:**

| Subcommand | Description | Example |
|------------|-------------|---------|
| `sftp config` | Configure SFTP connection (host/port/user/password/key_file/key_passphrase/remote_path) | `sbackup sftp config --host 192.168.1.100 --user admin` |
| `sftp test` | Test whether the SFTP connection works | `sbackup sftp test` |

**Authentication methods:**

| Method | Parameters | Description | Example |
|--------|-----------|-------------|---------|
| **Auto-detect** | (none) | Automatically tries `~/.ssh/id_ed25519` -> `id_rsa` -> `id_ecdsa` (recommended) | `sbackup sftp config --host ... --user ...` |
| Password | `--password` | Log in with a password | `sbackup sftp config --host ... --user ... --password secret` |
| Private key | `--key-file` | Log in with a specific SSH private key | `sbackup sftp config --host ... --user ... --key-file ~/.ssh/id_rsa` |
| Private key + passphrase | `--key-file` + `--key-passphrase` | When the private key requires a passphrase | `sbackup sftp config --host ... --user ... --key-file ~/.ssh/id_rsa --key-passphrase mypass` |

Supported key formats: RSA, Ed25519, ECDSA.

**Cross-platform path support:**

| Platform | Key path example | Description |
|----------|-----------------|-------------|
| Linux/macOS | `~/.ssh/id_rsa` | Expands to `/home/user/.ssh/id_rsa` |
| Windows | `~/.ssh/id_rsa` | Expands to `C:\Users\username\.ssh\id_rsa` |
| All platforms | Absolute path | Use the full path directly |

SFTP configuration is stored in the `sftp` field of `config.json` and can be set via command line or interactive input.

#### Viewing version information

```bash
sbackup version
```

## Configuration

Sbackup supports customization through a `config.json` file placed in the project root directory.

### Configuration options

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
  "password": "",
  "sftp": {
    "host": "",
    "port": 22,
    "user": "",
    "password": "",
    "key_file": "",
    "key_passphrase": "",
    "remote_path": "/",
    "enabled": false
  }
}
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `compression_format` | string | `"ZIP"` | Archive format: `ZIP`, `TAR`, `TAR_GZ`, `TAR_BZ2`, `TAR_XZ`, `TAR_ZST`, `7Z` |
| `compression.algorithm` | string | `"ZIP_DEFLATED"` | ZIP compression algorithm: `ZIP_DEFLATED`, `ZIP_STORED`, `ZIP_BZIP2`, `ZIP_LZMA` |
| `compression.level` | int | `6` | Compression level 0-9 (0 = no compression, 9 = maximum) |
| `skip_patterns` | list | `[".git", "__pycache__"]` | File/folder patterns to skip (supports fnmatch wildcards and path matching) |
| `data_file` | string | Platform default | Path to the backup strategy data file |
| `lang` | string | `"zh_CN"` | UI language: `zh_CN`, `en_US`, `fr_FR`, `es_ES`, `ru_RU`, `de_DE`, `ja_JP`, `pt_BR`, `ko_KR` |
| `password` | string | `""` | 7z encryption password |
| `sftp.host` | string | `""` | SFTP server address |
| `sftp.port` | int | `22` | SFTP port |
| `sftp.user` | string | `""` | SFTP username |
| `sftp.password` | string | `""` | SFTP password (for password authentication) |
| `sftp.key_file` | string | `""` | SSH private key file path (for key-based authentication) |
| `sftp.key_passphrase` | string | `""` | Private key passphrase (if required) |
| `sftp.remote_path` | string | `"/"` | Remote destination path |
| `sftp.enabled` | bool | `false` | Whether SFTP is enabled |

### Example configuration

Using tar.bz2 format for high-compression backups:

```json
{
  "compression_format": "TAR_BZ2",
  "compression_level": 9,
  "skip_patterns": [".git", "__pycache__", "node_modules", "*.log"],
  "data_file": "backup_strategies.json",
  "lang": "en_US"
}
```

### Archive format comparison

| Format | Extension | Compression | Speed | Dependencies | Best for |
|--------|-----------|-------------|-------|--------------|----------|
| ZIP | .zip | Medium | Fast | stdlib | General purpose, best Windows compatibility |
| tar | .tar | None | Very fast | stdlib | Archive only, pair with external compression |
| tar.gz | .tar.gz | Medium | Fast | stdlib | General Linux/macOS use |
| tar.bz2 | .tar.bz2 | High | Medium | stdlib | High-compression archives |
| tar.xz | .tar.xz | Highest | Slow | stdlib | Long-term archiving, space-sensitive |
| tar.zst | .tar.zst | Medium-high | Very fast | zstandard | Modern workloads, speed/size balance |
| 7z | .7z | Very high | Slow | py7zr | Maximum compression, encryption support |

#### WebDAV remote backup

WebDAV is an HTTP-based file protocol supported by Jianguoyun, NextCloud, Synology, and other popular cloud drives. Uses Python's standard library `urllib` with **zero extra dependencies**.

```bash
# ============ Quick start ============
# 1. Configure WebDAV
sbackup webdav config --url https://dav.jianguoyun.com/dav/ --user user@example.com --password secret

# 2. Test connection
sbackup webdav test

# 3. Run backup and upload
sbackup save --webdav

# ============ Use cases ============

# One-time backup with upload
sbackup save --webdav

# Scheduled backup with auto-upload (every 60 minutes)
sbackup watch --interval 60 --webdav

# Specify remote subdirectory
sbackup webdav config --url https://dav.jianguoyun.com/dav/ --user user@example.com --remote-path /backups/sbackup

# Upload to SFTP and WebDAV simultaneously
sbackup save --sftp --webdav

# ============ Common WebDAV service URLs ============
# Jianguoyun: https://dav.jianguoyun.com/dav/
# NextCloud: https://your-server/remote.php/dav/files/username/
# Synology: https://your-synology:5006/webdav/
```

**webdav subcommands:**

| Subcommand | Description | Example |
|------------|-------------|---------|
| `webdav config` | Configure WebDAV connection (url/user/password/remote_path) | `sbackup webdav config --url ... --user ...` |
| `webdav test` | Test whether the WebDAV connection works | `sbackup webdav test` |

| Option | Default | Description |
|--------|---------|-------------|
| `--url URL` | `""` | WebDAV server URL (e.g. `https://dav.jianguoyun.com/dav/`) |
| `--user USER` | `""` | WebDAV username (usually an email address) |
| `--password PASS` | `""` | WebDAV password (Jianguoyun requires generating an app password in settings) |
| `--remote-path PATH` | `/` | Remote destination path |

## How It Works

Sbackup implements backup through the following mechanisms:

1. **Strategy storage** -- backup strategies are stored in a JSON file containing folder paths, last-modified timestamps, target paths, ignore patterns, and per-entry archive formats.
2. **Incremental backup** -- by comparing each folder's last-modified timestamp, only changed folders are backed up.
3. **Multi-format compression** -- uses Python's built-in `zipfile` and `tarfile` modules, plus `zstandard` and `py7zr` third-party libraries, supporting seven archive formats.
4. **Per-entry format** -- each strategy can specify its own archive format (`add --format`), which takes priority over the global `--format` setting; when not specified, the global default is used.
5. **Backup cleanup** -- after a successful backup, the target directory is scanned, sorted by modification time, and older files exceeding the retention count are deleted.
6. **Encrypted backup** -- the 7z format supports LZMA2 encryption via the `--password` parameter or the `password` field in `config.json`.
7. **Scheduled backup** -- the `watch` command runs backups in a loop at the specified interval; `Ctrl+C` exits safely.
8. **Backup history** -- each backup records a timestamp, file size, and file count, keeping the 100 most recent entries.
9. **SFTP remote backup** -- an SFTP client built on paramiko with connection testing, automatic remote directory creation, and progress-bar file uploads.

### Data file format

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

Each backup strategy entry is a 4-element list: `[mtime, target, skip_patterns, compression_format]`

| Field | Description |
|-------|-------------|
| `mtime` | Last-modified timestamp of the source folder (used for incremental backup decisions) |
| `target` | Target path where backup files are stored |
| `skip_patterns` | List of file/folder patterns to skip |
| `compression_format` | Per-entry archive format (empty string means use the global default) |

## Development Guide

### Running tests

```bash
uv run coverage run -m unittest discover -s tests -t . && uv run coverage report -m
```

### Code structure

```
sbackup/
├── main.py              # Entry point
├── sbackup/
│   ├── __init__.py      # Core function exports
│   ├── __main__.py      # python -m sbackup entry point
│   ├── cli.py           # CLI argument parsing and command dispatch (30+ commands)
│   ├── config.py        # Configuration loading, encryption, webhook/SMTP config
│   ├── auto_save.py     # BackupManager core engine
│   ├── compression.py   # 7-format compression/decompression engine
│   ├── i18n.py          # Internationalization (9 languages)
│   ├── sftp.py          # SFTP remote backup client (paramiko)
│   ├── webdav.py        # WebDAV remote backup client (zero dependencies)
│   ├── cloud_storage.py # S3 cloud storage client (minio)
│   ├── multi_dest.py    # Multi-destination parallel backup
│   ├── handlers.py      # SFTP/WebDAV/Remote/Schedule command handlers
│   ├── hooks.py         # Pre/Post hook execution
│   ├── audit.py         # Audit log system
│   ├── profile.py       # Configuration profile management
│   ├── selective.py     # Selective restore
│   ├── cross_search.py  # Cross-archive search
│   ├── integrity.py     # SHA256 checksums
│   ├── rotation.py      # Backup rotation policies
│   ├── dryrun.py        # Dry-run preview
│   ├── diskcheck.py     # Disk space estimation
│   ├── task_queue.py    # Task queue system
│   ├── schema.py        # Configuration validator
│   ├── benchmark.py     # Compression benchmarks
│   ├── chunked_backup.py# Block-level incremental backup
│   ├── dedup.py         # File-level SHA256 deduplication
│   ├── export.py        # Metadata export (CSV/JSON)
│   ├── monitor.py       # watchdog filesystem monitor
│   ├── lock.py          # Cross-platform process lock
│   ├── retry.py         # Exponential backoff retry
│   ├── ratelimiter.py   # Token bucket rate limiter
│   ├── keychain.py      # System keychain integration
│   ├── parity.py        # Reed-Solomon error correction
│   ├── completion.py    # Shell auto-completion
│   ├── wizard.py        # Interactive configuration wizard
│   └── locales/         # Translation files for 9 languages
└── tests/
    └── sbackup/
        └── test_*.py    # 30 test files covering all modules
```

### Adding new features

1. Create a new module file under `sbackup/`
2. Import the new functions in `sbackup/__init__.py`
3. Add command-line command handling in the `run()` function
4. Add corresponding test files under `tests/`

## FAQ

### Q: What if the backup strategy file is accidentally deleted?

A: Backup strategies are stored in the data file. If accidentally deleted, you can re-add them by running the `add` command again.

### Q: How do I modify an existing backup strategy?

A: Use the `sbackup edit` command: `sbackup edit <source> --dest <new_dest> --ignore <patterns> --format <fmt>`.

### Q: Is remote backup supported?

A: Yes! Three remote backup methods are available:
- **SFTP**: configure with `sbackup sftp config`, upload with `sbackup save --sftp`
- **WebDAV**: configure with `sbackup webdav config`, upload with `sbackup save --webdav` (supports Jianguoyun, NextCloud, Synology)
- **S3 cloud storage**: configure the `cloud` field in `config.json`, upload with `sbackup save --cloud`
- Multiple can be combined: `sbackup save --sftp --webdav --cloud`

### Q: What is the difference between tar.gz and ZIP?

A: tar.gz is more common on Linux/macOS with slightly better compression; ZIP is more universal on Windows with the best compatibility. tar.bz2 and tar.xz offer higher compression but are slower. tar.zst is a modern algorithm that is extremely fast with good compression. 7z has the highest compression and supports encryption.

### Q: How do I encrypt a backup?

A: Use the 7z format with a password: `uv run python main.py --format 7z save --password yourpassword`. The password can also be set in the `password` field of `config.json`.

### Q: How do I automatically clean old backups?

A: Use the `--keep` parameter: `uv run python main.py save --keep 5` keeps only the 5 most recent backup files. This also works with scheduled backups: `uv run python main.py watch --interval 60 --keep 10`.

### Q: How do I set up scheduled backups?

A: Use the `watch` command: `uv run python main.py watch --interval 60` backs up every 60 minutes. Press `Ctrl+C` to stop.

### Q: Is password storage secure?

A: SFTP passwords and 7z encryption passwords in `config.json` are stored in **plain text**. Ensure that the `config.json` file is accessible only to trusted users (e.g. `chmod 600 config.json`). Do not commit `config.json` containing passwords to version control.

## Contributing

Issues and Pull Requests are welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Code style

This project follows PEP 8 and the Google Python Style Guide. Please ensure your code:
- Uses type annotations
- Follows Google-style docstrings
- Passes all unit tests

## License

This project is licensed under the GNU GPL v3.0 License. See the [LICENSE](LICENSE) file for details.

## Author

**xiatianxuan** (CodeSeed)

- [Gitee](https://gitee.com/xiatianxuan)
- [Homepage](https://xnors-codeseed.pages.dev/)

## Special Thanks

- [Xnors Studio](https://xnors.github.io/)

## Contact

For questions or suggestions, please email: xiatianxuan2025@163.com

---

*Last updated: June 19, 2026*
