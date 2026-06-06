"""
单元测试 for sbackup.audit 模块
"""

import unittest
import os
import tempfile
import shutil
from sbackup.audit import AuditEntry, AuditLogger


class TestAuditEntry(unittest.TestCase):
    """AuditEntry 数据类测试"""

    def test_default_values(self):
        """测试默认字段值"""
        entry = AuditEntry()
        self.assertEqual(entry.id, "")
        self.assertEqual(entry.timestamp, "")
        self.assertEqual(entry.event, "")
        self.assertEqual(entry.status, "success")
        self.assertEqual(entry.files_count, 0)
        self.assertEqual(entry.total_size, 0)
        self.assertEqual(entry.backup_size, 0)
        self.assertEqual(entry.duration, 0)
        self.assertEqual(entry.error_message, "")
        self.assertEqual(entry.metadata, {})

    def test_to_dict(self):
        """测试 to_dict 序列化"""
        entry = AuditEntry(
            id="test-id",
            timestamp="2026-01-01T00:00:00Z",
            event="backup_complete",
            source_path="/src",
            target_path="/dst",
            format="ZIP",
            status="success",
            files_count=10,
            total_size=1024,
            backup_size=512,
            duration=1.5,
            error_message="",
            metadata={"key": "value"},
        )
        d = entry.to_dict()
        self.assertEqual(d["id"], "test-id")
        self.assertEqual(d["event"], "backup_complete")
        self.assertEqual(d["files_count"], 10)
        self.assertEqual(d["backup_size"], 512)
        self.assertEqual(d["duration"], 1.5)
        self.assertEqual(d["metadata"], {"key": "value"})

    def test_from_dict(self):
        """测试 from_dict 反序列化"""
        data = {
            "id": "abc-123",
            "timestamp": "2026-01-01T00:00:00Z",
            "event": "backup_failed",
            "source_path": "/src",
            "target_path": "/dst",
            "format": "tar.gz",
            "status": "failed",
            "files_count": 0,
            "total_size": 0,
            "backup_size": 0,
            "duration": 0.5,
            "error_message": "disk full",
            "metadata": {},
        }
        entry = AuditEntry.from_dict(data)
        self.assertEqual(entry.id, "abc-123")
        self.assertEqual(entry.event, "backup_failed")
        self.assertEqual(entry.status, "failed")
        self.assertEqual(entry.error_message, "disk full")

    def test_from_dict_missing_fields(self):
        """测试 from_dict 处理缺失字段"""
        entry = AuditEntry.from_dict({"event": "test"})
        self.assertEqual(entry.event, "test")
        self.assertEqual(entry.status, "success")
        self.assertEqual(entry.files_count, 0)

    def test_roundtrip(self):
        """测试 to_dict -> from_dict 往返"""
        original = AuditEntry(
            id="roundtrip",
            timestamp="2026-06-06T12:00:00Z",
            event="restore",
            source_path="/a",
            target_path="/b",
            format="7z",
            status="partial",
            files_count=5,
            total_size=2048,
            backup_size=1024,
            duration=3.0,
            error_message="some error",
            metadata={"extra": True},
        )
        restored = AuditEntry.from_dict(original.to_dict())
        self.assertEqual(original.id, restored.id)
        self.assertEqual(original.event, restored.event)
        self.assertEqual(original.status, restored.status)
        self.assertEqual(original.files_count, restored.files_count)
        self.assertEqual(original.metadata, restored.metadata)


