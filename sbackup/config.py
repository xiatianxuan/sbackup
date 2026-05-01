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
    lang = config_data.get("lang", "en_US")
    compression_format = config_data.get("compression_format", "ZIP")

    return Config(
        folder_path="",
        zipfile_path=None,
        skip_patterns=skip_patterns,
        compression_format=compression_format,
        compression_algorithm=compression_config.get("algorithm", "ZIP_DEFLATED"),
        compression_level=compression_config.get("level", 6),
        lang=lang,
        data_file=data_file,
    )


def save_lang(lang: str, config_file: str = "config.json") -> None:
    """
    将语言偏好保存到配置文件
    """
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            logger.warning(t("log.config.reset"), config_file)
            data = {}
    else:
        data = {}

    data["lang"] = lang

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


def save_format(fmt: str, config_file: str = "config.json") -> None:
    """
    将打包格式偏好保存到配置文件
    """
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            logger.warning(t("log.config.reset"), config_file)
            data = {}
    else:
        data = {}

    data["compression_format"] = fmt

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
