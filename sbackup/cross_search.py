"""跨档案搜索模块：在多个备份文件中搜索匹配的文件名"""

import logging
import os
import tarfile
import tempfile
import time as _time
import zipfile
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

logger = logging.getLogger(__name__)

# 支持的备份文件后缀
_ARCHIVE_EXTENSIONS = {
    ".zip": "ZIP",
    ".tar": "TAR",
    ".tar.gz": "TAR_GZ",
    ".tar.bz2": "TAR_BZ2",
    ".tar.xz": "TAR_XZ",
    ".tar.zst": "TAR_ZST",
    ".7z": "7Z",
}


def _detect_format(filename: str) -> str:
    """根据文件名检测压缩格式，返回格式标识或空字符串"""
    name_lower = filename.lower()
    # 长后缀优先匹配
    for ext in sorted(_ARCHIVE_EXTENSIONS, key=len, reverse=True):
        if name_lower.endswith(ext):
            return _ARCHIVE_EXTENSIONS[ext]
    return ""


def _is_archive(filename: str) -> bool:
    """判断文件名是否为支持的备份格式"""
    return _detect_format(filename) != ""


def _get_member_names(backup_path: Path, password: str = "") -> list[dict]:
    """获取压缩包内所有成员信息，返回 [{"name": str, "size": int}]"""
    name_lower = backup_path.name.lower()
    try:
        if name_lower.endswith(".zip"):
            with zipfile.ZipFile(backup_path, "r") as zf:
                return [
                    {"name": info.filename, "size": info.file_size}
                    for info in zf.infolist()
                    if not info.is_dir()
                ]
        elif name_lower.endswith(".7z"):
            import py7zr

            szf_kwargs = {"file": backup_path, "mode": "r"}
            if password:
                szf_kwargs["password"] = password
            with py7zr.SevenZipFile(**szf_kwargs) as szf:
                return [
                    {"name": name, "size": 0}
                    for name in szf.getnames()
                    if not name.endswith("/")
                ]
        elif name_lower.endswith(".tar.zst"):
            import zstandard as zstd

            dctx = zstd.ZstdDecompressor()
            with tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024) as tmp:
                with open(backup_path, "rb") as f_in:
                    reader = dctx.stream_reader(f_in)
                    while True:
                        chunk = reader.read(65536)
                        if not chunk:
                            break
                        tmp.write(chunk)
                tmp.seek(0)
                with tarfile.open(fileobj=tmp, mode="r") as tarf:
                    return [
                        {"name": m.name, "size": m.size}
                        for m in tarf.getmembers()
                        if m.isfile()
                    ]
        else:
            # tar.gz / tar.bz2 / tar.xz / tar
            mode_map = {
                ".tar.gz": "r:gz",
                ".tgz": "r:gz",
                ".tar.bz2": "r:bz2",
                ".tbz2": "r:bz2",
                ".tar.xz": "r:xz",
                ".txz": "r:xz",
                ".tar": "r",
            }
            mode = None
            for suffix, m in mode_map.items():
                if name_lower.endswith(suffix):
                    mode = m
                    break
            if mode is None:
                return []
            with tarfile.open(backup_path, mode) as tarf:
                return [
                    {"name": member.name, "size": member.size}
                    for member in tarf.getmembers()
                    if member.isfile()
                ]
    except Exception as e:
        logger.debug("Failed to read archive %s: %s", backup_path, e)
        return []


@dataclass
class SearchResult:
    """搜索结果数据类"""

    archive: str  # 备份文件路径
    members: list[dict] = field(default_factory=list)  # [{"name": str, "size": int}]
    archive_size: int = 0  # 备份文件大小
    archive_mtime: str = ""  # 备份文件修改时间


