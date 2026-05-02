"""
单元测试 for sbackup.config 模块（load_config / save_lang）
"""

import unittest
import os
import tempfile
import json
from unittest.mock import patch
from sbackup.config import load_config, save_lang, save_format, save_sftp_config


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
            "compression": {"algorithm": "ZIP_STORED", "level": 1},
            "skip_patterns": [".git", "__pycache__", ".DS_Store"],
            "data_file": "custom_sbackup.json",
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
            "compression": {"algorithm": "ZIP_DEFLATED", "level": 6},
            "skip_patterns": [".git", "__pycache__"],
            "data_file": "sbackup.json",
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

    def test_save_lang_malformed_existing_file(self):
        """测试已有配置文件 JSON 损坏时 save_lang 重置"""
        with open(self.config_file, "w") as f:
            f.write("{bad json!!!")
        save_lang("en_US", self.config_file)
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["lang"], "en_US")

    @patch("os.makedirs")
    def test_save_lang_makedirs_error(self, mock_makedirs):
        """测试创建目录失败时 save_lang 静默返回"""
        mock_makedirs.side_effect = OSError("permission denied")
        save_lang("zh_CN", self.config_file)
        # 不应抛出异常

    @patch("builtins.open")
    def test_save_lang_write_error(self, mock_open):
        """测试写入文件失败时 save_lang 静默处理"""
        mock_open.side_effect = OSError("disk full")
        save_lang("zh_CN", self.config_file)
        # 不应抛出异常


class TestSaveFormat(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            import shutil

            shutil.rmtree(self.test_dir)

    def test_save_format_creates_new_file(self):
        """测试 save_format 创建新配置文件"""
        save_format("tar.gz", self.config_file)
        self.assertTrue(os.path.exists(self.config_file))
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["compression_format"], "tar.gz")

    def test_save_format_updates_existing(self):
        """测试 save_format 更新已有配置"""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump({"lang": "zh_CN"}, f)
        save_format("tar.xz", self.config_file)
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["compression_format"], "tar.xz")
        self.assertEqual(data["lang"], "zh_CN")

    def test_save_format_malformed_json(self):
        """测试配置文件损坏时 save_format 重置"""
        with open(self.config_file, "w") as f:
            f.write("{bad")
        save_format("tar.bz2", self.config_file)
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["compression_format"], "tar.bz2")

    @patch("os.makedirs")
    def test_save_format_makedirs_error(self, mock_makedirs):
        """测试创建目录失败"""
        mock_makedirs.side_effect = OSError("denied")
        save_format("tar.gz", self.config_file)

    @patch("builtins.open")
    def test_save_format_write_error(self, mock_open):
        """测试写入失败"""
        mock_open.side_effect = OSError("disk full")
        save_format("tar.gz", self.config_file)


