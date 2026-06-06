"""备份轮转/清理策略测试"""

import os
import time
import pytest
from pathlib import Path

from sbackup.rotation import BackupRotator, RotationPolicy, _is_backup_file


@pytest.fixture
def backup_dir(tmp_path):
    """创建临时备份目录并返回路径"""
    d = tmp_path / "backups"
    d.mkdir()
    return str(d)


def _create_backup(d: str, name: str, mtime_offset_days: int = 0) -> str:
    """在目录中创建一个假的备份文件，可设置修改时间偏移（天数）"""
    path = os.path.join(d, name)
    Path(path).touch()
    if mtime_offset_days != 0:
        old_time = time.time() - mtime_offset_days * 86400
        os.utime(path, (old_time, old_time))
    return path


# ============================================================
# _is_backup_file 测试
# ============================================================


class TestIsBackupFile:
    def test_zip(self):
        assert _is_backup_file("backup.zip") is True

    def test_tar(self):
        assert _is_backup_file("backup.tar") is True

    def test_tar_gz(self):
        assert _is_backup_file("backup.tar.gz") is True

    def test_tar_bz2(self):
        assert _is_backup_file("backup.tar.bz2") is True

    def test_tar_xz(self):
        assert _is_backup_file("backup.tar.xz") is True

    def test_tar_zst(self):
        assert _is_backup_file("backup.tar.zst") is True

    def test_7z(self):
        assert _is_backup_file("backup.7z") is True

    def test_unknown_extension(self):
        assert _is_backup_file("backup.txt") is False

    def test_no_extension(self):
        assert _is_backup_file("backupfile") is False

    def test_partial_name(self):
        assert _is_backup_file("my_archive_notazip") is False


# ============================================================
# scan_backups 测试
# ============================================================


class TestScanBackups:
    def test_scan_recognizes_known_suffixes(self, backup_dir):
        """扫描只识别已知后缀的文件"""
        _create_backup(backup_dir, "b1.zip", 0)
        _create_backup(backup_dir, "b2.tar", 0)
        _create_backup(backup_dir, "b3.tar.gz", 0)
        _create_backup(backup_dir, "b4.tar.bz2", 0)
        _create_backup(backup_dir, "b5.tar.xz", 0)
        _create_backup(backup_dir, "b6.tar.zst", 0)
        _create_backup(backup_dir, "b7.7z", 0)

        rotator = BackupRotator(backup_dir, RotationPolicy())
        backups = rotator.scan_backups()
        assert len(backups) == 7

    def test_scan_ignores_non_backup_files(self, backup_dir):
        """非备份文件不会被扫描到"""
        _create_backup(backup_dir, "backup.zip", 0)
        _create_backup(backup_dir, "readme.txt", 0)
        _create_backup(backup_dir, "data.csv", 0)
        _create_backup(backup_dir, "image.png", 0)

        rotator = BackupRotator(backup_dir, RotationPolicy())
        backups = rotator.scan_backups()
        assert len(backups) == 1
        assert backups[0]["name"] == "backup.zip"

    def test_scan_sorted_by_mtime_descending(self, backup_dir):
        """结果按修改时间降序排列"""
        _create_backup(backup_dir, "old.zip", 10)
        _create_backup(backup_dir, "mid.zip", 5)
        _create_backup(backup_dir, "new.zip", 0)

        rotator = BackupRotator(backup_dir, RotationPolicy())
        backups = rotator.scan_backups()
        names = [b["name"] for b in backups]
        assert names == ["new.zip", "mid.zip", "old.zip"]

    def test_scan_empty_dir(self, backup_dir):
        """空目录返回空列表"""
        rotator = BackupRotator(backup_dir, RotationPolicy())
        backups = rotator.scan_backups()
        assert backups == []

    def test_scan_nonexistent_dir(self):
        """不存在的目录返回空列表"""
        rotator = BackupRotator("/nonexistent/path", RotationPolicy())
        backups = rotator.scan_backups()
        assert backups == []

    def test_scan_skips_subdirectories(self, backup_dir):
        """不扫描子目录"""
        _create_backup(backup_dir, "backup.zip", 0)
        sub = os.path.join(backup_dir, "subdir")
        os.makedirs(sub)
        _create_backup(sub, "nested.zip", 0)

        rotator = BackupRotator(backup_dir, RotationPolicy())
        backups = rotator.scan_backups()
        assert len(backups) == 1
        assert backups[0]["name"] == "backup.zip"

    def test_scan_metadata_fields(self, backup_dir):
        """扫描结果包含正确的字段"""
        _create_backup(backup_dir, "test.zip", 0)

        rotator = BackupRotator(backup_dir, RotationPolicy())
        backups = rotator.scan_backups()
        assert len(backups) == 1
        b = backups[0]
        assert "path" in b
        assert "name" in b
        assert "size" in b
        assert "mtime" in b
        assert "mtime_iso" in b
        assert b["name"] == "test.zip"
        assert b["size"] == 0


