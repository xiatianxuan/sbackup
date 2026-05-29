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
    # 备份文件名模板
    name_template: str = ""
    # Webhook 通知 URL（单个，向后兼容）
    webhook_url: str = ""
    # Webhook 通知 URL 列表（支持多个）
    webhook_urls: list[str] = field(default_factory=list)
    # Webhook 自定义 payload 模板（空字符串使用默认 JSON）
    webhook_template: str = ""
    # Webhook 失败重试次数
    webhook_retries: int = 2
    # 符号链接处理
    follow_symlinks: bool = False
    # 文件过滤（字节数，0 = 不限制）
    max_size: int = 0
    min_size: int = 0
    # 文件年龄过滤（秒，0 = 不限制）
    max_age_seconds: float = 0
    # 增量备份：文件级元数据 {rel_path: [mtime, size]}
    file_metadata: dict = field(default_factory=dict)
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
    password = config_data.get("password", "")
    name_template = config_data.get("name_template", "")
    webhook_config = config_data.get("webhook", {})
    sftp_config = config_data.get("sftp", {})

    # 向后兼容：单个 url 字段自动迁移到 urls 列表
    webhook_urls: list[str] = []
    webhook_template = ""
    webhook_retries = 2
    webhook_url_legacy = ""
    if isinstance(webhook_config, dict):
        webhook_url_legacy = webhook_config.get("url", "")
        webhook_urls = webhook_config.get("urls", [])
        webhook_template = webhook_config.get("template", "")
        webhook_retries = webhook_config.get("retries", 2)
        # 向后兼容：如果有 url 但没有 urls，自动合并
        if webhook_url_legacy and not webhook_urls:
            webhook_urls = [webhook_url_legacy]
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
        password=password,
        name_template=name_template,
        webhook_url=webhook_url_legacy,
        webhook_urls=webhook_urls,
        webhook_template=webhook_template,
        webhook_retries=webhook_retries,
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


def generate_config_template(config_file: str = "config.json") -> None:
    """生成完整的 config.json 模板，包含所有配置项的默认值"""
    template = {
        "lang": "zh_CN",
        "compression_format": "ZIP",
        "compression": {
            "algorithm": "ZIP_DEFLATED",
            "level": 6,
        },
        "skip_patterns": [".git", "__pycache__"],
        "name_template": "",
        "password": "",
        "webhook": {
            "urls": [],
            "template": "",
            "retries": 2,
        },
        "sftp": {
            "host": "",
            "port": 22,
            "user": "",
            "password": "",
            "key_file": "",
            "key_passphrase": "",
            "remote_path": "/",
            "enabled": False,
        },
        "webdav": {
            "url": "",
            "user": "",
            "password": "",
            "remote_path": "/",
            "enabled": False,
        },
    }
    _save_json_file(template, config_file)


# 配置文件加密/解密
_SENSITIVE_FIELDS = [
    ("password",),
    ("sftp", "password"),
    ("sftp", "key_passphrase"),
    ("webdav", "password"),
]


def _derive_key(master_password: str, salt: bytes) -> bytes:
    """从主密码派生加密密钥"""
    import hashlib

    return hashlib.pbkdf2_hmac("sha256", master_password.encode("utf-8"), salt, 100_000)


def _encrypt_value(value: str, key: bytes) -> str:
    """加密单个字符串值，返回 base64 编码的 salt+密文"""
    import base64

    salt = os.urandom(16)
    derived = _derive_key(key.hex(), salt)
    encrypted = bytes(
        a ^ b for a, b in zip(value.encode("utf-8"), derived[: len(value)])
    )
    return base64.b64encode(salt + encrypted).decode("ascii")


def _decrypt_value(encrypted_value: str, key: bytes) -> str:
    """解密单个字符串值"""
    import base64

    data = base64.b64decode(encrypted_value)
    salt = data[:16]
    ciphertext = data[16:]
    derived = _derive_key(key.hex(), salt)
    decrypted = bytes(a ^ b for a, b in zip(ciphertext, derived[: len(ciphertext)]))
    return decrypted.decode("utf-8")


