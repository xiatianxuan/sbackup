import os
import json
import shutil
import logging
import unicodedata
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dataclasses import dataclass
from sbackup.config import (
    Config,
    load_config,
    get_default_data_file,
    DEFAULT_SKIP_PATTERNS,
)
from sbackup.compression import create_compressor
from sbackup.i18n import t

logger = logging.getLogger(__name__)

_HISTORY_KEY = "_history"


@dataclass
class BackupEntry:
    """备份策略条目"""

    mtime: float
    target: str
    skip_patterns: list[str]
    compression_format: str = ""  # 空字符串表示使用全局默认格式
    name_template: str = ""  # 空字符串表示使用全局默认模板

    def to_list(self) -> list:
        """转为 JSON 兼容的列表格式"""
        return [
            self.mtime,
            self.target,
            self.skip_patterns,
            self.compression_format,
            self.name_template,
        ]

    @staticmethod
    def from_list(data: list) -> "BackupEntry":
        """从 JSON 兼容的列表格式创建（向后兼容旧格式）"""
        if not isinstance(data, list) or len(data) < 3:
            return BackupEntry(mtime=0.0, target="", skip_patterns=[])
        fmt = data[3] if len(data) > 3 else ""
        tpl = data[4] if len(data) > 4 else ""
        return BackupEntry(
            mtime=data[0],
            target=data[1],
            skip_patterns=data[2],
            compression_format=fmt,
            name_template=tpl,
        )


