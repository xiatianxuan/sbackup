"""
单元测试 for sbackup.config 模块（load_config / save_lang）
"""

import unittest
import os
import tempfile
import json
from sbackup.config import load_config, save_lang, Config


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
        # 在临时目录中创建默认配置文件（而非项目根目录）
        default_config = os.path.join(self.test_dir, "config.json")
        config_data = {
            "compression": {
                "algorithm": "ZIP_DEFLATED",
                "level": 6
            },
            "skip_patterns": [".git", "__pycache__"],
            "data_file": "sbackup.json"
        }
        with open(default_config, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)

        config = load_config(default_config)

        self.assertEqual(config.compression_algorithm, "ZIP_DEFLATED")
        self.assertEqual(config.compression_level, 6)
        self.assertEqual(config.skip_patterns, [".git", "__pycache__"])

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

    def test_load_config_malformed_json(self):
        """测试配置文件 JSON 格式错误时使用默认配置"""
        malformed_config = os.path.join(self.test_dir, "bad_config.json")
        with open(malformed_config, "w", encoding="utf-8") as f:
            f.write("{invalid json content!!!")

        config = load_config(malformed_config)
        self.assertEqual(config.compression_algorithm, "ZIP_DEFLATED")
        self.assertEqual(config.compression_level, 6)


class TestSaveLang(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            import shutil
            shutil.rmtree(self.test_dir)

    def test_save_lang_creates_new_file(self):
        """测试 save_lang 在配置文件不存在时创建新文件"""
        save_lang("zh_CN", self.config_file)

        self.assertTrue(os.path.exists(self.config_file))
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["lang"], "zh_CN")

    def test_save_lang_updates_existing_file(self):
        """测试 save_lang 在已有配置文件中更新语言字段"""
        # 先写入已有配置
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump({"compression": {"algorithm": "ZIP_STORED", "level": 3}}, f)

        save_lang("en_US", self.config_file)

        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["lang"], "en_US")
        # 原有配置应保留
        self.assertEqual(data["compression"]["algorithm"], "ZIP_STORED")
        self.assertEqual(data["compression"]["level"], 3)

    def test_save_lang_overwrites_existing_lang(self):
        """测试 save_lang 覆盖已有的语言设置"""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump({"lang": "zh_CN"}, f)

        save_lang("en_US", self.config_file)

        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["lang"], "en_US")

    def test_save_lang_with_subdirectory(self):
        """测试 save_lang 在子目录中创建配置文件"""
        subdir_config = os.path.join(self.test_dir, "sub", "config.json")
        save_lang("zh_CN", subdir_config)

        self.assertTrue(os.path.exists(subdir_config))
        with open(subdir_config, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["lang"], "zh_CN")


if __name__ == "__main__":
    unittest.main()