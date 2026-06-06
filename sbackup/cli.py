"""CLI 模块：命令行解析、参数处理和主入口"""

import os
import sys
import argparse
import logging
from typing import NoReturn
from sbackup.auto_save import BackupManager
from sbackup.i18n import set_locale, t
from sbackup.config import Config, load_config, save_lang, save_format
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
        "--follow-symlinks",
        action="store_true",
        default=False,
        help=t("cli.help.follow_symlinks"),
    )
    parser.add_argument(
        "--incremental",
        nargs="?",
        const="file",
        default=None,
        choices=["file", "block"],
        help=t("cli.help.incremental"),
    )
    parser.add_argument(
        "--checksum",
        action="store_true",
        default=False,
        help=t("cli.help.checksum"),
    )
    parser.add_argument(
        "--dedup",
        action="store_true",
        default=False,
        help=t("cli.help.dedup"),
    )
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
    add_parser.add_argument(
        "--name-template",
        default=None,
        help=t("cli.help.add.name_template"),
    )
    add_parser.add_argument(
        "--from-gitignore",
        default=None,
        help=t("cli.help.add.from_gitignore"),
    )

    rm_parser = subparsers.add_parser("rm", aliases=["remove"], help=t("cli.help.rm"))
    rm_parser.add_argument("path", nargs="?", default=None, help=t("cli.help.rm.path"))
    rm_parser.add_argument("--all", action="store_true", help=t("cli.help.rm.all"))

    edit_parser = subparsers.add_parser("edit", help=t("cli.help.edit"))
    edit_parser.add_argument("source", help=t("cli.help.edit.source"))
    edit_parser.add_argument("--dest", default=None, help=t("cli.help.edit.dest"))
    edit_parser.add_argument("--ignore", default=None, help=t("cli.help.edit.ignore"))
    edit_parser.add_argument(
        "--format",
        default=None,
        choices=["zip", "tar", "tar.gz", "tar.bz2", "tar.xz", "tar.zst", "7z"],
        help=t("cli.help.edit.format"),
    )
    edit_parser.add_argument(
        "--name-template", default=None, help=t("cli.help.edit.name_template")
    )

    subparsers.add_parser("all", help=t("cli.help.all"))

    list_parser = subparsers.add_parser(
        "list", aliases=["history"], help=t("cli.help.list")
    )
    list_parser.add_argument(
        "--tags", action="store_true", help=t("cli.help.list.tags")
    )

    subparsers.add_parser("init", help=t("cli.help.init"))

    save_parser = subparsers.add_parser("save", help=t("cli.help.save"))
    save_parser.add_argument(
        "--keep", type=int, default=0, help=t("cli.help.save.keep")
    )
    save_parser.add_argument(
        "--keep-days", type=int, default=0, help=t("cli.help.save.keep_days")
    )
    save_parser.add_argument("--password", default="", help=t("cli.help.save.password"))
    save_parser.add_argument(
        "--sftp", action="store_true", default=False, help=t("cli.help.save.sftp")
    )
    save_parser.add_argument(
        "--webdav", action="store_true", default=False, help=t("cli.help.save.webdav")
    )
    save_parser.add_argument(
        "--cloud", action="store_true", default=False, help=t("cli.help.save.cloud")
    )
    save_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=t("cli.help.save.dry_run"),
    )
    save_parser.add_argument(
        "--verify",
        action="store_true",
        default=False,
        help=t("cli.help.save.verify"),
    )
    save_parser.add_argument(
        "--name-template",
        default=None,
        help=t("cli.help.save.name_template"),
    )
    save_parser.add_argument(
        "--webhook",
        action="append",
        default=None,
        help=t("cli.help.save.webhook"),
    )
    save_parser.add_argument(
        "--max-size", default=None, help=t("cli.help.save.max_size")
    )
    save_parser.add_argument(
        "--min-size", default=None, help=t("cli.help.save.min_size")
    )
    save_parser.add_argument("--split", default=None, help=t("cli.help.save.split"))
    save_parser.add_argument("--tag", default="", help=t("cli.help.save.tag"))
    save_parser.add_argument(
        "--older-than", default=None, help=t("cli.help.save.older_than")
    )
    save_parser.add_argument(
        "--pre-hook",
        action="append",
        default=None,
        help=t("cli.help.save.pre_hook"),
    )
    save_parser.add_argument(
        "--post-hook",
        action="append",
        default=None,
        help=t("cli.help.save.post_hook"),
    )
    save_parser.add_argument(
        "--threads",
        type=int,
        default=1,
        help=t("cli.help.save.threads"),
    )
    save_parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help=t("cli.help.strict"),
    )

    compress_parser = subparsers.add_parser("compress", help=t("cli.help.compress"))
    compress_parser.add_argument("source", help=t("cli.help.compress.source"))
    compress_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=t("cli.help.compress.dry_run"),
    )
    compress_parser.add_argument(
        "--format",
        default=None,
        choices=["zip", "tar", "tar.gz", "tar.bz2", "tar.xz", "tar.zst", "7z"],
        help=t("cli.help.compress.format"),
    )
    compress_parser.add_argument(
        "-o",
        "--output",
        default=None,
        help=t("cli.help.compress.output"),
    )
    compress_parser.add_argument(
        "--password", default="", help=t("cli.help.compress.password")
    )

    watch_parser = subparsers.add_parser("watch", help=t("cli.help.watch"))
    watch_parser.add_argument(
        "--interval", type=float, default=60, help=t("cli.help.watch.interval")
    )
    watch_parser.add_argument(
        "--keep", type=int, default=0, help=t("cli.help.watch.keep")
    )
    watch_parser.add_argument(
        "--keep-days", type=int, default=0, help=t("cli.help.watch.keep_days")
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
    watch_parser.add_argument(
        "--cloud", action="store_true", default=False, help=t("cli.help.watch.cloud")
    )
    watch_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=t("cli.help.watch.dry_run"),
    )
    watch_parser.add_argument(
        "--verify",
        action="store_true",
        default=False,
        help=t("cli.help.watch.verify"),
    )
    watch_parser.add_argument(
        "--name-template",
        default=None,
        help=t("cli.help.watch.name_template"),
    )
    watch_parser.add_argument(
        "--webhook",
        action="append",
        default=None,
        help=t("cli.help.watch.webhook"),
    )
    watch_parser.add_argument(
        "--max-size", default=None, help=t("cli.help.watch.max_size")
    )
    watch_parser.add_argument(
        "--min-size", default=None, help=t("cli.help.watch.min_size")
    )
    watch_parser.add_argument("--split", default=None, help=t("cli.help.watch.split"))
    watch_parser.add_argument("--tag", default="", help=t("cli.help.watch.tag"))
    watch_parser.add_argument(
        "--older-than", default=None, help=t("cli.help.watch.older_than")
    )
    watch_parser.add_argument(
        "--pre-hook",
        action="append",
        default=None,
        help=t("cli.help.watch.pre_hook"),
    )
    watch_parser.add_argument(
        "--post-hook",
        action="append",
        default=None,
        help=t("cli.help.watch.post_hook"),
    )
    watch_parser.add_argument(
        "--realtime",
        action="store_true",
        default=False,
        help=t("cli.help.watch.realtime"),
    )
    watch_parser.add_argument(
        "--debounce",
        type=float,
        default=30,
        help=t("cli.help.watch.debounce"),
    )
    watch_parser.add_argument(
        "--threads",
        type=int,
        default=1,
        help=t("cli.help.watch.threads"),
    )

    restore_parser = subparsers.add_parser("restore", help=t("cli.help.restore"))
    restore_parser.add_argument(
        "backup_file", nargs="?", default="", help=t("cli.help.restore.file")
    )
    restore_parser.add_argument(
        "target_dir", nargs="?", default="", help=t("cli.help.restore.dir")
    )
    restore_parser.add_argument(
        "--password", default="", help=t("cli.help.restore.password")
    )
    restore_parser.add_argument(
        "-l", "--list", action="store_true", help=t("cli.help.restore.list")
    )
    restore_parser.add_argument(
        "--select",
        default="",
        help=t("cli.help.restore.select"),
    )
    restore_parser.add_argument("--tag", default="", help=t("cli.help.restore.tag"))

    info_parser = subparsers.add_parser("info", help=t("cli.help.info"))
    info_parser.add_argument("backup_file", help=t("cli.help.info.file"))
    info_parser.add_argument("--password", default="", help=t("cli.help.info.password"))

    diff_parser = subparsers.add_parser("diff", help=t("cli.help.diff"))
    diff_parser.add_argument("source", help=t("cli.help.diff.source"))
    diff_parser.add_argument(
        "backup_file", nargs="?", default=None, help=t("cli.help.diff.file")
    )
    diff_parser.add_argument("--password", default="", help=t("cli.help.diff.password"))
    diff_parser.add_argument(
        "--detail",
        action="store_true",
        default=False,
        help=t("cli.help.diff.detail"),
    )

    verify_parser = subparsers.add_parser("verify", help=t("cli.help.verify"))
    verify_parser.add_argument(
        "backup_file", nargs="?", default=None, help=t("cli.help.verify.file")
    )
    verify_parser.add_argument(
        "--fast",
        action="store_true",
        default=False,
        help=t("cli.help.verify.fast"),
    )
    verify_parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help=t("cli.help.verify.all"),
    )
    verify_parser.add_argument(
        "--detail",
        action="store_true",
        default=False,
        help=t("cli.help.verify.detail"),
    )
    verify_parser.add_argument(
        "--split",
        action="store_true",
        default=False,
        help=t("cli.help.verify.split"),
    )
    verify_parser.add_argument(
        "--password", default="", help=t("cli.help.verify.password")
    )

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

    remote_parser = subparsers.add_parser("remote", help=t("cli.help.remote"))
    remote_sub = remote_parser.add_subparsers(
        dest="remote_action", help=t("cli.help.remote.action")
    )
    remote_list_parser = remote_sub.add_parser("list", help=t("cli.help.remote.list"))
    remote_list_parser.add_argument(
        "--path", default=None, help=t("cli.help.remote.list_path")
    )
    remote_list_parser.add_argument(
        "--sftp", action="store_true", default=False, help=t("cli.help.remote.sftp")
    )
    remote_list_parser.add_argument(
        "--webdav", action="store_true", default=False, help=t("cli.help.remote.webdav")
    )
    remote_rm_parser = remote_sub.add_parser("rm", help=t("cli.help.remote.rm"))
    remote_rm_parser.add_argument("filename", help=t("cli.help.remote.rm.filename"))
    remote_rm_parser.add_argument(
        "--sftp", action="store_true", default=False, help=t("cli.help.remote.sftp")
    )
    remote_rm_parser.add_argument(
        "--webdav", action="store_true", default=False, help=t("cli.help.remote.webdav")
    )

    export_parser = subparsers.add_parser("export", help=t("cli.help.export"))
    export_parser.add_argument(
        "file",
        nargs="?",
        default="sbackup_export.json",
        help=t("cli.help.export.file"),
    )

    import_parser = subparsers.add_parser("import", help=t("cli.help.import"))
    import_parser.add_argument("file", help=t("cli.help.import.file"))

    ignore_parser = subparsers.add_parser("ignore", help=t("cli.help.ignore"))
    ignore_parser.add_argument(
        "--preset",
        choices=["node", "python", "go", "rust", "java", "general"],
        default="general",
        help=t("cli.help.ignore.preset"),
    )
    ignore_parser.add_argument(
        "-o",
        "--output",
        default=".sbackupignore",
        help=t("cli.help.ignore.output"),
    )
    ignore_parser.add_argument(
        "--list",
        action="store_true",
        dest="list_presets",
        help=t("cli.help.ignore.list"),
    )

    subparsers.add_parser("status", help=t("cli.help.status"))

    report_parser = subparsers.add_parser("report", help=t("cli.help.report"))
    report_parser.add_argument(
        "-o", "--output", default="", help=t("cli.help.report.output")
    )

    search_parser = subparsers.add_parser("search", help=t("cli.help.search"))
    search_parser.add_argument("pattern", help=t("cli.help.search.pattern"))
    search_parser.add_argument(
        "--in", dest="backup_file", default=None, help=t("cli.help.search.in")
    )
    search_parser.add_argument(
        "--password", default="", help=t("cli.help.search.password")
    )

    versions_parser = subparsers.add_parser("versions", help=t("cli.help.versions"))
    versions_parser.add_argument(
        "source", nargs="?", default="", help=t("cli.help.versions.source")
    )
    versions_parser.add_argument("--tag", default="", help=t("cli.help.versions.tag"))

    schedule_parser = subparsers.add_parser("schedule", help=t("cli.help.schedule"))
    schedule_sub = schedule_parser.add_subparsers(
        dest="schedule_action", help=t("cli.help.schedule.action")
    )
    schedule_export = schedule_sub.add_parser(
        "export", help=t("cli.help.schedule.export")
    )
    schedule_export.add_argument(
        "--type",
        choices=["systemd", "crontab", "schtasks"],
        default="systemd",
        help=t("cli.help.schedule.type"),
    )
    schedule_export.add_argument(
        "--interval",
        type=int,
        default=60,
        help=t("cli.help.schedule.interval"),
    )
    schedule_export.add_argument(
        "-o", "--output", default="", help=t("cli.help.schedule.output")
    )

    schedule_install = schedule_sub.add_parser(
        "install", help=t("cli.help.schedule.install")
    )
    schedule_install.add_argument(
        "--type",
        choices=["systemd", "schtasks", "launchd"],
        default="systemd",
        help=t("cli.help.schedule.install.type"),
    )
    schedule_install.add_argument(
        "--interval",
        type=int,
        default=60,
        help=t("cli.help.schedule.install.interval"),
    )
    schedule_install.add_argument(
        "--user",
        default="",
        help=t("cli.help.schedule.install.user"),
    )

    webhook_parser = subparsers.add_parser("webhook", help=t("cli.help.webhook_cmd"))
    webhook_sub = webhook_parser.add_subparsers(
        dest="webhook_action", help=t("cli.help.webhook_cmd.action")
    )
    webhook_preset = webhook_sub.add_parser(
        "preset", help=t("cli.help.webhook_cmd.preset")
    )
    webhook_preset.add_argument(
        "name",
        choices=["dingtalk", "feishu", "wechat"],
        help=t("cli.help.webhook_cmd.preset.name"),
    )
    webhook_sub.add_parser("list", help=t("cli.help.webhook_cmd.list"))

    config_parser = subparsers.add_parser("config", help=t("cli.help.config_cmd"))
    config_sub = config_parser.add_subparsers(
        dest="config_action", help=t("cli.help.config_cmd.action")
    )
    config_lock = config_sub.add_parser("lock", help=t("cli.help.config_cmd.lock"))
    config_lock.add_argument(
        "--password", default="", help=t("cli.help.config_cmd.lock.password")
    )
    config_unlock = config_sub.add_parser(
        "unlock", help=t("cli.help.config_cmd.unlock")
    )
    config_unlock.add_argument(
        "--password", default="", help=t("cli.help.config_cmd.unlock.password")
    )
    config_sub.add_parser("validate", help=t("cli.help.config_cmd.validate"))

    clean_parser = subparsers.add_parser("clean", help=t("cli.help.clean"))
    clean_parser.add_argument(
        "--keep", type=int, default=0, help=t("cli.help.clean.keep")
    )
    clean_parser.add_argument(
        "--keep-days", type=int, default=0, help=t("cli.help.clean.keep_days")
    )
    completion_parser = subparsers.add_parser(
        "completion", help=t("cli.help.completion")
    )
    completion_parser.add_argument(
        "shell",
        nargs="?",
        default="bash",
        choices=["bash", "zsh", "fish", "powershell"],
        help=t("cli.help.completion.shell"),
    )

    clean_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=t("cli.help.clean.dry_run"),
    )

    rotate_parser = subparsers.add_parser("rotate", help=t("cli.help.rotate"))
    rotate_sub = rotate_parser.add_subparsers(
        dest="rotate_action", help="rotate action"
    )
    rotate_list_parser = rotate_sub.add_parser("list", help=t("cli.help.rotate_list"))
    rotate_list_parser.add_argument(
        "backup_dir", help=t("cli.help.rotate_list.backup_dir")
    )
    rotate_parser.add_argument(
        "backup_dir", nargs="?", default=None, help=t("cli.help.rotate.backup_dir")
    )
    rotate_parser.add_argument(
        "--keep-count",
        type=int,
        default=0,
        help=t("cli.help.rotate.keep_count"),
    )
    rotate_parser.add_argument(
        "--keep-days",
        type=int,
        default=0,
        help=t("cli.help.rotate.keep_days"),
    )
    rotate_parser.add_argument(
        "--keep-daily",
        type=int,
        default=0,
        help=t("cli.help.rotate.keep_daily"),
    )
    rotate_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=t("cli.help.rotate.dry_run"),
    )

    diskcheck_parser = subparsers.add_parser("diskcheck", help=t("cli.help.diskcheck"))
    diskcheck_parser.add_argument("source", help=t("cli.help.diskcheck.source"))
    diskcheck_parser.add_argument("target", help=t("cli.help.diskcheck.target"))
    diskcheck_parser.add_argument(
        "--level",
        type=int,
        default=6,
        help=t("cli.help.diskcheck.level"),
    )

    subparsers.add_parser("version", help=t("cli.help.version"))

    subparsers.add_parser("wizard", help=t("cli.help.wizard"))

    integrity_parser = subparsers.add_parser("integrity", help=t("cli.help.integrity"))
    integrity_sub = integrity_parser.add_subparsers(
        dest="integrity_action", help=t("cli.help.integrity.action")
    )
    integrity_gen = integrity_sub.add_parser(
        "generate", help=t("cli.help.integrity.generate")
    )
    integrity_gen.add_argument("path", help=t("cli.help.integrity.path"))
    integrity_verify = integrity_sub.add_parser(
        "verify", help=t("cli.help.integrity.verify")
    )
    integrity_verify.add_argument("path", help=t("cli.help.integrity.path"))

    task_parser = subparsers.add_parser("task", help=t("cli.help.task"))
    task_sub = task_parser.add_subparsers(
        dest="task_action", help=t("cli.help.task.action")
    )

    task_add = task_sub.add_parser("add", help=t("cli.help.task.add"))
    task_add.add_argument("name", help=t("cli.help.task.add.name"))
    task_add.add_argument("folder", help=t("cli.help.task.add.folder"))
    task_add.add_argument(
        "--format",
        default="ZIP",
        choices=["zip", "tar", "tar.gz", "tar.bz2", "tar.xz", "tar.zst", "7z"],
        help=t("cli.help.task.add.format"),
    )
    task_add.add_argument(
        "--output",
        default=None,
        help=t("cli.help.task.add.output"),
    )

    task_list = task_sub.add_parser("list", help=t("cli.help.task.list"))
    task_list.add_argument(
        "--status",
        default=None,
        choices=["pending", "running", "completed", "failed"],
        help=t("cli.help.task.list.status"),
    )

    task_sub.add_parser("run", help=t("cli.help.task.run"))
    task_sub.add_parser("run-all", help=t("cli.help.task.run_all"))

    task_cancel = task_sub.add_parser("cancel", help=t("cli.help.task.cancel"))
    task_cancel.add_argument("id", help=t("cli.help.task.cancel.id"))

    task_sub.add_parser("clear", help=t("cli.help.task.clear"))
    task_sub.add_parser("stats", help=t("cli.help.task.stats"))

    return parser


