import os
import sys
import getpass
import argparse
import logging
from typing import NoReturn
from sbackup.auto_save import BackupManager
from sbackup.i18n import set_locale, t
from sbackup.config import load_config, save_lang, save_format
from sbackup.compression import restore_backup

VERSION = "1.0.1"
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
        # "required" 仅替换独立出现的关键词（argparse 格式: "the following arguments are required"）
        localized = localized.replace("are required", t("err.argparse.required"))
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

    subparsers.add_parser("list", aliases=["history"], help=t("cli.help.list"))

    save_parser = subparsers.add_parser("save", help=t("cli.help.save"))
    save_parser.add_argument(
        "--keep", type=int, default=0, help=t("cli.help.save.keep")
    )
    save_parser.add_argument("--password", default="", help=t("cli.help.save.password"))
    save_parser.add_argument(
        "--sftp", action="store_true", default=False, help=t("cli.help.save.sftp")
    )
    save_parser.add_argument(
        "--webdav", action="store_true", default=False, help=t("cli.help.save.webdav")
    )

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
    watch_parser.add_argument(
        "--sftp", action="store_true", default=False, help=t("cli.help.watch.sftp")
    )
    watch_parser.add_argument(
        "--webdav", action="store_true", default=False, help=t("cli.help.watch.webdav")
    )

    restore_parser = subparsers.add_parser("restore", help=t("cli.help.restore"))
    restore_parser.add_argument("backup_file", help=t("cli.help.restore.file"))
    restore_parser.add_argument("target_dir", help=t("cli.help.restore.dir"))
    restore_parser.add_argument(
        "--password", default="", help=t("cli.help.restore.password")
    )
    restore_parser.add_argument(
        "-l", "--list", action="store_true", help=t("cli.help.restore.list")
    )

    verify_parser = subparsers.add_parser("verify", help=t("cli.help.verify"))
    verify_parser.add_argument("backup_file", help=t("cli.help.verify.file"))

    sftp_parser = subparsers.add_parser("sftp", help=t("cli.help.sftp"))
    sftp_sub = sftp_parser.add_subparsers(
        dest="sftp_action", help=t("cli.help.sftp.action")
    )
    sftp_config_parser = sftp_sub.add_parser("config", help=t("cli.help.sftp.config"))
    sftp_config_parser.add_argument(
        "--host", default=None, help=t("cli.help.sftp.host")
    )
    sftp_config_parser.add_argument(
        "--port", type=int, default=None, help=t("cli.help.sftp.port")
    )
    sftp_config_parser.add_argument(
        "--user", default=None, help=t("cli.help.sftp.user")
    )
    sftp_config_parser.add_argument(
        "--password", default=None, help=t("cli.help.sftp.password")
    )
    sftp_config_parser.add_argument(
        "--key-file", default=None, help=t("cli.help.sftp.key_file")
    )
    sftp_config_parser.add_argument(
        "--key-passphrase", default=None, help=t("cli.help.sftp.key_passphrase")
    )
    sftp_config_parser.add_argument(
        "--remote-path", default=None, help=t("cli.help.sftp.remote_path")
    )
    sftp_sub.add_parser("test", help=t("cli.help.sftp.test"))

    webdav_parser = subparsers.add_parser("webdav", help=t("cli.help.webdav"))
    webdav_sub = webdav_parser.add_subparsers(
        dest="webdav_action", help=t("cli.help.webdav.action")
    )
    webdav_config_parser = webdav_sub.add_parser(
        "config", help=t("cli.help.webdav.config")
    )
    webdav_config_parser.add_argument(
        "--url", default=None, help=t("cli.help.webdav.url")
    )
    webdav_config_parser.add_argument(
        "--user", default=None, help=t("cli.help.webdav.user")
    )
    webdav_config_parser.add_argument(
        "--password", default=None, help=t("cli.help.webdav.password")
    )
    webdav_config_parser.add_argument(
        "--remote-path", default=None, help=t("cli.help.webdav.remote_path")
    )
    webdav_sub.add_parser("test", help=t("cli.help.webdav.test"))

    subparsers.add_parser("version", help=t("cli.help.version"))

    return parser


