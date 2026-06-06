"""交互式配置向导：引导用户完成首次配置"""

import os
import logging
from sbackup.i18n import t
from sbackup.config import _load_json_file, _save_json_file

logger = logging.getLogger(__name__)


def run_wizard(data_file: str) -> int:
    """运行交互式配置向导"""
    print("=" * 50)
    print(t("cmd.wizard.welcome"))
    print("=" * 50)
    print()

    # Step 1: Language selection
    print(t("cmd.wizard.step_lang"))
    print("  1. 中文 (zh_CN)")
    print("  2. English (en_US)")
    choice = input(t("cmd.wizard.choice") + " ").strip()
    lang = "zh_CN" if choice == "1" else "en_US"
    from sbackup.config import save_lang

    save_lang(lang)
    from sbackup.i18n import set_locale

    set_locale(lang)
    print(t("cmd.wizard.lang_set", lang=lang))
    print()

    # Step 2: Add backup strategy
    from sbackup.auto_save import BackupManager

    manager = BackupManager(data_file=data_file)

    strategies_added = 0
    while True:
        print(t("cmd.wizard.step_strategy"))
        source = input(t("cmd.wizard.source") + " ").strip()
        if not source:
            break
        if not os.path.isdir(source):
            print(t("err.folder.invalid", path=source))
            continue

        dest = input(t("cmd.wizard.dest") + " ").strip()
        if not dest:
            break
        os.makedirs(dest, exist_ok=True)

        ignore = input(t("cmd.wizard.ignore") + " ").strip() or ".git,__pycache__"

        manager.add_folder(source, dest, ignore)
        strategies_added += 1
        print(t("cmd.add.success", source=source, dest=dest))

        more = input(t("cmd.wizard.more") + " ").strip().lower()
        if more not in ("y", "yes", "是", "yes"):
            break

    if strategies_added > 0:
        manager.save()

    # Step 3: Remote storage
    print()
    print(t("cmd.wizard.step_remote"))
    print("  1. SFTP")
    print("  2. WebDAV")
    print("  3. S3 Cloud Storage")
    print("  4. " + t("cmd.wizard.skip"))
    remote_choice = input(t("cmd.wizard.choice") + " ").strip()

    if remote_choice == "1":
        _setup_sftp()
    elif remote_choice == "2":
        _setup_webdav()
    elif remote_choice == "3":
        _setup_cloud()

    # Step 4: Email notifications
    print()
    print(t("cmd.wizard.step_email"))
    email = input(t("cmd.wizard.email_yn") + " ").strip().lower()
    if email in ("y", "yes", "是"):
        _setup_email()

    # Step 5: Schedule
    print()
    print(t("cmd.wizard.step_schedule"))
    schedule = input(t("cmd.wizard.schedule_yn") + " ").strip().lower()
    if schedule in ("y", "yes", "是"):
        interval_str = input(t("cmd.wizard.schedule_interval") + " ").strip()
        interval = int(interval_str) if interval_str.isdigit() else 60
        print(t("cmd.wizard.schedule_info", interval=interval))
        print(f"  sbackup watch --interval {interval}")

    # Summary
    print()
    print("=" * 50)
    print(t("cmd.wizard.complete"))
    print("=" * 50)
    print(t("cmd.wizard.summary", strategies=strategies_added))
    print()

    return 0


def _setup_sftp():
    """交互式配置 SFTP"""
    from sbackup.config import save_sftp_config

    host = input("  SFTP " + t("cmd.wizard.host") + " ").strip()
    if not host:
        return
    port_str = input("  SFTP " + t("cmd.wizard.port") + " [22] ").strip()
    port = int(port_str) if port_str.isdigit() else 22
    user = input("  SFTP " + t("cmd.wizard.user") + " ").strip()
    if not user:
        return
    pwd = input("  SFTP " + t("cmd.wizard.password") + " (enter to skip) ").strip()
    remote = input("  SFTP " + t("cmd.wizard.remote_path") + " [/] ").strip() or "/"

    save_sftp_config(host, port, user, pwd, remote, enabled=True)
    print(t("cmd.wizard.sftp_done"))


def _setup_webdav():
    """交互式配置 WebDAV"""
    from sbackup.config import save_webdav_config

    url = input("  WebDAV URL (e.g. https://dav.jianguoyun.com/dav/) ").strip()
    if not url:
        return
    user = input("  WebDAV " + t("cmd.wizard.user") + " ").strip()
    if not user:
        return
    pwd = input("  WebDAV " + t("cmd.wizard.password") + " (enter to skip) ").strip()
    remote = input("  WebDAV " + t("cmd.wizard.remote_path") + " [/] ").strip() or "/"

    save_webdav_config(url, user, pwd, remote, enabled=True)
    print(t("cmd.wizard.webdav_done"))


def _setup_cloud():
    """交互式配置 S3 云存储"""
    print(t("cmd.wizard.cloud_info"))
    endpoint = input("  S3 Endpoint (e.g. s3.amazonaws.com) ").strip()
    if not endpoint:
        return
    bucket = input("  Bucket ").strip()
    if not bucket:
        return
    access_key = input("  Access Key ").strip()
    secret_key = input("  Secret Key ").strip()
    region = input("  Region (enter to skip) ").strip()

    data = _load_json_file("config.json")
    data["cloud"] = {
        "endpoint": endpoint,
        "access_key": access_key,
        "secret_key": secret_key,
        "bucket": bucket,
        "region": region,
        "secure": True,
        "remote_path": "/",
        "enabled": True,
    }
    _save_json_file(data, "config.json")
    print(t("cmd.wizard.cloud_done"))


def _setup_email():
    """交互式配置 SMTP 邮件"""
    host = input("  SMTP " + t("cmd.wizard.host") + " ").strip()
    if not host:
        return
    port_str = input("  SMTP " + t("cmd.wizard.port") + " [587] ").strip()
    port = int(port_str) if port_str.isdigit() else 587
    user = input("  SMTP " + t("cmd.wizard.user") + " ").strip()
    if not user:
        return
    pwd = input("  SMTP " + t("cmd.wizard.password") + " (enter to skip) ").strip()
    from_addr = input("  SMTP From (email) ").strip()
    to_addr = input("  SMTP To (email) ").strip()

    data = _load_json_file("config.json")
    data["smtp"] = {
        "host": host,
        "port": port,
        "user": user,
        "password": pwd,
        "from": from_addr,
        "to": to_addr,
        "tls": True,
        "enabled": bool(from_addr and to_addr),
    }
    _save_json_file(data, "config.json")
    print(t("cmd.wizard.email_done"))