def parse_path(path_str: str) -> str:
    return os.path.expanduser(path_str.strip())


def _parse_size(size_str: str) -> int:
    """解析文件大小字符串（如 '1GB', '500MB', '100KB'）为字节数"""
    if not size_str:
        return 0
    size_str = size_str.strip().upper()
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
    for suffix, multiplier in units.items():
        if size_str.endswith(suffix):
            return int(float(size_str[: -len(suffix)]) * multiplier)
    return int(size_str)


def _parse_duration(duration_str: str) -> float:
    """解析时间 duration（如 '7d', '30d', '1y'）为秒数"""
    if not duration_str:
        return 0
    duration_str = duration_str.strip().lower()
    units = {"d": 86400, "w": 604800, "m": 2592000, "y": 31536000}
    for suffix, multiplier in units.items():
        if duration_str.endswith(suffix):
            return float(duration_str[: -len(suffix)]) * multiplier
    return float(duration_str)


def _handle_version(args, config, manager) -> int:
    print(t("cli.version", version=VERSION))
    return 0


def _handle_add(args, config, manager) -> int:
    source = parse_path(args.source)
    dest = parse_path(args.dest)
    entry_fmt = args.format.upper().replace(".", "_") if args.format else ""
    entry_template = args.name_template or ""
    # 从 .gitignore 导入忽略规则
    ignore_patterns = args.ignore
    if args.from_gitignore:
        from sbackup.config import parse_gitignore

        gitignore_patterns = parse_gitignore(args.from_gitignore)
        if gitignore_patterns:
            # 合并 .gitignore 规则和默认规则
            existing = [s.strip() for s in ignore_patterns.split(",") if s.strip()]
            merged = existing + gitignore_patterns
            ignore_patterns = ",".join(merged)
            print(
                t(
                    "cmd.add.gitignore_imported",
                    count=len(gitignore_patterns),
                    path=args.from_gitignore,
                )
            )
        else:
            print(t("cmd.add.gitignore_empty", path=args.from_gitignore))
    success = manager.add_folder(
        source, dest, ignore_patterns, entry_fmt, entry_template
    )
    if success:
        print(t("cmd.add.success", source=source, dest=dest))
        return 0
    return 1