# ============================================================
# keep_count 策略测试
# ============================================================


class TestKeepCount:
    def test_keep_count_basic(self, backup_dir):
        """保留最新的 N 个，删除其余"""
        _create_backup(backup_dir, "b1.zip", 10)
        _create_backup(backup_dir, "b2.zip", 8)
        _create_backup(backup_dir, "b3.zip", 5)
        _create_backup(backup_dir, "b4.zip", 2)
        _create_backup(backup_dir, "b5.zip", 0)

        policy = RotationPolicy(keep_count=2)
        rotator = BackupRotator(backup_dir, policy)
        keep, delete = rotator.plan()

        assert len(keep) == 2
        assert len(delete) == 3
        keep_names = {b["name"] for b in keep}
        assert "b5.zip" in keep_names
        assert "b4.zip" in keep_names

    def test_keep_count_zero(self, backup_dir):
        """keep_count=0 不限制"""
        _create_backup(backup_dir, "b1.zip", 0)
        _create_backup(backup_dir, "b2.zip", 0)

        policy = RotationPolicy(keep_count=0)
        rotator = BackupRotator(backup_dir, policy)
        keep, delete = rotator.plan()
        assert len(keep) == 2
        assert len(delete) == 0

    def test_keep_count_exceeds_total(self, backup_dir):
        """keep_count 大于总数时全部保留"""
        _create_backup(backup_dir, "b1.zip", 5)
        _create_backup(backup_dir, "b2.zip", 0)

        policy = RotationPolicy(keep_count=100)
        rotator = BackupRotator(backup_dir, policy)
        keep, delete = rotator.plan()
        assert len(keep) == 2
        assert len(delete) == 0

    def test_keep_count_one(self, backup_dir):
        """keep_count=1 只保留最新的一份"""
        _create_backup(backup_dir, "old.zip", 30)
        _create_backup(backup_dir, "new.zip", 0)

        policy = RotationPolicy(keep_count=1)
        rotator = BackupRotator(backup_dir, policy)
        keep, delete = rotator.plan()
        assert len(keep) == 1
        assert keep[0]["name"] == "new.zip"
        assert len(delete) == 1
        assert delete[0]["name"] == "old.zip"


# ============================================================
# keep_days 策略测试
# ============================================================


class TestKeepDays:
    def test_keep_days_basic(self, backup_dir):
        """保留 N 天内的文件"""
        _create_backup(backup_dir, "recent.zip", 1)
        _create_backup(backup_dir, "old.zip", 10)

        policy = RotationPolicy(keep_days=3)
        rotator = BackupRotator(backup_dir, policy)
        keep, delete = rotator.plan()

        assert len(keep) == 1
        assert keep[0]["name"] == "recent.zip"
        assert len(delete) == 1
        assert delete[0]["name"] == "old.zip"

    def test_keep_days_all_recent(self, backup_dir):
        """所有文件都在 N 天内则全部保留"""
        _create_backup(backup_dir, "b1.zip", 0)
        _create_backup(backup_dir, "b2.zip", 1)

        policy = RotationPolicy(keep_days=3)
        rotator = BackupRotator(backup_dir, policy)
        keep, delete = rotator.plan()
        assert len(keep) == 2
        assert len(delete) == 0

    def test_keep_days_all_old(self, backup_dir):
        """所有文件都超过 N 天则全部删除"""
        _create_backup(backup_dir, "b1.zip", 30)
        _create_backup(backup_dir, "b2.zip", 20)

        policy = RotationPolicy(keep_days=7)
        rotator = BackupRotator(backup_dir, policy)
        keep, delete = rotator.plan()
        assert len(keep) == 0
        assert len(delete) == 2

    def test_keep_days_boundary(self, backup_dir):
        """恰好在边界内的文件应该保留"""
        _create_backup(backup_dir, "exact.zip", 6)

        policy = RotationPolicy(keep_days=7)
        rotator = BackupRotator(backup_dir, policy)
        keep, delete = rotator.plan()
        assert len(keep) == 1
        assert len(delete) == 0


# ============================================================
# keep_daily 策略测试
# ============================================================


