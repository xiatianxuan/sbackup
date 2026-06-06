"""
配置校验模块：校验配置参数合法性、计算配置校验和检测篡改
"""

import os
import re
import hashlib
from dataclasses import dataclass

from sbackup.config import Config

VALID_COMPRESSION_FORMATS = {"ZIP", "TAR", "GZ", "BZ2", "XZ", "ZST", "7Z"}


@dataclass
class ValidationError:
    """校验错误/警告条目"""

    field: str
    message: str
    severity: str = "error"  # "error" / "warning"


def _is_valid_url(url: str) -> bool:
    """检查 URL 格式是否合法（仅允许 http/https）"""
    return bool(re.match(r"^https?://\S+$", url))


def _is_ip_address(host: str) -> bool:
    """检查字符串是否为 IP 地址格式"""
    return bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host))


class ConfigValidator:
    """配置校验器：对 Config 对象执行全面的合法性校验"""

    def __init__(self, config: Config):
        self.config = config
        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationError] = []

    def _add_error(self, field_name: str, message: str) -> None:
        self.errors.append(
            ValidationError(field=field_name, message=message, severity="error")
        )

    def _add_warning(self, field_name: str, message: str) -> None:
        self.warnings.append(
            ValidationError(field=field_name, message=message, severity="warning")
        )

    def validate_all(self) -> tuple[bool, list[ValidationError], list[ValidationError]]:
        """运行所有校验，返回 (is_valid, errors, warnings)"""
        self.errors.clear()
        self.warnings.clear()

        self._validate_compression()
        self._validate_sftp()
        self._validate_webdav()
        self._validate_cloud()
        self._validate_smtp()
        self._validate_webhook()
        self._validate_password()
        self._validate_paths()
        self._validate_network()
        self._validate_integrity()

        is_valid = len(self.errors) == 0
        return is_valid, list(self.errors), list(self.warnings)

    def _validate_compression(self) -> None:
        """校验压缩格式是否合法"""
        fmt = self.config.compression_format.upper()
        if fmt not in VALID_COMPRESSION_FORMATS:
            self._add_error(
                "compression_format",
                f"Invalid compression format: {self.config.compression_format}. "
                f"Valid formats: {', '.join(sorted(VALID_COMPRESSION_FORMATS))}",
            )

    def _validate_sftp(self) -> None:
        """校验 SFTP 配置"""
        if not self.config.sftp_enabled:
            return
        if not self.config.sftp_host:
            self._add_error(
                "sftp_host", "SFTP host cannot be empty when SFTP is enabled"
            )
        if not self.config.sftp_user:
            self._add_error(
                "sftp_user", "SFTP user cannot be empty when SFTP is enabled"
            )
        if not (1 <= self.config.sftp_port <= 65535):
            self._add_error(
                "sftp_port",
                f"SFTP port {self.config.sftp_port} is out of range (1-65535)",
            )
        if self.config.sftp_key_file and not os.path.isfile(self.config.sftp_key_file):
            self._add_warning(
                "sftp_key_file",
                f"SFTP key file does not exist: {self.config.sftp_key_file}",
            )

    def _validate_webdav(self) -> None:
        """校验 WebDAV 配置"""
        if not self.config.webdav_enabled:
            return
        if not self.config.webdav_url:
            self._add_error(
                "webdav_url", "WebDAV URL cannot be empty when WebDAV is enabled"
            )
        elif not _is_valid_url(self.config.webdav_url):
            self._add_error(
                "webdav_url",
                f"Invalid WebDAV URL format: {self.config.webdav_url}. Must start with http:// or https://",
            )

    def _validate_cloud(self) -> None:
        """校验云存储配置"""
        if not self.config.cloud_enabled:
            return
        if not self.config.cloud_endpoint:
            self._add_error(
                "cloud_endpoint",
                "Cloud endpoint cannot be empty when cloud storage is enabled",
            )
        if not self.config.cloud_bucket:
            self._add_error(
                "cloud_bucket",
                "Cloud bucket cannot be empty when cloud storage is enabled",
            )
        if not self.config.cloud_access_key:
            self._add_error(
                "cloud_access_key",
                "Cloud access_key cannot be empty when cloud storage is enabled",
            )
        if not self.config.cloud_secret_key:
            self._add_error(
                "cloud_secret_key",
                "Cloud secret_key cannot be empty when cloud storage is enabled",
            )

    def _validate_smtp(self) -> None:
        """校验 SMTP 配置"""
        if not self.config.smtp_enabled:
            return
        if not self.config.smtp_host:
            self._add_error(
                "smtp_host", "SMTP host cannot be empty when SMTP is enabled"
            )
        if not (1 <= self.config.smtp_port <= 65535):
            self._add_error(
                "smtp_port",
                f"SMTP port {self.config.smtp_port} is out of range (1-65535)",
            )

    def _validate_webhook(self) -> None:
        """校验 Webhook URL 列表"""
        for i, url in enumerate(self.config.webhook_urls):
            if not _is_valid_url(url):
                self._add_error(
                    "webhook_urls",
                    f"Invalid webhook URL at index {i}: {url}",
                )

    def _validate_password(self) -> None:
        """校验密码加密配置"""
        if self.config.password and not self.config.password.startswith("enc:"):
            self._add_warning(
                "password",
                "Password is stored as plaintext in config. Consider using 'sbackup config lock' to encrypt it",
            )

    def _validate_paths(self) -> None:
        """校验路径配置"""
        if self.config.folder_path and not os.path.isdir(self.config.folder_path):
            self._add_warning(
                "folder_path",
                f"Source folder does not exist: {self.config.folder_path}",
            )
        if self.config.zipfile_path:
            parent = os.path.dirname(self.config.zipfile_path)
            if parent and not os.path.isdir(parent):
                self._add_warning(
                    "zipfile_path",
                    f"Parent directory of zipfile_path does not exist: {parent}",
                )
            elif parent and not os.access(parent, os.W_OK):
                self._add_warning(
                    "zipfile_path",
                    f"Parent directory of zipfile_path is not writable: {parent}",
                )

    def _validate_network(self) -> None:
        """校验网络配置（SFTP/SMTP host 格式）"""
        hosts_to_check: list[tuple[str, str, int]] = []
        if self.config.sftp_enabled and self.config.sftp_host:
            hosts_to_check.append(
                ("sftp_host", self.config.sftp_host, self.config.sftp_port)
            )
        if self.config.smtp_enabled and self.config.smtp_host:
            hosts_to_check.append(
                ("smtp_host", self.config.smtp_host, self.config.smtp_port)
            )

        for field_name, host, port in hosts_to_check:
            if _is_ip_address(host):
                # IP 地址格式校验端口
                if not (1 <= port <= 65535):
                    self._add_error(
                        field_name,
                        f"Port {port} for {host} is out of range (1-65535)",
                    )
            else:
                # 非 IP 格式的 host（域名），跳过端口检查，但检查基本格式
                if not re.match(
                    r"^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*$",
                    host,
                ):
                    self._add_warning(
                        field_name,
                        f"Host format may be invalid: {host}",
                    )

    def _validate_integrity(self) -> None:
        """配置校验和：计算配置的校验和，检测意外修改"""
        checksum = get_config_checksum(self.config)
        self.config._config_checksum = checksum


def get_config_checksum(config: Config) -> str:
    """计算配置的 SHA256 校验和（排除 _encrypted、_key_salt、_config_checksum 字段）"""
    from dataclasses import fields as dc_fields

    exclude = {"_encrypted", "_key_salt", "_config_checksum"}
    parts: list[str] = []
    for f in sorted(dc_fields(config), key=lambda x: x.name):
        if f.name in exclude:
            continue
        value = getattr(config, f.name)
        parts.append(f"{f.name}={value!r}")
    raw = "\n".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_config_file(
    config: Config,
) -> tuple[bool, list[ValidationError], list[ValidationError]]:
    """快速校验配置对象，返回 (is_valid, errors, warnings)"""
    validator = ConfigValidator(config)
    return validator.validate_all()