def _handle_rm(args, config, manager) -> int:
    if args.all:
        entries = {k: v for k, v in manager.data.items() if k != "_history"}
        if not entries:
            print(t("cmd.rm.all.empty"))
            return 0
        count = len(entries)
        confirm_words = t("cmd.rm.all.confirm_words").split(",")
        confirm = input(t("cmd.rm.all.confirm", count=count))
        if confirm.strip().lower() in confirm_words:
            for key in list(manager.data.keys()):
                if key != "_history":
                    del manager.data[key]
            manager.save()
            print(t("cmd.rm.all.success", count=count))
            return 0
        return 1
    if not args.path:
        print(t("warn.no.strategy.found", path=""))
        return 1
    path = parse_path(args.path)
    success = manager.rm_folder(path)
    if success:
        print(t("cmd.rm.success", path=path))
        return 0
    return 1


def _handle_all(args, config, manager) -> int:
    print(manager.list_folder_table())
    return 0


def _handle_edit(args, config, manager) -> int:
    source = parse_path(args.source)
    new_fmt = args.format.upper().replace(".", "_") if args.format else None
    success = manager.edit_strategy(
        source,
        new_target=parse_path(args.dest) if args.dest else None,
        new_ignore=args.ignore,
        new_format=new_fmt,
        new_name_template=args.name_template,
    )
    if success:
        print(t("cmd.edit.success", path=source))
        return 0
    return 1


