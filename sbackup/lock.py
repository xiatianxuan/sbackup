"""备份锁模块：防止并发冲突

使用原子文件操作（tempfile + os.rename）实现跨平台进程锁，
确保同一时间只有一个 sbackup 实例在执行备份。
"""

import os
import sys
import tempfile
import atexit
import logging

logger = logging.getLogger(__name__)


class BackupLockError(Exception):
    """备份锁异常"""


class BackupLock:
    """跨平台备份进程锁

    基于 tempfile.mkstemp() + os.rename() 的原子性实现。

    Usage::

        lock = BackupLock(lock_dir)
        if lock.acquire():
            try:
                # do backup
            finally:
                lock.release()
        else:
            print("Another backup is running")
    """

    def __init__(self, lock_dir: str):
        self._lock_path = os.path.join(lock_dir, ".backup.lock")
        self._staging_path: str | None = None
        self._locked = False

    def acquire(self) -> bool:
        """尝试获取锁，成功返回 True"""
        if self._locked:
            return True

        # 清理过期锁
        self._clean_stale_lock()

        try:
            # 创建临时 staging 文件
            fd, self._staging_path = tempfile.mkstemp(
                dir=os.path.dirname(self._lock_path) or ".",
                prefix=".backup.lock.",
            )
            with os.fdopen(fd, "w") as f:
                f.write(str(os.getpid()))
                f.flush()
                os.fsync(f.fileno())

            # 原子 rename（Windows 上目标存在时失败）
            os.rename(self._staging_path, self._lock_path)

            self._locked = True
            atexit.register(self.release)
            return True

        except OSError:
            self._cleanup_staging()
            return False

    def release(self) -> None:
        """释放锁"""
        if not self._locked:
            return
        try:
            if os.path.exists(self._lock_path):
                os.unlink(self._lock_path)
        except OSError as e:
            logger.debug("Failed to remove lock file: %s", e)
        self._locked = False
        # 注销 atexit handler（Python 3.12+ 支持 unregister）
        try:
            atexit.unregister(self.release)
        except Exception:
            pass

    def _clean_stale_lock(self) -> None:
        """检查并清理过期锁文件"""
        try:
            if not os.path.exists(self._lock_path):
                return
            with open(self._lock_path) as f:
                content = f.read().strip()
            pid = int(content)
            if not _is_pid_alive(pid):
                os.unlink(self._lock_path)
                logger.info("Removed stale lock from dead PID %d", pid)
        except (OSError, ValueError):
            try:
                os.unlink(self._lock_path)
            except OSError:
                pass

    def _cleanup_staging(self) -> None:
        if self._staging_path and os.path.exists(self._staging_path):
            try:
                os.unlink(self._staging_path)
            except OSError:
                pass
        self._staging_path = None


def _is_pid_alive(pid: int) -> bool:
    """跨平台检查 PID 是否存活"""
    if sys.platform == "win32":
        try:
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(0x0400, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
        except Exception:
            pass
        return False
    # Unix: signal 0 仅检查进程是否存在
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
