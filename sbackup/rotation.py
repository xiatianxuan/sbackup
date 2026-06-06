"""
备份轮转/清理策略模块：根据策略自动清理旧备份文件
"""

import os
import time
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sbackup.i18n import t

logger = logging.getLogger(__name__)

# 所有已知的备份文件后缀（按长度降序排列，便于正确匹配 .tar.gz 等复合后缀）
BACKUP_EXTENSIONS = [
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".tar.zst",
    ".zip",
    ".tar",
    ".7z",
]


@dataclass
class RotationPolicy:
    """备份轮转策略配置"""

    keep_count: int = 0  # 保留最近 N 份（0=不限制）
    keep_days: int = 0  # 保留 N 天内的（0=不限制）
    keep_daily: int = 0  # 保留最近 N 天每天一份
    dry_run: bool = False  # 只显示会删除什么，不实际删除

    def has_any_rule(self) -> bool:
        """是否有至少一条非零规则"""
        return self.keep_count > 0 or self.keep_days > 0 or self.keep_daily > 0


class BackupRotator:
    """备份轮转清理器"""

    def __init__(self, backup_dir: str, policy: RotationPolicy):
        self.backup_dir = backup_dir
        self.policy = policy

    def scan_backups(self) -> list[dict]:
        """扫描目录下所有备份文件，返回按修改时间排序的列表（最新在前）

        Returns:
            [{"path": str, "name": str, "size": int, "mtime": float, "mtime_iso": str}]
            只识别已知后缀的文件
        """
        target = Path(self.backup_dir)
        if not target.is_dir():
            return []

        results = []
        for entry in target.iterdir():
            if not entry.is_file():
                continue
            if _is_backup_file(entry.name):
                try:
                    st = entry.stat()
                except OSError:
                    continue
                mtime = st.st_mtime
                results.append(
                    {
                        "path": str(entry.resolve()),
                        "name": entry.name,
                        "size": st.st_size,
                        "mtime": mtime,
                        "mtime_iso": datetime.fromtimestamp(mtime).isoformat(),
                    }
                )

        # 按修改时间降序排序（最新的在前）
        results.sort(key=lambda b: b["mtime"], reverse=True)
        return results

    def plan(self) -> tuple[list[dict], list[dict]]:
        """根据策略计算保留和删除列表

        多个策略取交集：一份文件必须同时满足所有非零策略才保留。
        如果一个文件只满足 keep_count 但不满足 keep_days，仍然删除。

        Returns:
            (keep_list, delete_list)
        """
        backups = self.scan_backups()
        if not backups:
            return [], []

        if not self.policy.has_any_rule():
            # 无策略时全部保留
            return backups, []

        # 收集每条规则保留的文件路径集合
        rule_keep_sets: list[set[str]] = []

        if self.policy.keep_count > 0:
            rule_keep_sets.append(self._apply_keep_count(backups))

        if self.policy.keep_days > 0:
            rule_keep_sets.append(self._apply_keep_days(backups))

        if self.policy.keep_daily > 0:
            rule_keep_sets.append(self._apply_keep_daily(backups))

        if not rule_keep_sets:
            return backups, []

        # 取交集：所有规则都保留的才保留
        keep_paths = rule_keep_sets[0]
        for s in rule_keep_sets[1:]:
            keep_paths = keep_paths & s

        keep_list = [b for b in backups if b["path"] in keep_paths]
        delete_list = [b for b in backups if b["path"] not in keep_paths]
        return keep_list, delete_list

    def execute(self) -> tuple[int, list[str]]:
        """执行清理

        Returns:
            (deleted_count, deleted_paths)
            如果 dry_run=True，只返回会删除的文件但不实际删除
        """
        _keep_list, delete_list = self.plan()

        if not delete_list:
            return 0, []

        deleted_paths: list[str] = []
        for item in delete_list:
            path = item["path"]
            if self.policy.dry_run:
                deleted_paths.append(path)
                logger.info(
                    t("log.rotation.dry_run_skip"), path, item["size"] / (1024 * 1024)
                )
            else:
                try:
                    os.remove(path)
                    deleted_paths.append(path)
                    logger.debug(
                        t("log.rotation.deleted"),
                        path,
                        item["size"] / (1024 * 1024),
                    )
                except OSError as e:
                    logger.error(t("log.rotation.delete_error"), path, e)

        return len(deleted_paths), deleted_paths

    def _apply_keep_days(self, backups: list[dict]) -> set[str]:
        """保留 N 天内的文件"""
        cutoff = time.time() - self.policy.keep_days * 86400
        keep: set[str] = set()
        for b in backups:
            if b["mtime"] >= cutoff:
                keep.add(b["path"])
        return keep

    def _apply_keep_count(self, backups: list[dict]) -> set[str]:
        """保留最新的 N 个文件"""
        keep: set[str] = set()
        for b in backups[: self.policy.keep_count]:
            keep.add(b["path"])
        return keep

    def _apply_keep_daily(self, backups: list[dict]) -> set[str]:
        """保留最近 N 天每天一份（每天保留最新的那个）"""
        if not backups:
            return set()

        # 按日期分组（忽略时间），每天只保留最新的一个文件
        daily_groups: dict[str, list[dict]] = {}
        for b in backups:
            dt = datetime.fromtimestamp(b["mtime"])
            day_key = dt.strftime("%Y-%m-%d")
            if day_key not in daily_groups:
                daily_groups[day_key] = []
            daily_groups[day_key].append(b)

        # 按日期降序排列，取最近 N 天
        sorted_days = sorted(daily_groups.keys(), reverse=True)
        selected_days = sorted_days[: self.policy.keep_daily]

        keep: set[str] = set()
        for day_key in selected_days:
            group = daily_groups[day_key]
            # 每天保留最新的一个（mtime 最大的）
            group.sort(key=lambda b: b["mtime"], reverse=True)
            keep.add(group[0]["path"])

        return keep


def _is_backup_file(filename: str) -> bool:
    """检查文件名是否是已知的备份文件格式"""
    name_lower = filename.lower()
    for ext in BACKUP_EXTENSIONS:
        if name_lower.endswith(ext):
            return True
    return False