def encrypt_config(master_password: str, config_file: str = "config.json") -> bool:
    """用主密码加密配置文件中的敏感字段
    :return: 是否成功
    """
    data = _load_json_file(config_file)
    if not data:
        return False

    import hashlib

    # 用主密码的哈希作为加密密钥
    key = hashlib.sha256(master_password.encode("utf-8")).digest()

    for field_path in _SENSITIVE_FIELDS:
        obj = data
        for part in field_path[:-1]:
            obj = obj.get(part, {})
        field_name = field_path[-1]
        value = obj.get(field_name, "")
        if value and not value.startswith("enc:"):
            obj[field_name] = "enc:" + _encrypt_value(value, key)

    data["_encrypted"] = True
    _save_json_file(data, config_file)
    return True


def decrypt_config(master_password: str, config_file: str = "config.json") -> bool:
    """用主密码解密配置文件中的敏感字段
    :return: 是否成功（密码错误时返回 False）
    """
    data = _load_json_file(config_file)
    if not data or not data.get("_encrypted"):
        return True  # 未加密，视为成功

    import hashlib

    key = hashlib.sha256(master_password.encode("utf-8")).digest()

    try:
        for field_path in _SENSITIVE_FIELDS:
            obj = data
            for part in field_path[:-1]:
                obj = obj.get(part, {})
            field_name = field_path[-1]
            value = obj.get(field_name, "")
            if value and value.startswith("enc:"):
                obj[field_name] = _decrypt_value(value[4:], key)
    except (UnicodeDecodeError, ValueError):
        return False

    data["_encrypted"] = False
    _save_json_file(data, config_file)
    return True


def is_config_encrypted(config_file: str = "config.json") -> bool:
    """检查配置文件是否已加密"""
    data = _load_json_file(config_file)
    return bool(data.get("_encrypted", False))


# IM 通知 Webhook 预设模板
WEBHOOK_PRESETS: dict[str, dict[str, str]] = {
    "dingtalk": {
        "name": "钉钉机器人",
        "template": '{"msgtype":"text","text":{"content":"[sbackup] {status} | 备份: {backed} | 跳过: {skipped} | 耗时: {elapsed}s"}}',
        "content_type": "application/json",
    },
    "feishu": {
        "name": "飞书机器人",
        "template": '{"msg_type":"text","content":{"text":"[sbackup] {status} | 备份: {backed} | 跳过: {skipped} | 耗时: {elapsed}s"}}',
        "content_type": "application/json",
    },
    "wechat": {
        "name": "企业微信机器人",
        "template": '{"msgtype":"text","text":{"content":"[sbackup] {status}\n备份: {backed}\n跳过: {skipped}\n耗时: {elapsed}s"}}',
        "content_type": "application/json",
    },
}


def setup_webhook_preset(preset: str, config_file: str = "config.json") -> str:
    """配置 IM 通知 Webhook 预设
    :param preset: 预设名称（dingtalk/feishu/wechat）
    :return: 预设的 template 字符串
    """
    info = WEBHOOK_PRESETS.get(preset)
    if not info:
        return ""
    data = _load_json_file(config_file)
    webhook = data.get("webhook", {})
    webhook["template"] = info["template"]
    data["webhook"] = webhook
    _save_json_file(data, config_file)
    return info["template"]


def parse_gitignore(gitignore_path: str) -> list[str]:
    """解析 .gitignore 文件并转换为 sbackup 的 skip_patterns
    :param gitignore_path: .gitignore 文件路径
    :return: skip_patterns 列表
    """
    if not os.path.isfile(gitignore_path):
        return []

    patterns = []
    try:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释
                if not line or line.startswith("#"):
                    continue
                # 取反模式保留
                if line.startswith("!"):
                    pattern = line[1:]
                    patterns.append("!" + _gitignore_to_fnmatch(pattern))
                else:
                    patterns.append(_gitignore_to_fnmatch(line))
    except OSError:
        pass
    return patterns


def _gitignore_to_fnmatch(pattern: str) -> str:
    """将单个 .gitignore 模式转换为 fnmatch 兼容模式"""
    # 移除尾部斜杠（目录标记）
    pattern = pattern.rstrip("/")
    # 移除开头斜杠（根目录标记，fnmatch 不需要）
    pattern = pattern.lstrip("/")
    # ** 匹配任意路径深度 → 转为 *
    pattern = pattern.replace("**/", "*")
    pattern = pattern.replace("/**", "*")
    # 如果模式不包含路径分隔符且不以 * 开头，添加前缀匹配
    # 例如 "build" 应匹配 "build" 和 "sub/build"
    if "/" not in pattern and not pattern.startswith("*"):
        pattern = f"*{pattern}"
    return pattern
