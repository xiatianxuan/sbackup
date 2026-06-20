"""
多目标同时备份模块：支持并行备份到本地 + 多个远程目标
"""

import os
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from sbackup.config import Config
from sbackup.i18n import t

logger = logging.getLogger(__name__)


@dataclass
class DestResult:
    """单个目标的备份/上传结果"""

    name: str  # 目标名称（"local", "sftp", "webdav", "cloud"）
    success: bool
    path: str = ""  # 目标路径
    error: str = ""
    size: int = 0  # 上传文件大小
    duration: float = 0  # 耗时


class MultiDestBackup:
    """多目标备份管理器：先本地备份，再并行上传到远程目标"""

    def __init__(self, config: Config):
        self.config = config
        self.results: list[DestResult] = []

    def get_enabled_destinations(self) -> list[str]:
        """返回所有启用的目标列表
        始终包含 "local"（本地备份）
        如果 sftp_enabled → "sftp"
        如果 webdav_enabled → "webdav"
        如果 cloud_enabled → "cloud"
        """
        destinations = ["local"]
        if self.config.sftp_enabled:
            destinations.append("sftp")
        if self.config.webdav_enabled:
            destinations.append("webdav")
        if self.config.cloud_enabled:
            destinations.append("cloud")
        return destinations

    def backup_to_local(
        self,
        source_path: str,
        backup_path: str,
        incremental: str | None = None,
        checksum: bool = False,
        file_metadata: dict | None = None,
        chunk_meta: dict | None = None,
    ) -> DestResult:
        """执行本地备份（调用 BackupManager）
        :param source_path: 源文件夹路径
        :param backup_path: 本地备份目标文件夹路径
        """
        start = time.monotonic()
        try:
            from sbackup.compression import create_compressor

            abs_source = os.path.abspath(source_path)
            abs_dest = os.path.abspath(backup_path)

            if not os.path.isdir(abs_source):
                return DestResult(
                    name="local",
                    success=False,
                    error=t("err.folder.invalid", path=abs_source),
                )

            os.makedirs(abs_dest, exist_ok=True)

            # 块级增量：已有元数据时构建增量归档，仅打包变化块
            if incremental == "block" and chunk_meta:
                from sbackup.auto_save import BackupManager

                result = BackupManager._build_block_incremental(
                    source_path=abs_source,
                    target_dir=abs_dest,
                    chunk_meta=chunk_meta,
                    skip_patterns=self.config.skip_patterns,
                    compression_format=self.config.compression_format,
                    compression_algorithm=self.config.compression_algorithm,
                    compression_level=self.config.compression_level,
                    password=self.config.password or "",
                    name_template=self.config.name_template or "",
                    threads=getattr(self.config, "threads", 1),
                )
            else:
                # 构建 Config 用于压缩
                compress_config = Config(
                    folder_path=abs_source,
                    skip_patterns=self.config.skip_patterns,
                    compression_format=self.config.compression_format,
                    compression_algorithm=self.config.compression_algorithm,
                    compression_level=self.config.compression_level,
                    password=self.config.password,
                    follow_symlinks=self.config.follow_symlinks,
                    name_template=self.config.name_template,
                    # 文件级增量元数据
                    file_metadata=file_metadata or {},
                )

                compressor = create_compressor(compress_config)
                result = compressor.compress()

            elapsed = time.monotonic() - start

            if result and result.get("success"):
                backup_file = result.get("path", "")
                file_size = 0
                if backup_file and os.path.isfile(backup_file):
                    file_size = os.path.getsize(backup_file)
                return DestResult(
                    name="local",
                    success=True,
                    path=backup_file,
                    size=file_size,
                    duration=elapsed,
                )
            else:
                error_msg = ""
                if result:
                    error_msg = result.get("error", "") or result.get("message", "")
                return DestResult(
                    name="local",
                    success=False,
                    error=error_msg or t("multi_dest.local.failed"),
                    duration=elapsed,
                )
        except Exception as e:
            elapsed = time.monotonic() - start
            logger.error("Local backup failed: %s", e)
            return DestResult(
                name="local",
                success=False,
                error=str(e),
                duration=elapsed,
            )

    def upload_to_sftp(self, backup_path: str) -> DestResult:
        """上传到 SFTP"""
        start = time.monotonic()
        try:
            from sbackup.sftp import SFTPClient

            if not self.config.sftp_enabled or not self.config.sftp_host:
                return DestResult(
                    name="sftp",
                    success=False,
                    error=t("err.sftp.not_configured"),
                )

            # 获取认证凭据
            key_file = self.config.sftp_key_file
            key_passphrase = self.config.sftp_key_passphrase
            password = self.config.sftp_password

            if not key_file and not password:
                default_key = SFTPClient.try_default_key()
                if default_key:
                    key_file = default_key
                    key_passphrase = SFTPClient.resolve_key_passphrase(default_key)
                    if key_passphrase is None:
                        key_file = ""
                        password = self.config.sftp_password
                        key_passphrase = ""
                else:
                    return DestResult(
                        name="sftp",
                        success=False,
                        error=t("cmd.sftp.no_default_key"),
                    )
            elif key_file and not key_passphrase and not password:
                key_passphrase = SFTPClient.resolve_key_passphrase(key_file)
                if key_passphrase is None:
                    key_file = ""
                    password = self.config.sftp_password
                    key_passphrase = ""

            with SFTPClient(
                self.config.sftp_host,
                self.config.sftp_port,
                self.config.sftp_user,
                password,
                key_file,
                key_passphrase,
            ) as client:
                client.upload_file(backup_path, self.config.sftp_remote_path)

            elapsed = time.monotonic() - start
            file_size = (
                os.path.getsize(backup_path) if os.path.isfile(backup_path) else 0
            )
            return DestResult(
                name="sftp",
                success=True,
                path=backup_path,
                size=file_size,
                duration=elapsed,
            )
        except Exception as e:
            elapsed = time.monotonic() - start
            logger.error("SFTP upload failed: %s", e)
            return DestResult(
                name="sftp",
                success=False,
                error=str(e),
                duration=elapsed,
            )

    def upload_to_webdav(self, backup_path: str) -> DestResult:
        """上传到 WebDAV"""
        start = time.monotonic()
        try:
            from sbackup.webdav import WebDAVClient

            if not self.config.webdav_enabled or not self.config.webdav_url:
                return DestResult(
                    name="webdav",
                    success=False,
                    error=t("err.webdav.not_configured"),
                )

            filename = os.path.basename(backup_path)
            remote_path = self.config.webdav_remote_path.rstrip("/") + "/" + filename

            client = WebDAVClient(
                self.config.webdav_url,
                self.config.webdav_user,
                self.config.webdav_password,
            )
            client.connect()
            client.upload_file(backup_path, remote_path)

            elapsed = time.monotonic() - start
            file_size = (
                os.path.getsize(backup_path) if os.path.isfile(backup_path) else 0
            )
            return DestResult(
                name="webdav",
                success=True,
                path=remote_path,
                size=file_size,
                duration=elapsed,
            )
        except Exception as e:
            elapsed = time.monotonic() - start
            logger.error("WebDAV upload failed: %s", e)
            return DestResult(
                name="webdav",
                success=False,
                error=str(e),
                duration=elapsed,
            )

    def upload_to_cloud(self, backup_path: str) -> DestResult:
        """上传到 S3 云存储"""
        start = time.monotonic()
        try:
            from sbackup.cloud_storage import CloudStorageClient

            if not self.config.cloud_enabled or not self.config.cloud_endpoint:
                return DestResult(
                    name="cloud",
                    success=False,
                    error=t("err.cloud.not_configured"),
                )

            filename = os.path.basename(backup_path)
            remote_path = (
                self.config.cloud_remote_path.rstrip("/") + "/" + filename
            ).lstrip("/")

            with CloudStorageClient(
                self.config.cloud_endpoint,
                self.config.cloud_access_key,
                self.config.cloud_secret_key,
                self.config.cloud_bucket,
                region=self.config.cloud_region or None,
                secure=self.config.cloud_secure,
            ) as client:
                client.upload_file(backup_path, remote_path)

            elapsed = time.monotonic() - start
            file_size = (
                os.path.getsize(backup_path) if os.path.isfile(backup_path) else 0
            )
            return DestResult(
                name="cloud",
                success=True,
                path=remote_path,
                size=file_size,
                duration=elapsed,
            )
        except Exception as e:
            elapsed = time.monotonic() - start
            logger.error("Cloud upload failed: %s", e)
            return DestResult(
                name="cloud",
                success=False,
                error=str(e),
                duration=elapsed,
            )

    def execute_all(
        self,
        source_path: str,
        backup_path: str,
        incremental: str | None = None,
        checksum: bool = False,
        file_metadata: dict | None = None,
        chunk_meta: dict | None = None,
    ) -> list[DestResult]:
        """并行执行所有目标的备份/上传
        1. 先执行本地备份（必须成功）
        2. 如果本地成功，并行上传到所有启用的远程目标
        3. 每个目标独立处理异常，一个失败不影响其他
        4. 汇总所有结果
        """
        self.results = []
        destinations = self.get_enabled_destinations()

        # Step 1: 执行本地备份
        local_result = self.backup_to_local(
            source_path, backup_path,
            incremental=incremental,
            checksum=checksum,
            file_metadata=file_metadata,
            chunk_meta=chunk_meta,
        )
        self.results.append(local_result)

        if not local_result.success:
            logger.error(
                "Multi-dest backup aborted: local backup failed (%s)",
                local_result.error,
            )
            return self.results

        uploaded_file = local_result.path
        if not uploaded_file or not os.path.isfile(uploaded_file):
            logger.error("Multi-dest backup aborted: local backup file not found")
            return self.results

        # Step 2: 并行上传到远程目标
        remote_destinations = [d for d in destinations if d != "local"]
        if not remote_destinations:
            return self.results

        # 构建远程上传任务映射
        upload_map: dict[str, callable] = {}
        for dest in remote_destinations:
            if dest == "sftp":
                upload_map["sftp"] = self.upload_to_sftp
            elif dest == "webdav":
                upload_map["webdav"] = self.upload_to_webdav
            elif dest == "cloud":
                upload_map["cloud"] = self.upload_to_cloud

        if not upload_map:
            return self.results

        logger.debug(
            "Multi-dest: parallel upload to %d remote targets", len(upload_map)
        )

        with ThreadPoolExecutor(max_workers=len(upload_map)) as executor:
            futures = {
                executor.submit(fn, uploaded_file): name
                for name, fn in upload_map.items()
            }
            for future in as_completed(futures):
                dest_name = futures[future]
                try:
                    result = future.result()
                    self.results.append(result)
                except Exception as e:
                    logger.error("Upload to %s failed unexpectedly: %s", dest_name, e)
                    self.results.append(
                        DestResult(
                            name=dest_name,
                            success=False,
                            error=str(e),
                        )
                    )

        return self.results

    def format_results(self, results: list[DestResult], lang: str = "zh_CN") -> str:
        """格式化所有目标的结果"""
        lines: list[str] = []

        # 表头
        if lang == "zh_CN":
            lines.append("═══ 多目标备份结果 ═══")
        else:
            lines.append("=== Multi-Destination Backup Results ===")

        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count

        for r in results:
            status_icon = "[OK]" if r.success else "[FAIL]"

            if lang == "zh_CN":
                dest_label = {
                    "local": "本地",
                    "sftp": "SFTP",
                    "webdav": "WebDAV",
                    "cloud": "云存储",
                }.get(r.name, r.name)
            else:
                dest_label = {
                    "local": "Local",
                    "sftp": "SFTP",
                    "webdav": "WebDAV",
                    "cloud": "Cloud",
                }.get(r.name, r.name)

            if r.success:
                size_mb = r.size / (1024 * 1024) if r.size > 0 else 0
                if lang == "zh_CN":
                    lines.append(
                        f"  {status_icon} {dest_label}: {r.path}"
                        f" ({size_mb:.2f} MB, {r.duration:.1f}秒)"
                    )
                else:
                    lines.append(
                        f"  {status_icon} {dest_label}: {r.path}"
                        f" ({size_mb:.2f} MB, {r.duration:.1f}s)"
                    )
            else:
                if lang == "zh_CN":
                    lines.append(f"  {status_icon} {dest_label}: {r.error}")
                else:
                    lines.append(f"  {status_icon} {dest_label}: {r.error}")

        # 汇总
        if lang == "zh_CN":
            lines.append(
                f"  ── 共 {len(results)} 个目标, "
                f"成功 {success_count} 个, 失败 {fail_count} 个 ──"
            )
        else:
            lines.append(
                f"  -- {len(results)} target(s), "
                f"{success_count} succeeded, {fail_count} failed --"
            )

        return "\n".join(lines)
