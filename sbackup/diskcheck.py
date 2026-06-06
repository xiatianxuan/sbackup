"""
磁盘空间预估模块：扫描源目录、估算备份大小、检查目标磁盘空间
"""

import os
import sys
import logging
from dataclasses import dataclass, field
from pathlib import Path

from sbackup.i18n import t

logger = logging.getLogger(__name__)

# 按文件扩展名分类的压缩比映射
# 文本类：高压缩率
_TEXT_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".txt",
        ".json",
        ".xml",
        ".html",
        ".css",
        ".md",
        ".csv",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".sh",
        ".bat",
        ".cmd",
        ".ps1",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".sql",
        ".log",
        ".rtf",
        ".tex",
    }
)

# 数据库文件
_DB_EXTENSIONS = frozenset({".db", ".sqlite", ".sqlite3"})

# 图片文件（几乎不压缩）
_IMAGE_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".heic"}
)

# 视频/音频文件（几乎不压缩）
_MEDIA_EXTENSIONS = frozenset(
    {".mp4", ".mp3", ".wav", ".avi", ".mkv", ".flac", ".ogg", ".aac", ".wma", ".mov"}
)

# 已压缩的归档文件
_ARCHIVE_EXTENSIONS = frozenset(
    {".zip", ".gz", ".7z", ".rar", ".xz", ".bz2", ".zst", ".lz4"}
)

# 各文件类型的默认压缩比
_RATIO_TEXT = 0.3
_RATIO_DB = 0.5
_RATIO_DEFAULT = 0.6
_RATIO_IMAGE = 0.95
_RATIO_MEDIA = 0.98
_RATIO_ARCHIVE = 0.99
_RATIO_UNCOMPRESSED = 1.0


def _get_extension_ratio(ext: str) -> float:
    """根据文件扩展名返回估算压缩比（压缩后大小 / 原始大小）"""
    ext = ext.lower()
    if ext in _TEXT_EXTENSIONS:
        return _RATIO_TEXT
    if ext in _DB_EXTENSIONS:
        return _RATIO_DB
    if ext in _IMAGE_EXTENSIONS:
        return _RATIO_IMAGE
    if ext in _MEDIA_EXTENSIONS:
        return _RATIO_MEDIA
    if ext in _ARCHIVE_EXTENSIONS:
        return _RATIO_ARCHIVE
    return _RATIO_DEFAULT


def _get_disk_space_info(path: str) -> tuple[int, int, int]:
    """获取指定路径所在磁盘的空间信息（跨平台）
    :return: (total, used, free) 单位 bytes
    """
    target = os.path.realpath(path)
    if sys.platform == "win32":
        import ctypes

        free_bytes = ctypes.c_ulonglong(0)
        total_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(target),
            None,
            ctypes.pointer(total_bytes),
            ctypes.pointer(free_bytes),
        )
        total = total_bytes.value
        free = free_bytes.value
        used = total - free
        return total, used, free
    else:
        usage = os.statvfs(target)
        total = usage.f_blocks * usage.f_frsize
        free = usage.f_bavail * usage.f_frsize
        used = total - free
        return total, used, free


@dataclass
class DiskSpaceInfo:
    """磁盘空间检查结果"""

    total: int = 0  # 目标磁盘总空间 (bytes)
    used: int = 0  # 已用空间
    free: int = 0  # 可用空间
    # 备份相关
    source_total: int = 0  # 源文件总大小
    estimated_backup: int = 0  # 估算备份文件大小
    margin: int = 0  # 剩余空间 - 估算大小
    enough: bool = True  # 空间是否足够
    warnings: list[str] = field(default_factory=list)


