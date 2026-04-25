"""
单元测试 for sbackup._compression.load_config 函数
"""

import unittest
import os
import tempfile
import json
from sbackup._compression import load_config, Config


class TestConfig(unittest.TestCase):
    def setUp(self):
        """
        设置测试环境
        """
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        """
        清理测试环境
        """
        # 清理临时目录
        if os.path.exists(self.test_dir):
            import shutil
            shutil.rmtree(self.test_dir)

    def test_load_config_from_file(self):
        """
        测试从配置文件中加载配置
        """
        # 创建配置文件
        config_data = {
            "compression": {
                "algorithm": "ZIP_STORED",
                "level": 1
            },
            "skip_patterns": [".git", "__pycache__", ".DS_Store"],
            "data_file": "custom_sbackup.json"
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)

        # 加载配置
        config = load_config(self.config_file)

        # 验证配置
        self.assertEqual(config.compression_algorithm, "ZIP_STORED")
        self.assertEqual(config.compression_level, 1)
        self.assertEqual(config.skip_patterns, [".git", "__pycache__", ".DS_Store"])

    def test_load_config_from_default_file(self):
        """
        测试从默认配置文件中加载配置
        """
        # 创建默认配置文件
        config_data = {
            "compression": {
                "algorithm": "ZIP_DEFLATED",
                "level": 6
            },
            "skip_patterns": [".git", "__pycache__"],
            "data_file": "sbackup.json"
        }
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)

        # 加载配置
        config = load_config()

        # 验证配置
        self.assertEqual(config.compression_algorithm, "ZIP_DEFLATED")
        self.assertEqual(config.compression_level, 6)
        self.assertEqual(config.skip_patterns, [".git", "__pycache__"])
        
        # 清理默认配置文件
        os.remove("config.json")

    def test_load_config_from_nonexistent_file(self):
        """
        测试从不存在的配置文件中加载配置
        """
        # 加载配置
        config = load_config("nonexistent_config.json")

        # 验证配置
        self.assertEqual(config.compression_algorithm, "ZIP_DEFLATED")
        self.assertEqual(config.compression_level, 6)
        self.assertEqual(config.skip_patterns, [".git", "__pycache__"])


if __name__ == "__main__":
    unittest.main()