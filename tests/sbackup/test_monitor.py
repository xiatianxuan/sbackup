"""
单元测试 for sbackup.monitor 模块
"""

import tempfile
import threading
import time as _time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from sbackup.monitor import FileSystemMonitor, _BackupEventHandler


class TestBackupEventHandler(unittest.TestCase):
    """测试 _BackupEventHandler 内部类"""

    def test_on_any_event_ignores_directories(self):
        """测试目录事件被忽略"""
        callback = MagicMock()
        handler = _BackupEventHandler(callback)

        mock_event = MagicMock()
        mock_event.is_directory = True
        mock_event.src_path = "/some/dir"

        handler.on_any_event(mock_event)
        callback.assert_not_called()

    def test_on_any_event_triggers_for_files(self):
        """测试文件事件触发回调"""
        callback = MagicMock()
        handler = _BackupEventHandler(callback)

        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = "/some/file.txt"

        handler.on_any_event(mock_event)
        callback.assert_called_once_with("/some/file.txt")


class TestFileSystemMonitor(unittest.TestCase):
    """测试 FileSystemMonitor 类"""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.source = Path(self.tmpdir.name) / "src"
        self.source.mkdir()
        self.source_dirs = {str(self.source): "/backup"}

    def test_init_stores_dirs_and_debounce(self):
        """测试初始化存储源目录和防抖参数"""
        monitor = FileSystemMonitor(self.source_dirs, debounce_seconds=10)
        assert monitor._source_dirs == self.source_dirs
        assert monitor._debounce == 10
        assert monitor._observer is None
        assert monitor._running is False
        assert monitor._backup_callback is None

    def test_set_backup_callback(self):
        """测试设置备份回调"""
        monitor = FileSystemMonitor(self.source_dirs)

        def noop():
            pass

        monitor.set_backup_callback(noop)
        assert monitor._backup_callback is noop

    def test_start_stop_lifecycle(self):
        """测试启动/停止生命周期"""
        monitor = FileSystemMonitor(self.source_dirs, debounce_seconds=1)
        try:
            monitor.start()
            # 等待 observer 线程启动
            _time.sleep(0.2)
            assert monitor.is_running()
        finally:
            monitor.stop()
        assert not monitor.is_running()

    def test_double_start_noop(self):
        """测试重复启动不创建多个 observer"""
        monitor = FileSystemMonitor(self.source_dirs, debounce_seconds=1)
        try:
            monitor.start()
            _time.sleep(0.2)
            first_observer = monitor._observer
            monitor.start()
            assert monitor._observer is first_observer
        finally:
            monitor.stop()

    def test_on_file_change_marks_dirty(self):
        """测试文件变化标记源目录为 dirty"""
        monitor = FileSystemMonitor(self.source_dirs, debounce_seconds=60)
        test_file = self.source / "test.txt"
        test_file.write_text("hello")

        monitor._on_file_change(str(test_file))
        dirty = monitor.get_dirty_sources()
        assert str(self.source) in dirty

    def test_on_file_change_outside_source_ignored(self):
        """测试外部文件变化不标记 dirty"""
        monitor = FileSystemMonitor(self.source_dirs, debounce_seconds=60)
        outside_file = Path(self.tmpdir.name) / "outside.txt"
        outside_file.write_text("hello")

        monitor._on_file_change(str(outside_file))
        dirty = monitor.get_dirty_sources()
        assert len(dirty) == 0

    def test_on_file_change_multiple_dirs(self):
        """测试多个源目录分别标记"""
        src2 = Path(self.tmpdir.name) / "src2"
        src2.mkdir()
        dirs = {str(self.source): "/backup1", str(src2): "/backup2"}

        monitor = FileSystemMonitor(dirs, debounce_seconds=60)
        (self.source / "a.txt").write_text("a")
        (src2 / "b.txt").write_text("b")

        monitor._on_file_change(str(self.source / "a.txt"))
        monitor._on_file_change(str(src2 / "b.txt"))

        dirty = monitor.get_dirty_sources()
        assert str(self.source) in dirty
        assert str(src2) in dirty
        assert len(dirty) == 2

    def test_debounce_reset_on_multiple_changes(self):
        """测试多次变化时防抖计时器重置"""
        monitor = FileSystemMonitor(self.source_dirs, debounce_seconds=10)
        cb = MagicMock()
        monitor.set_backup_callback(cb)

        f1 = self.source / "a.txt"
        f2 = self.source / "b.txt"
        f1.write_text("a")
        f2.write_text("b")

        # 第一次变化启动计时
        monitor._on_file_change(str(f1))
        timer1 = monitor._debounce_timer
        assert timer1 is not None

        # 第二次变化应取消旧计时并启动新计时
        monitor._on_file_change(str(f2))
        timer2 = monitor._debounce_timer
        assert timer2 is not None
        assert timer2 is not timer1  # 不是同一个 timer 对象

    def test_trigger_backup_calls_callback(self):
        """测试防抖超时后触发回调"""
        monitor = FileSystemMonitor(self.source_dirs, debounce_seconds=0.1)
        cb = MagicMock()
        monitor.set_backup_callback(cb)

        (self.source / "test.txt").write_text("data")
        monitor._on_file_change(str(self.source / "test.txt"))

        # 等待防抖触发
        _time.sleep(0.3)
        cb.assert_called_once()

    def test_trigger_backup_no_dirty_noop(self):
        """测试没有 dirty 目录时不触发回调"""
        monitor = FileSystemMonitor(self.source_dirs, debounce_seconds=0.1)
        cb = MagicMock()
        monitor.set_backup_callback(cb)

        monitor._trigger_backup()
        cb.assert_not_called()

    def test_trigger_backup_clears_dirty(self):
        """测试触发备份后清除 dirty 标记"""
        monitor = FileSystemMonitor(self.source_dirs, debounce_seconds=0.1)
        cb = MagicMock()
        monitor.set_backup_callback(cb)

        (self.source / "test.txt").write_text("data")
        monitor._on_file_change(str(self.source / "test.txt"))
        _time.sleep(0.3)

        assert len(monitor.get_dirty_sources()) == 0

    def test_callback_exception_caught(self):
        """测试回调异常不影响监控器"""
        monitor = FileSystemMonitor(self.source_dirs, debounce_seconds=0.1)

        def failing_cb():
            raise RuntimeError("test error")

        monitor.set_backup_callback(failing_cb)

        (self.source / "test.txt").write_text("data")
        monitor._on_file_change(str(self.source / "test.txt"))

        # 不应抛出异常
        _time.sleep(0.3)
        assert monitor._dirty == set()

    def test_start_from_missing_source_dir(self):
        """测试源目录不存在时优雅处理"""
        missing = str(Path(self.tmpdir.name) / "nonexistent")
        monitor = FileSystemMonitor({missing: "/backup"}, debounce_seconds=1)

        monitor.start()
        assert not monitor.is_running()
        assert monitor._observer is None

    def test_stop_cancels_pending_timer(self):
        """测试 stop 取消待处理的防抖计时器"""
        monitor = FileSystemMonitor(self.source_dirs, debounce_seconds=30)
        cb = MagicMock()
        monitor.set_backup_callback(cb)

        (self.source / "test.txt").write_text("data")
        monitor._on_file_change(str(self.source / "test.txt"))
        assert monitor._debounce_timer is not None

        monitor.stop()
        assert monitor._debounce_timer is None
        cb.assert_not_called()

    def test_concurrent_file_changes_thread_safety(self):
        """测试多线程并发文件变化的线程安全性"""
        monitor = FileSystemMonitor(self.source_dirs, debounce_seconds=0.1)
        cb = MagicMock()
        monitor.set_backup_callback(cb)

        def write_file(i):
            f = self.source / f"file_{i}.txt"
            f.write_text(str(i))
            monitor._on_file_change(str(f))

        threads = []
        for i in range(10):
            t = threading.Thread(target=write_file, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        _time.sleep(0.3)
        # 回调应至少被调用一次
        assert cb.call_count >= 1