def _handle_list(args, config, manager) -> int:
    if getattr(args, "tags", False):
        tags = manager.get_tags()
        if not tags:
            print(t("cmd.list.tags.empty"))
        else:
            print(t("cmd.list.tags.header"))
            for tag in sorted(tags):
                print(f"  {tag}")
        return 0
    print(manager.format_history_table())
    return 0


def _handle_save(args, config, manager) -> int:
    from sbackup.lock import BackupLock

    if args.password:
        print(t("warn.password_in_cli"), file=sys.stderr)
    lock = BackupLock(os.path.dirname(config.data_file) or ".")
    if not lock.acquire():
        print(t("err.lock.conflict"))
        return 1
    try:
        if args.dry_run:
            # 使用 DryRunScanner 生成详细的预览报告
            from sbackup.dryrun import DryRunScanner

            for key, raw in manager.data.items():
                if key in ("_history", "_file_meta"):
                    continue
                from sbackup.auto_save import BackupEntry

                entry = BackupEntry.from_list(raw)
                source_dir = key
                if not os.path.isdir(source_dir):
                    continue
                scan_config = Config(
                    folder_path=source_dir,
                    skip_patterns=entry.skip_patterns,
                    include_patterns=getattr(entry, "include_patterns", []),
                    exclude_patterns=getattr(entry, "exclude_patterns", []),
                    max_size=_parse_size(args.max_size) if args.max_size else 0,
                    min_size=_parse_size(args.min_size) if args.min_size else 0,
                    follow_symlinks=args.follow_symlinks,
                )
                scanner = DryRunScanner(source_dir, scan_config)
                result = scanner.scan()
                print(scanner.format_summary(result, lang=config.lang))
                print()
        else:
            # 备份前磁盘空间检查
            from sbackup.diskcheck import DiskChecker
            from sbackup.diskcheck import _format_size as _fmt_size

            strict = getattr(args, "strict", False)
            for key, raw in manager.data.items():
                if key in ("_history", "_file_meta"):
                    continue
                from sbackup.auto_save import BackupEntry

                entry = BackupEntry.from_list(raw)
                source_dir = key
                target_dir = entry.target
                if not os.path.isdir(source_dir):
                    continue
                fmt = config.compression_format
                level = config.compression_level
                checker = DiskChecker(source_dir, target_dir)
                info = checker.check(fmt=fmt, compression_level=level)
                if not info.enough:
                    report = checker.format_report(info, lang=config.lang)
                    print(report)
                    if strict:
                        print(
                            t(
                                "diskcheck.insufficient",
                                needed=_fmt_size(info.estimated_backup),
                                available=_fmt_size(info.free),
                                missing=_fmt_size(abs(info.margin)),
                            )
                        )
                        return 1

            manager.execute_backups(
                keep=args.keep,
                keep_days=args.keep_days,
                password=args.password,
                sftp_upload=args.sftp,
                webdav_upload=args.webdav,
                cloud_upload=args.cloud,
                dry_run=False,
                verify=args.verify,
                name_template=args.name_template,
                webhook_url=args.webhook,
                follow_symlinks=args.follow_symlinks,
                max_size=_parse_size(args.max_size) if args.max_size else 0,
                min_size=_parse_size(args.min_size) if args.min_size else 0,
                max_age_seconds=_parse_duration(args.older_than)
                if args.older_than
                else 0,
                incremental=args.incremental,
                split_size=_parse_size(args.split) if args.split else 0,
                tag=args.tag or "",
                checksum=args.checksum,
                pre_hooks=getattr(args, "pre_hook", None) or [],
                post_hooks=getattr(args, "post_hook", None) or [],
                dedup=args.dedup,
                threads=args.threads,
            )
    finally:
        lock.release()
    return 0


