"""命令处理器模块：SFTP 和 WebDAV 子命令的交互逻辑"""

import getpass
import logging
import os
import sys
from sbackup.i18n import t

logger = logging.getLogger(__name__)


def _validate_remote_filename(filename: str) -> str | None:
    """验证远程文件名安全性，返回净化后的文件名或 None（不安全时）
    只允许纯文件名，拒绝路径分隔符和 .. 序列
    """
    if not filename:
        return None
    # 拒绝 null 字节注入
    if "\x00" in filename:
        return None
    # 拒绝路径分隔符
    if "/" in filename or "\\" in filename:
        return None
    # 拒绝 .. 序列
    if ".." in filename:
        return None
    # 拒绝绝对路径
    if os.path.isabs(filename):
        return None
    # 只取 basename（防御性编程）
    safe_name = os.path.basename(filename)
    if not safe_name or safe_name in (".", ".."):
        return None
    return safe_name


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

        # 警告：通过 CLI 传递密码会暴露在进程列表中
        if args.password:
            print(
                t("warn.password_in_cli", arg="--password"),
                file=sys.stderr,
            )
        if args.key_passphrase:
            print(
                t("warn.password_in_cli", arg="--key-passphrase"),
                file=sys.stderr,
            )

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
        # 警告：通过 CLI 传递密码会暴露在进程列表中
        if args.password:
            print(
                t("warn.password_in_cli", arg="--password"),
                file=sys.stderr,
            )
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


def _format_file_size(size_bytes: int) -> str:
    """格式化文件大小为人类可读格式"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def handle_remote(args, config) -> int:
    """处理 remote 子命令"""
    use_sftp = getattr(args, "sftp", False)
    use_webdav = getattr(args, "webdav", False)

    # 如果两个都没指定，默认使用 sftp
    if not use_sftp and not use_webdav:
        use_sftp = True

    if use_sftp:
        return _handle_remote_sftp(args, config)
    elif use_webdav:
        return _handle_remote_webdav(args, config)
    else:
        print(t("cmd.remote.select_protocol"))
        return 1


def _handle_remote_sftp(args, config) -> int:
    """处理 SFTP 远程文件管理"""
    import time as _time_mod
    from sbackup.sftp import SFTPClient, SFTPError

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

    try:
        with SFTPClient(
            config.sftp_host,
            config.sftp_port,
            config.sftp_user,
            password,
            key_file,
            key_passphrase,
        ) as client:
            if args.remote_action == "list":
                remote_path = getattr(args, "path", None) or config.sftp_remote_path
                files = client.list_remote_files(remote_path)
                if not files:
                    print(t("cmd.remote.empty", path=remote_path))
                    return 0
                print(t("cmd.remote.list_header", path=remote_path, count=len(files)))
                for f in files:
                    mtime_str = (
                        _time_mod.strftime(
                            "%Y-%m-%d %H:%M:%S", _time_mod.localtime(f["mtime"])
                        )
                        if f["mtime"]
                        else "N/A"
                    )
                    size_str = _format_file_size(f["size"])
                    print(f"  {f['name']:40s} {size_str:>10s}  {mtime_str}")
                return 0

            elif args.remote_action == "rm":
                safe_name = _validate_remote_filename(args.filename)
                if not safe_name:
                    print(t("err.invalid_filename", filename=args.filename))
                    return 1
                remote_path = config.sftp_remote_path.rstrip("/") + "/" + safe_name
                client.delete_remote_file(remote_path)
                print(t("cmd.remote.deleted", path=remote_path))
                return 0

    except SFTPError as e:
        print(str(e))
        return 1

    print(t("cli.help.remote.action"))
    return 1


def _handle_remote_webdav(args, config) -> int:
    """处理 WebDAV 远程文件管理"""
    import time as _time_mod
    from sbackup.webdav import WebDAVClient, WebDAVError

    if not config.webdav_enabled or not config.webdav_url:
        print(t("err.webdav.not_configured"))
        return 1

    try:
        client = WebDAVClient(
            config.webdav_url,
            config.webdav_user,
            config.webdav_password,
        )
        client.connect()

        if args.remote_action == "list":
            remote_path = getattr(args, "path", None) or config.webdav_remote_path
            files = client.list_remote_files(remote_path)
            if not files:
                print(t("cmd.remote.empty", path=remote_path))
                return 0
            print(t("cmd.remote.list_header", path=remote_path, count=len(files)))
            for f in files:
                mtime_str = (
                    _time_mod.strftime(
                        "%Y-%m-%d %H:%M:%S", _time_mod.localtime(f["mtime"])
                    )
                    if f["mtime"]
                    else "N/A"
                )
                size_str = _format_file_size(f["size"])
                print(f"  {f['name']:40s} {size_str:>10s}  {mtime_str}")
            return 0

        elif args.remote_action == "rm":
            safe_name = _validate_remote_filename(args.filename)
            if not safe_name:
                print(t("err.invalid_filename", filename=args.filename))
                return 1
            remote_path = config.webdav_remote_path.rstrip("/") + "/" + safe_name
            client.delete_remote_file(remote_path)
            print(t("cmd.remote.deleted", path=remote_path))
            return 0

    except WebDAVError as e:
        print(str(e))
        return 1

    print(t("cli.help.remote.action"))
    return 1


def handle_schedule(args, config) -> int:
    """处理 schedule 子命令"""
    if args.schedule_action == "export":
        return _export_schedule(args, config)
    print(t("cli.help.schedule.action"))
    return 1


def _export_schedule(args, config) -> int:
    """导出定时调度配置"""
    fmt = args.type
    interval = args.interval
    output = args.output or ""

    if fmt == "systemd":
        content = _generate_systemd(interval)
    elif fmt == "crontab":
        content = _generate_crontab(interval)
    elif fmt == "schtasks":
        content = _generate_schtasks(interval)
    else:
        print(t("cmd.schedule.unknown_type", type=fmt))
        return 1

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(content)
        print(t("cmd.schedule.exported", path=output, type=fmt))
    else:
        print(content)
    return 0


def _generate_systemd(interval_minutes: int) -> str:
    """生成 systemd service + timer 配置"""
    import shutil

    sbackup_path = shutil.which("sbackup") or "/usr/local/bin/sbackup"
    service = f"""[Unit]