class TestKeepDaily:
    def test_keep_daily_basic(self, backup_dir):
        """保留最近 N 天每天一份"""
        _create_backup(backup_dir, "day1.zip", 5)
        _create_backup(backup_dir, "day2.zip", 4)
        _create_backup(backup_dir, "day3.zip", 3)
        _create_backup(backup_dir, "day4.zip", 2)
        _create_backup(backup_dir, "day5.zip", 1)

        policy = RotationPolicy(keep_daily=3)
        rotator = BackupRotator(backup_dir, policy)
        keep, delete = rotator.plan()

        assert len(keep) == 3
        assert len(delete) == 2

    def test_keep_daily_same_day_multiple(self, backup_dir):
        """同一天有多份备份时只保留最新的一个"""
        # 使用固定时间创建文件，确保同一天
        base_time = time.time() - 86400  # 昨天
        p1 = os.path.join(backup_dir, "morning.zip")
        p2 = os.path.join(backup_dir, "evening.zip")
        Path(p1).touch()
        Path(p2).touch()
        # morning 比 evening 早 3 小时
        os.utime(p1, (base_time, base_time))
        os.utime(p2, (base_time + 10800, base_time + 10800))

        # 3 天前的旧备份
        _create_backup(backup_dir, "old.zip", 5)

        policy = RotationPolicy(keep_daily=2)
        rotator = BackupRotator(backup_dir, policy)
        keep, delete = rotator.plan()

        # 应该保留昨天的 evening（最新）和 3 天前的 old
        assert len(keep) == 2
        keep_names = {b["name"] for b in keep}
        assert "evening.zip" in keep_names
        assert "old.zip" in keep_names
        # morning 不应该被保留（同天已被 evening 替代）
        assert "morning.zip" not in keep_names

    def test_keep_daily_one_day(self, backup_dir):
        """keep_daily=1 只保留今天的一份"""
        _create_backup(backup_dir, "today.zip", 0)
        _create_backup(backup_dir, "yesterday.zip", 1)
        _create_backup(backup_dir, "twodays.zip", 2)

        policy = RotationPolicy(keep_daily=1)
        rotator = BackupRotator(backup_dir, policy)
        keep, delete = rotator.plan()

        assert len(keep) == 1
        assert keep[0]["name"] == "today.zip"


# ============================================================
# 多策略交集测试
# ============================================================


class TestPolicyIntersection:
    def test_keep_count_and_keep_days_intersection(self, backup_dir):
        """keep_count 和 keep_days 的交集"""
        # Files sorted by mtime (newest first): b1(2d), b2(4d), b3(8d), b4(15d)
        _create_backup(backup_dir, "b1.zip", 2)
        _create_backup(backup_dir, "b2.zip", 4)
        _create_backup(backup_dir, "b3.zip", 8)
        _create_backup(backup_dir, "b4.zip", 15)

        # keep_count=2 keeps: b1, b2 (two newest)
        # keep_days=5 keeps: b1, b2 (within 5 days)
        # intersection = b1, b2
        # But b3 is only 8 days old, outside keep_days, even though it would be in keep_count=4
        # Let's use keep_count=4 to make the intersection more interesting:
        # keep_count=4 keeps: b1, b2, b3, b4 (all four)
        # keep_days=5 keeps: b1, b2 (within 5 days)
        # intersection = b1, b2
        policy = RotationPolicy(keep_count=4, keep_days=5)
        rotator = BackupRotator(backup_dir, policy)
        keep, delete = rotator.plan()

        keep_names = {b["name"] for b in keep}
        delete_names = {b["name"] for b in delete}
        # b1 and b2 satisfy both policies -> kept
        assert "b1.zip" in keep_names
        assert "b2.zip" in keep_names
        # b3 satisfies keep_count=4 but not keep_days=5 -> deleted
        assert "b3.zip" in delete_names
        # b4 satisfies neither -> deleted
        assert "b4.zip" in delete_names

    def test_all_three_policies(self, backup_dir):
        """三个策略的交集"""
        # 创建覆盖多天的备份
        _create_backup(backup_dir, "a.zip", 0)
        _create_backup(backup_dir, "b.zip", 1)
        _create_backup(backup_dir, "c.zip", 3)
        _create_backup(backup_dir, "d.zip", 7)
        _create_backup(backup_dir, "e.zip", 10)

        # keep_count=4: 保留 a,b,c,d
        # keep_days=5: 保留 a,b,c
        # keep_daily=2: 保留 a,c（或 a,b 取决于具体日期，但至少保留今天和昨天各一个）
        # 交集 = 至少保留 a（今天最新的）
        policy = RotationPolicy(keep_count=4, keep_days=5, keep_daily=2)
        rotator = BackupRotator(backup_dir, policy)
        keep, delete = rotator.plan()

        # a.zip 一定在交集内
        keep_names = {b["name"] for b in keep}
        assert "a.zip" in keep_names
        # e.zip 一定被删除
        delete_names = {b["name"] for b in delete}
        assert "e.zip" in delete_names


# ============================================================
# dry_run 测试
# ============================================================


