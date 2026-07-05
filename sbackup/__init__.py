"""sbackup 包入口：导出核心函数供 CLI 和外部调用"""

from sbackup.cli import run, VERSION, get_parser, LocalizedArgumentParser, parse_path

__all__ = [
    "run",
    "VERSION",
    "get_parser",
    "LocalizedArgumentParser",
    "parse_path",
]