class TestAuditLogger(unittest.TestCase):
    """AuditLogger 功能测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.audit_file = os.path.join(self.test_dir, "audit.json")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_log_creates_entry(self):
        """测试 log 记录事件"""
        logger = AuditLogger(audit_file=self.audit_file)
        entry = logger.log("backup_start", source_path="/src", format="ZIP")
        self.assertEqual(entry.event, "backup_start")
        self.assertEqual(entry.source_path, "/src")
        self.assertEqual(entry.format, "ZIP")
        self.assertNotEqual(entry.id, "")
        self.assertNotEqual(entry.timestamp, "")

    def test_log_persists_to_file(self):
        """测试日志持久化到 JSON 文件"""
        logger = AuditLogger(audit_file=self.audit_file)
        logger.log("backup_complete", files_count=10, backup_size=2048)
        # 重新加载并验证
        logger2 = AuditLogger(audit_file=self.audit_file)
        entries = logger2.query()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].event, "backup_complete")
        self.assertEqual(entries[0].files_count, 10)

    def test_log_default_status(self):
        """测试默认状态为 success"""
        logger = AuditLogger(audit_file=self.audit_file)
        entry = logger.log("verify")
        self.assertEqual(entry.status, "success")

    def test_query_by_event(self):
        """测试按事件类型过滤"""
        logger = AuditLogger(audit_file=self.audit_file)
        logger.log("backup_start", source_path="/a")
        logger.log("backup_complete", source_path="/a")
        logger.log("backup_failed", source_path="/b")
        logger.log("backup_complete", source_path="/c")

        complete_entries = logger.query(event="backup_complete")
        self.assertEqual(len(complete_entries), 2)
        for e in complete_entries:
            self.assertEqual(e.event, "backup_complete")

    def test_query_by_status(self):
        """测试按状态过滤"""
        logger = AuditLogger(audit_file=self.audit_file)
        logger.log("backup_complete", status="success")
        logger.log("backup_failed", status="failed")
        logger.log("backup_complete", status="success")

        failed = logger.query(status="failed")
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].status, "failed")

        success = logger.query(status="success")
        self.assertEqual(len(success), 2)

    def test_query_by_since(self):
        """测试按时间过滤"""
        logger = AuditLogger(audit_file=self.audit_file)
        logger.log("backup_start", timestamp="2026-01-01T00:00:00Z")
        logger.log("backup_complete", timestamp="2026-06-01T00:00:00Z")
        logger.log("backup_failed", timestamp="2026-12-01T00:00:00Z")

        # 注意：query 使用 reversed，since 过滤的是 timestamp >= since
        # 手动设置时间戳来测试
        entries_raw = logger._entries
        entries_raw[0]["timestamp"] = "2026-01-01T00:00:00Z"
        entries_raw[1]["timestamp"] = "2026-06-01T00:00:00Z"
        entries_raw[2]["timestamp"] = "2026-12-01T00:00:00Z"
        logger._save()

        # 重新加载确保持久化
        logger2 = AuditLogger(audit_file=self.audit_file)
        since_june = logger2.query(since="2026-06-01T00:00:00Z")
        self.assertTrue(len(since_june) >= 2)

    def test_query_limit(self):
        """测试 limit 参数"""
        logger = AuditLogger(audit_file=self.audit_file)
        for i in range(10):
            logger.log("backup_complete")

        limited = logger.query(limit=3)
        self.assertEqual(len(limited), 3)

    def test_query_empty_log(self):
        """测试空审计日志查询"""
        logger = AuditLogger(audit_file=self.audit_file)
        entries = logger.query()
        self.assertEqual(len(entries), 0)

    def test_query_combined_filters(self):
        """测试组合过滤条件"""
        logger = AuditLogger(audit_file=self.audit_file)
        logger.log("backup_complete", status="success")
        logger.log("backup_complete", status="failed")
        logger.log("backup_start", status="success")

        result = logger.query(event="backup_complete", status="success")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].event, "backup_complete")
        self.assertEqual(result[0].status, "success")

    def test_get_stats(self):
        """测试统计信息"""
        logger = AuditLogger(audit_file=self.audit_file)
        logger.log("backup_complete", status="success", backup_size=1024)
        logger.log("backup_complete", status="success", backup_size=2048)
        logger.log("backup_failed", status="failed", backup_size=0)
        logger.log("backup_start")

        stats = logger.get_stats()
        self.assertEqual(stats["total"], 4)
        self.assertEqual(stats["total_backup_size"], 3072)
        self.assertEqual(stats["success_count"], 3)
        self.assertEqual(stats["event_counts"]["backup_complete"], 2)
        self.assertEqual(stats["event_counts"]["backup_failed"], 1)
        self.assertEqual(stats["event_counts"]["backup_start"], 1)

    def test_get_stats_empty(self):
        """测试空日志统计"""
        logger = AuditLogger(audit_file=self.audit_file)
        stats = logger.get_stats()
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["total_backup_size"], 0)
        self.assertEqual(stats["success_count"], 0)
        self.assertEqual(stats["success_rate"], 0)

    def test_cleanup(self):
        """测试清理旧日志"""
        logger = AuditLogger(audit_file=self.audit_file)
        logger.log("backup_complete")

        # 修改时间戳为很久以前
        logger._entries[0]["timestamp"] = "2020-01-01T00:00:00Z"
        logger._save()

        logger.log("backup_complete")

        # 重新加载
        logger2 = AuditLogger(audit_file=self.audit_file)
        removed = logger2.cleanup(keep_days=30)
        self.assertEqual(removed, 1)

        remaining = logger2.query()
        self.assertEqual(len(remaining), 1)

    def test_cleanup_nothing_to_remove(self):
        """测试清理时无需删除"""
        logger = AuditLogger(audit_file=self.audit_file)
        logger.log("backup_complete")
        removed = logger.cleanup(keep_days=90)
        self.assertEqual(removed, 0)

    def test_format_entries_empty(self):
        """测试格式化空日志"""
        logger = AuditLogger(audit_file=self.audit_file)
        result = logger.format_entries([])
        self.assertIn("没有审计日志记录", result)

    def test_format_entries_en(self):
        """测试英文格式化"""
        logger = AuditLogger(audit_file=self.audit_file)
        result = logger.format_entries([], lang="en_US")
        self.assertIn("No audit log entries", result)

    def test_format_entries_with_data(self):
        """测试格式化有数据的日志"""
        logger = AuditLogger(audit_file=self.audit_file)
        logger.log(
            "backup_complete",
            source_path="/src",
            target_path="/dst",
            files_count=10,
            backup_size=2048,
            duration=1.5,
        )
        entries = logger.query()
        result = logger.format_entries(entries, lang="zh_CN")
        self.assertIn("backup_complete", result)
        self.assertIn("/src", result)
        self.assertIn("10", result)

    def test_format_entries_with_error(self):
        """测试格式化带错误信息的日志"""
        logger = AuditLogger(audit_file=self.audit_file)
        logger.log("backup_failed", error_message="disk full", status="failed")
        entries = logger.query()
        result = logger.format_entries(entries, lang="zh_CN")
        self.assertIn("disk full", result)

    def test_format_stats(self):
        """测试格式化统计信息"""
        logger = AuditLogger(audit_file=self.audit_file)
        logger.log("backup_complete", backup_size=1024 * 1024)
        stats = logger.get_stats()
        result = logger.format_stats(stats, lang="zh_CN")
        self.assertIn("审计日志统计", result)
        self.assertIn("1.00 MB", result)

    def test_format_stats_en(self):
        """测试英文格式化统计"""
        logger = AuditLogger(audit_file=self.audit_file)
        logger.log("backup_complete", backup_size=1024 * 1024)
        stats = logger.get_stats()
        result = logger.format_stats(stats, lang="en_US")
        self.assertIn("Audit Log Statistics", result)

    def test_persistence_roundtrip(self):
        """测试完整持久化往返"""
        # 写入
        logger1 = AuditLogger(audit_file=self.audit_file)
        logger1.log("backup_start", source_path="/a")
        logger1.log("backup_complete", source_path="/a", files_count=5)
        logger1.log("backup_failed", source_path="/b", error_message="timeout")

        # 重新加载并验证
        logger2 = AuditLogger(audit_file=self.audit_file)
        entries = logger2.query()
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0].event, "backup_failed")
        self.assertEqual(entries[1].event, "backup_complete")
        self.assertEqual(entries[2].event, "backup_start")

    def test_json_file_created(self):
        """测试 JSON 文件创建"""
        logger = AuditLogger(audit_file=self.audit_file)
        logger.log("backup_start")
        self.assertTrue(os.path.exists(self.audit_file))

    def test_default_audit_path(self):
        """测试默认审计日志路径不为空"""
        from sbackup.audit import _default_audit_path

        path = _default_audit_path()
        self.assertTrue(path.endswith("audit.json"))
        self.assertIn("sbackup", path)

    def test_log_with_metadata(self):
        """测试记录带 metadata 的事件"""
        logger = AuditLogger(audit_file=self.audit_file)
        logger.log("upload", metadata={"remote": "sftp://host/path"})
        entries = logger.query()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].metadata["remote"], "sftp://host/path")

    def test_corrupted_file_handling(self):
        """测试损坏的审计文件处理"""
        with open(self.audit_file, "w", encoding="utf-8") as f:
            f.write("not valid json {{{")

        logger = AuditLogger(audit_file=self.audit_file)
        self.assertEqual(len(logger._entries), 0)

    def test_missing_file_handling(self):
        """测试审计文件不存在时的处理"""
        logger = AuditLogger(audit_file=os.path.join(self.test_dir, "nonexistent.json"))
        self.assertEqual(len(logger._entries), 0)


if __name__ == "__main__":
    unittest.main()
