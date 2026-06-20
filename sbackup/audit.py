"""审计日志模块：记录备份、恢复等操作的审计事件"""

import os
import sys
import json
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """审计日志条目"""

    id: str = ""
    timestamp: str = ""
    event: str = ""
    source_path: str = ""
    target_path: str = ""
    format: str = ""
    status: str = "success"
    files_count: int = 0
    total_size: int = 0
    backup_size: int = 0
    duration: float = 0
    error_message: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典"""
        d = {
            "id": self.id,
            "timestamp": self.timestamp,
            "event": self.event,
            "source_path": self.source_path,
            "target_path": self.target_path,
            "format": self.format,
            "status": self.status,
            "files_count": self.files_count,
            "total_size": self.total_size,
            "backup_size": self.backup_size,
            "duration": self.duration,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }
        return d

    @staticmethod
    def from_dict(data: dict) -> "AuditEntry":
        """从字典创建 AuditEntry"""
        return AuditEntry(
            id=data.get("id", ""),
            timestamp=data.get("timestamp", ""),
            event=data.get("event", ""),
            source_path=data.get("source_path", ""),
            target_path=data.get("target_path", ""),
            format=data.get("format", ""),
            status=data.get("status", "success"),
            files_count=data.get("files_count", 0),
            total_size=data.get("total_size", 0),
            backup_size=data.get("backup_size", 0),
            duration=data.get("duration", 0),
            error_message=data.get("error_message", ""),
            metadata=data.get("metadata", {}),
        )


def _default_audit_path() -> str:
    """返回跨平台的默认审计日志路径"""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return os.path.join(base, "sbackup", "audit.json")


class AuditLogger:
    """审计日志管理器"""

    def __init__(self, audit_file: str = ""):
        self.audit_file = audit_file or _default_audit_path()
        self._entries: list[dict] = []
        self._load()

    def _load(self) -> None:
        """从 JSON 文件加载审计日志"""
        if not os.path.exists(self.audit_file):
            self._entries = []
            return
        try:
            with open(self.audit_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._entries = data
            else:
                self._entries = []
        except (json.JSONDecodeError, OSError):
            self._entries = []

    def _save(self) -> None:
        """保存审计日志到 JSON 文件（原子写入）"""
        data_dir = os.path.dirname(self.audit_file)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)

        tmp_path = self.audit_file + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, ensure_ascii=False, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.audit_file)
        except OSError:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    def log(self, event: str, **kwargs) -> AuditEntry:
        """记录一条审计事件"""
        entry = AuditEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event=event,
            source_path=kwargs.get("source_path", ""),
            target_path=kwargs.get("target_path", ""),
            format=kwargs.get("format", ""),
            status=kwargs.get("status", "success"),
            files_count=kwargs.get("files_count", 0),
            total_size=kwargs.get("total_size", 0),
            backup_size=kwargs.get("backup_size", 0),
            duration=kwargs.get("duration", 0),
            error_message=kwargs.get("error_message", ""),
            metadata=kwargs.get("metadata", {}),
        )
        self._entries.append(entry.to_dict())
        self._save()
        return entry

    def query(
        self,
        event: str = "",
        status: str = "",
        since: str = "",
        limit: int = 50,
    ) -> list[AuditEntry]:
        """查询审计日志，支持按事件类型/状态/时间过滤"""
        results: list[AuditEntry] = []
        for raw in reversed(self._entries):
            if event and raw.get("event") != event:
                continue
            if status and raw.get("status") != status:
                continue
            if since:
                entry_time = raw.get("timestamp", "")
                if entry_time < since:
                    continue
            results.append(AuditEntry.from_dict(raw))
            if len(results) >= limit:
                break
        return results

    def get_stats(self) -> dict:
        """统计信息：各事件类型数量、总备份大小、成功率"""
        total = len(self._entries)
        event_counts: dict[str, int] = {}
        total_backup_size = 0
        success_count = 0

        for raw in self._entries:
            event = raw.get("event", "")
            event_counts[event] = event_counts.get(event, 0) + 1
            total_backup_size += raw.get("backup_size", 0)
            if raw.get("status") == "success":
                success_count += 1

        success_rate = (success_count / total * 100) if total > 0 else 0

        return {
            "total": total,
            "event_counts": event_counts,
            "total_backup_size": total_backup_size,
            "success_count": success_count,
            "success_rate": round(success_rate, 1),
        }

    def cleanup(self, keep_days: int = 90) -> int:
        """清理旧日志，返回删除的条数"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
        cutoff_str = cutoff.isoformat()
        before = len(self._entries)
        self._entries = [
            e for e in self._entries if e.get("timestamp", "") >= cutoff_str
        ]
        removed = before - len(self._entries)
        if removed > 0:
            self._save()
        return removed

    def format_entries(self, entries: list[AuditEntry], lang: str = "zh_CN") -> str:
        """格式化审计条目为可读表格"""
        if not entries:
            if lang == "zh_CN":
                return "没有审计日志记录。"
            return "No audit log entries."

        lines: list[str] = []
        if lang == "zh_CN":
            lines.append("═══ 审计日志 ═══")
        else:
            lines.append("=== Audit Log ===")

        for entry in entries:
            if lang == "zh_CN":
                lines.append(f"  [{entry.event}] {entry.timestamp}")
                lines.append(f"    状态: {entry.status}")
            else:
                lines.append(f"  [{entry.event}] {entry.timestamp}")
                lines.append(f"    Status: {entry.status}")

            if entry.source_path:
                if lang == "zh_CN":
                    lines.append(f"    源路径: {entry.source_path}")
                else:
                    lines.append(f"    Source: {entry.source_path}")
            if entry.target_path:
                if lang == "zh_CN":
                    lines.append(f"    目标路径: {entry.target_path}")
                else:
                    lines.append(f"    Target: {entry.target_path}")
            if entry.files_count > 0:
                if lang == "zh_CN":
                    lines.append(f"    文件数: {entry.files_count}")
                else:
                    lines.append(f"    Files: {entry.files_count}")
            if entry.backup_size > 0:
                size_mb = entry.backup_size / (1024 * 1024)
                if lang == "zh_CN":
                    lines.append(f"    备份大小: {size_mb:.2f} MB")
                else:
                    lines.append(f"    Backup size: {size_mb:.2f} MB")
            if entry.duration > 0:
                if lang == "zh_CN":
                    lines.append(f"    耗时: {entry.duration:.1f}秒")
                else:
                    lines.append(f"    Duration: {entry.duration:.1f}s")
            if entry.error_message:
                if lang == "zh_CN":
                    lines.append(f"    错误: {entry.error_message}")
                else:
                    lines.append(f"    Error: {entry.error_message}")
            lines.append("")

        return "\n".join(lines)

    def format_stats(self, stats: dict, lang: str = "zh_CN") -> str:
        """格式化统计信息"""
        lines: list[str] = []
        if lang == "zh_CN":
            lines.append("═══ 审计日志统计 ═══")
            lines.append(f"总记录数: {stats['total']}")
            lines.append(
                f"总备份大小: {stats['total_backup_size'] / (1024 * 1024):.2f} MB"
            )
            lines.append(f"成功次数: {stats['success_count']}")
            lines.append(f"成功率: {stats['success_rate']}%")
            lines.append("")
            lines.append("事件类型统计:")
        else:
            lines.append("=== Audit Log Statistics ===")
            lines.append(f"Total entries: {stats['total']}")
            lines.append(
                f"Total backup size: {stats['total_backup_size'] / (1024 * 1024):.2f} MB"
            )
            lines.append(f"Success count: {stats['success_count']}")
            lines.append(f"Success rate: {stats['success_rate']}%")
            lines.append("")
            lines.append("Event type breakdown:")

        for event, count in stats.get("event_counts", {}).items():
            lines.append(f"  {event}: {count}")

        return "\n".join(lines)
