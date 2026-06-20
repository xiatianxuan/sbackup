"""元数据导出模块：支持导出备份历史和审计日志为 CSV/JSON 格式"""

import csv
import json
import os
from datetime import datetime, timezone

from sbackup.config import get_default_data_file


class MetadataExporter:
    """备份元数据导出器"""

    def __init__(self, data_file: str = ""):
        self.data_file = data_file or get_default_data_file()

    # ── 内部数据加载 ──────────────────────────────────────────

    def _load_data(self) -> dict:
        """加载数据文件"""
        if not os.path.exists(self.data_file):
            return {}
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _load_audit_entries(self) -> list[dict]:
        """加载审计日志文件"""
        from sbackup.audit import _default_audit_path

        audit_file = _default_audit_path()
        if not os.path.exists(audit_file):
            return []
        try:
            with open(audit_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    # ── 公共查询方法 ──────────────────────────────────────────

    def get_history(self, strategy_name: str = "") -> list[dict]:
        """获取备份历史记录

        :param strategy_name: 策略名称过滤（匹配 source 路径包含），空字符串导出全部
        """
        data = self._load_data()
        history = data.get("_history", [])
        if strategy_name:
            history = [e for e in history if strategy_name in e.get("source", "")]
        return history

    def get_audit_entries(self, event: str = "") -> list[dict]:
        """获取审计日志条目

        :param event: 事件类型过滤，空字符串导出全部
        """
        entries = self._load_audit_entries()
        if event:
            entries = [e for e in entries if e.get("event") == event]
        return entries

    # ── 历史导出 ──────────────────────────────────────────────

    def export_history_csv(self, output_path: str, strategy_name: str = "") -> int:
        """导出备份历史到 CSV 文件

        列: time, strategy, source, files_count, size, checksum
        返回导出的行数
        """
        history = self.get_history(strategy_name)
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        fieldnames = ["time", "strategy", "source", "files_count", "size", "checksum"]
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for entry in history:
                source = entry.get("source", "")
                writer.writerow(
                    {
                        "time": entry.get("time", ""),
                        "strategy": os.path.basename(source) if source else "",
                        "source": source,
                        "files_count": entry.get("files_count", 0),
                        "size": entry.get("size_mb", 0),
                        "checksum": entry.get("sha256", ""),
                    }
                )
        return len(history)

    def export_history_json(self, output_path: str, strategy_name: str = "") -> int:
        """导出备份历史到 JSON 文件（格式化输出）

        返回导出的行数
        """
        history = self.get_history(strategy_name)
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return len(history)

    # ── 审计日志导出 ──────────────────────────────────────────

    def export_audit_csv(self, output_path: str, event: str = "") -> int:
        """导出审计日志到 CSV 文件

        列: id, timestamp, event, status, source_path, target_path,
            format, files_count, total_size, backup_size, duration, error_message
        返回导出的行数
        """
        entries = self.get_audit_entries(event)
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        fieldnames = [
            "id",
            "timestamp",
            "event",
            "status",
            "source_path",
            "target_path",
            "format",
            "files_count",
            "total_size",
            "backup_size",
            "duration",
            "error_message",
        ]
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for entry in entries:
                writer.writerow({k: entry.get(k, "") for k in fieldnames})
        return len(entries)

    def export_audit_json(self, output_path: str, event: str = "") -> int:
        """导出审计日志到 JSON 文件

        返回导出的行数
        """
        entries = self.get_audit_entries(event)
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        return len(entries)

    # ── 综合导出 ──────────────────────────────────────────────

    def _compute_stats(self) -> dict:
        """计算历史和审计的统计信息"""
        data = self._load_data()
        history = data.get("_history", [])
        audit_entries = self._load_audit_entries()

        total_size_mb = sum(e.get("size_mb", 0) for e in history)
        total_files = sum(e.get("files_count", 0) for e in history)

        # 审计统计
        audit_event_counts: dict[str, int] = {}
        for entry in audit_entries:
            evt = entry.get("event", "")
            audit_event_counts[evt] = audit_event_counts.get(evt, 0) + 1

        return {
            "history_count": len(history),
            "audit_count": len(audit_entries),
            "total_size_mb": round(total_size_mb, 2),
            "total_files": total_files,
            "audit_event_counts": audit_event_counts,
        }

    def export_combined(self, output_path: str, fmt: str = "json") -> int:
        """导出综合报告：历史 + 审计 + 统计信息

        :param fmt: 输出格式，"json" 或 "csv"
        :return: 导出的历史记录数 + 审计条目数
        """
        history = self.get_history()
        audit_entries = self.get_audit_entries()
        stats = self._compute_stats()
        export_time = datetime.now(timezone.utc).isoformat()

        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        if fmt == "csv":
            # CSV 综合导出：两个独立的 CSV 文件通过后缀区分
            history_path = output_path.replace(".csv", "_history.csv")
            audit_path = output_path.replace(".csv", "_audit.csv")
            self.export_history_csv(history_path)
            self.export_audit_csv(audit_path)
            # 额外写入统计信息到 JSON
            stats_path = output_path.replace(".csv", "_stats.json")
            with open(stats_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"export_time": export_time, "stats": stats},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            return len(history) + len(audit_entries)

        # JSON 格式（默认）
        report = {
            "export_time": export_time,
            "history": history,
            "audit": audit_entries,
            "stats": stats,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        return len(history) + len(audit_entries)
