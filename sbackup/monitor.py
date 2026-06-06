"""
文件系统监控模块：基于 watchdog 的实时备份触发
"""

import logging
import os
import threading
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from sbackup.i18n import t

logger = logging.getLogger(__name__)


class _BackupEventHandler(FileSystemEventHandler):
    """watchdog 事件处理器：目录变化时触发回调"""

    def __init__(self, on_change_callback):
        super().__init__()
        self._on_change = on_change_callback

    def on_any_event(self, event):
        if event.is_directory:
            return
        self._on_change(event.src_path)


class FileSystemMonitor:
    """文件系统监控器：监听策略源目录变化，防抖后触发备份

    使用方式::

        monitor = FileSystemMonitor(source_dirs, debounce_seconds=30)
        monitor.set_backup_callback(lambda: manager.execute_backups(...))
        monitor.start()
        # ... 等待 ...
        monitor.stop()
    """

    def __init__(
        self,
        source_dirs: dict[str, str],
        debounce_seconds: float = 30,
    ):
        """
        :param source_dirs: {源目录绝对路径: 目标目录}（仅用于确定监控范围）
        :param debounce_seconds: 防抖秒数，文件最后一次变化后等待此时间再触发备份
        """
        self._source_dirs = source_dirs
        self._debounce = debounce_seconds
        self._observer: Observer | None = None
        self._dirty: set[str] = set()
        self._lock = threading.Lock()
        self._debounce_timer: threading.Timer | None = None
        self._backup_callback = None
        self._running = False

    def set_backup_callback(self, callback) -> None:
        """设置备份回调函数（变化触发时调用）"""
        self._backup_callback = callback

    def _on_file_change(self, path_str: str) -> None:
        """文件变化时标记对应源目录为 dirty 并重置防抖计时器"""
        path = Path(path_str)
        matched_source = None
        for source in self._source_dirs:
            try:
                path.relative_to(Path(source))
                matched_source = source
                break
            except ValueError:
                continue

        if matched_source is None:
            return

        with self._lock:
            self._dirty.add(matched_source)
            count = len(self._dirty)

        logger.debug(t("log.monitor.change", path=path_str, dirty_count=count))
        self._reset_debounce()

    def _reset_debounce(self) -> None:
        """重置防抖计时器：取消旧计时，启动新计时"""
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(self._debounce, self._trigger_backup)
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _trigger_backup(self) -> None:
        """防抖超时后触发备份回调"""
        with self._lock:
            if not self._dirty:
                return
            dirty_count = len(self._dirty)
            self._dirty.clear()

        logger.debug(t("log.monitor.trigger", dirty_count=dirty_count))
        if self._backup_callback:
            try:
                self._backup_callback()
            except Exception:
                logger.exception("FileSystemMonitor 回调执行异常")

    def get_dirty_sources(self) -> list[str]:
        """获取当前标记为 dirty 的源目录列表（用于调试）"""
        with self._lock:
            return list(self._dirty)

    def start(self) -> None:
        """启动文件系统监控"""
        if self._observer is not None:
            return

        self._observer = Observer()
        scheduled = 0
        for source in self._source_dirs:
            if not os.path.isdir(source):
                logger.warning(t("log.monitor.source_missing", path=source))
                continue
            handler = _BackupEventHandler(self._on_file_change)
            self._observer.schedule(handler, source, recursive=True)
            scheduled += 1
            logger.debug(t("log.monitor.watching", path=source))

        if scheduled == 0:
            logger.warning(t("log.monitor.no_sources"))
            self._observer = None
            return

        self._observer.start()
        self._running = True

    def stop(self) -> None:
        """停止文件系统监控"""
        self._running = False
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None

        if self._observer is not None:
            self._observer.stop()
            try:
                self._observer.join(timeout=5)
            except RuntimeError:
                pass
            self._observer = None

    def is_running(self) -> bool:
        """检查监控是否在运行"""
        return (
            self._running and self._observer is not None and self._observer.is_alive()
        )