def _handle_compress(args, config, manager) -> int:
    """处理 compress 子命令：直接压缩指定文件夹"""
    source = parse_path(args.source)
    if not os.path.isdir(source):
        print(t("err.folder.invalid", path=source))
        return 1

    # 构建 Config
    fmt = args.format.upper().replace(".", "_") if args.format else None
    compress_config = Config(
        folder_path=source,
        compression_format=fmt or config.compression_format,
        skip_patterns=config.skip_patterns,
        password=args.password or config.password,
        follow_symlinks=args.follow_symlinks,
        name_template=config.name_template,
    )
    if args.output:
        compress_config.zipfile_path = args.output

    if args.dry_run:
        # Dry-run: 使用 DryRunScanner 扫描并显示预览
        from sbackup.dryrun import DryRunScanner

        scanner = DryRunScanner(source, compress_config)
        result = scanner.scan()
        print(scanner.format_summary(result, lang=config.lang))
        return 0

    # 实际执行压缩
    from sbackup.compression import create_compressor

    compressor = create_compressor(compress_config)
    result = compressor.compress()
    return 0 if result.get("success") else 1


def _handle_watch(args, config, manager) -> int:
    from sbackup.lock import BackupLock

    import time as _time

    interval_sec = max(args.interval, 1) * 60
    realtime = getattr(args, "realtime", False)
    debounce = max(getattr(args, "debounce", 30), 1)

    # watch 命令长期持有锁，阻止并发 save/watch
    lock = BackupLock(os.path.dirname(config.data_file) or ".")
    if not lock.acquire():
        print(t("err.lock.conflict"))
        return 1

    if args.password:
        print(t("warn.password_in_cli"), file=sys.stderr)

    def do_backup() -> None:
        manager.execute_backups(
            keep=args.keep,
            keep_days=args.keep_days,
            password=args.password,
            sftp_upload=args.sftp,
            webdav_upload=args.webdav,
            cloud_upload=args.cloud,
            dry_run=args.dry_run,
            verify=args.verify,
            name_template=args.name_template,
            webhook_url=args.webhook,
            follow_symlinks=args.follow_symlinks,
            max_size=_parse_size(args.max_size) if args.max_size else 0,
            min_size=_parse_size(args.min_size) if args.min_size else 0,
            max_age_seconds=_parse_duration(args.older_than) if args.older_than else 0,
            incremental=args.incremental,
            split_size=_parse_size(args.split) if args.split else 0,
            tag=args.tag or "",
            checksum=args.checksum,
            pre_hooks=getattr(args, "pre_hook", None) or [],
            post_hooks=getattr(args, "post_hook", None) or [],
            dedup=args.dedup,
            threads=args.threads,
        )

    try:
        if realtime:
            from sbackup.monitor import FileSystemMonitor
            from sbackup.auto_save import BackupEntry

            source_dirs: dict[str, str] = {}
            for key, raw in manager.data.items():
                if key in ("_history", "_file_meta"):
                    continue
                entry = BackupEntry.from_list(raw)
                source_dirs[key] = entry.target

            if not source_dirs:
                print(t("cmd.all.empty"))
                return 1

            monitor = FileSystemMonitor(source_dirs, debounce_seconds=debounce)
            monitor.set_backup_callback(do_backup)

            print(t("cmd.watch.start_realtime", debounce=debounce))
            monitor.start()

            if not monitor.is_running():
                return 1

            try:
                do_backup()
                while True:
                    _time.sleep(interval_sec)
                    do_backup()
            except KeyboardInterrupt:
                pass
            finally:
                monitor.stop()
            return 0

        print(t("cmd.watch.start", interval=args.interval))
        while True:
            do_backup()
            _time.sleep(interval_sec)
    except KeyboardInterrupt:
        return 0
    finally:
        lock.release()


def _handle_restore(args, config, manager) -> int:
    tag = getattr(args, "tag", "") or ""
    if tag:
        entries = manager.get_history_by_tag(tag)
        if not entries:
            print(t("cmd.restore.tag_not_found", tag=tag))
            return 1
        backup_path = entries[-1].get("path", "")
        if not backup_path or not os.path.isfile(backup_path):
            print(t("cmd.restore.tag_not_found", tag=tag))
            return 1
        target_dir = args.backup_file or ""
        if not target_dir:
            print(t("cli.help.restore.dir"))
            return 1
    else:
        backup_path = args.backup_file or ""
        target_dir = args.target_dir or ""
        if not backup_path or not target_dir:
            parser = get_parser()
            parser.print_help()
            return 1
    if args.list:
        from sbackup.compression import list_backup_contents

        print(list_backup_contents(backup_path, args.password))
        return 0
    result = restore_backup(
        backup_path,
        target_dir,
        args.password,
        select_pattern=getattr(args, "select", "") or "",
    )
    return 0 if result["success"] else 1


def _handle_info(args, config, manager) -> int:
    from sbackup.compression import get_backup_info, format_backup_info

    info = get_backup_info(args.backup_file, args.password)
    print(format_backup_info(info))
    return 0 if info.get("success") else 1


def _handle_diff(args, config, manager) -> int:
    source = parse_path(args.source)
    diff_result = manager.diff_backup(
        source, args.backup_file, args.password, detail=args.detail
    )
    if not diff_result.get("success"):
        return 1

    if args.detail:
        # 显示详细的行级差异
        print(t("cmd.diff.detail_header"))
        detail_map = diff_result.get("detail", {})
        modified = diff_result.get("modified", [])
        for f in modified:
            if f in detail_map:
                print(f"\n--- {f} ---")
                print(detail_map[f])
            else:
                print(f"\n--- {f} ---")
                print(t("cmd.diff.no_detail"))
        has_changes = diff_result["added"] or diff_result["removed"] or modified
        return 1 if has_changes else 0
    else:
        print(manager.format_diff(diff_result))
        has_changes = (
            diff_result["added"] or diff_result["removed"] or diff_result["modified"]
        )
        return 1 if has_changes else 0


