"""增量链合并模块：将增量备份链合并为一个新的全量备份

使用场景：长期增量备份后链过长，还原时需要逐个打补丁，
consolidate 将 base 全量 + N 个增量合并为一个新全量，缩短还原路径。
"""

import os
import json
import logging
import shutil
import tempfile
from pathlib import Path

from sbackup.i18n import t
from sbackup.compression import (
    restore_backup,
    _get_archive_member_names,
    create_compressor,
)
from sbackup.config import Config

logger = logging.getLogger(__name__)

# 所有已知的备份文件扩展名（从 rotation.py 同步）
BACKUP_EXTENSIONS = {
    ".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst",
    ".zip", ".tar", ".7z",
    ".tgz", ".tbz2", ".txz",
}

# 增量 manifest 标记文件
_INCREMENTAL_MARKER = "_sbackup_manifest.json"


def _extract_base_name(fname: str) -> tuple[str, str]:
    """从文件名中提取纯源名称和扩展名

    处理复合扩展名如 .tar.gz：
    >>> _extract_base_name("my_folder.tar.gz")
    ("my_folder", ".tar.gz")
    >>> _extract_base_name("docs.zip")
    ("docs", ".zip")
    """
    # 优先匹配复合扩展名
    for ext in sorted(BACKUP_EXTENSIONS, key=len, reverse=True):
        if fname.lower().endswith(ext):
            return fname[: -len(ext)], fname[-len(ext) :]
    base, ext = os.path.splitext(fname)
    return base, ext.lower()


def _is_backup_file(fname: str) -> bool:
    """判断文件是否为已知格式的备份归档"""
    for ext in BACKUP_EXTENSIONS:
        if fname.lower().endswith(ext):
            return True
    return False


def _detect_archive_type(archive_path: str, password: str = "") -> str:
    """检测归档类型：'full' / 'incremental' / 'unknown'

    增量归档内含 {source_name}/_sbackup_manifest.json（或根目录）。
    """
    try:
        members = _get_archive_member_names(Path(archive_path), password)
        for m in members:
            if m.endswith("/" + _INCREMENTAL_MARKER) or m == _INCREMENTAL_MARKER:
                return "incremental"
        return "full"
    except Exception:
        return "unknown"


def _match_source(fname: str, source_name: str) -> bool:
    """检查文件名是否属于指定源策略（按前缀匹配）

    去掉扩展名后比较：
    - source_name → "my_folder" → 匹配 "my_folder.zip", "my_folder_20260705_143022.zip"
    - 排除 "_consolidated" 后缀
    """
    base, _ = _extract_base_name(fname)
    if not base:
        return False
    if base == source_name:
        return True
    if base.startswith(source_name + "_"):
        # 排除合并产物自身
        if base.endswith("_consolidated"):
            return False
        return True
    return False


def _gather_backups(
    target_dir: str,
    source_name: str,
    password: str = "",
) -> tuple[list[tuple[float, str]], list[tuple[float, str]]]:
    """扫描目录，收集指定源的所有备份文件并区分类型

    :returns: (full_backups, incremental_backups)
             每个列表为 [(mtime, path), ...] 按 mtime 升序
    """
    full_backups: list[tuple[float, str]] = []
    incremental_backups: list[tuple[float, str]] = []

    if not os.path.isdir(target_dir):
        return full_backups, incremental_backups

    for fname in sorted(os.listdir(target_dir)):
        fpath = os.path.join(target_dir, fname)
        if not os.path.isfile(fpath):
            continue
        if not _is_backup_file(fname):
            continue
        if not _match_source(fname, source_name):
            continue

        atype = _detect_archive_type(fpath, password)
        mtime = os.path.getmtime(fpath)
        if atype == "full":
            full_backups.append((mtime, fpath))
        elif atype == "incremental":
            incremental_backups.append((mtime, fpath))

    full_backups.sort(key=lambda x: x[0])
    incremental_backups.sort(key=lambda x: x[0])
    return full_backups, incremental_backups


def _select_backups(
    full_backups: list[tuple[float, str]],
    incremental_backups: list[tuple[float, str]],
    count: int = 0,
) -> list[str]:
    """选择要合并的备份文件路径列表

    将所有备份按 mtime 排序，取最新的 count 个。
    如果 count≤0 或超过总数，取全部。
    确保列表第一个（最旧备份）是全量：
      如果最旧的是增量，自动向前包含最近的全量。
    """
    all_bu: list[tuple[float, str, str]] = [
        (mt, p, "full") for mt, p in full_backups
    ]
    all_bu.extend((mt, p, "inc") for mt, p in incremental_backups)
    all_bu.sort(key=lambda x: x[0])

    if count <= 0 or count >= len(all_bu):
        selected = all_bu
    else:
        selected = all_bu[-count:]

    # 确保最旧的是全量
    if selected and selected[0][2] != "full":
        oldest_mtime = selected[0][0]
        # 寻找该时间之前最近的全量
        candidates = [
            (mt, p) for mt, p, tp in all_bu
            if mt < oldest_mtime and tp == "full"
        ]
        if candidates:
            candidates.sort(key=lambda x: x[0])
            selected = [(candidates[-1][0], candidates[-1][1], "full")] + selected
        else:
            logger.warning(t("consolidate.warn.no_base_full"))
            return []

    return [p for _, p, _ in selected]


