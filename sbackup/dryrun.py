"""Dry-run 预览模式：扫描目录并模拟备份的文件选择逻辑，不创建任何文件"""

import os
from pathlib import Path
from fnmatch import fnmatch
from dataclasses import dataclass, field
from sbackup.i18n import t
from sbackup.config import Config


@dataclass
class DryRunResult:
    """Dry-run 扫描结果"""

    total_files: int = 0
    included_files: int = 0
    excluded_files: int = 0
    total_size: int = 0
    included_size: int = 0
    excluded_size: int = 0
    skip_patterns_matched: dict = field(default_factory=dict)  # pattern -> [files]
    large_files: list = field(default_factory=list)  # 最大的 10 个文件
    file_types: dict = field(default_factory=dict)  # extension -> count
    warnings: list = field(default_factory=list)  # 磁盘空间不足等
    included_list: list = field(default_factory=list)  # (rel_path, size)
    excluded_list: list = field(default_factory=list)  # (rel_path, size, reason)


class DryRunScanner:
    """扫描目录，模拟备份的文件选择逻辑，返回分析结果"""

    def __init__(self, folder_path: str, config: Config):
        self.folder_path = folder_path
        self.config = config

    def scan(self) -> DryRunResult:
        """扫描目录，模拟备份的文件选择逻辑（skip_patterns, include/exclude, max_size, min_size）
        不创建任何文件，只返回分析结果
        """
        result = DryRunResult()
        folder = Path(self.folder_path)

        if not folder.is_dir():
            result.warnings.append(t("dryrun.warning.not_dir", path=self.folder_path))
            return result

        skip_patterns = self.config.skip_patterns or []
        include_patterns = self.config.include_patterns or []
        exclude_patterns = self.config.exclude_patterns or []
        max_size = self.config.max_size
        min_size = self.config.min_size

        # 加载 .sbackupignore 文件
        extra_patterns = self._load_ignore_file(folder)

        all_files: list[tuple[str, int]] = []  # (rel_path, size)

        try:
            for dirpath, dirnames, filenames in os.walk(
                folder, followlinks=self.config.follow_symlinks
            ):
                rel_dir = os.path.relpath(dirpath, folder)
                if rel_dir == ".":
                    rel_dir = ""

                # 过滤子目录（与 skip_patterns 匹配的目录不再遍历）
                filtered_dirs = []
                for d in dirnames:
                    dir_rel = (
                        os.path.join(rel_dir, d).replace("\\", "/") if rel_dir else d
                    )
                    if self._matches_skip_pattern(
                        dir_rel, skip_patterns, extra_patterns
                    ):
                        continue
                    filtered_dirs.append(d)
                dirnames[:] = filtered_dirs

                for filename in filenames:
                    file_rel = (
                        os.path.join(rel_dir, filename).replace("\\", "/")
                        if rel_dir
                        else filename
                    )

                    try:
                        file_path = Path(dirpath) / filename
                        file_size = file_path.stat().st_size
                    except OSError:
                        continue

                    result.total_files += 1
                    result.total_size += file_size

                    all_files.append((file_rel, file_size))

                    # 1. skip_patterns 过滤
                    skip_reason = self._check_skip_pattern(
                        file_rel, skip_patterns, extra_patterns
                    )
                    if skip_reason:
                        result.excluded_files += 1
                        result.excluded_size += file_size
                        result.excluded_list.append((file_rel, file_size, skip_reason))
                        result.skip_patterns_matched.setdefault(skip_reason, []).append(
                            file_rel
                        )
                        continue

                    # 2. include_patterns 过滤
                    if include_patterns:
                        basename = os.path.basename(file_rel)
                        if not any(
                            fnmatch(file_rel, p) or fnmatch(basename, p)
                            for p in include_patterns
                        ):
                            reason = t("dryrun.reason.not_included")
                            result.excluded_files += 1
                            result.excluded_size += file_size
                            result.excluded_list.append((file_rel, file_size, reason))
                            continue

                    # 3. exclude_patterns 过滤
                    if exclude_patterns:
                        basename = os.path.basename(file_rel)
                        if any(
                            fnmatch(file_rel, p) or fnmatch(basename, p)
                            for p in exclude_patterns
                        ):
                            matched_pattern = self._find_matching_exclude(
                                file_rel, exclude_patterns
                            )
                            reason = (
                                f"{t('dryrun.reason.excluded')} {matched_pattern}"
                                if matched_pattern
                                else t("dryrun.reason.excluded")
                            )
                            result.excluded_files += 1
                            result.excluded_size += file_size
                            result.excluded_list.append((file_rel, file_size, reason))
                            continue

                    # 4. max_size 过滤
                    if max_size > 0 and file_size > max_size:
                        reason = f"{t('dryrun.reason.too_large')} > {self._format_size(max_size)}"
                        result.excluded_files += 1
                        result.excluded_size += file_size
                        result.excluded_list.append((file_rel, file_size, reason))
                        continue

                    # 5. min_size 过滤
                    if min_size > 0 and file_size < min_size:
                        reason = f"{t('dryrun.reason.too_small')} < {self._format_size(min_size)}"
                        result.excluded_files += 1
                        result.excluded_size += file_size
                        result.excluded_list.append((file_rel, file_size, reason))
                        continue

                    # 文件被包含
                    result.included_files += 1
                    result.included_size += file_size
                    result.included_list.append((file_rel, file_size))

                    # 统计文件类型
                    ext = Path(filename).suffix.lower() or t("dryrun.no_extension")
                    result.file_types[ext] = result.file_types.get(ext, 0) + 1

        except PermissionError:
            result.warnings.append(
                t("dryrun.warning.permission", path=self.folder_path)
            )
        except OSError as e:
            result.warnings.append(t("dryrun.warning.os_error", error=e))

        # 找出最大的 10 个文件
        all_files_sorted = sorted(all_files, key=lambda x: x[1], reverse=True)
        result.large_files = [(path, size) for path, size in all_files_sorted[:10]]

        # 检查磁盘空间
        self._check_disk_space(result)

        return result

    def format_summary(self, result: DryRunResult, lang: str = "zh_CN") -> str:
        """格式化扫描结果为可读文本"""
        lines = []
        lines.append(f"{'=' * 20} {t('dryrun.title')} {'=' * 20}")
        lines.append(f"{t('dryrun.scanned_dir')}: {self.folder_path}")
        lines.append(
            f"{t('dryrun.total_files')}: {result.total_files} "
            f"({t('dryrun.total_size')}: {self._format_size(result.total_size)})"
        )
        lines.append(
            f"{t('dryrun.included_files')}: {result.included_files} "
            f"({self._format_size(result.included_size)})"
        )
        lines.append(
            f"{t('dryrun.excluded_files')}: {result.excluded_files} "
            f"({self._format_size(result.excluded_size)})"
        )

        # 排除原因
        if result.skip_patterns_matched:
            lines.append("")
            lines.append(f"{t('dryrun.exclusion_reasons')}:")
            for pattern, files in sorted(
                result.skip_patterns_matched.items(),
                key=lambda x: len(x[1]),
                reverse=True,
            ):
                size = sum(
                    s
                    for _, s, r in result.excluded_list
                    if r == pattern or r.startswith(pattern)
                )
                lines.append(
                    f"  {t('dryrun.skip')}: {pattern}: "
                    f"{len(files)} {t('dryrun.unit_files')} "
                    f"({self._format_size(size)})"
                )

        # 统计非 skip_patterns 的排除原因
        other_reasons: dict[str, int] = {}
        for _, _, reason in result.excluded_list:
            if reason not in result.skip_patterns_matched:
                other_reasons[reason] = other_reasons.get(reason, 0) + 1
        if other_reasons:
            if not result.skip_patterns_matched:
                lines.append("")
                lines.append(f"{t('dryrun.exclusion_reasons')}:")
            for reason, count in sorted(
                other_reasons.items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"  {reason}: {count} {t('dryrun.unit_files')}")

        # 文件类型分布
        if result.file_types:
            lines.append("")
            lines.append(f"{t('dryrun.file_types')}:")
            sorted_types = sorted(
                result.file_types.items(), key=lambda x: x[1], reverse=True
            )
            for ext, count in sorted_types[:10]:
                lines.append(f"  {ext}: {count} {t('dryrun.unit_files')}")
            if len(sorted_types) > 10:
                remaining = sum(c for _, c in sorted_types[10:])
                lines.append(
                    f"  ... {t('dryrun.and_others')}: {remaining} {t('dryrun.unit_files')}"
                )

        # 最大文件
        if result.large_files:
            lines.append("")
            lines.append(f"{t('dryrun.largest_files')}:")
            for i, (fpath, fsize) in enumerate(result.large_files, 1):
                lines.append(f"  {i}. {fpath} ({self._format_size(fsize)})")

        # 警告
        if result.warnings:
            lines.append("")
            lines.append(f"{t('dryrun.warnings')}:")
            for w in result.warnings:
                lines.append(f"  {w}")

        return "\n".join(lines)

    def format_file_list(
        self,
        result: DryRunResult,
        show_excluded: bool = False,
        limit: int = 50,
    ) -> str:
        """格式化文件列表"""
        lines = []
        if show_excluded:
            files = result.excluded_list
            lines.append(
                f"--- {t('dryrun.excluded_files_list')} ({len(files)} {t('dryrun.unit_files')}) ---"
            )
            for fpath, fsize, reason in files[:limit]:
                lines.append(f"  {fpath}  ({self._format_size(fsize)})  [{reason}]")
            if len(files) > limit:
                lines.append(
                    f"  ... {t('dryrun.more_files', count=len(files) - limit)}"
                )
        else:
            files = result.included_list
            lines.append(
                f"--- {t('dryrun.included_files_list')} ({len(files)} {t('dryrun.unit_files')}) ---"
            )
            for fpath, fsize in files[:limit]:
                lines.append(f"  {fpath}  ({self._format_size(fsize)})")
            if len(files) > limit:
                lines.append(
                    f"  ... {t('dryrun.more_files', count=len(files) - limit)}"
                )

        return "\n".join(lines)

    # ----- 内部辅助方法 -----

    def _load_ignore_file(self, folder_path: Path) -> list[str]:
        """从源目录的 .sbackupignore 文件加载忽略规则"""
        ignore_file = folder_path / ".sbackupignore"
        if not ignore_file.is_file():
            return []
        try:
            lines = ignore_file.read_text(encoding="utf-8").splitlines()
            patterns = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
            return patterns
        except OSError:
            return []

    def _matches_skip_pattern(
        self,
        rel_path: str,
        skip_patterns: list[str],
        extra_patterns: list[str],
    ) -> bool:
        """检查路径是否匹配 skip_patterns（用于目录级过滤）"""
        basename = os.path.basename(rel_path)
        all_patterns = skip_patterns + extra_patterns
        negated = []
        matched = False
        for pattern in all_patterns:
            if pattern.startswith("!"):
                negated.append(pattern[1:])
                continue
            if fnmatch(rel_path, pattern) or fnmatch(basename, pattern):
                matched = True
        if not matched:
            return False
        for pattern in negated:
            if fnmatch(rel_path, pattern) or fnmatch(basename, pattern):
                return False
        return True

    def _check_skip_pattern(
        self,
        rel_path: str,
        skip_patterns: list[str],
        extra_patterns: list[str],
    ) -> str | None:
        """检查文件是否匹配 skip_patterns，返回匹配的 pattern 或 None"""
        import re

        basename = os.path.basename(rel_path)
        all_patterns = skip_patterns + extra_patterns
        negated = []
        matched_pattern = None

        for pattern in all_patterns:
            if pattern.startswith("!"):
                negated.append(pattern[1:])
                continue
            if pattern.startswith("re:"):
                regex_str = pattern[3:]
                if len(regex_str) > 256:
                    continue
                try:
                    if re.search(regex_str, rel_path) or re.search(regex_str, basename):
                        matched_pattern = pattern
                except re.error:
                    pass
            else:
                if fnmatch(rel_path, pattern) or fnmatch(basename, pattern):
                    matched_pattern = pattern

        if not matched_pattern:
            return None

        for pattern in negated:
            if pattern.startswith("re:"):
                regex_str = pattern[3:]
                if len(regex_str) > 256:
                    continue
                try:
                    if re.search(regex_str, rel_path) or re.search(regex_str, basename):
                        return None
                except re.error:
                    pass
            else:
                if fnmatch(rel_path, pattern) or fnmatch(basename, pattern):
                    return None

        return matched_pattern

    def _find_matching_exclude(self, rel_path: str, exclude_patterns: list[str]) -> str:
        """找到匹配的 exclude pattern"""
        basename = os.path.basename(rel_path)
        for p in exclude_patterns:
            if fnmatch(rel_path, p) or fnmatch(basename, p):
                return p
        return ""

    def _check_disk_space(self, result: DryRunResult) -> None:
        """检查目标目录是否有足够磁盘空间"""
        folder = Path(self.folder_path)
        try:
            stat = os.statvfs(str(folder))
            free_bytes = stat.f_bavail * stat.f_frsize
            if free_bytes < result.included_size:
                result.warnings.append(
                    t(
                        "dryrun.warning.disk_space",
                        free=self._format_size(free_bytes),
                        need=self._format_size(result.included_size),
                    )
                )
        except (OSError, AttributeError):
            # Windows 没有 statvfs，使用 shutil
            try:
                import shutil

                free_bytes, _, _ = shutil.disk_usage(str(folder))
                if free_bytes < result.included_size:
                    result.warnings.append(
                        t(
                            "dryrun.warning.disk_space",
                            free=self._format_size(free_bytes),
                            need=self._format_size(result.included_size),
                        )
                    )
            except OSError:
                pass

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """将字节数格式化为可读的大小字符串"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
