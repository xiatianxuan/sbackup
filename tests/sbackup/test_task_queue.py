"""单元测试 for sbackup.task_queue 模块"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from sbackup.task_queue import BackupTask, TaskQueue


class TestBackupTask(unittest.TestCase):
    """测试 BackupTask 数据类"""

    def test_create_task(self):
        """测试创建备份任务"""
        task = BackupTask(
            id="test-id-1",
            name="test-backup",
            folder_path="/tmp/test",
            zipfile_path=None,
            compression_format="ZIP",
            config_overrides={},
        )
        self.assertEqual(task.id, "test-id-1")
        self.assertEqual(task.name, "test-backup")
        self.assertEqual(task.status, "pending")
        self.assertEqual(task.compression_format, "ZIP")

    def test_task_to_dict(self):
        """测试任务转字典"""
        task = BackupTask(
            id="id-1",
            name="backup1",
            folder_path="/tmp/test",
            zipfile_path="/tmp/out.zip",
            compression_format="ZIP",
            config_overrides={"password": "secret"},
            status="completed",
            created_at="2026-01-01T00:00:00+00:00",
            result_path="/tmp/out.zip",
        )
        d = task.to_dict()
        self.assertEqual(d["id"], "id-1")
        self.assertEqual(d["name"], "backup1")
        self.assertEqual(d["status"], "completed")
        self.assertEqual(d["config_overrides"], {"password": "secret"})
        self.assertEqual(d["result_path"], "/tmp/out.zip")

    def test_task_from_dict(self):
        """测试从字典创建任务"""
        data = {
            "id": "id-2",
            "name": "backup2",
            "folder_path": "/tmp/folder",
            "zipfile_path": None,
            "compression_format": "TAR_GZ",
            "config_overrides": {},
            "status": "failed",
            "created_at": "2026-01-01T00:00:00+00:00",
            "started_at": "",
            "finished_at": "2026-01-01T00:01:00+00:00",
            "error": "backup failed",
            "result_path": "",
        }
        task = BackupTask.from_dict(data)
        self.assertEqual(task.id, "id-2")
        self.assertEqual(task.name, "backup2")
        self.assertEqual(task.status, "failed")
        self.assertEqual(task.error, "backup failed")
        self.assertIsNone(task.zipfile_path)

    def test_task_from_dict_defaults(self):
        """测试从不完整字典创建任务使用默认值"""
        task = BackupTask.from_dict({})
        self.assertEqual(task.id, "")
        self.assertEqual(task.status, "pending")
        self.assertEqual(task.compression_format, "ZIP")
        self.assertEqual(task.config_overrides, {})


class TestTaskQueue(unittest.TestCase):
    """测试 TaskQueue 类"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.queue_file = os.path.join(self.test_dir, "test_queue.json")
        self.queue = TaskQueue(self.queue_file)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_init_empty_queue(self):
        """测试初始化空队列"""
        self.assertEqual(len(self.queue.tasks), 0)
        self.assertFalse(os.path.exists(self.queue_file))

    def test_add_task(self):
        """测试添加任务"""
        task_id = self.queue.add_task("backup1", "/tmp/test")
        self.assertIsNotNone(task_id)
        self.assertEqual(len(self.queue.tasks), 1)
        self.assertEqual(self.queue.tasks[0].name, "backup1")
        self.assertEqual(self.queue.tasks[0].status, "pending")

    def test_add_task_with_options(self):
        """测试添加带选项的任务"""
        task_id = self.queue.add_task(
            name="backup2",
            folder_path="/tmp/test",
            zipfile_path="/tmp/out.zip",
            compression_format="tar.gz",
            config_overrides={"password": "123"},
        )
        task = self.queue.get_task(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task.zipfile_path, "/tmp/out.zip")
        self.assertEqual(task.compression_format, "TAR.GZ")
        self.assertEqual(task.config_overrides, {"password": "123"})

    def test_add_multiple_tasks(self):
        """测试添加多个任务"""
        self.queue.add_task("task1", "/tmp/test1")
        self.queue.add_task("task2", "/tmp/test2")
        self.queue.add_task("task3", "/tmp/test3")
        self.assertEqual(len(self.queue.tasks), 3)

    def test_list_tasks_all(self):
        """测试列出所有任务"""
        self.queue.add_task("task1", "/tmp/test1")
        self.queue.add_task("task2", "/tmp/test2")
        tasks = self.queue.list_tasks()
        self.assertEqual(len(tasks), 2)

    def test_list_tasks_by_status(self):
        """测试按状态过滤任务"""
        id1 = self.queue.add_task("task1", "/tmp/test1")
        self.queue.add_task("task2", "/tmp/test2")
        self.queue.cancel_task(id1)
        pending = self.queue.list_tasks(status="pending")
        failed = self.queue.list_tasks(status="failed")
        self.assertEqual(len(pending), 1)
        self.assertEqual(len(failed), 1)

    def test_get_task(self):
        """测试获取指定任务"""
        task_id = self.queue.add_task("backup1", "/tmp/test")
        task = self.queue.get_task(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task.name, "backup1")

    def test_get_task_not_found(self):
        """测试获取不存在的任务"""
        task = self.queue.get_task("nonexistent-id")
        self.assertIsNone(task)

    def test_cancel_task(self):
        """测试取消任务"""
        task_id = self.queue.add_task("backup1", "/tmp/test")
        result = self.queue.cancel_task(task_id)
        self.assertTrue(result)
        task = self.queue.get_task(task_id)
        self.assertEqual(task.status, "failed")
        self.assertTrue(len(task.error) > 0)

    def test_cancel_task_not_found(self):
        """测试取消不存在的任务"""
        result = self.queue.cancel_task("nonexistent")
        self.assertFalse(result)

    def test_cancel_task_not_pending(self):
        """测试取消非 pending 状态的任务"""
        task_id = self.queue.add_task("backup1", "/tmp/test")
        self.queue.cancel_task(task_id)  # 先取消一次
        result = self.queue.cancel_task(task_id)  # 再取消应该失败
        self.assertFalse(result)

    @patch("sbackup.task_queue.load_config")
    @patch("sbackup.task_queue.BackupManager")
    def test_run_next(self, mock_manager_cls, mock_load_config):
        """测试执行下一个 pending 任务"""
        # 设置 mock
        mock_config = MagicMock()
        mock_config.data_file = os.path.join(self.test_dir, "sbackup.json")
        mock_load_config.return_value = mock_config

        mock_manager = MagicMock()
        mock_manager.add_folder.return_value = True
        mock_manager_cls.return_value = mock_manager

        # 添加并执行任务
        self.queue.add_task("backup1", "/tmp/test")
        task = self.queue.run_next()

        self.assertIsNotNone(task)
        self.assertEqual(task.status, "completed")
        mock_manager.add_folder.assert_called_once()
        mock_manager.execute_backups.assert_called_once()

    @patch("sbackup.task_queue.load_config")
    @patch("sbackup.task_queue.BackupManager")
    def test_run_next_failure(self, mock_manager_cls, mock_load_config):
        """测试执行任务失败"""
        mock_config = MagicMock()
        mock_config.data_file = os.path.join(self.test_dir, "sbackup.json")
        mock_load_config.return_value = mock_config

        mock_manager = MagicMock()
        mock_manager.add_folder.side_effect = Exception("disk full")
        mock_manager_cls.return_value = mock_manager

        self.queue.add_task("backup1", "/tmp/test")
        task = self.queue.run_next()

        self.assertIsNotNone(task)
        self.assertEqual(task.status, "failed")
        self.assertIn("disk full", task.error)

    def test_run_next_empty_queue(self):
        """测试空队列执行"""
        task = self.queue.run_next()
        self.assertIsNone(task)

    @patch("sbackup.task_queue.load_config")
    @patch("sbackup.task_queue.BackupManager")
    def test_run_all(self, mock_manager_cls, mock_load_config):
        """测试执行所有 pending 任务"""
        mock_config = MagicMock()
        mock_config.data_file = os.path.join(self.test_dir, "sbackup.json")
        mock_load_config.return_value = mock_config

        mock_manager = MagicMock()
        mock_manager.add_folder.return_value = True
        mock_manager_cls.return_value = mock_manager

        self.queue.add_task("task1", "/tmp/test1")
        self.queue.add_task("task2", "/tmp/test2")
        self.queue.add_task("task3", "/tmp/test3")

        executed = self.queue.run_all()
        self.assertEqual(len(executed), 3)
        self.assertTrue(all(t.status == "completed" for t in executed))

    def test_run_all_empty(self):
        """测试执行空队列"""
        executed = self.queue.run_all()
        self.assertEqual(len(executed), 0)

    def test_clear_completed(self):
        """测试清除已完成任务"""
        self.queue.add_task("task1", "/tmp/test1")
        self.queue.add_task("task2", "/tmp/test2")
        self.queue.add_task("task3", "/tmp/test3")

        # 取消两个任务（设为 failed）
        self.queue.cancel_task(self.queue.tasks[0].id)
        self.queue.cancel_task(self.queue.tasks[1].id)

        count = self.queue.clear_completed()
        self.assertEqual(count, 2)
        self.assertEqual(len(self.queue.tasks), 1)

    def test_clear_completed_none(self):
        """测试清除无已完成任务"""
        self.queue.add_task("task1", "/tmp/test1")
        count = self.queue.clear_completed()
        self.assertEqual(count, 0)
        self.assertEqual(len(self.queue.tasks), 1)

    def test_get_stats(self):
        """测试获取统计信息"""
        self.queue.add_task("task1", "/tmp/test1")
        self.queue.add_task("task2", "/tmp/test2")
        self.queue.add_task("task3", "/tmp/test3")

        self.queue.cancel_task(self.queue.tasks[0].id)

        stats = self.queue.get_stats()
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["pending"], 2)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["completed"], 0)
        self.assertEqual(stats["running"], 0)


