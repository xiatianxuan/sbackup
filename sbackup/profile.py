"""
配置 Profile 管理模块：支持多配置方案的保存、切换、导入导出
"""

import os
import json
import logging

from sbackup.config import Config, load_config, _load_json_file, _save_json_file

logger = logging.getLogger(__name__)


class ProfileManager:
    """管理命名配置 Profile：保存、加载、切换、导入导出"""

    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file

    def list_profiles(self) -> dict[str, dict]:
        """列出所有 profile，返回 {name: config_dict}"""
        data = _load_json_file(self.config_file)
        return data.get("profiles", {})

    def get_profile(self, name: str) -> dict | None:
        """获取指定 profile 的配置，不存在返回 None"""
        profiles = self.list_profiles()
        return profiles.get(name)

    def save_profile(self, name: str, config: Config) -> bool:
        """保存当前配置为命名 profile"""
        if not name:
            return False

        # 从 Config dataclass 中提取字段作为 profile dict
        profile_dict = _config_to_profile_dict(config)

        data = _load_json_file(self.config_file)
        profiles = data.get("profiles", {})
        profiles[name] = profile_dict
        data["profiles"] = profiles
        _save_json_file(data, self.config_file)
        return True

    def delete_profile(self, name: str) -> bool:
        """删除指定 profile，返回是否成功"""
        data = _load_json_file(self.config_file)
        profiles = data.get("profiles", {})
        if name not in profiles:
            return False
        del profiles[name]
        data["profiles"] = profiles
        _save_json_file(data, self.config_file)
        return True

    def activate_profile(self, name: str) -> Config | None:
        """激活 profile：将 profile 配置合并到主配置。
        只覆盖 profile 中明确设置的字段，不修改 config.json。
        返回合并后的 Config 对象，profile 不存在返回 None。
        """
        profile = self.get_profile(name)
        if profile is None:
            return None

        # 读取当前主配置
        main_config = load_config(self.config_file)

        # 用 profile 字段覆盖主配置
        merged = _merge_profile_to_config(main_config, profile)
        return merged

    def export_profile(self, name: str, export_path: str) -> bool:
        """导出 profile 到独立 JSON 文件"""
        profile = self.get_profile(name)
        if profile is None:
            return False

        export_data = {"profile_name": name, "config": profile}
        try:
            _save_json_file(export_data, export_path)
            return True
        except Exception:
            logger.exception("Failed to export profile %s", name)
            return False

    def import_profile(self, import_path: str, name: str = "") -> bool:
        """从 JSON 文件导入 profile。name 为空时使用文件名（不含扩展名）。
        文件格式：{"profile_name": "xxx", "config": {...}} 或直接 {...}
        """
        if not os.path.isfile(import_path):
            return False

        try:
            with open(import_path, "r", encoding="utf-8") as f:
                import_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.exception("Failed to read import file: %s", import_path)
            return False

        # 支持两种格式
        if isinstance(import_data, dict) and "config" in import_data:
            profile_dict = import_data["config"]
            if not name and "profile_name" in import_data:
                name = import_data["profile_name"]
        else:
            profile_dict = import_data

        if not name:
            # 使用文件名（不含扩展名）作为 profile 名
            name = os.path.splitext(os.path.basename(import_path))[0]

        if not name or not isinstance(profile_dict, dict):
            return False

        data = _load_json_file(self.config_file)
        profiles = data.get("profiles", {})
        profiles[name] = profile_dict
        data["profiles"] = profiles
        _save_json_file(data, self.config_file)
        return True


# --- 内部辅助函数 ---

# Config dataclass 字段名到 JSON 序列化名的映射
_CONFIG_FIELD_MAP = {
    "folder_path": "folder_path",
    "zipfile_path": "zipfile_path",
    "skip_patterns": "skip_patterns",
    "compression_format": "compression_format",
    "compression_algorithm": "compression_algorithm",
    "compression_level": "compression_level",
    "lang": "lang",
    "data_file": None,  # 不序列化
    "password": "password",
    "name_template": "name_template",
    "webhook_url": None,  # 使用 webhook_urls
    "webhook_urls": "webhook_urls",
    "webhook_template": "webhook_template",
    "webhook_retries": "webhook_retries",
    "follow_symlinks": "follow_symlinks",
    "max_size": "max_size",
    "min_size": "min_size",
    "include_patterns": "include_patterns",
    "exclude_patterns": "exclude_patterns",
    "threads": "threads",
    "max_age_seconds": "max_age_seconds",
    "file_metadata": None,  # 内部状态，不序列化
    "sftp_host": None,  # 使用嵌套结构
    "sftp_port": None,
    "sftp_user": None,
    "sftp_password": None,
    "sftp_key_file": None,
    "sftp_key_passphrase": None,
    "sftp_remote_path": None,
    "sftp_enabled": None,
    "webdav_url": None,
    "webdav_user": None,
    "webdav_password": None,
    "webdav_remote_path": None,
    "webdav_enabled": None,
    "cloud_endpoint": None,
    "cloud_access_key": None,
    "cloud_secret_key": None,
    "cloud_bucket": None,
    "cloud_region": None,
    "cloud_secure": None,
    "cloud_remote_path": None,
    "cloud_enabled": None,
    "smtp_host": None,
    "smtp_port": None,
    "smtp_user": None,
    "smtp_password": None,
    "smtp_from": None,
    "smtp_to": None,
    "smtp_tls": None,
    "smtp_enabled": None,
    "rotation_keep_count": "rotation_keep_count",
    "rotation_keep_days": "rotation_keep_days",
    "rotation_keep_daily": "rotation_keep_daily",
    "_config_checksum": None,
}