def _handle_verify(args, config, manager) -> int:
    from sbackup.compression import (
        verify_backup,
        verify_backup_fast,
        get_backup_info,
        verify_split_integrity,
    )

    # 分卷完整性验证
    if args.split:
        if not args.backup_file:
            print(t("cmd.verify.no_file"))
            return 1
        result = verify_split_integrity(args.backup_file)
        if result["success"]:
            print(
                t(
                    "cmd.verify.split_success",
                    file=result.get("original_file", ""),
                    parts=result.get("parts_count", 0),
                )
            )
            return 0
        else:
            error = result.get("error", "")
            if error:
                print(t("cmd.verify.split_error", error=error))
            else:
                print(
                    t("cmd.verify.split_failed", file=result.get("original_file", ""))
                )
                for r in result.get("results", []):
                    if r["status"] != "ok":
                        print(f"  {r['path']}: {r['status']}")
            return 1

    # 批量验证所有备份
    if args.all:
        history = manager.get_history()
        if not history:
            print(t("cmd.verify.no_history"))
            return 1

        success_count = 0
        fail_count = 0
        for entry in reversed(history):
            source = entry.get("source", "")
            sha256 = entry.get("sha256", "")
            if not source or not os.path.isfile(source):
                continue

            if args.detail:
                info = get_backup_info(source, args.password)
                print(t("cmd.verify.detail_header", path=source))
                print(
                    t(
                        "cmd.verify.detail_info",
                        size=info.get("size_mb", 0),
                        files=info.get("files_count", 0),
                        fmt=info.get("format", "unknown"),
                        sha256=sha256[:16] if sha256 else "N/A",
                    )
                )

            if sha256:
                result = verify_backup_fast(source, sha256)
            else:
                result = verify_backup(source, args.password)

            if result["success"]:
                print(t("cmd.verify.batch_success", path=source))
                success_count += 1
            else:
                print(t("cmd.verify.batch_failed", path=source))
                fail_count += 1

        print(t("cmd.verify.batch_summary", success=success_count, fail=fail_count))
        return 0 if fail_count == 0 else 1

    # 单文件验证
    if not args.backup_file:
        print(t("cmd.verify.no_file"))
        return 1

    if args.detail:
        info = get_backup_info(args.backup_file, args.password)
        sha256 = manager.find_checksum(args.backup_file)
        print(t("cmd.verify.detail_header", path=args.backup_file))
        print(
            t(
                "cmd.verify.detail_info",
                size=info.get("size_mb", 0),
                files=info.get("files_count", 0),
                fmt=info.get("format", "unknown"),
                sha256=sha256[:16] if sha256 else "N/A",
            )
        )

    if args.fast:
        # 快速验证：用历史 SHA256 比对，无需解压
        sha256 = manager.find_checksum(args.backup_file)
        if sha256:
            result = verify_backup_fast(args.backup_file, sha256)
            if result["success"]:
                print(
                    t("cmd.verify.fast_success", path=args.backup_file, sha256=sha256)
                )
                return 0
            else:
                print(t("cmd.verify.fast_failed", path=args.backup_file))
                return 1
        else:
            print(t("cmd.verify.no_checksum", path=args.backup_file))
            # 回退到完整验证
            result = verify_backup(args.backup_file, args.password)
            return 0 if result["success"] else 1
    else:
        result = verify_backup(args.backup_file, args.password)
        return 0 if result["success"] else 1


def _handle_sftp(args, config, manager) -> int:
    from sbackup.handlers import handle_sftp

    return handle_sftp(args, config)


def _handle_webdav(args, config, manager) -> int:
    from sbackup.handlers import handle_webdav

    return handle_webdav(args, config)


def _handle_remote(args, config, manager) -> int:
    """处理 remote 子命令"""
    from sbackup.handlers import handle_remote

    return handle_remote(args, config)


def _handle_report(args, config, manager) -> int:
    report = manager.export_report(args.output)
    if not args.output:
        print(report)
    return 0


def _handle_search(args, config, manager) -> int:
    from pathlib import Path
    from sbackup.compression import search_in_backup
    from sbackup.auto_save import BackupEntry

    if args.backup_file:
        results = search_in_backup(args.backup_file, args.pattern, args.password)
        if results:
            print(t("cmd.search.results", path=args.backup_file, count=len(results)))
            for r in results:
                print(f"  {r}")
        else:
            print(
                t("cmd.search.no_results", pattern=args.pattern, path=args.backup_file)
            )
        return 0 if results else 1

    # 在所有策略的最新备份中搜索
    total_found = 0
    for key, raw in manager.data.items():
        if key == "_history" or key == "_file_meta":
            continue

        entry = BackupEntry.from_list(raw)
        target_dir = Path(entry.target)
        if not target_dir.is_dir():
            continue
        patterns = [
            "*.zip",
            "*.tar",
            "*.tar.gz",
            "*.tar.bz2",
            "*.tar.xz",
            "*.tar.zst",
            "*.7z",
        ]
        all_files = []
        for pat in patterns:
            all_files.extend(target_dir.glob(pat))
        if not all_files:
            continue
        all_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest = str(all_files[0])
        results = search_in_backup(latest, args.pattern, args.password)
        if results:
            print(t("cmd.search.results", path=latest, count=len(results)))
            for r in results:
                print(f"  {r}")
            total_found += len(results)

    if total_found == 0:
        print(t("cmd.search.no_results_global", pattern=args.pattern))
        return 1
    return 0


def _handle_export(args, config, manager) -> int:
    count = manager.export_strategies(args.file)
    if count > 0:
        print(t("cmd.export.success", count=count, path=args.file))
    return 0


def _handle_import(args, config, manager) -> int:
    result = manager.import_strategies(args.file)
    if result is None:
        print(t("cmd.import.empty", path=args.file))
        return 1
    imported, skipped = result
    if imported > 0:
        print(t("cmd.import.success", count=imported, skipped=skipped))
    else:
        print(t("cmd.import.empty", path=args.file))
    return 0


def _handle_ignore(args, config, manager) -> int:
    if args.list_presets:
        from sbackup.compression import IGNORE_PRESETS

        print(t("cmd.ignore.available_presets"))
        for name, patterns in IGNORE_PRESETS.items():
            print(f"  {name:10s} ({len(patterns)} rules)")
        return 0

    from sbackup.compression import generate_ignore_content

    content = generate_ignore_content(args.preset)
    output_path = args.output

    if os.path.exists(output_path):
        confirm = input(t("cmd.ignore.overwrite", path=output_path))
        if confirm.strip().lower() not in ("y", "yes", "是"):
            print(t("cmd.ignore.cancelled"))
            return 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(t("cmd.ignore.generated", path=output_path, preset=args.preset))
    return 0


def _handle_versions(args, config, manager) -> int:
    source = parse_path(args.source) if args.source else ""
    tag = getattr(args, "tag", "") or ""
    print(manager.format_versions(source, tag=tag))
    return 0


def _handle_schedule(args, config, manager) -> int:
    from sbackup.handlers import handle_schedule

    return handle_schedule(args, config)


