"""单元测试 for sbackup.lock 模块"""

import os
import unittest
import tempfile
import shutil

from sbackup.lock import BackupLock


class TestBackupLock(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_acquire_and_release(self):
        """测试获取和释放锁"""
        lock = BackupLock(self.test_dir)
        self.assertTrue(lock.acquire())
        self.assertTrue(lock._locked)
        lock.release()
        self.assertFalse(lock._locked)
        self.assertFalse(os.path.exists(lock._lock_path))

    def test_acquire_exclusive(self):
        """测试锁的排他性：第二个获取应该失败"""
        lock1 = BackupLock(self.test_dir)
        lock2 = BackupLock(self.test_dir)

        self.assertTrue(lock1.acquire())
        self.assertFalse(lock2.acquire())

        lock1.release()

        # 释放后第二个可以获取
        self.assertTrue(lock2.acquire())
        lock2.release()

    def test_double_acquire(self):
        """测试重复获取：同一个实例多次获取应返回 True"""
        lock = BackupLock(self.test_dir)
        self.assertTrue(lock.acquire())
        self.assertTrue(lock.acquire())  # 已锁定，直接返回 True
        lock.release()

    def test_clean_stale_lock(self):
        """测试清理过期锁（死进程留下的锁文件）"""
        lock = BackupLock(self.test_dir)
        lock_path = os.path.join(self.test_dir, ".backup.lock")

        # 模拟一个死进程的锁文件
        dead_pid = 999999999  # 不可能存在的 PID
        with open(lock_path, "w") as f:
            f.write(str(dead_pid))

        # 尝试获取，应该清理并成功
        self.assertTrue(lock.acquire())
        self.assertTrue(os.path.exists(lock_path))
        # 锁文件内容应该是当前进程的 PID
        with open(lock_path) as f:
            self.assertEqual(f.read().strip(), str(os.getpid()))
        lock.release()

    def test_clean_corrupted_lock(self):
        """测试清理损坏的锁文件"""
        lock = BackupLock(self.test_dir)
        lock_path = os.path.join(self.test_dir, ".backup.lock")

        # 写入无效内容
        with open(lock_path, "w") as f:
            f.write("not_a_pid")

        self.assertTrue(lock.acquire())
        lock.release()

    def test_release_no_lock(self):
        """测试未获取锁时释放不报错"""
        lock = BackupLock(self.test_dir)
        lock.release()  # 不应抛异常

    def test_context_manager_usage(self):
        """测试手动 try/finally 用法（测试 release 防护）"""
        lock = BackupLock(self.test_dir)
        self.assertTrue(lock.acquire())
        # 模拟异常情况下的 release
        lock.release()
        self.assertFalse(lock._locked)

    def test_lock_file_location(self):
        """测试锁文件路径正确"""
        lock = BackupLock(self.test_dir)
        expected = os.path.join(self.test_dir, ".backup.lock")
        self.assertEqual(lock._lock_path, expected)

    def test_successive_acquire_after_release(self):
        """测试释放后可以再次获取"""
        lock = BackupLock(self.test_dir)
        self.assertTrue(lock.acquire())
        lock.release()
        self.assertTrue(lock.acquire())
        lock.release()

    def test_stale_lock_with_alive_pid(self):
        """测试活进程的锁文件不会被清理"""
        lock = BackupLock(self.test_dir)

        # 先获取锁
        lock.acquire()

        # 创建另一个锁实例，锁文件被活进程持有
        lock2 = BackupLock(self.test_dir)
        self.assertFalse(lock2.acquire())

        lock.release()


class TestIsPidAlive(unittest.TestCase):
    """测试 _is_pid_alive 函数"""

    def test_own_pid_is_alive(self):
        """当前进程的 PID 应该存活"""
        from sbackup.lock import _is_pid_alive

        self.assertTrue(_is_pid_alive(os.getpid()))

    def test_nonexistent_pid_is_dead(self):
        """不存在的 PID 应该返回 False"""
        from sbackup.lock import _is_pid_alive

        # 使用一个极不可能存在的 PID
        self.assertFalse(_is_pid_alive(999999999))