class TestDryRun:
    def test_dry_run_no_deletion(self, backup_dir):
        """dry_run=True 时不实际删除文件"""
        p1 = _create_backup(backup_dir, "old.zip", 30)
        p2 = _create_backup(backup_dir, "new.zip", 0)

        policy = RotationPolicy(keep_count=1, dry_run=True)
        rotator = BackupRotator(backup_dir, policy)
        deleted_count, deleted_paths = rotator.execute()

        # 应该报告要删除但不实际删除
        assert deleted_count == 1
        assert len(deleted_paths) == 1
        assert os.path.exists(p1)  # 文件仍然存在
        assert os.path.exists(p2)

    def test_dry_run_false_actually_deletes(self, backup_dir):
        """dry_run=False 时实际删除文件"""
        _create_backup(backup_dir, "old.zip", 30)
        _create_backup(backup_dir, "new.zip", 0)

        policy = RotationPolicy(keep_count=1, dry_run=False)
        rotator = BackupRotator(backup_dir, policy)
        deleted_count, deleted_paths = rotator.execute()

        assert deleted_count == 1
        # old.zip 应该被删除了
        assert not os.path.exists(os.path.join(backup_dir, "old.zip"))
        assert os.path.exists(os.path.join(backup_dir, "new.zip"))


# ============================================================
# 空目录测试
# ============================================================


class TestEmptyDir:
    def test_empty_dir_plan(self, backup_dir):
        """空目录的 plan 返回空列表"""
        policy = RotationPolicy(keep_count=5)
        rotator = BackupRotator(backup_dir, policy)
        keep, delete = rotator.plan()
        assert keep == []
        assert delete == []

    def test_empty_dir_execute(self, backup_dir):
        """空目录的 execute 返回 (0, [])"""
        policy = RotationPolicy(keep_count=5)
        rotator = BackupRotator(backup_dir, policy)
        deleted_count, deleted_paths = rotator.execute()
        assert deleted_count == 0
        assert deleted_paths == []


# ============================================================
# 非备份文件不被删除测试
# ============================================================


class TestNonBackupFilesNotDeleted:
    def test_non_backup_files_preserved(self, backup_dir):
        """非备份文件在轮转后仍然存在"""
        _create_backup(backup_dir, "old.zip", 30)
        _create_backup(backup_dir, "new.zip", 0)

        # 创建一些非备份文件
        readme = os.path.join(backup_dir, "readme.txt")
        data = os.path.join(backup_dir, "data.csv")
        sub = os.path.join(backup_dir, "subdir.zip")  # 看起来像备份但不是后缀

        Path(readme).write_text("hello")
        Path(data).write_text("data")
        Path(sub).mkdir()  # 这是个目录，不是文件

        policy = RotationPolicy(keep_count=1)
        rotator = BackupRotator(backup_dir, policy)
        deleted_count, _ = rotator.execute()

        assert deleted_count == 1  # 只删除 old.zip
        assert os.path.exists(readme)
        assert os.path.exists(data)
        assert os.path.isdir(sub)


# ============================================================
# execute 功能测试
# ============================================================


class TestExecute:
    def test_execute_deletes_correct_files(self, backup_dir):
        """execute 正确删除文件并返回路径"""
        p1 = _create_backup(backup_dir, "a.zip", 10)
        p2 = _create_backup(backup_dir, "b.zip", 5)
        p3 = _create_backup(backup_dir, "c.zip", 0)

        policy = RotationPolicy(keep_count=1)
        rotator = BackupRotator(backup_dir, policy)
        deleted_count, deleted_paths = rotator.execute()

        assert deleted_count == 2
        assert len(deleted_paths) == 2
        assert os.path.exists(p3)  # 最新的保留
        assert not os.path.exists(p1)
        assert not os.path.exists(p2)

    def test_execute_no_deletion_when_all_kept(self, backup_dir):
        """全部保留时不删除任何文件"""
        _create_backup(backup_dir, "b1.zip", 0)
        _create_backup(backup_dir, "b2.zip", 0)

        policy = RotationPolicy(keep_count=10)
        rotator = BackupRotator(backup_dir, policy)
        deleted_count, deleted_paths = rotator.execute()
        assert deleted_count == 0
        assert deleted_paths == []


# ============================================================
# RotationPolicy 测试
# ============================================================


class TestRotationPolicy:
    def test_has_any_rule_none(self):
        policy = RotationPolicy()
        assert policy.has_any_rule() is False

    def test_has_any_rule_count(self):
        policy = RotationPolicy(keep_count=5)
        assert policy.has_any_rule() is True

    def test_has_any_rule_days(self):
        policy = RotationPolicy(keep_days=7)
        assert policy.has_any_rule() is True

    def test_has_any_rule_daily(self):
        policy = RotationPolicy(keep_daily=3)
        assert policy.has_any_rule() is True

    def test_defaults(self):
        policy = RotationPolicy()
        assert policy.keep_count == 0
        assert policy.keep_days == 0
        assert policy.keep_daily == 0
        assert policy.dry_run is False
