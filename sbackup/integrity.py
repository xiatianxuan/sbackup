"""
数据完整性校验模块：SHA256 校验和计算、校验文件生成与验证
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

BACKUP_EXTENSIONS = {
    ".zip",
    ".tar",
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".tar.zst",
    ".7z",
}


def compute_checksum(filepath: str, chunk_size: int = 8192) -> str:
    """计算文件的 SHA256 校验和。

    Args:
        filepath: 文件路径
        chunk_size: 每次读取的块大小

    Returns:
        SHA256 十六进制摘要字符串

    Raises:
        FileNotFoundError: 文件不存在
        OSError: 读取文件出错
    """
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def generate_checksum_file(filepath: str) -> str:
    """为文件生成 `.sha256` 校验文件。

    校验文件格式: ``HASH  FILENAME``（与 sha256sum 工具兼容）。

    Args:
        filepath: 源文件路径

    Returns:
        生成的 .sha256 文件路径

    Raises:
        FileNotFoundError: 源文件不存在
    """
    filepath = os.path.abspath(filepath)
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    file_hash = compute_checksum(filepath)
    filename = os.path.basename(filepath)
    checksum_path = filepath + ".sha256"

    with open(checksum_path, "w", encoding="utf-8") as f:
        f.write(f"{file_hash}  {filename}\n")

    logger.debug("Checksum file generated: %s", checksum_path)
    return checksum_path


def verify_checksum_file(filepath: str) -> tuple[bool, str]:
    """验证文件是否与对应的 `.sha256` 校验文件匹配。

    Args:
        filepath: 源文件路径（会查找 ``filepath.sha256``）

    Returns:
        (是否通过, 消息)
    """
    filepath = os.path.abspath(filepath)
    checksum_path = filepath + ".sha256"

    if not os.path.isfile(filepath):
        return False, f"File not found: {filepath}"
    if not os.path.isfile(checksum_path):
        return False, f"Checksum file not found: {checksum_path}"

    with open(checksum_path, "r", encoding="utf-8") as f:
        line = f.readline().strip()

    if not line:
        return False, f"Checksum file is empty: {checksum_path}"

    # 解析 "HASH  FILENAME" 格式
    parts = line.split("  ", 1)
    if len(parts) != 2:
        return False, f"Invalid checksum file format: {checksum_path}"

    expected_hash, expected_filename = parts
    actual_filename = os.path.basename(filepath)

    if expected_filename != actual_filename:
        return (
            False,
            f"Filename mismatch: expected '{expected_filename}', got '{actual_filename}'",
        )

    actual_hash = compute_checksum(filepath)
    if actual_hash == expected_hash:
        return True, f"Checksum verified: {filepath}"
    else:
        return (
            False,
            f"Checksum mismatch for {filepath}: "
            f"expected {expected_hash[:16]}..., got {actual_hash[:16]}...",
        )


def generate_backup_integrity(backup_path: str) -> str:
    """扫描备份目录下所有备份文件，生成 ``integrity.json``。

    Args:
        backup_path: 备份目录路径

    Returns:
        生成的 integrity.json 文件路径

    Raises:
        NotADirectoryError: 路径不是目录
        OSError: 目录不存在
    """
    backup_path = os.path.abspath(backup_path)
    if not os.path.isdir(backup_path):
        raise NotADirectoryError(f"Not a directory: {backup_path}")

    files_map: dict[str, str] = {}
    backup_dir = Path(backup_path)

    for ext in BACKUP_EXTENSIONS:
        for filepath in backup_dir.glob(f"*{ext}"):
            name = filepath.name
            if name not in files_map:
                logger.debug("Computing checksum for: %s", filepath)
                files_map[name] = compute_checksum(str(filepath))

    # 同时扫描带 .001 后缀的分卷文件（如 backup.zip.001）
    for filepath in backup_dir.glob("*.001"):
        name = filepath.name
        if name not in files_map:
            logger.debug("Computing checksum for split part: %s", filepath)
            files_map[name] = compute_checksum(str(filepath))

    integrity_data = {
        "created": datetime.now(timezone.utc).isoformat(),
        "files": dict(sorted(files_map.items())),
    }

    integrity_path = os.path.join(backup_path, "integrity.json")
    with open(integrity_path, "w", encoding="utf-8") as f:
        json.dump(integrity_data, f, indent=2, ensure_ascii=False)

    logger.debug(
        "Integrity manifest generated: %s (%d files)", integrity_path, len(files_map)
    )
    return integrity_path


def verify_backup_integrity(backup_path: str) -> tuple[bool, list[str]]:
    """使用 ``integrity.json`` 验证备份目录中所有文件的完整性。

    Args:
        backup_path: 备份目录路径

    Returns:
        (是否全部通过, 消息列表)
    """
    backup_path = os.path.abspath(backup_path)
    integrity_path = os.path.join(backup_path, "integrity.json")

    if not os.path.isfile(integrity_path):
        return False, [f"Integrity manifest not found: {integrity_path}"]

    with open(integrity_path, "r", encoding="utf-8") as f:
        try:
            integrity_data = json.load(f)
        except json.JSONDecodeError as e:
            return False, [f"Invalid integrity manifest: {e}"]

    files_map = integrity_data.get("files", {})
    if not files_map:
        return True, ["No files recorded in integrity manifest"]

    messages: list[str] = []
    all_ok = True

    for filename, expected_hash in files_map.items():
        filepath = os.path.join(backup_path, filename)
        if not os.path.isfile(filepath):
            messages.append(f"MISSING: {filename}")
            all_ok = False
            continue

        actual_hash = compute_checksum(filepath)
        if actual_hash == expected_hash:
            messages.append(f"OK: {filename}")
        else:
            messages.append(
                f"FAILED: {filename} — expected {expected_hash[:16]}..., "
                f"got {actual_hash[:16]}..."
            )
            all_ok = False

    return all_ok, messages