class BackupManager:
    """
    管理备份策略的类，封装状态和读写操作
    """

    def __init__(self, data_file: str = ""):
        self.data_file: str = data_file or get_default_data_file()
        self.data: dict[str, list] = {}
        self.load()

    def load(self):
        """
        从 JSON 文件加载数据到内存
        """
        logger.debug(t("log.data.read"), self.data_file)
        if not os.path.exists(self.data_file):
            logger.debug(t("log.data.create"), self.data_file)
            self.save(initial=True)
        else:
            logger.debug(t("log.data.load"), self.data_file)
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except json.JSONDecodeError:
                print(t("warn.json.decode.error", path=self.data_file))
                # 备份损坏文件，避免数据丢失
                backup_path = self.data_file + ".bak"
                try:
                    shutil.copy2(self.data_file, backup_path)
                    print(t("warn.json.backup", path=backup_path))
                except OSError:
                    # 备份失败时重命名损坏文件，避免下次再次触发
                    try:
                        os.rename(self.data_file, self.data_file + ".corrupted")
                        print(
                            t("warn.json.renamed", path=self.data_file + ".corrupted")
                        )
                    except OSError:
                        pass
                self.data = {}

    def save(self, initial: bool = False):
        """
        将内存数据写入 JSON 文件
        """
        if not initial:
            logger.debug(t("log.data.write"), self.data_file)

        data_dir = os.path.dirname(self.data_file)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)

        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    def _get_entry(self, key: str) -> BackupEntry | None:
        """获取指定路径的备份策略条目"""
        raw = self.data.get(key)
        if raw is None:
            return None
        return BackupEntry.from_list(raw)

    def _set_entry(self, key: str, entry: BackupEntry):
        """设置指定路径的备份策略条目"""
        self.data[key] = entry.to_list()

    def add_folder(
        self,
        folder_path: str,
        target_folder: str,
        skip_patterns: str | None = None,
        compression_format: str = "",
        name_template: str = "",
    ):
        """
        添加备份策略
        :param compression_format: 条目级打包格式，空字符串使用全局默认
        :param name_template: 条目级文件名模板，空字符串使用全局默认
        """
        if skip_patterns is None:
            skip_patterns = ",".join(DEFAULT_SKIP_PATTERNS)
        skip_list = (
            [s.strip() for s in skip_patterns.split(",") if s.strip()]
            if skip_patterns
            else []
        )

        if not os.path.isdir(folder_path):
            print(t("err.folder.invalid", path=folder_path))
            return False
        if not os.path.isdir(target_folder):
            print(t("err.dest.invalid", path=target_folder))
            return False

        abs_path = os.path.abspath(folder_path)
        abs_dest = os.path.abspath(target_folder)
        if abs_path == abs_dest:
            print(t("err.dest.invalid", path=target_folder))
            return False
        if abs_path in self.data:
            print(t("info.already.added", path=abs_path))
            return False

        try:
            entry = BackupEntry(
                mtime=os.stat(abs_path).st_mtime,
                target=os.path.abspath(target_folder),
                skip_patterns=skip_list,
                compression_format=compression_format,
                name_template=name_template,
            )
        except OSError as e:
            print(t("err.os", error=e))
            return False
        self._set_entry(abs_path, entry)
        self.save()
        return True

    def rm_folder(self, folder_path: str) -> bool:
        """
        删除备份策略
        """
        abs_path = os.path.abspath(folder_path)
        if abs_path in self.data:
            del self.data[abs_path]
            self.save()
            return True
        else:
            print(t("warn.no.strategy.found", path=abs_path))
            return False

    def execute_backups(
        self,
        keep: int = 0,
        password: str = "",
        sftp_upload: bool = False,
        webdav_upload: bool = False,
        dry_run: bool = False,
        verify: bool = False,
        name_template: str | None = None,
        webhook_url: str | None = None,
        follow_symlinks: bool = False,
        max_size: int = 0,
        min_size: int = 0,
        max_age_seconds: float = 0,
        incremental: bool = False,
    ):
        """
        执行所有备份策略
        :param keep: 保留最近 N 个备份文件，0 表示不清理
        :param password: 加密密码（仅 7z 格式支持）
        :param sftp_upload: 是否在备份后上传到 SFTP 服务器
        :param webdav_upload: 是否在备份后上传到 WebDAV 服务器
        :param dry_run: 仅预览将备份的文件，不实际执行
        :param verify: 备份后自动校验完整性
        :param name_template: 备份文件名模板（覆盖全局和条目级设置）
        :param webhook_url: 备份完成后 POST 结果到此 URL
        :param follow_symlinks: 是否跟随符号链接
        :param max_size: 文件大小上限（字节），0 不限制
        :param min_size: 文件大小下限（字节），0 不限制
        :param max_age_seconds: 文件年龄上限（秒），0 不限制
        :param incremental: 文件级增量备份（仅压缩变化的文件）
        """
        config = load_config()
        start_time = time.monotonic()

        # 加载文件级元数据（增量备份用）
        file_meta_all = self.data.get("_file_meta", {}) if incremental else {}

        # 收集需要备份的条目
        tasks = []
        skip_count = 0
        for key, raw in list(self.data.items()):
            if key in (_HISTORY_KEY, "_file_meta"):
                continue
            if not os.path.exists(key):
                print(t("warn.source.missing", path=key))
                continue
            try:
                current_mtime = os.stat(key).st_mtime
            except OSError as e:
                print(t("err.os", error=e))
                continue
            entry = BackupEntry.from_list(raw)
            file_meta = file_meta_all.get(key, {}) if incremental else {}
            if entry.mtime != current_mtime:
                tasks.append(
                    (
                        key,
                        entry,
                        current_mtime,
                        config,
                        password,
                        name_template,
                        follow_symlinks,
                        max_size,
                        min_size,
                        max_age_seconds,
                        file_meta,
                    )
                )
            else:
                skip_count += 1

        # dry-run 模式：仅预览，不执行备份
        if dry_run:
            self._dry_run_preview(tasks, config)
            return

        backup_count = 0
        verify_failures = 0
        uploaded_files = []

        if len(tasks) > 1:
            # 并行备份多个策略
            logger.debug(t("log.parallel.backup"), len(tasks))
            with ThreadPoolExecutor() as executor:
                futures = {
                    executor.submit(self._do_backup, *task): task for task in tasks
                }
                for future in as_completed(futures):
                    key, entry, current_mtime, _, _, _, _, _, _, _, _ = futures[future]
                    try:
                        result = future.result()
                    except Exception as e:
                        logger.error("Backup failed for %s: %s", key, e)
                        result = {"success": False}
                    if result and result.get("success"):
                        entry.mtime = current_mtime
                        self._set_entry(key, entry)
                        self._add_history(
                            key,
                            result["size_mb"],
                            result["files_count"],
                            result.get("original_size_mb", 0.0),
                        )
                        if incremental:
                            self.data.setdefault("_file_meta", {})[key] = (
                                self._collect_file_meta(key)
                            )
                        if keep > 0:
                            self._cleanup_old_backups(entry.target, keep)
                        backup_count += 1
                        if sftp_upload and result.get("path"):
                            uploaded_files.append(result["path"])
                        if verify and result.get("path"):
                            if not self._verify_single(result["path"], password):
                                verify_failures += 1
        else:
            # 单策略串行执行
            for (
                key,
                entry,
                current_mtime,
                cfg,
                pwd,
                tpl,
                sym,
                mx,
                mn,
                age,
                fmeta,
            ) in tasks:
                result = self._do_backup(
                    key, entry, current_mtime, cfg, pwd, tpl, sym, mx, mn, age, fmeta
                )
                if result and result.get("success"):
                    entry.mtime = current_mtime
                    self._set_entry(key, entry)
                    self._add_history(
                        key,
                        result["size_mb"],
                        result["files_count"],
                        result.get("original_size_mb", 0.0),
                    )
                    if incremental:
                        self.data.setdefault("_file_meta", {})[key] = (
                            self._collect_file_meta(key)
                        )
                    if keep > 0:
                        self._cleanup_old_backups(entry.target, keep)
                    backup_count += 1
                    if sftp_upload and result.get("path"):
                        uploaded_files.append(result["path"])
                    if verify and result.get("path"):
                        if not self._verify_single(result["path"], password):
                            verify_failures += 1

        elapsed = time.monotonic() - start_time
        total = backup_count + skip_count

        if backup_count > 0:
            self.save()
            print(t("cmd.save.completed", count=backup_count))
        elif skip_count > 0:
            print(t("cmd.save.uptodate"))

        # 统计摘要
        if total > 0:
            print(
                t(
                    "cmd.save.summary",
                    total=total,
                    backed=backup_count,
                    skipped=skip_count,
                    elapsed=elapsed,
                )
            )

        # 校验失败提示
        if verify_failures > 0:
            print(t("cmd.verify.partial_fail", count=verify_failures))

        # SFTP 上传
        if sftp_upload and uploaded_files:
            self._upload_to_sftp(uploaded_files, config)

        # WebDAV 上传
        if webdav_upload and uploaded_files:
            self._upload_to_webdav(uploaded_files, config)

        # Webhook 通知
        effective_webhook = webhook_url or getattr(config, "webhook_url", "")
        if effective_webhook:
            status = "success" if verify_failures == 0 else "partial"
            if backup_count == 0:
                status = "skipped"
            self._send_webhook(
                effective_webhook,
                status=status,
                backed=backup_count,
                skipped=skip_count,
                elapsed=elapsed,
                verify_failures=verify_failures,
            )

    @staticmethod
    def _do_backup(
        key: str,
        entry: BackupEntry,
        current_mtime: float,
        config: Config,
        password: str,
        name_template: str | None = None,
        follow_symlinks: bool = False,
        max_size: int = 0,
        min_size: int = 0,
        max_age_seconds: float = 0,
        file_metadata: dict | None = None,
    ) -> dict:
        """执行单个备份策略（线程安全）"""
        fmt = entry.compression_format or config.compression_format
        # 模板优先级：CLI 参数 > 条目级 > 全局配置
        effective_template = (
            name_template or entry.name_template or config.name_template
        )
        # 磁盘空间检查
        BackupManager._check_disk_space(entry.target)
        config_instance = Config(
            folder_path=key,
            zipfile_path=entry.target,
            skip_patterns=entry.skip_patterns,
            compression_format=fmt,
            compression_algorithm=config.compression_algorithm,
            compression_level=config.compression_level,
            password=password,
            name_template=effective_template,
            follow_symlinks=follow_symlinks,
            max_size=max_size,
            min_size=min_size,
            max_age_seconds=max_age_seconds,
            file_metadata=file_metadata or {},
        )
        result = create_compressor(config_instance).compress()
        # 非 7z 格式 + 有密码 → 全格式加密
        if result.get("success") and password and fmt != "7Z" and result.get("path"):
            from sbackup.compression import _encrypt_file

            encrypted_path = _encrypt_file(result["path"], password)
            result["path"] = encrypted_path
        return result

    @staticmethod
    def _collect_file_meta(source_path: str) -> dict[str, list]:
        """收集源目录下所有文件的元数据 {rel_path: [mtime, size]}"""
        meta = {}
        source = Path(source_path)
        if not source.is_dir():
            return meta
        try:
            for dirpath, dirnames, filenames in os.walk(source):
                rel_dir = os.path.relpath(dirpath, source)
                if rel_dir == ".":
                    rel_dir = ""
                for filename in filenames:
                    file_rel = (
                        os.path.join(rel_dir, filename).replace("\\", "/")
                        if rel_dir
                        else filename
                    )
                    try:
                        stat = (Path(dirpath) / filename).stat()
                        meta[file_rel] = [stat.st_mtime, stat.st_size]
                    except OSError:
                        pass
        except OSError:
            pass
        return meta

    @staticmethod
    def _check_disk_space(target_dir: str, min_ratio: float = 0.05) -> None:
        """检查目标目录剩余空间，不足时打印警告"""
        try:
            target = Path(target_dir)
            if not target.is_dir():
                return
            usage = shutil.disk_usage(target)
            # 如果剩余空间不足总量的 min_ratio，发出警告
            if usage.free < usage.total * min_ratio:
                need_mb = (usage.total * min_ratio) / (1024 * 1024)
                free_mb = usage.free / (1024 * 1024)
                print(
                    t(
                        "warn.disk.space",
                        path=target_dir,
                        need=need_mb,
                        free=free_mb,
                    )
                )
        except OSError:
            pass

    @staticmethod
    def _dry_run_preview(tasks: list[tuple], config: Config) -> None:
        """预览将要备份的文件（dry-run 模式）"""
        from sbackup.compression import create_compressor as _create

        if not tasks:
            print(t("cmd.dry_run.nothing"))
            return

        print(t("cmd.dry_run.header"))
        total_files = 0
        total_size = 0.0
        for key, entry, _, _, _, _ in tasks:
            fmt = entry.compression_format or config.compression_format
            cfg = Config(
                folder_path=key,
                zipfile_path=entry.target,
                skip_patterns=entry.skip_patterns,
                compression_format=fmt,
            )
            compressor = _create(cfg)
            files = compressor._collect_files(Path(key))
            file_count = len(files)
            size_bytes = sum(
                (Path(dp) / fn).stat().st_size
                for dp, fn in files
                if (Path(dp) / fn).exists()
            )
            size_mb = size_bytes / (1024 * 1024)
            total_files += file_count
            total_size += size_mb
            print(
                t(
                    "cmd.dry_run.item",
                    source=key,
                    target=entry.target,
                    format=fmt,
                    count=file_count,
                    size=f"{size_mb:.2f}",
                )
            )
        print(
            t(
                "cmd.dry_run.total",
                count=len(tasks),
                files=total_files,
                size=f"{total_size:.2f}",
            )
        )

    @staticmethod
    def _verify_single(backup_path: str, password: str = "") -> bool:
        """校验单个备份文件完整性"""
        from sbackup.compression import verify_backup

        result = verify_backup(backup_path, password)
        return result.get("success", False)

    @staticmethod
    def _send_webhook(
        url: str,
        *,
        status: str,
        backed: int,
        skipped: int,
        elapsed: float,
        verify_failures: int = 0,
    ) -> None:
        """POST 备份结果到 webhook URL"""
        import urllib.request
        import urllib.error
        from datetime import datetime

        payload = json.dumps(
            {
                "status": status,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "backed": backed,
                "skipped": skipped,
                "elapsed_seconds": round(elapsed, 2),
                "verify_failures": verify_failures,
            },
            ensure_ascii=False,
        ).encode("utf-8")

        try:
            req = urllib.request.Request(
                url,
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
            logger.debug("Webhook 通知成功: %s", url)
        except (urllib.error.URLError, OSError) as e:
            logger.warning("Webhook 通知失败: %s — %s", url, e)

    # 向后兼容别名
    save_folder = execute_backups

    @staticmethod
    def _upload_to_sftp(file_paths: list[str], config: Config) -> None:
        """将备份文件上传到 SFTP 服务器"""
        from sbackup.sftp import SFTPClient, SFTPError

        if not config.sftp_enabled or not config.sftp_host:
            print(t("err.sftp.not_configured"))
            return

        # 获取认证凭据：优先使用配置中的私钥，否则尝试默认私钥
        key_file = config.sftp_key_file
        key_passphrase = config.sftp_key_passphrase
        password = config.sftp_password

        if not key_file and not password:
            default_key = SFTPClient.try_default_key()
            if default_key:
                print(t("cmd.sftp.using_default_key", path=default_key))
                key_file = default_key
                key_passphrase = SFTPClient.resolve_key_passphrase(default_key)
                if key_passphrase is None:
                    key_file = ""
                    password = config.sftp_password
                    key_passphrase = ""
            else:
                print(t("cmd.sftp.no_default_key"))
                return
        elif key_file and not key_passphrase and not password:
            key_passphrase = SFTPClient.resolve_key_passphrase(key_file)
            if key_passphrase is None:
                key_file = ""
                password = config.sftp_password
                key_passphrase = ""

        try:
            with SFTPClient(
                config.sftp_host,
                config.sftp_port,
                config.sftp_user,
                password,
                key_file,
                key_passphrase,
            ) as client:
                for local_path in file_paths:
                    filename = os.path.basename(local_path)
                    file_size = os.path.getsize(local_path)
                    print(t("cmd.sftp.uploading", file=filename))
                    try:
                        from tqdm import tqdm as tqdm_cls

                        with tqdm_cls(
                            total=file_size,
                            unit="B",
                            unit_scale=True,
                            desc=t("cmd.sftp.progress"),
                        ) as pbar:
                            client.upload_file(
                                local_path,
                                config.sftp_remote_path,
                                progress_callback=lambda sent, total: pbar.update(
                                    sent - pbar.n
                                ),
                            )
                        print(t("cmd.sftp.success", file=filename))
                    except SFTPError as e:
                        print(str(e))
        except SFTPError as e:
            print(str(e))

    @staticmethod
    def _upload_to_webdav(file_paths: list[str], config: Config) -> None:
        """将备份文件上传到 WebDAV 服务器"""
        from sbackup.webdav import WebDAVClient, WebDAVError

        if not config.webdav_enabled or not config.webdav_url:
            print(t("err.webdav.not_configured"))
            return

        try:
            client = WebDAVClient(
                config.webdav_url,
                config.webdav_user,
                config.webdav_password,
            )
            client.connect()
            for local_path in file_paths:
                filename = os.path.basename(local_path)
                print(t("cmd.webdav.uploading", file=filename))
                try:
                    remote_path = config.webdav_remote_path.rstrip("/") + "/" + filename
                    client.upload_file(local_path, remote_path)
                    print(t("cmd.webdav.success", file=filename))
                except WebDAVError as e:
                    print(str(e))
        except WebDAVError as e:
            print(str(e))

    def _add_history(
        self,
        source: str,
        size_mb: float,
        files_count: int,
        original_size_mb: float = 0.0,
    ):
        """记录备份历史"""
        from datetime import datetime

        history = self.data.setdefault(_HISTORY_KEY, [])
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "source": source,
            "size_mb": round(size_mb, 2),
            "files_count": files_count,
        }
        if original_size_mb > 0:
            entry["original_size_mb"] = round(original_size_mb, 2)
            entry["ratio"] = (
                round((1 - size_mb / original_size_mb) * 100, 1)
                if original_size_mb > 0
                else 0
            )
        history.append(entry)
        # 保留最近 100 条记录
        if len(history) > 100:
            self.data[_HISTORY_KEY] = history[-100:]

    def get_history(self) -> list[dict]:
        """获取备份历史记录"""
        return self.data.get(_HISTORY_KEY, [])

    def format_history_table(self) -> str:
        """生成备份历史的对齐文本表格"""
        history = self.get_history()
        if not history:
            return t("cmd.list.empty")

        headers = [
            t("table.header.time"),
            t("table.header.source"),
            t("table.header.size"),
            t("table.header.ratio"),
            t("table.header.files"),
        ]
        rows = []
        for entry in reversed(history):
            ratio = entry.get("ratio")
            ratio_str = f"{ratio:.0f}%" if ratio is not None else "-"
            rows.append(
                [
                    entry.get("time", ""),
                    entry.get("source", ""),
                    str(entry.get("size_mb", 0)),
                    ratio_str,
                    str(entry.get("files_count", 0)),
                ]
            )

        return self._render_table(headers, rows)

    @staticmethod
    def _cleanup_old_backups(target_dir: str, keep: int):
        """清理旧备份文件，仅保留最近 keep 个（keep=0 时不清理）"""
        if keep <= 0:
            return

        target = Path(target_dir)
        if not target.is_dir():
            return
        # 收集所有备份文件（.zip / .tar.* / .7z）
        patterns = [
            "*.zip",
            "*.tar",
            "*.tar.gz",
            "*.tar.bz2",
            "*.tar.xz",
            "*.tar.zst",
            "*.7z",
        ]
        files = []
        for pat in patterns:
            files.extend(target.glob(pat))
        if len(files) <= keep:
            return
        # 按修改时间排序，删除旧的
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        for old_file in files[keep:]:
            try:
                old_file.unlink()
                logger.debug(t("log.cleanup.delete"), old_file)
            except OSError:
                pass

    def export_strategies(self, output_file: str) -> int:
        """导出所有备份策略到 JSON 文件，返回导出的策略数"""
        export_data = {}
        for key, raw in self.data.items():
            if key == _HISTORY_KEY:
                continue
            export_data[key] = raw
        data_dir = os.path.dirname(output_file)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=4)
        return len(export_data)

    def import_strategies(self, input_file: str) -> tuple[int, int] | None:
        """从 JSON 文件导入备份策略，返回 (导入数, 跳过数) 或 None"""
        if not os.path.exists(input_file):
            return None
        try:
            with open(input_file, "r", encoding="utf-8") as f:
                import_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(import_data, dict):
            return None
        imported = 0
        skipped = 0
        for key, raw in import_data.items():
            if not isinstance(raw, list) or len(raw) < 3:
                continue
            if key in self.data:
                skipped += 1
                continue
            self.data[key] = raw
            imported += 1
        if imported > 0:
            self.save()
        return imported, skipped

    def format_status(self) -> str:
        """生成备份状态仪表盘"""
        lines = [t("cmd.status.header")]

        # 统计策略数
        strategies = {k: v for k, v in self.data.items() if k != _HISTORY_KEY}
        lines.append(t("cmd.status.strategies", count=len(strategies)))

        # 统计历史记录
        history = self.get_history()
        lines.append(t("cmd.status.history", count=len(history)))

        # 计算备份总大小和平均压缩率
        total_size = 0.0
        ratios = []
        for entry in history:
            total_size += entry.get("size_mb", 0)
            if "ratio" in entry:
                ratios.append(entry["ratio"])
        lines.append(t("cmd.status.total_size", size=total_size))
        if ratios:
            avg_ratio = sum(ratios) / len(ratios)
            lines.append(t("cmd.status.avg_ratio", ratio=avg_ratio))

        # 策略详情
        lines.append("")
        lines.append(t("cmd.status.strategy.header"))
        for source, raw in strategies.items():
            entry = BackupEntry.from_list(raw)
            lines.append(
                t("cmd.status.strategy.item", source=source, target=entry.target)
            )
            # 查找该策略的最后一次备份时间
            last_backup = None
            for h in reversed(history):
                if h.get("source") == source:
                    last_backup = h.get("time")
                    break
            if last_backup:
                lines.append(t("cmd.status.strategy.last_backup", time=last_backup))
            else:
                lines.append(t("cmd.status.strategy.never"))

            fmt = entry.compression_format or t("table.cell.default")
            lines.append(t("cmd.status.strategy.format", format=fmt))

            # 计算目标目录大小
            target_path = Path(entry.target)
            if target_path.is_dir():
                dir_size = sum(
                    f.stat().st_size for f in target_path.rglob("*") if f.is_file()
                )
                lines.append(
                    t("cmd.status.strategy.size", size=dir_size / (1024 * 1024))
                )

        return "\n".join(lines)

    def all_folder(self) -> dict[str, str]:
        """
        查看所有备份策略（已废弃，请使用 list_folder_table）

        .. deprecated::
            CLI 的 all 命令已改用 list_folder_table()，此方法保留仅为外部 API 兼容。
        """
        return {
            key: BackupEntry.from_list(raw).target
            for key, raw in self.data.items()
            if key != _HISTORY_KEY
        }

    @staticmethod
    def _display_width(s: str) -> int:
        """计算字符串的终端显示宽度（东亚宽字符算2，其余算1）"""
        if not isinstance(s, str):
            return len(str(s))
        width = 0
        for ch in s:
            eaw = unicodedata.east_asian_width(ch)
            if eaw in ("W", "F"):
                width += 2
            else:
                width += 1
        return width

    @staticmethod
    def _render_table(headers: list[str], rows: list[list[str]]) -> str:
        """生成对齐的文本表格"""
        col_widths = [BackupManager._display_width(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], BackupManager._display_width(cell))

        fmt = " | ".join(["{:<" + str(w) + "}" for w in col_widths])
        sep = "-+-".join(["-" * w for w in col_widths])

        lines = [fmt.format(*headers), sep]
        for row in rows:
            lines.append(fmt.format(*row))
        return "\n".join(lines)

    def list_folder_table(self) -> str:
        """
        生成对齐的文本表格
        """
        non_history_keys = [k for k in self.data if k != _HISTORY_KEY]
        if not non_history_keys:
            return t("cmd.all.empty")

        headers = [
            t("table.header.source"),
            t("table.header.dest"),
            t("table.header.format"),
            t("table.header.ignore"),
        ]
        rows = []
        for path, raw in self.data.items():
            if path == _HISTORY_KEY:
                continue
            entry = BackupEntry.from_list(raw)
            fmt_display = (
                entry.compression_format
                if entry.compression_format
                else t("table.cell.default")
            )
            skip = (
                ", ".join(entry.skip_patterns)
                if entry.skip_patterns
                else t("table.cell.none")
            )
            rows.append([path, entry.target, fmt_display, skip])

        return self._render_table(headers, rows)
