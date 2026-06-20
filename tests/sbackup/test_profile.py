"""
单元测试 for sbackup.profile 模块 (ProfileManager)
"""

import unittest
import os
import tempfile
import shutil
import json

from sbackup.config import Config
from sbackup.profile import ProfileManager


class TestProfileManagerInit(unittest.TestCase):
    """测试 ProfileManager 初始化"""

    def test_init_default_config_file(self):
        """测试默认 config_file 参数"""
        pm = ProfileManager()
        self.assertEqual(pm.config_file, "config.json")

    def test_init_custom_config_file(self):
        """测试自定义 config_file 参数"""
        pm = ProfileManager("/tmp/test_config.json")
        self.assertEqual(pm.config_file, "/tmp/test_config.json")


class TestListProfiles(unittest.TestCase):
    """测试 list_profiles"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_list_profiles_empty(self):
        """测试无 profile 时返回空字典"""
        pm = ProfileManager(self.config_file)
        result = pm.list_profiles()
        self.assertEqual(result, {})

    def test_list_profiles_nonempty(self):
        """测试有 profile 时正确返回"""
        # 先写入含 profiles 的配置
        data = {
            "profiles": {
                "work": {"folder_path": "/work", "compression_format": "7Z"},
                "personal": {"folder_path": "/photos"},
            }
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        pm = ProfileManager(self.config_file)
        profiles = pm.list_profiles()
        self.assertEqual(len(profiles), 2)
        self.assertIn("work", profiles)
        self.assertIn("personal", profiles)
        self.assertEqual(profiles["work"]["folder_path"], "/work")

    def test_list_profiles_no_profiles_key(self):
        """测试 config 中无 profiles 键时返回空字典"""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump({"lang": "zh_CN"}, f)
        pm = ProfileManager(self.config_file)
        self.assertEqual(pm.list_profiles(), {})


class TestGetProfile(unittest.TestCase):
    """测试 get_profile"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_profile_exists(self):
        """测试获取存在的 profile"""
        data = {
            "profiles": {
                "work": {"folder_path": "/work", "compression_format": "7Z"},
            }
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        pm = ProfileManager(self.config_file)
        result = pm.get_profile("work")
        self.assertIsNotNone(result)
        self.assertEqual(result["folder_path"], "/work")

    def test_get_profile_not_exists(self):
        """测试获取不存在的 profile 返回 None"""
        data = {"profiles": {"work": {"folder_path": "/work"}}}
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        pm = ProfileManager(self.config_file)
        result = pm.get_profile("nonexistent")
        self.assertIsNone(result)

    def test_get_profile_no_profiles_section(self):
        """测试 config 无 profiles 段时返回 None"""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump({}, f)

        pm = ProfileManager(self.config_file)
        result = pm.get_profile("work")
        self.assertIsNone(result)


class TestSaveProfile(unittest.TestCase):
    """测试 save_profile"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_profile_creates_entry(self):
        """测试保存 profile 创建新条目"""
        pm = ProfileManager(self.config_file)
        config = Config(folder_path="/home/user/work", compression_format="7Z")
        result = pm.save_profile("work", config)
        self.assertTrue(result)

        # 验证已保存
        profile = pm.get_profile("work")
        self.assertIsNotNone(profile)
        self.assertEqual(profile["folder_path"], "/home/user/work")
        self.assertEqual(profile["compression_format"], "7Z")

    def test_save_profile_overwrites_existing(self):
        """测试保存同名 profile 覆盖原有内容"""
        pm = ProfileManager(self.config_file)
        config1 = Config(folder_path="/old/path", compression_format="ZIP")
        pm.save_profile("work", config1)

        config2 = Config(folder_path="/new/path", compression_format="7Z")
        pm.save_profile("work", config2)

        profile = pm.get_profile("work")
        self.assertEqual(profile["folder_path"], "/new/path")
        self.assertEqual(profile["compression_format"], "7Z")

    def test_save_profile_empty_name_returns_false(self):
        """测试空名称返回 False"""
        pm = ProfileManager(self.config_file)
        config = Config()
        result = pm.save_profile("", config)
        self.assertFalse(result)

    def test_save_profile_preserves_existing_config(self):
        """测试保存 profile 不影响主配置其他字段"""
        # 先有 lang 设置
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump({"lang": "en_US", "compression_format": "ZIP"}, f)

        pm = ProfileManager(self.config_file)
        config = Config(folder_path="/work")
        pm.save_profile("work", config)

        # 验证主配置字段保留
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["lang"], "en_US")
        self.assertEqual(data["compression_format"], "ZIP")
        self.assertIn("profiles", data)


class TestDeleteProfile(unittest.TestCase):
    """测试 delete_profile"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_delete_profile_success(self):
        """测试成功删除 profile"""
        data = {"profiles": {"work": {"folder_path": "/work"}}}
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        pm = ProfileManager(self.config_file)
        result = pm.delete_profile("work")
        self.assertTrue(result)
        self.assertIsNone(pm.get_profile("work"))

    def test_delete_profile_not_exists_returns_false(self):
        """测试删除不存在的 profile 返回 False"""
        data = {"profiles": {"work": {"folder_path": "/work"}}}
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        pm = ProfileManager(self.config_file)
        result = pm.delete_profile("nonexistent")
        self.assertFalse(result)

    def test_delete_preserves_other_profiles(self):
        """测试删除 profile 不影响其他 profile"""
        data = {
            "profiles": {
                "work": {"folder_path": "/work"},
                "personal": {"folder_path": "/photos"},
            }
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        pm = ProfileManager(self.config_file)
        pm.delete_profile("work")
        self.assertIsNotNone(pm.get_profile("personal"))
        self.assertIsNone(pm.get_profile("work"))


class TestActivateProfile(unittest.TestCase):
    """测试 activate_profile 合并逻辑"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _write_config(self, data: dict) -> None:
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def test_activate_profile_merges_fields(self):
        """测试 profile 字段覆盖主配置对应字段"""
        self._write_config(
            {
                "lang": "zh_CN",
                "compression_format": "ZIP",
                "profiles": {
                    "work": {
                        "folder_path": "/home/user/work",
                        "compression_format": "7Z",
                    }
                },
            }
        )

        pm = ProfileManager(self.config_file)
        merged = pm.activate_profile("work")
        self.assertIsNotNone(merged)
        self.assertEqual(merged.folder_path, "/home/user/work")
        self.assertEqual(merged.compression_format, "7Z")
        # lang 不在 profile 中，应保持主配置值
        self.assertEqual(merged.lang, "zh_CN")

    def test_activate_profile_partial_override(self):
        """测试 profile 只覆盖明确设置的字段"""
        self._write_config(
            {
                "lang": "en_US",
                "compression_format": "ZIP",
                "password": "main_pass",
                "profiles": {
                    "work": {
                        "compression_format": "7Z",
                    }
                },
            }
        )

        pm = ProfileManager(self.config_file)
        merged = pm.activate_profile("work")
        self.assertIsNotNone(merged)
        self.assertEqual(merged.compression_format, "7Z")
        # password 不在 profile 中，保持主配置
        self.assertEqual(merged.password, "main_pass")
        # lang 保持主配置
        self.assertEqual(merged.lang, "en_US")

    def test_activate_profile_not_exists_returns_none(self):
        """测试激活不存在的 profile 返回 None"""
        self._write_config(
            {"lang": "zh_CN", "profiles": {"work": {"folder_path": "/work"}}}
        )

        pm = ProfileManager(self.config_file)
        merged = pm.activate_profile("nonexistent")
        self.assertIsNone(merged)

    def test_activate_profile_with_sftp(self):
        """测试 profile 覆盖 SFTP 嵌套配置"""
        self._write_config(
            {
                "lang": "zh_CN",
                "sftp": {
                    "host": "old-host",
                    "port": 22,
                    "user": "old-user",
                    "remote_path": "/old",
                    "enabled": False,
                },
                "profiles": {
                    "work": {
                        "sftp": {
                            "host": "new-host",
                            "user": "new-user",
                        }
                    }
                },
            }
        )

        pm = ProfileManager(self.config_file)
        merged = pm.activate_profile("work")
        self.assertIsNotNone(merged)
        self.assertEqual(merged.sftp_host, "new-host")
        self.assertEqual(merged.sftp_user, "new-user")
        # port 和 remote_path 未在 profile 中覆盖，应保持主配置值
        self.assertEqual(merged.sftp_port, 22)

    def test_activate_profile_does_not_modify_config_file(self):
        """测试 activate_profile 不修改 config.json"""
        self._write_config(
            {
                "lang": "zh_CN",
                "compression_format": "ZIP",
                "profiles": {
                    "work": {
                        "compression_format": "7Z",
                    }
                },
            }
        )

        pm = ProfileManager(self.config_file)
        pm.activate_profile("work")

        # 验证 config.json 未被修改
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["compression_format"], "ZIP")

    def test_activate_profile_with_password(self):
        """测试 profile 覆盖密码"""
        self._write_config(
            {
                "password": "old_pass",
                "profiles": {"work": {"password": "work_pass"}},
            }
        )

        pm = ProfileManager(self.config_file)
        merged = pm.activate_profile("work")
        self.assertIsNotNone(merged)
        self.assertEqual(merged.password, "work_pass")


class TestExportImportProfile(unittest.TestCase):
    """测试 export_profile 和 import_profile"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _write_config(self, data: dict) -> None:
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def test_export_profile_success(self):
        """测试导出 profile"""
        self._write_config(
            {
                "profiles": {
                    "work": {
                        "folder_path": "/work",
                        "compression_format": "7Z",
                    }
                }
            }
        )

        pm = ProfileManager(self.config_file)
        export_path = os.path.join(self.test_dir, "exported.json")
        result = pm.export_profile("work", export_path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(export_path))

        with open(export_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["profile_name"], "work")
        self.assertEqual(data["config"]["folder_path"], "/work")

    def test_export_profile_not_exists_returns_false(self):
        """测试导出不存在的 profile 返回 False"""
        self._write_config({"profiles": {}})
        pm = ProfileManager(self.config_file)
        export_path = os.path.join(self.test_dir, "exported.json")
        result = pm.export_profile("nonexistent", export_path)
        self.assertFalse(result)
        self.assertFalse(os.path.exists(export_path))

    def test_import_profile_wrapped_format(self):
        """测试导入包裹格式的 profile 文件"""
        self._write_config({"lang": "zh_CN"})

        import_file = os.path.join(self.test_dir, "import.json")
        import_data = {
            "profile_name": "imported",
            "config": {"folder_path": "/imported", "compression_format": "tar.gz"},
        }
        with open(import_file, "w", encoding="utf-8") as f:
            json.dump(import_data, f, ensure_ascii=False)

        pm = ProfileManager(self.config_file)
        result = pm.import_profile(import_file, "imported")
        self.assertTrue(result)

        profile = pm.get_profile("imported")
        self.assertIsNotNone(profile)
        self.assertEqual(profile["folder_path"], "/imported")

    def test_import_profile_direct_format(self):
        """测试直接导入 profile dict 格式的文件"""
        self._write_config({"lang": "zh_CN"})

        import_file = os.path.join(self.test_dir, "direct.json")
        import_data = {"folder_path": "/direct", "compression_format": "7Z"}
        with open(import_file, "w", encoding="utf-8") as f:
            json.dump(import_data, f, ensure_ascii=False)

        pm = ProfileManager(self.config_file)
        # 不指定 name，应使用文件名 "direct"
        result = pm.import_profile(import_file)
        self.assertTrue(result)

        profile = pm.get_profile("direct")
        self.assertIsNotNone(profile)
        self.assertEqual(profile["folder_path"], "/direct")

    def test_import_profile_custom_name(self):
        """测试导入时指定自定义名称"""
        self._write_config({"lang": "zh_CN"})

        import_file = os.path.join(self.test_dir, "somefile.json")
        import_data = {"folder_path": "/custom"}
        with open(import_file, "w", encoding="utf-8") as f:
            json.dump(import_data, f, ensure_ascii=False)

        pm = ProfileManager(self.config_file)
        result = pm.import_profile(import_file, "custom_name")
        self.assertTrue(result)

        profile = pm.get_profile("custom_name")
        self.assertIsNotNone(profile)

    def test_import_profile_nonexistent_file_returns_false(self):
        """测试导入不存在的文件返回 False"""
        pm = ProfileManager(self.config_file)
        result = pm.import_profile("/nonexistent/file.json")
        self.assertFalse(result)

    def test_import_profile_invalid_json_returns_false(self):
        """测试导入无效 JSON 文件返回 False"""
        self._write_config({"lang": "zh_CN"})
        bad_file = os.path.join(self.test_dir, "bad.json")
        with open(bad_file, "w") as f:
            f.write("{invalid json!!!")

        pm = ProfileManager(self.config_file)
        result = pm.import_profile(bad_file)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