def parse_path(path_str: str) -> str:
    return os.path.expanduser(path_str.strip())


def _try_load_key_passphrase(key_file: str) -> str | None:
    """
    尝试加载私钥，检测是否需要密码短语
    :return: 密码短语（空字符串表示不需要），None 表示用户放弃输入
    """
    from sbackup.sftp import SFTPClient, SFTPError

    try:
        SFTPClient._load_private_key(key_file, "")
        return ""
    except SFTPError:
        # 需要密码短语，循环提示直到输入正确或放弃
        while True:
            passphrase = getpass.getpass(t("cli.prompt.sftp.key_passphrase") + " ")
            if not passphrase:
                return None  # 用户放弃输入，回退到密码认证
            # 验证密码短语是否正确
            try:
                SFTPClient._load_private_key(key_file, passphrase)
                return passphrase
            except SFTPError:
                print(t("err.sftp.wrong_passphrase"))
                # 继续循环，让用户重新输入


def _handle_sftp(args, config) -> int:
    """处理 sftp 子命令"""
    from sbackup.config import save_sftp_config
    from sbackup.sftp import SFTPClient, SFTPError

    if args.sftp_action == "config":
        # 交互式配置
        host = args.host or input(t("cli.prompt.sftp.host") + " ")
        port_str = (
            str(args.port)
            if args.port is not None
            else input(t("cli.prompt.sftp.port") + " ")
        )
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                print(t("err.sftp.ssh", error=f"port {port} out of range"))
                port = 22
        except ValueError:
            print(t("err.sftp.ssh", error=f"invalid port: {port_str}"))
            port = 22
        user = args.user or input(t("cli.prompt.sftp.user") + " ")
        key_file_input = args.key_file or input(t("cli.prompt.sftp.key_file") + " ")

        # 如果用户没有指定私钥，尝试默认位置
        if not key_file_input:
            default_key = SFTPClient.try_default_key()
            if default_key:
                print(t("cmd.sftp.using_default_key", path=default_key))
                key_file_input = default_key
                # 尝试加载私钥，检测是否需要密码短语
                key_passphrase_input = _try_load_key_passphrase(default_key)
                if key_passphrase_input is None:
                    # 用户放弃输入密码短语，回退到密码认证
                    key_file_input = ""
                    password = args.password or getpass.getpass(
                        t("cli.prompt.sftp.password") + " "
                    )
                    key_passphrase_input = ""
                else:
                    password = ""
            else:
                # 没有默认私钥，提示输入密码
                password = args.password or getpass.getpass(
                    t("cli.prompt.sftp.password") + " "
                )
                key_passphrase_input = ""
        else:
            # 用户指定了私钥，先尝试无密码加载，需要时再提示
            if not args.key_passphrase:
                key_passphrase_input = _try_load_key_passphrase(key_file_input)
                if key_passphrase_input is None:
                    # 用户放弃输入密码短语，回退到密码认证
                    key_file_input = ""
                    password = args.password or getpass.getpass(
                        t("cli.prompt.sftp.password") + " "
                    )
                    key_passphrase_input = ""
                else:
                    password = ""
            else:
                password = ""
                key_passphrase_input = args.key_passphrase

        remote_path = (
            args.remote_path or input(t("cli.prompt.sftp.remote_path") + " ") or "/"
        )

        save_sftp_config(
            host,
            port,
            user,
            password,
            remote_path,
            key_file=key_file_input,
            key_passphrase=key_passphrase_input,
        )
        print(t("cmd.sftp.config_saved"))
        return 0

    elif args.sftp_action == "test":
        if not config.sftp_enabled or not config.sftp_host:
            print(t("err.sftp.not_configured"))
            return 1

        # 获取认证凭据：优先使用配置中的私钥，否则尝试默认私钥
        key_file = config.sftp_key_file
        key_passphrase = config.sftp_key_passphrase
        password = config.sftp_password

        if not key_file and not password:
            default_key = SFTPClient.try_default_key()
            if default_key:
                print(t("cmd.sftp.using_default_key", path=default_key))
                key_file = default_key
                key_passphrase = _try_load_key_passphrase(default_key)
                if key_passphrase is None:
                    # 用户放弃输入密码短语，回退到密码认证
                    key_file = ""
                    password = config.sftp_password
                    key_passphrase = ""
            else:
                print(t("cmd.sftp.no_default_key"))
        elif key_file and not key_passphrase and not password:
            # 已配置私钥但未设置密码短语，检测是否需要
            key_passphrase = _try_load_key_passphrase(key_file)
            if key_passphrase is None:
                # 用户放弃输入密码短语，回退到密码认证
                key_file = ""
                password = config.sftp_password
                key_passphrase = ""

        print(t("cmd.sftp.testing", host=config.sftp_host))
        try:
            client = SFTPClient(
                config.sftp_host,
                config.sftp_port,
                config.sftp_user,
                password,
                key_file,
                key_passphrase,
            )
            client.connect()
            client.disconnect()
            print(t("cmd.sftp.test_ok"))
            return 0
        except SFTPError as e:
            print(str(e))
            return 1

    print(t("cli.help.sftp.action"))
    return 1