class CrossSearcher:
    """跨档案搜索器，在多个备份文件中搜索匹配的文件名"""

    def __init__(self, search_dirs: list[str], password: str = ""):
        self.search_dirs = search_dirs
        self.password = password

    def scan_archives(self) -> list[dict]:
        """扫描搜索目录下所有备份文件

        递归搜索，识别 .zip/.tar*/.7z 后缀
        返回 [{"path": str, "size": int, "mtime": str, "format": str}]
        """
        archives = []
        for search_dir in self.search_dirs:
            dir_path = Path(search_dir)
            if not dir_path.is_dir():
                logger.debug("Directory does not exist: %s", search_dir)
                continue
            try:
                for root, _dirs, files in os.walk(dir_path):
                    for filename in files:
                        fmt = _detect_format(filename)
                        if not fmt:
                            continue
                        filepath = Path(root) / filename
                        try:
                            stat = filepath.stat()
                            mtime_str = _time.strftime(
                                "%Y-%m-%d %H:%M:%S",
                                _time.localtime(stat.st_mtime),
                            )
                            archives.append(
                                {
                                    "path": str(filepath),
                                    "size": stat.st_size,
                                    "mtime": mtime_str,
                                    "format": fmt,
                                }
                            )
                        except OSError:
                            continue
            except OSError:
                continue
        # 按修改时间倒序排列
        archives.sort(key=lambda a: a["mtime"], reverse=True)
        return archives

    def _list_members(self, archive_path: str) -> list[dict]:
        """列出单个档案的成员信息"""
        return _get_member_names(Path(archive_path), self.password)

    def search(self, keyword: str) -> list[SearchResult]:
        """在所有备份文件中搜索匹配 keyword 的文件名

        不区分大小写，返回每个匹配的档案及其匹配成员
        """
        results = []
        for archive_info in self.scan_archives():
            archive_path = archive_info["path"]
            members = self._list_members(archive_path)
            matched = [m for m in members if keyword.lower() in m["name"].lower()]
            if matched:
                results.append(
                    SearchResult(
                        archive=archive_path,
                        members=matched,
                        archive_size=archive_info["size"],
                        archive_mtime=archive_info["mtime"],
                    )
                )
        return results

    def search_by_pattern(self, pattern: str) -> list[SearchResult]:
        """按 glob 模式搜索（使用 fnmatch）"""
        results = []
        for archive_info in self.scan_archives():
            archive_path = archive_info["path"]
            members = self._list_members(archive_path)
            matched = [
                m
                for m in members
                if fnmatch(m["name"], pattern)
                or fnmatch(os.path.basename(m["name"]), pattern)
            ]
            if matched:
                results.append(
                    SearchResult(
                        archive=archive_path,
                        members=matched,
                        archive_size=archive_info["size"],
                        archive_mtime=archive_info["mtime"],
                    )
                )
        return results

    def search_by_extension(self, ext: str) -> list[SearchResult]:
        """按扩展名搜索（如 .log, .py）"""
        if not ext.startswith("."):
            ext = "." + ext
        ext_lower = ext.lower()
        results = []
        for archive_info in self.scan_archives():
            archive_path = archive_info["path"]
            members = self._list_members(archive_path)
            matched = [
                m
                for m in members
                if os.path.splitext(m["name"])[1].lower() == ext_lower
            ]
            if matched:
                results.append(
                    SearchResult(
                        archive=archive_path,
                        members=matched,
                        archive_size=archive_info["size"],
                        archive_mtime=archive_info["mtime"],
                    )
                )
        return results

    def get_summary(self, results: list[SearchResult]) -> dict:
        """搜索结果统计

        返回 {"total_archives": int, "matched_archives": int, "total_matches": int}
        """
        total_archives = len(self.scan_archives())
        matched_archives = len(results)
        total_matches = sum(len(r.members) for r in results)
        return {
            "total_archives": total_archives,
            "matched_archives": matched_archives,
            "total_matches": total_matches,
        }

    def format_results(self, results: list[SearchResult], lang: str = "zh_CN") -> str:
        """格式化搜索结果"""
        if not results:
            if lang == "zh_CN":
                return "未找到匹配的文件。"
            return "No matching files found."

        lines: list[str] = []
        summary = self.get_summary(results)
        if lang == "zh_CN":
            lines.append(
                f"搜索结果: {summary['matched_archives']}/{summary['total_archives']} "
                f"个档案包含匹配项, 共 {summary['total_matches']} 个匹配文件"
            )
        else:
            lines.append(
                f"Search results: {summary['matched_archives']}/{summary['total_archives']} "
                f"archives matched, {summary['total_matches']} matching files total"
            )
        lines.append("")

        for result in results:
            if lang == "zh_CN":
                lines.append(
                    f"  档案: {result.archive} "
                    f"({result.archive_size / (1024 * 1024):.2f} MB, {result.archive_mtime})"
                )
                lines.append(f"  匹配文件 ({len(result.members)}):")
            else:
                lines.append(
                    f"  Archive: {result.archive} "
                    f"({result.archive_size / (1024 * 1024):.2f} MB, {result.archive_mtime})"
                )
                lines.append(f"  Matching files ({len(result.members)}):")
            for m in result.members:
                lines.append(f"    {m['name']}")
            lines.append("")

        return "\n".join(lines)
