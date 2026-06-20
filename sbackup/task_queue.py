"""任务队列系统：管理本地备份任务队列，支持添加、执行、取消任务"""

import json
import os
import uuid
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

from sbackup.config import load_config
from sbackup.auto_save import BackupManager
from sbackup.i18n import t

logger = logging.getLogger(__name__)


@dataclass
class BackupTask:
    """备份任务数据类"""

    id: str  # UUID
    name: str  # 任务名称
    folder_path: str  # 备份目录
    zipfile_path: str | None  # 输出路径
    compression_format: str  # 格式
    config_overrides: dict[str, Any]  # 配置覆盖
    status: str = "pending"  # pending/running/completed/failed
    created_at: str = ""  # ISO 时间
    started_at: str = ""
    finished_at: str = ""
    error: str = ""
    result_path: str = ""  # 备份文件路径

    def to_dict(self) -> dict[str, Any]:
        """转为 JSON 兼容字典"""
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "BackupTask":
        """从字典创建 BackupTask"""
        return BackupTask(
            id=data.get("id", ""),
            name=data.get("name", ""),
            folder_path=data.get("folder_path", ""),
            zipfile_path=data.get("zipfile_path"),
            compression_format=data.get("compression_format", "ZIP"),
            config_overrides=data.get("config_overrides", {}),
            status=data.get("status", "pending"),
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at", ""),
            finished_at=data.get("finished_at", ""),
            error=data.get("error", ""),
            result_path=data.get("result_path", ""),
        )


class TaskQueue:
    """本地备份任务队列管理器"""

    def __init__(self, queue_file: str = ""):
        """
        初始化任务队列
        :param queue_file: 队列数据存储的 JSON 文件路径
        """
        if not queue_file:
            queue_file = os.path.join(
                os.path.dirname(load_config().data_file), "task_queue.json"
            )
        self.queue_file = queue_file
        self.tasks: list[BackupTask] = []
        self._load()

    def _load(self) -> None:
        """从 JSON 文件加载队列数据"""
        if not os.path.exists(self.queue_file):
            self.tasks = []
            return
        try:
            with open(self.queue_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.tasks = [BackupTask.from_dict(item) for item in data]
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load task queue: %s", e)
            self.tasks = []

    def _save(self) -> None:
        """将队列数据保存到 JSON 文件（原子写入）"""
        data_dir = os.path.dirname(self.queue_file)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)

        tmp_path = self.queue_file + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(
                    [task.to_dict() for task in self.tasks],
                    f,
                    ensure_ascii=False,
                    indent=4,
                )
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.queue_file)
        except OSError:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    def add_task(
        self,
        name: str,
        folder_path: str,
        zipfile_path: str | None = None,
        compression_format: str = "ZIP",
        config_overrides: dict[str, Any] | None = None,
    ) -> str:
        """
        添加一个新任务到队列
        :param name: 任务名称
        :param folder_path: 备份目录
        :param zipfile_path: 输出路径
        :param compression_format: 压缩格式
        :param config_overrides: 配置覆盖参数
        :return: 任务 ID
        """
        task_id = str(uuid.uuid4())
        task = BackupTask(
            id=task_id,
            name=name,
            folder_path=os.path.abspath(folder_path),
            zipfile_path=zipfile_path,
            compression_format=compression_format.upper(),
            config_overrides=config_overrides or {},
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.tasks.append(task)
        self._save()
        return task_id

    def list_tasks(self, status: str | None = None) -> list[BackupTask]:
        """
        列出任务
        :param status: 按状态过滤，None 返回所有任务
        :return: 任务列表
        """
        if status is None:
            return list(self.tasks)
        return [t for t in self.tasks if t.status == status]

    def get_task(self, task_id: str) -> BackupTask | None:
        """
        获取指定 ID 的任务
        :param task_id: 任务 ID
        :return: 任务对象，未找到返回 None
        """
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def cancel_task(self, task_id: str) -> bool:
        """
        取消一个 pending 状态的任务
        :param task_id: 任务 ID
        :return: 是否取消成功
        """
        task = self.get_task(task_id)
        if task is None:
            return False
        if task.status != "pending":
            return False
        task.status = "failed"
        task.error = t("task_queue.cancelled")
        task.finished_at = datetime.now(timezone.utc).isoformat()
        self._save()
        return True

    def run_next(self) -> BackupTask | None:
        """
        取下一个 pending 任务并执行
        :return: 执行的任务对象，无 pending 任务时返回 None
        """
        task = None
        for task_item in self.tasks:
            if task_item.status == "pending":
                task = task_item
                break

        if task is None:
            return None

        # 设为 running
        task.status = "running"
        task.started_at = datetime.now(timezone.utc).isoformat()
        self._save()

        try:
            config = load_config()
            # 应用配置覆盖
            for key, value in task.config_overrides.items():
                if hasattr(config, key):
                    setattr(config, key, value)

            manager = BackupManager(data_file=config.data_file)

            # 如果设置了输出路径，临时创建备份策略
            source_path = task.folder_path
            if task.zipfile_path:
                dest_dir = os.path.dirname(task.zipfile_path)
            else:
                # 使用默认目标路径（与源同级的 _backups 目录）
                dest_dir = os.path.join(
                    os.path.dirname(source_path),
                    "_backups",
                )

            os.makedirs(dest_dir, exist_ok=True)

            entry_fmt = task.compression_format
            success = manager.add_folder(
                source_path, dest_dir, compression_format=entry_fmt
            )
            if not success:
                # 可能已存在，继续执行
                pass

            manager.execute_backups()

            # 查找生成的备份文件
            result_path = ""
            if task.zipfile_path:
                result_path = task.zipfile_path
            else:
                # 查找最新生成的备份文件
                from pathlib import Path

                patterns = [
                    "*.zip",
                    "*.tar",
                    "*.tar.gz",
                    "*.tar.bz2",
                    "*.tar.xz",
                    "*.tar.zst",
                    "*.7z",
                ]
                all_files = []
                dest_path = Path(dest_dir)
                if dest_path.is_dir():
                    for pat in patterns:
                        all_files.extend(dest_path.glob(pat))
                    if all_files:
                        all_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                        result_path = str(all_files[0])

            task.status = "completed"
            task.result_path = result_path
            task.finished_at = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.finished_at = datetime.now(timezone.utc).isoformat()
            logger.error("Task %s failed: %s", task.id, e)

        self._save()
        return task

    def run_all(self, max_concurrent: int = 1) -> list[BackupTask]:
        """
        顺序执行所有 pending 任务
        :param max_concurrent: 最大并发数（当前仅支持 1，顺序执行）
        :return: 已执行的任务列表
        """
        executed: list[BackupTask] = []
        while True:
            task = self.run_next()
            if task is None:
                break
            executed.append(task)
        return executed

    def clear_completed(self) -> int:
        """
        清除已完成和已失败的任务
        :return: 清除的任务数量
        """
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.status not in ("completed", "failed")]
        removed = before - len(self.tasks)
        if removed > 0:
            self._save()
        return removed

    def get_stats(self) -> dict[str, int]:
        """
        获取各状态任务数统计
        :return: {"pending": N, "running": N, "completed": N, "failed": N, "total": N}
        """
        stats: dict[str, int] = {
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "total": len(self.tasks),
        }
        for task in self.tasks:
            if task.status in stats:
                stats[task.status] += 1
        return stats