class TestSaveSftpConfig(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            import shutil

            shutil.rmtree(self.test_dir)

    def test_save_sftp_config_creates_new_file(self):
        """测试 save_sftp_config 创建新配置文件"""
        save_sftp_config(
            "host.com",
            2222,
            "admin",
            "secret",
            "/backups",
            key_file="/path/to/key",
            key_passphrase="keypass",
            config_file=self.config_file,
        )
        self.assertTrue(os.path.exists(self.config_file))
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["sftp"]["host"], "host.com")
        self.assertEqual(data["sftp"]["port"], 2222)
        self.assertEqual(data["sftp"]["user"], "admin")
        self.assertEqual(data["sftp"]["password"], "secret")
        self.assertEqual(data["sftp"]["key_file"], "/path/to/key")
        self.assertEqual(data["sftp"]["key_passphrase"], "keypass")
        self.assertEqual(data["sftp"]["remote_path"], "/backups")
        self.assertTrue(data["sftp"]["enabled"])

    def test_save_sftp_config_updates_existing(self):
        """测试 save_sftp_config 更新已有配置"""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump({"lang": "zh_CN", "compression_format": "zip"}, f)
        save_sftp_config(
            "newhost",
            22,
            "user",
            "pass",
            "/",
            key_file="",
            key_passphrase="",
            config_file=self.config_file,
        )
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["sftp"]["host"], "newhost")
        self.assertEqual(data["lang"], "zh_CN")
        self.assertEqual(data["compression_format"], "zip")

    def test_save_sftp_config_disabled(self):
        """测试 save_sftp_config 禁用 SFTP"""
        save_sftp_config(
            "host",
            22,
            "user",
            "pass",
            "/",
            enabled=False,
            key_file="",
            key_passphrase="",
            config_file=self.config_file,
        )
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertFalse(data["sftp"]["enabled"])

    def test_save_sftp_config_malformed_json(self):
        """测试配置文件损坏时 save_sftp_config 重置"""
        with open(self.config_file, "w") as f:
            f.write("{bad")
        save_sftp_config(
            "host",
            22,
            "user",
            "pass",
            "/",
            key_file="",
            key_passphrase="",
            config_file=self.config_file,
        )
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["sftp"]["host"], "host")

    @patch("os.makedirs")
    def test_save_sftp_config_makedirs_error(self, mock_makedirs):
        """测试创建目录失败"""
        mock_makedirs.side_effect = OSError("denied")
        save_sftp_config(
            "host",
            22,
            "user",
            "pass",
            "/",
            key_file="",
            key_passphrase="",
            config_file=self.config_file,
        )

    @patch("builtins.open")
    def test_save_sftp_config_write_error(self, mock_open):
        """测试写入失败"""
        mock_open.side_effect = OSError("disk full")
        save_sftp_config("host", 22, "user", "pass", "/", config_file=self.config_file)

    def test_load_config_with_sftp(self):
        """测试 load_config 读取 SFTP 配置"""
        config_data = {
            "lang": "en_US",
            "sftp": {
                "host": "sftp.example.com",
                "port": 2222,
                "user": "backup",
                "password": "s3cret",
                "remote_path": "/data/backups",
                "enabled": True,
            },
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f)
        config = load_config(self.config_file)
        self.assertEqual(config.sftp_host, "sftp.example.com")
        self.assertEqual(config.sftp_port, 2222)
        self.assertEqual(config.sftp_user, "backup")
        self.assertEqual(config.sftp_password, "s3cret")
        self.assertEqual(config.sftp_remote_path, "/data/backups")
        self.assertTrue(config.sftp_enabled)

    def test_load_config_sftp_defaults(self):
        """测试 load_config 无 SFTP 配置时使用默认值"""
        config_data = {"lang": "en_US"}
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f)
        config = load_config(self.config_file)
        self.assertEqual(config.sftp_host, "")
        self.assertEqual(config.sftp_port, 22)
        self.assertEqual(config.sftp_user, "")
        self.assertEqual(config.sftp_password, "")
        self.assertEqual(config.sftp_remote_path, "/")
        self.assertFalse(config.sftp_enabled)

    def test_load_config_with_sftp_key(self):
        """测试加载包含私钥的 SFTP 配置"""
        config_data = {
            "sftp": {
                "host": "keyhost",
                "port": 2222,
                "user": "keyuser",
                "password": "",
                "key_file": "/home/user/.ssh/id_rsa",
                "key_passphrase": "keypass",
                "remote_path": "/backups",
                "enabled": True,
            }
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f)
        config = load_config(self.config_file)
        self.assertEqual(config.sftp_host, "keyhost")
        self.assertEqual(config.sftp_port, 2222)
        self.assertEqual(config.sftp_user, "keyuser")
        self.assertEqual(config.sftp_key_file, "/home/user/.ssh/id_rsa")
        self.assertEqual(config.sftp_key_passphrase, "keypass")
        self.assertTrue(config.sftp_enabled)


if __name__ == "__main__":
    unittest.main()
