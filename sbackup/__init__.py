import sys
import os
import argparse
import logging
from sbackup.auto_save import BackupManager
from sbackup.i18n import set_locale, t
from sbackup.config import load_config, save_lang

VERSION = "1.0.0"
logger = logging.getLogger(__name__)

EXAMPLES = """示例:
  添加备份策略:
    sbackup add F:/my_folder F:/backup -i node_modules,.git
    
  删除备份策略:
    sbackup rm F:/my_folder
    
  查看所有策略:
    sbackup all
    
  执行备份任务:
    sbackup save
    
  使用英文界面:
    sbackup --lang en_US save
"""

def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sbackup",
        description=f"""Sbackup v{VERSION} — 轻量级增量备份工具

Sbackup 帮助您轻松管理多文件夹的备份任务。它采用增量备份策略，
仅对已修改的文件进行压缩，支持自定义忽略规则，并提供直观的进度反馈。

可用命令:
  add     添加新的备份策略 (源目录 -> 目标目录)
  rm      删除现有的备份策略
  all     显示所有已配置的备份策略详情
  save    根据策略执行备份任务
  version 查看版本信息""",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False
    )

    # 全局参数
    parser.add_argument("--debug", action="store_true", help="开启调试模式，输出详细的运行日志和状态信息")
    parser.add_argument("-h", "--help", action="help", help="显示此帮助信息并退出")
    parser.add_argument("--lang", default=None, help="设置界面语言: zh_CN (默认) 或 en_US")
    
    subparsers = parser.add_subparsers(dest="command", help="选择要执行的命令")

    # add command
    add_parser = subparsers.add_parser("add", help="添加新的备份策略")
    add_parser.add_argument("source", help="源文件夹路径: 需要被备份的目录")
    add_parser.add_argument("dest", help="目标文件夹路径: 存放生成的 .zip 备份文件的目录")
    add_parser.add_argument("-i", "--ignore", default=".git,__pycache__", help="需要忽略的文件或文件夹名称 (使用逗号分隔，默认: .git,__pycache__)")

    # rm command
    rm_parser = subparsers.add_parser("rm", aliases=["remove"], help="删除备份策略")
    rm_parser.add_argument("path", help="需要删除备份策略的源文件夹路径")

    # all command
    subparsers.add_parser("all", help="查看所有备份策略")

    # save command
    subparsers.add_parser("save", help="执行所有备份策略")

    # version command
    subparsers.add_parser("version", help="查看版本信息")

    return parser


def parse_path(path_str: str) -> str:
    """
    清理并解析路径
    """
    return os.path.expanduser(path_str.strip())


def run() -> int:
    """
    主运行函数，返回退出码：0 成功，1 失败
    """
    parser = get_parser()
    args = parser.parse_args()

    # 加载配置以获取默认语言设置
    config = load_config()

    # 检查是否显式提供了 --lang 参数
    if args.lang is not None:
        current_lang = args.lang
        # 持久化语言设置
        save_lang(current_lang)
    else:
        current_lang = config.lang

    # 初始化语言环境
    set_locale(current_lang)

    # 配置日志：仅在有 --debug 参数时开启
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S"
        )

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "version":
        print(f"""
Sbackup v{VERSION} — Copyright © 2026 xiatianxuan
Licensed under GNU GPL v3.0 — https://www.gnu.org/licenses/gpl-3.0.html
""")
        return 0

    manager = BackupManager(data_file=config.data_file)

    if args.command == "add":
        source = parse_path(args.source)
        dest = parse_path(args.dest)
        success = manager.add_folder(source, dest, args.ignore)
        if success:
            print(t("cmd.add.success", source=source, dest=dest))
            return 0
        return 1
    elif args.command in ("rm", "remove"):
        path = parse_path(args.path)
        success = manager.rm_folder(path)
        if success:
            print(t("cmd.rm.success", path=path))
            return 0
        return 1
    elif args.command == "all":
        print(manager.list_folder_table())
        return 0
    elif args.command == "save":
        manager.execute_backups()
        return 0