class DiskChecker:
    """磁盘空间检查器"""

    def __init__(self, source_path: str, target_path: str) -> None:
        self.source_path = os.path.realpath(source_path)
        self.target_path = os.path.realpath(target_path)

    def get_disk_space(self, path: str) -> DiskSpaceInfo:
        """获取指定路径所在磁盘的空间信息（跨平台）"""
        real_path = os.path.realpath(path)
        if not os.path.isdir(real_path):
            # 尝试取父目录
            real_path = str(Path(real_path).parent)
        total, used, free = _get_disk_space_info(real_path)
        return DiskSpaceInfo(total=total, used=used, free=free)

    def scan_source(self) -> int:
        """扫描源目录，返回总文件大小（bytes）"""
        total = 0
        if not os.path.isdir(self.source_path):
            return 0
        for dirpath, _dirnames, filenames in os.walk(self.source_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total += os.path.getsize(filepath)
                except OSError:
                    pass
        return total

    def estimate_backup_size(
        self,
        fmt: str = "ZIP",
        compression_level: int = 6,
        source_total: int | None = None,
    ) -> int:
        """估算备份文件大小

        简单估算：
        - TAR 格式（无压缩）：所有文件压缩比 1.0
        - 其他格式：按文件类型选择压缩比
        - 压缩级别越高，压缩比越低（在基础上乘以一个调整系数）
        """
        if source_total is None:
            source_total = self.scan_source()

        # TAR 格式不压缩
        fmt_upper = fmt.upper().replace(".", "_")
        if fmt_upper == "TAR":
            return source_total

        # 压缩级别调整系数：级别 0 时不压缩，级别 9 时最佳压缩
        level_factor = 1.0
        if fmt_upper == "7Z":
            # 7z 默认更优
            level_factor = max(0.7, 1.0 - compression_level * 0.035)
        else:
            level_factor = max(0.85, 1.0 - compression_level * 0.02)

        total = 0
        if not os.path.isdir(self.source_path):
            return 0

        for dirpath, _dirnames, filenames in os.walk(self.source_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    size = os.path.getsize(filepath)
                except OSError:
                    continue
                ext = Path(filename).suffix
                ratio = _get_extension_ratio(ext)
                total += int(size * ratio * level_factor)

        return max(total, 1 if source_total > 0 else 0)

    def check(
        self,
        fmt: str = "ZIP",
        compression_level: int = 6,
    ) -> DiskSpaceInfo:
        """完整检查：扫描源 + 估算大小 + 检查目标磁盘空间"""
        # 扫描源目录
        source_total = self.scan_source()

        # 获取目标磁盘空间
        disk_info = self.get_disk_space(self.target_path)

        # 估算备份大小
        estimated = self.estimate_backup_size(fmt, compression_level, source_total)

        # 计算剩余空间
        margin = disk_info.free - estimated
        enough = margin >= 0

        disk_info.source_total = source_total
        disk_info.estimated_backup = estimated
        disk_info.margin = margin
        disk_info.enough = enough

        # 生成警告
        if not enough:
            missing = abs(margin)
            disk_info.warnings.append(
                t(
                    "diskcheck.insufficient",
                    needed=_format_size(estimated),
                    available=_format_size(disk_info.free),
                    missing=_format_size(missing),
                )
            )

        return disk_info

    def format_report(self, info: DiskSpaceInfo, lang: str = "zh_CN") -> str:
        """格式化检查报告"""
        lines: list[str] = []
        lines.append(t("diskcheck.header"))
        lines.append(t("diskcheck.source", path=self.source_path))
        lines.append(t("diskcheck.target", path=self.target_path))
        lines.append("")

        # 源文件信息
        lines.append(t("diskcheck.source_size", size=_format_size(info.source_total)))
        lines.append(
            t(
                "diskcheck.estimated_size",
                size=_format_size(info.estimated_backup),
                ratio=_calc_ratio_text(info.source_total, info.estimated_backup),
            )
        )
        lines.append("")

        # 目标磁盘信息
        lines.append(t("diskcheck.disk_header"))
        lines.append(t("diskcheck.disk_total", size=_format_size(info.total)))
        lines.append(t("diskcheck.disk_used", size=_format_size(info.used)))
        lines.append(t("diskcheck.disk_free", size=_format_size(info.free)))
        lines.append("")

        # 空间检查结果
        if info.enough:
            lines.append(
                t(
                    "diskcheck.status.ok",
                    margin=_format_size(info.margin),
                )
            )
        else:
            missing = abs(info.margin)
            lines.append(
                t(
                    "diskcheck.status.insufficient",
                    needed=_format_size(info.estimated_backup),
                    available=_format_size(info.free),
                    missing=_format_size(missing),
                )
            )

        for w in info.warnings:
            lines.append(f"  {w}")

        return "\n".join(lines)


def _format_size(size_bytes: int) -> str:
    """将字节数格式化为人类可读的字符串"""
    if size_bytes < 0:
        return f"-{_format_size(-size_bytes)}"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024**3:
        return f"{size_bytes / (1024**2):.1f} MB"
    return f"{size_bytes / (1024**3):.2f} GB"


def _calc_ratio_text(original: int, compressed: int) -> str:
    """计算并返回压缩比百分比文本"""
    if original <= 0:
        return "0%"
    ratio = compressed / original * 100
    return f"{ratio:.1f}%"
