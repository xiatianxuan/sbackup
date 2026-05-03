"""
配置管理模块：配置加载、语言持久化、数据路径
"""

import os
import sys
import json
import logging
from dataclasses import dataclass, field
from sbackup.i18n import t

logger = logging.getLogger(__name__)

DEFAULT_SKIP_PATTERNS = [".git", "__pycache__"]


def _load_json_file(config_file: str) -> dict:
    """读取 JSON 配置文件，损坏时返回空字典"""
    if not os.path.exists(config_file):
        return {}
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.warning(t("log.config.reset"), config_file)
        return {}


def _save_json_file(data: dict, config_file: str) -> None:
    """将字典写入 JSON 配置文件，自动创建目录"""
    data_dir = os.path.dirname(config_file)
    if data_dir:
        try:
            os.makedirs(data_dir, exist_ok=True)
        except OSError as e:
            logger.error(t("log.config.mkdir.error"), data_dir, e)
            return

    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except OSError as e:
        logger.error(t("log.config.write.error"), config_file, e)


def get_default_data_file() -> str:
    """返回跨平台的默认数据文件路径"""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return os.path.join(base, "sbackup", "sbackup.json")


@dataclass
class Config:
    folder_path: str = "."
    zipfile_path: str | None = None
    skip_patterns: list[str] = field(
        default_factory=lambda: list(DEFAULT_SKIP_PATTERNS)
    )
    compression_format: str = "ZIP"
    compression_algorithm: str = "ZIP_DEFLATED"
    compression_level: int = 6
    lang: str = "zh_CN"
    data_file: str = field(default_factory=get_default_data_file)
    password: str = ""
    # SFTP 配置
    sftp_host: str = ""
    sftp_port: int = 22
    sftp_user: str = ""
    sftp_password: str = ""
    sftp_key_file: str = ""
    sftp_key_passphrase: str = ""
    sftp_remote_path: str = "/"
    sftp_enabled: bool = False
    # WebDAV 配置
    webdav_url: str = ""
    webdav_user: str = ""
    webdav_password: str = ""
    webdav_remote_path: str = "/"
    webdav_enabled: bool = False


def load_config(config_file: str = "config.json") -> Config:
    """
    从配置文件中加载配置
    """
    if not os.path.exists(config_file):
        return Config()

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config_data = json.load(f)
    except json.JSONDecodeError:
        logger.warning(t("log.config.malformed"), config_file)
        return Config()

    compression_config = config_data.get("compression", {})
    skip_patterns = config_data.get("skip_patterns", DEFAULT_SKIP_PATTERNS)
    data_file = config_data.get("data_file", get_default_data_file())
    lang = config_data.get("lang", "zh_CN")
    compression_format = config_data.get("compression_format", "ZIP")
    sftp_config = config_data.get("sftp", {})
    webdav_config = config_data.get("webdav", {})

    return Config(
        folder_path="",
        zipfile_path=None,
        skip_patterns=skip_patterns,
        compression_format=compression_format,
        compression_algorithm=compression_config.get("algorithm", "ZIP_DEFLATED"),
        compression_level=compression_config.get("level", 6),
        lang=lang,
        data_file=data_file,
        sftp_host=sftp_config.get("host", ""),
        sftp_port=sftp_config.get("port", 22),
        sftp_user=sftp_config.get("user", ""),
        sftp_password=sftp_config.get("password", ""),
        sftp_key_file=sftp_config.get("key_file", ""),
        sftp_key_passphrase=sftp_config.get("key_passphrase", ""),
        sftp_remote_path=sftp_config.get("remote_path", "/"),
        sftp_enabled=sftp_config.get("enabled", False),
        webdav_url=webdav_config.get("url", ""),
        webdav_user=webdav_config.get("user", ""),
        webdav_password=webdav_config.get("password", ""),
        webdav_remote_path=webdav_config.get("remote_path", "/"),
        webdav_enabled=webdav_config.get("enabled", False),
    )


def save_lang(lang: str, config_file: str = "config.json") -> None:
    """将语言偏好保存到配置文件"""
    data = _load_json_file(config_file)
    data["lang"] = lang
    _save_json_file(data, config_file)


def save_format(fmt: str, config_file: str = "config.json") -> None:
    """将打包格式偏好保存到配置文件"""
    data = _load_json_file(config_file)
    data["compression_format"] = fmt
    _save_json_file(data, config_file)


def save_sftp_config(
    host: str,
    port: int,
    user: str,
    password: str,
    remote_path: str,
    enabled: bool = True,
    key_file: str = "",
    key_passphrase: str = "",
    config_file: str = "config.json",
) -> None:
    """将 SFTP 配置保存到配置文件"""
    data = _load_json_file(config_file)
    data["sftp"] = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "key_file": key_file,
        "key_passphrase": key_passphrase,
        "remote_path": remote_path,
        "enabled": enabled,
    }
    _save_json_file(data, config_file)


def save_webdav_config(
    url: str,
    user: str,
    password: str,
    remote_path: str = "/",
    enabled: bool = True,
    config_file: str = "config.json",
) -> None:
    """将 WebDAV 配置保存到配置文件"""
    data = _load_json_file(config_file)
    data["webdav"] = {
        "url": url,
        "user": user,
        "password": password,
        "remote_path": remote_path,
        "enabled": enabled,
    }
    _save_json_file(data, config_file)