def _config_to_profile_dict(config: Config) -> dict:
    """将 Config dataclass 转换为可序列化的 profile dict（扁平化）"""
    profile: dict = {}

    # 简单字段
    simple_fields = [
        "folder_path",
        "compression_format",
        "compression_algorithm",
        "compression_level",
        "password",
        "name_template",
        "skip_patterns",
        "follow_symlinks",
        "max_size",
        "min_size",
        "include_patterns",
        "exclude_patterns",
        "threads",
        "max_age_seconds",
        "webhook_urls",
        "webhook_template",
        "webhook_retries",
        "rotation_keep_count",
        "rotation_keep_days",
        "rotation_keep_daily",
    ]
    for field_name in simple_fields:
        value = getattr(config, field_name, None)
        if value is not None:
            profile[field_name] = value

    # SFTP 嵌套结构
    sftp = {}
    for suffix in [
        "host",
        "port",
        "user",
        "password",
        "key_file",
        "key_passphrase",
        "remote_path",
        "enabled",
    ]:
        val = getattr(config, f"sftp_{suffix}", None)
        if val is not None and val != "" and val is not False:
            sftp[suffix] = val
    if sftp:
        profile["sftp"] = sftp

    # WebDAV 嵌套结构
    webdav = {}
    for suffix in ["url", "user", "password", "remote_path", "enabled"]:
        val = getattr(config, f"webdav_{suffix}", None)
        if val is not None and val != "" and val is not False:
            webdav[suffix] = val
    if webdav:
        profile["webdav"] = webdav

    # Cloud 嵌套结构
    cloud = {}
    for suffix in [
        "endpoint",
        "access_key",
        "secret_key",
        "bucket",
        "region",
        "secure",
        "remote_path",
        "enabled",
    ]:
        val = getattr(config, f"cloud_{suffix}", None)
        if val is not None and val != "" and val is not True and val is not False:
            cloud[suffix] = val
        elif val is True or val is False:
            cloud[suffix] = val
    if cloud:
        profile["cloud"] = cloud

    # SMTP 嵌套结构
    smtp = {}
    for suffix in ["host", "port", "user", "password", "from", "to", "tls", "enabled"]:
        val = getattr(config, f"smtp_{suffix}", None)
        if val is not None and val != "" and val is not False:
            smtp[suffix] = val
    if smtp:
        profile["smtp"] = smtp

    return profile


def _merge_profile_to_config(config: Config, profile: dict) -> Config:
    """将 profile dict 合并到 Config 对象，profile 中明确设置的字段覆盖主配置。
    返回新的 Config 对象（不修改原 config）。
    """
    import dataclasses

    # 将 Config 转为 dict
    config_dict = dataclasses.asdict(config)

    # 扁平化合并
    for key, value in profile.items():
        if key == "sftp" and isinstance(value, dict):
            for sftp_key, sftp_val in value.items():
                field_name = f"sftp_{sftp_key}"
                if field_name in config_dict:
                    config_dict[field_name] = sftp_val
        elif key == "webdav" and isinstance(value, dict):
            for wd_key, wd_val in value.items():
                field_name = f"webdav_{wd_key}"
                if field_name in config_dict:
                    config_dict[field_name] = wd_val
        elif key == "cloud" and isinstance(value, dict):
            for c_key, c_val in value.items():
                field_name = f"cloud_{c_key}"
                if field_name in config_dict:
                    config_dict[field_name] = c_val
        elif key == "smtp" and isinstance(value, dict):
            for s_key, s_val in value.items():
                field_name = f"smtp_{s_key}"
                if field_name in config_dict:
                    config_dict[field_name] = s_val
        elif key in config_dict:
            config_dict[key] = value

    # 移除内部字段（不在 dataclass 构造函数中）
    config_dict.pop("_config_checksum", None)

    return Config(**config_dict)
