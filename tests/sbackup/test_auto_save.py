"""
单元测试 for sbackup.auto_save 模块
"""
import unittest
import os
import json
import tempfile
import shutil
from sbackup.auto_save import add_folder, rm_folder


class TestAutoSave(unittest.TestCase):
    def setUp(self):
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()
        self.data_file = os.path.join(self.test_dir, "sbackup.json")
        
        # 设置环境变量
        os.environ["SBACKUP_DATA_FILE"] = self.data_file
        
        # 创建测试文件夹
        self.source_folder = os.path.join(self.test_dir, "source")
        self.target_folder = os.path.join(self.test_dir, "target")
        os.makedirs(self.source_folder)
        os.makedirs(self.target_folder)

    def tearDown(self):
        # 清理临时目录
        shutil.rmtree(self.test_dir)
        
    def test_add_folder(self):
        """测试添加备份策略"""
        # 添加策略
        add_folder(self.source_folder, self.target_folder, ".git")
        
        # 验证数据文件
        import time
        time.sleep(0.5)  # 确保文件写入完成
        
        # 检查文件是否存在
        self.assertTrue(os.path.exists(self.data_file), f"数据文件 {self.data_file} 不存在")
        
        with open(self.data_file, "r") as f:
            data = json.load(f)
            self.assertIn(os.path.abspath(self.source_folder), data, f"数据文件内容: {data}")

if __name__ == "__main__":
    unittest.main()