def _handle_webhook_cmd(args, config, manager) -> int:
    if args.webhook_action == "preset":
        from sbackup.config import setup_webhook_preset

        template = setup_webhook_preset(args.name)
        if template:
            print(t("cmd.webhook.preset_set", name=args.name, template=template))
            return 0
        print(t("cmd.webhook.preset_unknown", name=args.name))
        return 1
    elif args.webhook_action == "list":
        from sbackup.config import WEBHOOK_PRESETS

        print(t("cmd.webhook.available_presets"))
        for key, info in WEBHOOK_PRESETS.items():
            print(f"  {key:10s} — {info['name']}")
        return 0
    print(t("cli.help.webhook_cmd.action"))
    return 1


def _handle_config_cmd(args, config, manager) -> int:
    import getpass
    from sbackup.config import encrypt_config, decrypt_config, is_config_encrypted

    config_path = os.path.abspath("config.json")
    if args.config_action == "lock":
        if is_config_encrypted(config_path):
            print(t("cmd.config.already_locked"))
            return 1
        password = args.password or getpass.getpass(
            t("cmd.config.enter_password") + " "
        )
        if not password:
            print(t("cmd.config.no_password"))
            return 1
        if encrypt_config(password, config_path):
            print(t("cmd.config.locked"))
            return 0
        print(t("cmd.config.lock_failed"))
        return 1
    elif args.config_action == "unlock":
        if not is_config_encrypted(config_path):
            print(t("cmd.config.not_locked"))
            return 0
        password = args.password or getpass.getpass(
            t("cmd.config.enter_password") + " "
        )
        if decrypt_config(password, config_path):
            print(t("cmd.config.unlocked"))
            return 0
        print(t("cmd.config.wrong_password"))
        return 1
    elif args.config_action == "validate":
        from sbackup.schema import validate_config_file

        is_valid, errors, warnings = validate_config_file(config)
        if errors:
            print(t("cmd.config.validate.errors"))
            for e in errors:
                print(f"  [{e.severity}] {e.field}: {e.message}")
        if warnings:
            print(t("cmd.config.validate.warnings"))
            for w in warnings:
                print(f"  [{w.severity}] {w.field}: {w.message}")
        if is_valid and not warnings:
            print(t("cmd.config.validate.passed"))
        elif is_valid:
            print(t("cmd.config.validate.passed_with_warnings"))
        else:
            print(t("cmd.config.validate.failed"))
        return 0 if is_valid else 1
    print(t("cli.help.config_cmd.action"))
    return 1


def _handle_status(args, config, manager) -> int:
    print(manager.format_status())
    return 0


def _handle_clean(args, config, manager) -> int:
    if args.keep <= 0 and args.keep_days <= 0:
        print(t("cmd.clean.no_criteria"))
        return 1
    result = manager.clean_all_backups(
        keep=args.keep, keep_days=args.keep_days, dry_run=args.dry_run
    )
    deleted = result["deleted"]
    if not deleted:
        print(t("cmd.clean.nothing"))
        return 0
    if args.dry_run:
        print(t("cmd.clean.dry_run_header"))
    for f in deleted:
        print(f"  {' rm ' if not args.dry_run else '~~'} {f}")
    print(t("cmd.clean.summary", count=len(deleted)))
    return 0


