"""
单元测试 for sbackup.export 模块
"""

import csv
import json
import os
import tempfile
import shutil
import unittest

from sbackup.export import MetadataExporter


class TestMetadataExporter(unittest.TestCase):
    """MetadataExporter 类测试"""

    def setUp(self):
        """创建临时目录和测试数据文件"""
        self.tmpdir = tempfile.mkdtemp()
        # 创建模拟数据文件（包含历史记录）
        self.data_file = os.path.join(self.tmpdir, "sbackup.json")
        self.data = {
            "_history": [
                {
                    "time": "2026-06-07T10:30:00",
                    "source": "/home/user/docs",
                    "size_mb": 25.6,
                    "files_count": 150,
                    "sha256": "abc123def456",
                },
                {
                    "time": "2026-06-08T11:00:00",
                    "source": "/home/user/photos",
                    "size_mb": 1024.0,
                    "files_count": 500,
                    "sha256": "789abc012def",
                },
            ],
        }
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

        # 创建模拟审计日志文件
        # 计算审计文件路径（使用与 AuditLogger 相同的逻辑）
        if os.name == "nt":
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
        elif __import__("sys").platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support")
        else:
            base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        self.audit_dir = os.path.join(base, "sbackup_test_export")
        os.makedirs(self.audit_dir, exist_ok=True)
        self.audit_file = os.path.join(self.audit_dir, "audit.json")
        self.audit_data = [
            {
                "id": "uuid-001",
                "timestamp": "2026-06-07T10:30:00Z",
                "event": "backup_complete",
                "source_path": "/home/user/docs",
                "target_path": "/backup/docs",
                "format": "ZIP",
                "status": "success",
                "files_count": 150,
                "total_size": 26843545,
                "backup_size": 25600000,
                "duration": 5.3,
                "error_message": "",
                "metadata": {},
            },
            {
                "id": "uuid-002",
                "timestamp": "2026-06-08T11:00:00Z",
                "event": "backup_failed",
                "source_path": "/home/user/photos",
                "target_path": "/backup/photos",
                "format": "tar.gz",
                "status": "failed",
                "files_count": 0,
                "total_size": 0,
                "backup_size": 0,
                "duration": 1.2,
                "error_message": "disk full",
                "metadata": {},
            },
        ]
        with open(self.audit_file, "w", encoding="utf-8") as f:
            json.dump(self.audit_data, f, ensure_ascii=False, indent=4)

        # 创建导出器，使用测试数据文件，并 mock 审计日志路径
        self.exporter = MetadataExporter(data_file=self.data_file)
        # monkey-patch 审计日志加载以使用测试文件
        self.exporter._load_audit_entries = self._mock_load_audit

    def _mock_load_audit(self) -> list[dict]:
        """模拟加载审计日志"""
        if not os.path.exists(self.audit_file):
            return []
        try:
            with open(self.audit_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def tearDown(self):
        """清理临时目录"""
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.audit_dir, ignore_errors=True)

    # ── 历史记录 CSV 导出 ────────────────────────────────────

    def test_export_history_csv(self):
        """测试 CSV 导出备份历史"""
        output = os.path.join(self.tmpdir, "history.csv")
        count = self.exporter.export_history_csv(output)
        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(output))

    def test_export_history_csv_content(self):
        """测试 CSV 文件格式正确性（header + data rows）"""
        output = os.path.join(self.tmpdir, "history.csv")
        self.exporter.export_history_csv(output)
        with open(output, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        # header + 2 data rows
        self.assertEqual(len(rows), 3)
        # 验证 header
        self.assertEqual(
            rows[0],
            ["time", "strategy", "source", "files_count", "size", "checksum"],
        )
        # 验证数据行
        self.assertEqual(rows[1][0], "2026-06-07T10:30:00")
        self.assertEqual(rows[1][2], "/home/user/docs")
        self.assertEqual(rows[1][3], "150")
        self.assertEqual(rows[1][5], "abc123def456")

    def test_export_history_csv_strategy_basename(self):
        """测试 CSV 中 strategy 列为 source 路径的 basename"""
        output = os.path.join(self.tmpdir, "history.csv")
        self.exporter.export_history_csv(output)
        with open(output, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(rows[0]["strategy"], "docs")
        self.assertEqual(rows[1]["strategy"], "photos")

    # ── 历史记录 JSON 导出 ───────────────────────────────────

    def test_export_history_json(self):
        """测试 JSON 导出备份历史"""
        output = os.path.join(self.tmpdir, "history.json")
        count = self.exporter.export_history_json(output)
        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(output))

    def test_export_history_json_content(self):
        """测试 JSON 文件内容正确"""
        output = os.path.join(self.tmpdir, "history.json")
        self.exporter.export_history_json(output)
        with open(output, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["source"], "/home/user/docs")
        self.assertEqual(data[1]["source"], "/home/user/photos")

    # ── 审计日志 CSV 导出 ────────────────────────────────────

    def test_export_audit_csv(self):
        """测试 CSV 导出审计日志"""
        output = os.path.join(self.tmpdir, "audit.csv")
        count = self.exporter.export_audit_csv(output)
        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(output))

    def test_export_audit_csv_content(self):
        """测试审计 CSV 文件格式正确性"""
        output = os.path.join(self.tmpdir, "audit.csv")
        self.exporter.export_audit_csv(output)
        with open(output, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        # header + 2 data rows
        self.assertEqual(len(rows), 3)
        # 验证 header
        self.assertEqual(
            rows[0],
            [
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
            ],
        )
        # 验证数据行
        self.assertEqual(rows[1][0], "uuid-001")
        self.assertEqual(rows[1][2], "backup_complete")
        self.assertEqual(rows[1][3], "success")

    # ── 审计日志 JSON 导出 ───────────────────────────────────

    def test_export_audit_json(self):
        """测试 JSON 导出审计日志"""
        output = os.path.join(self.tmpdir, "audit.json")
        count = self.exporter.export_audit_json(output)
        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(output))

    def test_export_audit_json_content(self):
        """测试审计 JSON 文件内容正确"""
        output = os.path.join(self.tmpdir, "audit.json")
        self.exporter.export_audit_json(output)
        with open(output, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["event"], "backup_complete")
        self.assertEqual(data[1]["event"], "backup_failed")

    # ── 综合导出 ─────────────────────────────────────────────

    def test_export_combined_json(self):
        """测试 JSON 综合导出"""
        output = os.path.join(self.tmpdir, "combined.json")
        count = self.exporter.export_combined(output, fmt="json")
        self.assertEqual(count, 4)  # 2 history + 2 audit
        self.assertTrue(os.path.exists(output))
        with open(output, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("export_time", data)
        self.assertIn("history", data)
        self.assertIn("audit", data)
        self.assertIn("stats", data)
        self.assertEqual(len(data["history"]), 2)
        self.assertEqual(len(data["audit"]), 2)
        self.assertEqual(data["stats"]["history_count"], 2)
        self.assertEqual(data["stats"]["audit_count"], 2)

    def test_export_combined_csv(self):
        """测试 CSV 综合导出（生成多个文件）"""
        output = os.path.join(self.tmpdir, "combined.csv")
        count = self.exporter.export_combined(output, fmt="csv")
        self.assertEqual(count, 4)  # 2 history + 2 audit
        # 应该生成 history CSV、audit CSV 和 stats JSON
        self.assertTrue(
            os.path.exists(os.path.join(self.tmpdir, "combined_history.csv"))
        )
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, "combined_audit.csv")))
        self.assertTrue(
            os.path.exists(os.path.join(self.tmpdir, "combined_stats.json"))
        )

    # ── 策略名称过滤 ─────────────────────────────────────────

    def test_strategy_name_filter(self):
        """测试按策略名称过滤历史记录"""
        output = os.path.join(self.tmpdir, "filtered.csv")
        count = self.exporter.export_history_csv(output, strategy_name="docs")
        self.assertEqual(count, 1)
        with open(output, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "/home/user/docs")

    def test_strategy_name_filter_no_match(self):
        """测试策略名称过滤无匹配"""
        output = os.path.join(self.tmpdir, "filtered.csv")
        count = self.exporter.export_history_csv(output, strategy_name="nonexistent")
        self.assertEqual(count, 0)

    def test_strategy_name_filter_json(self):
        """测试 JSON 格式策略名称过滤"""
        output = os.path.join(self.tmpdir, "filtered.json")
        count = self.exporter.export_history_json(output, strategy_name="photos")
        self.assertEqual(count, 1)
        with open(output, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["source"], "/home/user/photos")

    # ── 事件类型过滤 ─────────────────────────────────────────

    def test_event_filter(self):
        """测试按事件类型过滤审计日志"""
        output = os.path.join(self.tmpdir, "filtered.csv")
        count = self.exporter.export_audit_csv(output, event="backup_complete")
        self.assertEqual(count, 1)
        with open(output, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event"], "backup_complete")

    def test_event_filter_no_match(self):
        """测试事件类型过滤无匹配"""
        output = os.path.join(self.tmpdir, "filtered.csv")
        count = self.exporter.export_audit_csv(output, event="restore")
        self.assertEqual(count, 0)

    def test_event_filter_json(self):
        """测试 JSON 格式事件类型过滤"""
        output = os.path.join(self.tmpdir, "filtered.json")
        count = self.exporter.export_audit_json(output, event="backup_failed")
        self.assertEqual(count, 1)
        with open(output, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["event"], "backup_failed")

    # ── 空历史记录 ───────────────────────────────────────────

    def test_empty_history_csv(self):
        """测试空历史记录的 CSV 导出"""
        empty_data_file = os.path.join(self.tmpdir, "empty.json")
        with open(empty_data_file, "w", encoding="utf-8") as f:
            json.dump({}, f)
        exporter = MetadataExporter(data_file=empty_data_file)
        output = os.path.join(self.tmpdir, "empty.csv")
        count = exporter.export_history_csv(output)
        self.assertEqual(count, 0)
        with open(output, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        # 仅 header 行
        self.assertEqual(len(rows), 1)

    def test_empty_history_json(self):
        """测试空历史记录的 JSON 导出"""
        empty_data_file = os.path.join(self.tmpdir, "empty.json")
        with open(empty_data_file, "w", encoding="utf-8") as f:
            json.dump({}, f)
        exporter = MetadataExporter(data_file=empty_data_file)
        output = os.path.join(self.tmpdir, "empty.json")
        count = exporter.export_history_json(output)
        self.assertEqual(count, 0)
        with open(output, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data, [])

    def test_empty_audit_csv(self):
        """测试空审计日志的 CSV 导出"""
        exporter = MetadataExporter(data_file=self.data_file)
        exporter._load_audit_entries = lambda: []
        output = os.path.join(self.tmpdir, "empty_audit.csv")
        count = exporter.export_audit_csv(output)
        self.assertEqual(count, 0)
        with open(output, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        # 仅 header 行
        self.assertEqual(len(rows), 1)

    # ── get_history / get_audit_entries ───────────────────────

    def test_get_history_all(self):
        """测试获取全部历史记录"""
        history = self.exporter.get_history()
        self.assertEqual(len(history), 2)

    def test_get_history_filtered(self):
        """测试过滤获取历史记录"""
        history = self.exporter.get_history(strategy_name="docs")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["source"], "/home/user/docs")

    def test_get_audit_entries_all(self):
        """测试获取全部审计日志"""
        entries = self.exporter.get_audit_entries()
        self.assertEqual(len(entries), 2)

    def test_get_audit_entries_filtered(self):
        """测试过滤获取审计日志"""
        entries = self.exporter.get_audit_entries(event="backup_complete")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["event"], "backup_complete")

    # ── 创建输出目录 ─────────────────────────────────────────

    def test_export_creates_output_directory(self):
        """测试导出时自动创建输出目录"""
        output = os.path.join(self.tmpdir, "subdir", "nested", "history.csv")
        count = self.exporter.export_history_csv(output)
        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(output))

    # ── 不存在的数据文件 ─────────────────────────────────────

    def test_nonexistent_data_file(self):
        """测试数据文件不存在时的处理"""
        exporter = MetadataExporter(data_file="/nonexistent/path/data.json")
        history = exporter.get_history()
        self.assertEqual(history, [])

    # ── get_history 返回 dict 列表 ───────────────────────────

    def test_get_history_returns_list_of_dicts(self):
        """测试 get_history 返回 list[dict]"""
        history = self.exporter.get_history()
        self.assertIsInstance(history, list)
        for entry in history:
            self.assertIsInstance(entry, dict)

    def test_get_audit_entries_returns_list_of_dicts(self):
        """测试 get_audit_entries 返回 list[dict]"""
        entries = self.exporter.get_audit_entries()
        self.assertIsInstance(entries, list)
        for entry in entries:
            self.assertIsInstance(entry, dict)


if __name__ == "__main__":
    unittest.main()
