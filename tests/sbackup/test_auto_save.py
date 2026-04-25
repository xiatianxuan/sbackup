"""
单元测试 for sbackup.auto_save 模块
"""

import unittest
import os
import json
import tempfile
import shutil
from sbackup.auto_save import BackupManager


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


if __name__ == "__main__":
    unittest.main()