def _format_size(size_bytes: int) -> str:
    """格式化文件大小为可读字符串"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def _handle_rotate(args, config, manager) -> int:
    """处理 rotate 子命令"""
    from sbackup.rotation import BackupRotator, RotationPolicy

    action = getattr(args, "rotate_action", None)

    if action == "list":
        backup_dir = parse_path(args.backup_dir)
        if not os.path.isdir(backup_dir):
            print(t("err.folder.invalid", path=backup_dir))
            return 1
        rotator = BackupRotator(backup_dir, RotationPolicy())
        backups = rotator.scan_backups()
        if not backups:
            print(t("cmd.rotate.scan_empty", path=backup_dir))
            return 0
        print(t("cmd.rotate.scan_found", count=len(backups), path=backup_dir))
        for b in backups:
            print(
                t(
                    "cmd.rotate.scan_item",
                    name=b["name"],
                    size=_format_size(b["size"]),
                    time=b["mtime_iso"],
                )
            )
        return 0

    # 默认 rotate 行为：根据策略清理
    backup_dir = getattr(args, "backup_dir", None)
    if not backup_dir:
        print(t("cli.help.rotate"))
        return 1

    backup_dir = parse_path(backup_dir)
    if not os.path.isdir(backup_dir):
        print(t("err.folder.invalid", path=backup_dir))
        return 1

    # CLI 参数优先，未指定时从 config 获取
    keep_count = args.keep_count
    keep_days = args.keep_days
    keep_daily = args.keep_daily
    if keep_count <= 0:
        keep_count = config.rotation_keep_count
    if keep_days <= 0:
        keep_days = config.rotation_keep_days
    if keep_daily <= 0:
        keep_daily = config.rotation_keep_daily

    if keep_count <= 0 and keep_days <= 0 and keep_daily <= 0:
        print(t("cmd.clean.no_criteria"))
        return 1

    policy = RotationPolicy(
        keep_count=keep_count,
        keep_days=keep_days,
        keep_daily=keep_daily,
        dry_run=args.dry_run,
    )
    rotator = BackupRotator(backup_dir, policy)
    _keep_list, delete_list = rotator.plan()

    if not delete_list:
        print(t("cmd.rotate.no_action"))
        return 0

    if args.dry_run:
        print(t("cmd.rotate.dry_run_header"))
        for item in delete_list:
            print(
                t(
                    "cmd.rotate.dry_run_item",
                    name=item["name"],
                    size=_format_size(item["size"]),
                    time=item["mtime_iso"],
                )
            )
    else:
        print(t("cmd.rotate.plan_delete", count=len(delete_list)))
        for item in delete_list:
            print(
                t(
                    "cmd.rotate.delete_item",
                    name=item["name"],
                    size=_format_size(item["size"]),
                )
            )

    deleted_count, deleted_paths = rotator.execute()
    if deleted_count > 0 and not args.dry_run:
        print(t("cmd.rotate.done", count=deleted_count))
    return 0


def _handle_diskcheck(args, config, manager) -> int:
    """执行磁盘空间检查"""
    from sbackup.diskcheck import DiskChecker

    source = parse_path(args.source)
    target = parse_path(args.target)

    if not os.path.isdir(source):
        print(t("err.folder.invalid", path=source))
        return 1

    fmt = config.compression_format
    level = args.level
    checker = DiskChecker(source, target)
    info = checker.check(fmt=fmt, compression_level=level)
    report = checker.format_report(info, lang=config.lang)
    print(report)
    return 0 if info.enough else 1


def _handle_completion(args, config, manager) -> int:
    """生成并输出 shell 自动补全脚本"""
    from sbackup.completion import generate

    try:
        script = generate(args.shell)
        print(script, end="")
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


def _handle_integrity(args, config, manager) -> int:
    from sbackup.integrity import generate_backup_integrity, verify_backup_integrity

    action = getattr(args, "integrity_action", None)
    path = parse_path(args.path)

    if action == "generate":
        try:
            integrity_path = generate_backup_integrity(path)
            print(t("cmd.integrity.generate.success", path=integrity_path))
            return 0
        except NotADirectoryError:
            print(t("cmd.integrity.generate.not_dir", path=path))
            return 1
        except OSError as e:
            print(t("err.os", error=e))
            return 1

    elif action == "verify":
        all_ok, messages = verify_backup_integrity(path)
        for msg in messages:
            print(f"  {msg}")
        if all_ok:
            print(t("cmd.integrity.verify.success", path=path))
        else:
            print(t("cmd.integrity.verify.failed", path=path))
        return 0 if all_ok else 1

    else:
        parser = get_parser()
        parser.parse_args(["integrity", "--help"])
        return 1


def _handle_wizard(args, config, manager) -> int:
    from sbackup.wizard import run_wizard

    return run_wizard(config.data_file)


def _handle_task(args, config, manager) -> int:
    from sbackup.task_queue import TaskQueue

    queue = TaskQueue()
    action = getattr(args, "task_action", None)

    if action == "add":
        task_id = queue.add_task(
            name=args.name,
            folder_path=args.folder,
            zipfile_path=args.output,
            compression_format=args.format,
        )
        print(t("task_queue.added", name=args.name, id=task_id))
        return 0

    elif action == "list":
        status_filter = getattr(args, "status", None)
        tasks = queue.list_tasks(status=status_filter)
        if not tasks:
            print(t("task_queue.list.empty"))
            return 0
        print(t("task_queue.list.header", count=len(tasks)))
        for task in tasks:
            print(
                t(
                    "task_queue.list.item",
                    status=task.status,
                    name=task.name,
                    id=task.id,
                )
            )
            print(t("task_queue.list.item_detail", folder=task.folder_path))
            if task.result_path:
                print(t("task_queue.list.item_result", result=task.result_path))
            if task.error:
                print(t("task_queue.list.item_error", error=task.error))
            if task.created_at:
                print(t("task_queue.list.item_time", created=task.created_at))
        return 0

    elif action == "run":
        task = queue.run_next()
        if task is None:
            print(t("task_queue.run.none"))
            return 0
        if task.status == "completed":
            print(t("task_queue.run.success", name=task.name, result=task.result_path))
            return 0
        else:
            print(t("task_queue.run.failed", name=task.name, error=task.error))
            return 1

    elif action == "run-all":
        executed = queue.run_all()
        if not executed:
            print(t("task_queue.run.none"))
            return 0
        success = sum(1 for t in executed if t.status == "completed")
        failed = len(executed) - success
        print(
            t(
                "task_queue.run_all.done",
                count=len(executed),
                success=success,
                failed=failed,
            )
        )
        return 0 if failed == 0 else 1

    elif action == "cancel":
        if queue.cancel_task(args.id):
            print(t("task_queue.cancelled.success", id=args.id))
            return 0
        else:
            print(t("task_queue.cancelled.fail"))
            return 1

    elif action == "clear":
        count = queue.clear_completed()
        if count > 0:
            print(t("task_queue.clear.done", count=count))
        else:
            print(t("task_queue.clear.none"))
        return 0

    elif action == "stats":
        stats = queue.get_stats()
        print(t("task_queue.stats.header"))
        print(t("task_queue.stats.total", total=stats["total"]))
        print(t("task_queue.stats.pending", pending=stats["pending"]))
        print(t("task_queue.stats.running", running=stats["running"]))
        print(t("task_queue.stats.completed", completed=stats["completed"]))
        print(t("task_queue.stats.failed", failed=stats["failed"]))
        return 0

    else:
        parser = get_parser()
        parser.parse_args(["task", "--help"])
        return 1


_COMMAND_HANDLERS: dict[str, callable] = {
    "version": _handle_version,
    "wizard": _handle_wizard,
    "add": _handle_add,
    "rm": _handle_rm,
    "remove": _handle_rm,
    "edit": _handle_edit,
    "all": _handle_all,
    "list": _handle_list,
    "history": _handle_list,
    "save": _handle_save,
    "watch": _handle_watch,
    "compress": _handle_compress,
    "restore": _handle_restore,
    "info": _handle_info,
    "diff": _handle_diff,
    "verify": _handle_verify,
    "sftp": _handle_sftp,
    "webdav": _handle_webdav,
    "remote": _handle_remote,
    "export": _handle_export,
    "import": _handle_import,
    "status": _handle_status,
    "ignore": _handle_ignore,
    "versions": _handle_versions,
    "schedule": _handle_schedule,
    "webhook": _handle_webhook_cmd,
    "config": _handle_config_cmd,
    "report": _handle_report,
    "search": _handle_search,
    "clean": _handle_clean,
    "rotate": _handle_rotate,
    "diskcheck": _handle_diskcheck,
    "completion": _handle_completion,
    "integrity": _handle_integrity,
    "task": _handle_task,
}


def run() -> int:
    # 预处理 --debug：允许放在子命令之后
    debug_enabled = "--debug" in sys.argv
    cleaned_argv = [arg for arg in sys.argv if arg != "--debug"]

    # 先检测 --lang 参数，初始化语言环境，再创建本地化 parser
    lang_from_argv = _detect_lang_from_argv()
    config = load_config()
    current_lang = lang_from_argv if lang_from_argv is not None else config.lang
    set_locale(current_lang)

    # 保存并替换 sys.argv，用 cleaned_argv 解析
    original_argv = sys.argv
    sys.argv = cleaned_argv

    parser = get_parser()
    args = parser.parse_args()

    # 恢复原始 sys.argv（避免影响其他代码）
    sys.argv = original_argv

    # init 命令在持久化语言设置之前处理（避免 save_lang 创建 config.json）
    if args.command == "init":
        config_path = os.path.abspath("config.json")
        if os.path.exists(config_path):
            print(t("cmd.init.exists", path=config_path))
            return 1
        from sbackup.config import generate_config_template

        generate_config_template(config_path)
        print(t("cmd.init.success", path=config_path))
        return 0

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

    handler = _COMMAND_HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
        return 0

    manager = BackupManager(data_file=config.data_file)
    return handler(args, config, manager)
