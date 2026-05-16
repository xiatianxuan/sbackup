"""命令处理器模块：SFTP 和 WebDAV 子命令的交互逻辑"""

import getpass
import logging
from sbackup.i18n import t

logger = logging.getLogger(__name__)


def _resolve_sftp_auth(
    key_file: str,
    key_passphrase: str,
    password: str,
    *,
    interactive: bool = False,
) -> tuple[str, str, str]:
    """
    解析 SFTP 认证凭据，返回 (key_file, key_passphrase, password)。

    优先使用私钥认证，自动检测默认密钥，必要时交互式提示输入密码短语。
    用户放弃输入密码短语时回退到密码认证。

    :param key_file: 私钥文件路径（空字符串表示未指定）
    :param key_passphrase: 私钥密码短语（空字符串表示未指定）
    :param password: 密码（空字符串表示未指定）
    :param interactive: 是否在缺少密码时交互式提示输入
    """
    from sbackup.sftp import SFTPClient

    # 已有完整私钥凭据，直接返回
    if key_file and key_passphrase:
        return key_file, key_passphrase, ""
    # 已有密码，直接返回
    if password:
        return "", "", password

    # 尝试解析私钥
    effective_key = key_file

    if not effective_key:
        # 未指定私钥，尝试默认位置
        default_key = SFTPClient.try_default_key()
        if default_key:
            print(t("cmd.sftp.using_default_key", path=default_key))
            effective_key = default_key
        else:
            # 无默认私钥，回退到密码
            if interactive and not password:
                password = getpass.getpass(t("cli.prompt.sftp.password") + " ")
            return "", "", password

    # 检测私钥是否需要密码短语
    resolved = SFTPClient.resolve_key_passphrase(effective_key)
    if resolved is None:
        # 用户放弃输入密码短语，回退到密码认证
        if interactive and not password:
            password = getpass.getpass(t("cli.prompt.sftp.password") + " ")
        return "", "", password

    return effective_key, resolved, ""


def handle_sftp(args, config) -> int:
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

        key_file, key_passphrase, password = _resolve_sftp_auth(
            key_file_input,
            args.key_passphrase or "",
            args.password or "",
            interactive=True,
        )

        remote_path = (
            args.remote_path or input(t("cli.prompt.sftp.remote_path") + " ") or "/"
        )

        save_sftp_config(
            host,
            port,
            user,
            password,
            remote_path,
            key_file=key_file,
            key_passphrase=key_passphrase,
        )
        print(t("cmd.sftp.config_saved"))
        return 0

    elif args.sftp_action == "test":
        if not config.sftp_enabled or not config.sftp_host:
            print(t("err.sftp.not_configured"))
            return 1

        key_file, key_passphrase, password = _resolve_sftp_auth(
            config.sftp_key_file,
            config.sftp_key_passphrase,
            config.sftp_password,
        )

        if not key_file and not password:
            print(t("cmd.sftp.no_default_key"))
            return 1

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


def handle_webdav(args, config) -> int:
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