class TestTaskQueuePersistence(unittest.TestCase):
    """测试队列持久化"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.queue_file = os.path.join(self.test_dir, "queue.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_and_load(self):
        """测试保存后重新加载"""
        queue1 = TaskQueue(self.queue_file)
        queue1.add_task("task1", "/tmp/test1")
        queue1.add_task("task2", "/tmp/test2")

        # 重新加载
        queue2 = TaskQueue(self.queue_file)
        self.assertEqual(len(queue2.tasks), 2)
        self.assertEqual(queue2.tasks[0].name, "task1")
        self.assertEqual(queue2.tasks[1].name, "task2")

    def test_persist_status_changes(self):
        """测试状态变更持久化"""
        queue1 = TaskQueue(self.queue_file)
        task_id = queue1.add_task("task1", "/tmp/test1")
        queue1.cancel_task(task_id)

        queue2 = TaskQueue(self.queue_file)
        self.assertEqual(len(queue2.tasks), 1)
        self.assertEqual(queue2.tasks[0].status, "failed")

    def test_load_corrupted_file(self):
        """测试加载损坏的 JSON 文件"""
        with open(self.queue_file, "w") as f:
            f.write("not valid json {{{")
        queue = TaskQueue(self.queue_file)
        self.assertEqual(len(queue.tasks), 0)

    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        queue = TaskQueue("/nonexistent/path/queue.json")
        self.assertEqual(len(queue.tasks), 0)


if __name__ == "__main__":
    unittest.main()