def detect_and_list_backups(
    target_dir: str,
    source_name: str,
    password: str = "",
) -> dict:
    """列出某个源目录的所有备份及类型

    :returns: {"full": [paths...], "incremental": [paths...]}
    """
    fulls, incs = _gather_backups(target_dir, source_name, password)
    return {
        "full": [p for _, p in fulls],
        "incremental": [p for _, p in incs],
    }


def consolidate_backups(
    source_name: str,
    target_dir: str,
    output_path: str = "",
    count: int = 0,
    delete_old: bool = False,
    password: str = "",
    compression_format: str = "ZIP",
    compression_algorithm: str = "ZIP_DEFLATED",
    compression_level: int = 6,
    threads: int = 1,
) -> dict:
    """将增量备份链合并为一个新的全量备份

    :param source_name: 源文件夹名称
    :param target_dir: 备份文件所在目录
    :param output_path: 输出路径，空字符串自动生成到 target_dir
    :param count: 要合并的份数（0=全部），含 base 全量
    :param delete_old: 合并后删除旧的 base 全量和增量
    :param password: 加密密码
    :param compression_format: 输出格式
    :param compression_algorithm: 压缩算法
    :param compression_level: 压缩级别
    :param threads: 并行线程数
    :returns: 同 compress() 返回值：{success, path, files_count, size_mb}
    """
    full_backups, incremental_backups = _gather_backups(
        target_dir, source_name, password
    )

    if not full_backups:
        return {"success": False, "error": t("consolidate.error.no_full_backup")}
    if not incremental_backups:
        return {"success": True, "path": full_backups[-1][1], "note": t("consolidate.info.no_incremental")}

    selected = _select_backups(full_backups, incremental_backups, count)
    if not selected:
        return {"success": False, "error": t("consolidate.error.no_valid_chain")}

    base_path = selected[0]
    inc_paths = selected[1:]

    logger.info(
        t("consolidate.progress.start"),
        base=base_path,
        count=len(inc_paths),
        paths=", ".join(os.path.basename(p) for p in inc_paths),
    )

    tmp_dir = tempfile.mkdtemp(prefix="sbackup_consolidate_")
    try:
        # 步骤 1：还原全量
        logger.debug(t("consolidate.progress.restore_full"), base_path)
        result = restore_backup(base_path, tmp_dir, password, quiet=True)
        if not result.get("success"):
            return {
                "success": False,
                "error": t("consolidate.error.restore_failed", path=base_path),
            }

        # 步骤 2：依次还原增量（restore_backup 自动调用 _apply_incremental_manifest）
        for inc_path in inc_paths:
            logger.debug(t("consolidate.progress.restore_incremental"), inc_path)
            result = restore_backup(inc_path, tmp_dir, password, quiet=True)
            if not result.get("success"):
                return {
                    "success": False,
                    "error": t("consolidate.error.restore_failed", path=inc_path),
                }

        # 步骤 3：确定输出路径
        if not output_path:
            ext_map = {
                "ZIP": ".zip",
                "TAR": ".tar",
                "TAR_GZ": ".tar.gz",
                "TAR_BZ2": ".tar.bz2",
                "TAR_XZ": ".tar.xz",
                "TAR_ZST": ".tar.zst",
                "7Z": ".7z",
            }
            ext = ext_map.get(compression_format.upper(), ".zip")
            output_path = os.path.join(
                target_dir, f"{source_name}_consolidated{ext}"
            )
        elif os.path.isdir(output_path):
            ext = ".zip"
            output_path = os.path.join(output_path, f"{source_name}_consolidated{ext}")

        # 步骤 4：重新压缩为全量
        # 使用 source_name 子目录作为压缩根，确保归档内路径一致
        compress_root = os.path.join(tmp_dir, source_name)
        if not os.path.isdir(compress_root):
            # 回退：文件可能直接在 tmp_dir 根目录
            compress_root = tmp_dir
        logger.info(t("consolidate.progress.compressing"), output_path)
        cfg = Config(
            folder_path=compress_root,
            zipfile_path=output_path,
            skip_patterns=[],
            compression_format=compression_format,
            compression_algorithm=compression_algorithm,
            compression_level=compression_level,
            password=password,
            threads=threads,
        )
        compress_result = create_compressor(cfg).compress()

        if not compress_result.get("success"):
            return {
                "success": False,
                "error": t("consolidate.error.compress_failed"),
                "details": compress_result,
            }

        # 步骤 5：可选删除旧文件
        if delete_old:
            for old_path in [base_path] + inc_paths:
                try:
                    os.remove(old_path)
                    logger.info(t("consolidate.info.deleted"), old_path)
                except OSError as e:
                    logger.warning(t("consolidate.warn.delete_failed"), old_path, e)

        logger.info(
            t("consolidate.info.done"),
            path=compress_result.get("path", output_path),
            files=compress_result.get("files_count", 0),
            size=compress_result.get("size_mb", 0),
        )
        return compress_result
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
