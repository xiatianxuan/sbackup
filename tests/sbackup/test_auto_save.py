"""
单元测试 for sbackup.auto_save 模块
"""

import unittest
import os
import json
import tempfile
import shutil
import time
from pathlib import Path
from sbackup.auto_save import BackupManager
from sbackup.i18n import t


class TestAutoSave(unittest.TestCase):
    def setUp(self):
        """
        设置测试环境
        """
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()
        
        # 保存原始工作目录并切换到测试目录，以便测试相对路径逻辑
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # 定义测试使用的数据文件
        self.data_file = os.path.join(self.test_dir, "test_sbackup.json")
        
        # 初始化 BackupManager 实例
        self.manager = BackupManager(self.data_file)

        # 创建测试文件夹
        self.source_folder = os.path.join(self.test_dir, "source")
        self.target_folder = os.path.join(self.test_dir, "target")
        os.makedirs(self.source_folder)
        os.makedirs(self.target_folder)

    def tearDown(self):
        """
        清理测试环境
        """
        # 恢复原始工作目录
        os.chdir(self.original_cwd)
        # 清理临时目录
        shutil.rmtree(self.test_dir)

    def test_add_folder(self):
        """测试添加备份策略"""
        # 添加策略
        result = self.manager.add_folder(self.source_folder, self.target_folder, ".git")
        
        self.assertTrue(result)

        # 验证数据文件
        self.assertTrue(os.path.exists(self.data_file), f"数据文件 {self.data_file} 不存在")

        with open(self.data_file, "r") as f:
            data = json.load(f)
            self.assertIn(os.path.abspath(self.source_folder), data, f"数据文件内容: {data}")

    def test_rm_folder(self):
        """测试删除备份策略"""
        # 先添加
        self.manager.add_folder(self.source_folder, self.target_folder)
        self.assertIn(os.path.abspath(self.source_folder), self.manager.data)

        # 再删除
        result = self.manager.rm_folder(self.source_folder)
        self.assertTrue(result)
        self.assertNotIn(os.path.abspath(self.source_folder), self.manager.data)

    def test_save_folder_updates_mtime(self):
        """测试执行备份后时间戳被更新，实现增量备份"""
        # 添加策略
        self.manager.add_folder(self.source_folder, self.target_folder, "")
        abs_source = os.path.abspath(self.source_folder)
        original_mtime = self.manager.data[abs_source][0]

        # 修改源文件夹内容，触发备份条件
        time.sleep(0.1)
        (Path(self.source_folder) / "new_file.txt").write_text("new content")

        # 执行备份（使用新方法名 execute_backups）
        self.manager.execute_backups()

        # 验证 mtime 已更新
        new_mtime = self.manager.data[abs_source][0]
        self.assertNotEqual(original_mtime, new_mtime, "备份后 mtime 应被更新")
        self.assertEqual(new_mtime, os.stat(abs_source).st_mtime)

        # 验证数据已持久化
        self.manager.load()
        self.assertEqual(self.manager.data[abs_source][0], new_mtime)

    def test_execute_backups_alias(self):
        """测试 save_folder 向后兼容别名"""
        self.assertTrue(hasattr(self.manager, "save_folder"))
        # 验证 save_folder 指向 execute_backups 的底层函数
        self.assertIs(
            self.manager.save_folder.__func__,
            self.manager.execute_backups.__func__
        )

    def test_add_folder_skip_patterns_stripped(self):
        """测试忽略模式中的空格被正确去除"""
        result = self.manager.add_folder(
            self.source_folder, self.target_folder, " .git , node_modules "
        )
        self.assertTrue(result)
        abs_source = os.path.abspath(self.source_folder)
        skip_list = self.manager.data[abs_source][2]
        self.assertEqual(skip_list, [".git", "node_modules"])

    def test_add_duplicate_folder(self):
        """测试重复添加同一文件夹应失败"""
        result1 = self.manager.add_folder(self.source_folder, self.target_folder)
        self.assertTrue(result1)
        result2 = self.manager.add_folder(self.source_folder, self.target_folder)
        self.assertFalse(result2)
        abs_source = os.path.abspath(self.source_folder)
        self.assertEqual(len(self.manager.data), 1)

    def test_rm_nonexistent_folder(self):
        """测试删除不存在的策略应失败"""
        result = self.manager.rm_folder("/nonexistent/path")
        self.assertFalse(result)

    def test_add_invalid_source(self):
        """测试添加无效源目录应失败"""
        result = self.manager.add_folder("/nonexistent/path", self.target_folder)
        self.assertFalse(result)

    def test_add_invalid_dest(self):
        """测试添加无效目标目录应失败"""
        result = self.manager.add_folder(self.source_folder, "/nonexistent/path")
        self.assertFalse(result)

    def test_save_missing_source(self):
        """测试源文件夹不存在时的 save 行为"""
        # 手动构造一条源文件夹不存在的记录
        self.manager.data["/nonexistent/source"] = [0.0, self.target_folder, []]
        self.manager.save()
        # save_folder 应打印警告并跳过，不抛出异常
        self.manager.save_folder()
        # 数据应保持不变（不会被删除）
        self.assertIn("/nonexistent/source", self.manager.data)

    def test_list_folder_table_empty(self):
        """测试空策略时表格返回提示文本"""
        text = self.manager.list_folder_table()
        self.assertEqual(text, t("cmd.all.empty"))

    def test_all_folder(self):
        """测试 all_folder 返回正确字典"""
        self.manager.add_folder(self.source_folder, self.target_folder)
        result = self.manager.all_folder()
        abs_source = os.path.abspath(self.source_folder)
        self.assertEqual(result[abs_source], os.path.abspath(self.target_folder))


if __name__ == "__main__":
    unittest.main()