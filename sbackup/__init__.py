import os
import sys
import argparse
import logging
from typing import NoReturn
from sbackup.auto_save import BackupManager
from sbackup.i18n import set_locale, t
from sbackup.config import load_config, save_lang, save_format
from sbackup.compression import restore_backup

VERSION = "1.0.0"
logger = logging.getLogger(__name__)


class LocalizedArgumentParser(argparse.ArgumentParser):
    """本地化错误输出的 ArgumentParser 子类"""

    def error(self, message: str) -> NoReturn:
        # 将 argparse 生成的英文错误关键词替换为本地化文本
        localized = message
        localized = localized.replace(
            "invalid choice: ", t("err.argparse.invalid_choice")
        )
        localized = localized.replace("choose from", t("err.argparse.choose_from"))
        localized = localized.replace(
            "invalid float value: ", t("err.argparse.invalid_float")
        )
        localized = localized.replace(
            "invalid int value: ", t("err.argparse.invalid_int")
        )
        localized = localized.replace(
            "unrecognized arguments: ", t("err.argparse.unrecognized_args")
        )
        localized = localized.replace("required", t("err.argparse.required"))
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: {localized}\n")
        sys.exit(2)


def _detect_lang_from_argv() -> str | None:
    """从 sys.argv 中提取 --lang 参数值"""
    for i, arg in enumerate(sys.argv):
        if arg == "--lang" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if arg.startswith("--lang="):
            return arg.split("=", 1)[1]
    return None


def get_parser() -> argparse.ArgumentParser:
    parser = LocalizedArgumentParser(
        prog="sbackup",
        description=t("cli.description", version=VERSION),
        epilog=t("cli.epilog"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )

    parser.add_argument("--debug", action="store_true", help=t("cli.help.debug"))
    parser.add_argument("-h", "--help", action="help", help=t("cli.help.help"))
    parser.add_argument("--lang", default=None, help=t("cli.help.lang"))
    parser.add_argument(
        "--format",
        default=None,
        choices=["zip", "tar", "tar.gz", "tar.bz2", "tar.xz", "tar.zst", "7z"],
        help=t("cli.help.format"),
    )

    subparsers = parser.add_subparsers(dest="command", help=t("cli.help.subcommands"))

    add_parser = subparsers.add_parser("add", help=t("cli.help.add"))
    add_parser.add_argument("source", help=t("cli.help.add.source"))
    add_parser.add_argument("dest", help=t("cli.help.add.dest"))
    add_parser.add_argument(
        "-i", "--ignore", default=".git,__pycache__", help=t("cli.help.add.ignore")
    )
    add_parser.add_argument(
        "--format",
        default=None,
        choices=["zip", "tar", "tar.gz", "tar.bz2", "tar.xz", "tar.zst", "7z"],
        help=t("cli.help.add.format"),
    )

    rm_parser = subparsers.add_parser("rm", aliases=["remove"], help=t("cli.help.rm"))
    rm_parser.add_argument("path", help=t("cli.help.rm.path"))

    subparsers.add_parser("all", help=t("cli.help.all"))

    save_parser = subparsers.add_parser("save", help=t("cli.help.save"))
    save_parser.add_argument(
        "--keep", type=int, default=0, help=t("cli.help.save.keep")
    )
    save_parser.add_argument("--password", default="", help=t("cli.help.save.password"))

    watch_parser = subparsers.add_parser("watch", help=t("cli.help.watch"))
    watch_parser.add_argument(
        "--interval", type=float, default=60, help=t("cli.help.watch.interval")
    )
    watch_parser.add_argument(
        "--keep", type=int, default=0, help=t("cli.help.watch.keep")
    )
    watch_parser.add_argument(
        "--password", default="", help=t("cli.help.watch.password")
    )

    restore_parser = subparsers.add_parser("restore", help=t("cli.help.restore"))
    restore_parser.add_argument("backup_file", help=t("cli.help.restore.file"))
    restore_parser.add_argument("target_dir", help=t("cli.help.restore.dir"))

    subparsers.add_parser("version", help=t("cli.help.version"))

    return parser


def parse_path(path_str: str) -> str:
    return os.path.expanduser(path_str.strip())


def run() -> int:
    # 先检测 --lang 参数，初始化语言环境，再创建本地化 parser
    lang_from_argv = _detect_lang_from_argv()
    config = load_config()
    current_lang = lang_from_argv if lang_from_argv is not None else config.lang
    set_locale(current_lang)

    parser = get_parser()
    args = parser.parse_args()

    # 持久化语言设置
    if lang_from_argv is not None:
        save_lang(lang_from_argv)

    # 持久化格式设置
    if args.format is not None:
        save_format(args.format)
        config.compression_format = args.format.upper().replace(".", "_")

    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "version":
        print(t("cli.version", version=VERSION))
        return 0

    manager = BackupManager(data_file=config.data_file)

    if args.command == "add":
        source = parse_path(args.source)
        dest = parse_path(args.dest)
        # 条目级格式：用户在 add 时指定的 --format 仅作用于该条目
        entry_fmt = args.format.upper().replace(".", "_") if args.format else ""
        success = manager.add_folder(source, dest, args.ignore, entry_fmt)
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
        manager.execute_backups(keep=args.keep, password=args.password)
        return 0
    elif args.command == "watch":
        import time as _time

        interval_sec = args.interval * 60
        print(t("cmd.watch.start", interval=args.interval))
        try:
            while True:
                manager.execute_backups(keep=args.keep, password=args.password)
                _time.sleep(interval_sec)
        except KeyboardInterrupt:
            return 0
    elif args.command == "restore":
        result = restore_backup(args.backup_file, args.target_dir)
        return 0 if result["success"] else 1

    return 0