Description=Sbackup incremental backup
After=network.target

[Service]
Type=oneshot
ExecStart={sbackup_path} save
"""
    timer = f"""[Unit]
Description=Run sbackup every {interval_minutes} minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec={interval_minutes}min
Persistent=true

[Install]
WantedBy=timers.target
"""
    return (
        "# === sbackup.service ===\n"
        + service
        + "\n# === sbackup.timer ===\n"
        + timer
        + "\n# 安装方法:\n"
        + "#   sudo cp sbackup.service sbackup.timer /etc/systemd/system/\n"
        + "#   sudo systemctl daemon-reload\n"
        + "#   sudo systemctl enable --now sbackup.timer\n"
    )


def _generate_crontab(interval_minutes: int) -> str:
    """生成 crontab 条目"""
    import shutil

    sbackup_path = shutil.which("sbackup") or "/usr/local/bin/sbackup"

    if interval_minutes < 60:
        cron_expr = f"*/{interval_minutes} * * * *"
    elif interval_minutes < 1440:
        hours = interval_minutes // 60
        cron_expr = f"0 */{hours} * * *"
    else:
        days = interval_minutes // 1440
        cron_expr = f"0 0 */{days} * *"

    return (
        f"# sbackup 定时备份 (每 {interval_minutes} 分钟)\n"
        f"{cron_expr} {sbackup_path} save\n"
        f"\n# 安装方法:\n"
        f"#   crontab -e  然后粘贴上面的行\n"
    )


def _generate_schtasks(interval_minutes: int) -> str:
    """生成 Windows 计划任务 XML 和 schtasks 命令"""
    import shutil

    sbackup_path = shutil.which("sbackup") or "sbackup"

    # 计算重复间隔（PT{H}H{M}M 格式）
    hours = interval_minutes // 60
    minutes = interval_minutes % 60
    if hours > 0 and minutes > 0:
        repetition = f"PT{hours}H{minutes}M"
    elif hours > 0:
        repetition = f"PT{hours}H"
    else:
        repetition = f"PT{minutes}M"

    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Sbackup incremental backup (every {interval_minutes} min)</Description>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <Repetition>
        <Interval>{repetition}</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>2026-01-01T00:00:00</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Actions>
    <Exec>
      <Command>{sbackup_path}</Command>
      <Arguments>save</Arguments>
    </Exec>
  </Actions>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
  </Settings>
</Task>"""

    cmd = f'schtasks /create /tn "SbackupBackup" /tr "{sbackup_path} save" /sc MINUTE /mo {interval_minutes} /f'

    return (
        f"# === schtasks 命令（推荐） ===\n"
        f"# 以管理员权限运行以下命令:\n"
        f"{cmd}\n"
        f"\n# === 或使用 XML 导入 ===\n"
        f"# 保存为 sbackup_task.xml，然后运行:\n"
        f'#   schtasks /create /tn "SbackupBackup" /xml sbackup_task.xml /f\n'
        f"\n{xml}"
    )