def _handle_webdav(args, config) -> int:
    """处理 webdav 子命令"""
    from sbackup.config import save_webdav_config
    from sbackup.webdav import WebDAVClient, WebDAVError

    if args.webdav_action == "config":
        # 交互式配置
        url = args.url or input(t("cli.prompt.webdav.url") + " ")
        user = args.user or input(t("cli.prompt.webdav.user") + " ")
        password = args.password or getpass.getpass(
            t("cli.prompt.webdav.password") + " "
        )
        remote_path = (
            args.remote_path or input(t("cli.prompt.webdav.remote_path") + " ") or "/"
        )

        save_webdav_config(url, user, password, remote_path)
        print(t("cmd.webdav.config_saved"))
        return 0

    elif args.webdav_action == "test":
        if not config.webdav_enabled or not config.webdav_url:
            print(t("err.webdav.not_configured"))
            return 1

        print(t("cmd.webdav.testing", url=config.webdav_url))
        try:
            client = WebDAVClient(
                config.webdav_url,
                config.webdav_user,
                config.webdav_password,
            )
            client.connect()
            print(t("cmd.webdav.test_ok"))
            return 0
        except WebDAVError as e:
            print(str(e))
            return 1

    print(t("cli.help.webdav.action"))
    return 1


def run() -> int:
    # 预处理 --debug：允许放在子命令之后
    debug_enabled = "--debug" in sys.argv
    cleaned_argv = [arg for arg in sys.argv if arg != "--debug"]
    sys.argv = cleaned_argv

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

    if debug_enabled:
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
    elif args.command in ("list", "history"):
        print(manager.format_history_table())
        return 0
    elif args.command == "save":
        manager.execute_backups(
            keep=args.keep,
            password=args.password,
            sftp_upload=args.sftp,
            webdav_upload=args.webdav,
        )
        return 0
    elif args.command == "watch":
        import time as _time

        interval_sec = max(args.interval, 0.1) * 60  # 最小 6 秒
        print(t("cmd.watch.start", interval=args.interval))
        try:
            while True:
                manager.execute_backups(
                    keep=args.keep,
                    password=args.password,
                    sftp_upload=args.sftp,
                    webdav_upload=args.webdav,
                )
                _time.sleep(interval_sec)
        except KeyboardInterrupt:
            return 0
    elif args.command == "restore":
        if args.list:
            from sbackup.compression import list_backup_contents

            print(list_backup_contents(args.backup_file, args.password))
            return 0
        result = restore_backup(args.backup_file, args.target_dir, args.password)
        return 0 if result["success"] else 1
    elif args.command == "verify":
        from sbackup.compression import verify_backup

        result = verify_backup(args.backup_file, args.password)
        return 0 if result["success"] else 1
    elif args.command == "sftp":
        return _handle_sftp(args, config)
    elif args.command == "webdav":
        return _handle_webdav(args, config)

    return 0
