"""
单元测试 for sbackup._compression 模块
"""
import unittest
import os
import shutil
import zipfile
from pathlib import Path
from unittest.mock import patch
from sbackup._compression import Config, ZipfileCompression


class TestCompression(unittest.TestCase):
    def setUp(self):
        # 创建测试文件夹
        self.test_dir = "test_data"
        os.makedirs(self.test_dir, exist_ok=True)
        (Path(self.test_dir) / "file1.txt").write_text("test content 1")
        (Path(self.test_dir) / "subdir").mkdir()
        (Path(self.test_dir) / "subdir" / "file2.txt").write_text("test content 2")
        
        self.zip_path = "test.zip"
        if os.path.exists(self.zip_path):
            os.remove(self.zip_path)

    def tearDown(self):
        # 清理测试文件夹
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        if os.path.exists(self.zip_path):
            os.remove(self.zip_path)

    def test_zip_folder_basic(self):
        """测试基本压缩功能"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path=self.zip_path,
        )
        compressor = ZipfileCompression(config)
        compressor.zip_folder()
        
        self.assertTrue(os.path.exists(self.zip_path))
        self.assertGreater(os.path.getsize(self.zip_path), 0)

if __name__ == "__main__":
    unittest.main()