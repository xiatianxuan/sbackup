"""
单元测试 for sbackup.multi_dest 模块
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from sbackup.config import Config
from sbackup.multi_dest import DestResult, MultiDestBackup


class TestDestResult(unittest.TestCase):
    """测试 DestResult 数据类"""

    def test_create_minimal(self):
        """最小化创建 DestResult"""
        r = DestResult(name="local", success=True)
        self.assertEqual(r.name, "local")
        self.assertTrue(r.success)
        self.assertEqual(r.path, "")
        self.assertEqual(r.error, "")
        self.assertEqual(r.size, 0)
        self.assertEqual(r.duration, 0.0)

    def test_create_full(self):
        """完整参数创建 DestResult"""
        r = DestResult(
            name="sftp",
            success=True,
            path="/remote/backup.zip",
            size=1024000,
            duration=2.5,
        )
        self.assertEqual(r.name, "sftp")
        self.assertTrue(r.success)
        self.assertEqual(r.path, "/remote/backup.zip")
        self.assertEqual(r.size, 1024000)
        self.assertAlmostEqual(r.duration, 2.5)

    def test_create_with_error(self):
        """带错误信息创建 DestResult"""
        r = DestResult(
            name="webdav",
            success=False,
            error="Connection timeout",
        )
        self.assertEqual(r.name, "webdav")
        self.assertFalse(r.success)
        self.assertEqual(r.error, "Connection timeout")


class TestGetEnabledDestinations(unittest.TestCase):
    """测试 get_enabled_destinations 方法"""

    def test_only_local(self):
        """默认配置只有本地"""
        config = Config()
        multi = MultiDestBackup(config)
        destinations = multi.get_enabled_destinations()
        self.assertEqual(destinations, ["local"])

    def test_local_and_sftp(self):
        """启用 SFTP"""
        config = Config(sftp_enabled=True)
        multi = MultiDestBackup(config)
        destinations = multi.get_enabled_destinations()
        self.assertEqual(destinations, ["local", "sftp"])

    def test_local_and_webdav(self):
        """启用 WebDAV"""
        config = Config(webdav_enabled=True)
        multi = MultiDestBackup(config)
        destinations = multi.get_enabled_destinations()
        self.assertEqual(destinations, ["local", "webdav"])

    def test_local_and_cloud(self):
        """启用云存储"""
        config = Config(cloud_enabled=True)
        multi = MultiDestBackup(config)
        destinations = multi.get_enabled_destinations()
        self.assertEqual(destinations, ["local", "cloud"])

    def test_all_enabled(self):
        """所有目标都启用"""
        config = Config(
            sftp_enabled=True,
            webdav_enabled=True,
            cloud_enabled=True,
        )
        multi = MultiDestBackup(config)
        destinations = multi.get_enabled_destinations()
        self.assertEqual(destinations, ["local", "sftp", "webdav", "cloud"])

    def test_sftp_and_webdav(self):
        """SFTP 和 WebDAV 同时启用"""
        config = Config(sftp_enabled=True, webdav_enabled=True)
        multi = MultiDestBackup(config)
        destinations = multi.get_enabled_destinations()
        self.assertEqual(destinations, ["local", "sftp", "webdav"])

    def test_sftp_and_cloud(self):
        """SFTP 和云存储同时启用"""
        config = Config(sftp_enabled=True, cloud_enabled=True)
        multi = MultiDestBackup(config)
        destinations = multi.get_enabled_destinations()
        self.assertEqual(destinations, ["local", "sftp", "cloud"])


class TestBackupToLocal(unittest.TestCase):
    """测试 backup_to_local 方法"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.source_dir = os.path.join(self.test_dir, "source")
        self.target_dir = os.path.join(self.test_dir, "target")
        os.makedirs(self.source_dir)
        os.makedirs(self.target_dir)
        # 创建测试文件
        with open(os.path.join(self.source_dir, "test.txt"), "w") as f:
            f.write("hello world")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_local_backup_invalid_source(self):
        """源目录不存在时返回失败"""
        config = Config()
        multi = MultiDestBackup(config)
        result = multi.backup_to_local("/nonexistent/path", self.target_dir)
        self.assertFalse(result.success)
        self.assertEqual(result.name, "local")
        self.assertTrue(len(result.error) > 0)

    @patch("sbackup.compression.create_compressor")
    def test_local_backup_success(self, mock_create):
        """本地备份成功"""
        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = {
            "success": True,
            "path": os.path.join(self.target_dir, "backup.zip"),
            "size_mb": 1.0,
        }
        mock_create.return_value = mock_compressor

        config = Config()
        multi = MultiDestBackup(config)
        result = multi.backup_to_local(self.source_dir, self.target_dir)

        self.assertTrue(result.success)
        self.assertEqual(result.name, "local")
        self.assertGreaterEqual(result.duration, 0)

    @patch("sbackup.compression.create_compressor")
    def test_local_backup_failure(self, mock_create):
        """本地备份失败"""
        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = {
            "success": False,
            "error": "Disk full",
        }
        mock_create.return_value = mock_compressor

        config = Config()
        multi = MultiDestBackup(config)
        result = multi.backup_to_local(self.source_dir, self.target_dir)

        self.assertFalse(result.success)
        self.assertIn("Disk full", result.error)

    @patch("sbackup.compression.create_compressor")
    def test_local_backup_exception(self, mock_create):
        """本地备份异常"""
        mock_create.side_effect = RuntimeError("Unexpected error")

        config = Config()
        multi = MultiDestBackup(config)
        result = multi.backup_to_local(self.source_dir, self.target_dir)

        self.assertFalse(result.success)
        self.assertIn("Unexpected error", result.error)


class TestExecuteAll(unittest.TestCase):
    """测试 execute_all 并行执行"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.source_dir = os.path.join(self.test_dir, "source")
        self.target_dir = os.path.join(self.test_dir, "target")
        os.makedirs(self.source_dir)
        os.makedirs(self.target_dir)
        with open(os.path.join(self.source_dir, "test.txt"), "w") as f:
            f.write("hello world")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("sbackup.compression.create_compressor")
    def test_only_local(self, mock_create):
        """只有本地目标"""
        mock_compressor = MagicMock()
        backup_file = os.path.join(self.target_dir, "backup.zip")
        mock_compressor.compress.return_value = {
            "success": True,
            "path": backup_file,
            "size_mb": 0.01,
        }
        mock_create.return_value = mock_compressor

        config = Config()
        multi = MultiDestBackup(config)
        results = multi.execute_all(self.source_dir, self.target_dir)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "local")
        self.assertTrue(results[0].success)

    @patch("sbackup.compression.create_compressor")
    @patch.object(MultiDestBackup, "upload_to_sftp")
    def test_local_and_sftp(self, mock_sftp, mock_create):
        """本地 + SFTP 并行"""
        mock_compressor = MagicMock()
        backup_file = os.path.join(self.target_dir, "backup.zip")
        # 创建一个真实文件使 os.path.getsize 工作
        with open(backup_file, "wb") as f:
            f.write(b"fake zip data")
        mock_compressor.compress.return_value = {
            "success": True,
            "path": backup_file,
            "size_mb": 0.01,
        }
        mock_create.return_value = mock_compressor

        mock_sftp.return_value = DestResult(
            name="sftp",
            success=True,
            path=backup_file,
            size=1024,
            duration=1.0,
        )

        config = Config(sftp_enabled=True)
        multi = MultiDestBackup(config)
        results = multi.execute_all(self.source_dir, self.target_dir)

        self.assertEqual(len(results), 2)
        names = {r.name for r in results}
        self.assertEqual(names, {"local", "sftp"})
        self.assertTrue(all(r.success for r in results))

    @patch("sbackup.compression.create_compressor")
    @patch.object(MultiDestBackup, "upload_to_sftp")
    def test_one_target_failure_does_not_affect_others(self, mock_sftp, mock_create):
        """一个目标失败不影响其他"""
        mock_compressor = MagicMock()
        backup_file = os.path.join(self.target_dir, "backup.zip")
        with open(backup_file, "wb") as f:
            f.write(b"fake zip data")
        mock_compressor.compress.return_value = {
            "success": True,
            "path": backup_file,
            "size_mb": 0.01,
        }
        mock_create.return_value = mock_compressor

        # SFTP 上传失败
        mock_sftp.return_value = DestResult(
            name="sftp",
            success=False,
            error="Connection refused",
        )

        config = Config(sftp_enabled=True)
        multi = MultiDestBackup(config)
        results = multi.execute_all(self.source_dir, self.target_dir)

        self.assertEqual(len(results), 2)
        # 本地成功
        local_result = next(r for r in results if r.name == "local")
        self.assertTrue(local_result.success)
        # SFTP 失败
        sftp_result = next(r for r in results if r.name == "sftp")
        self.assertFalse(sftp_result.success)
        self.assertIn("Connection refused", sftp_result.error)

    @patch("sbackup.compression.create_compressor")
    def test_local_failure_aborts(self, mock_create):
        """本地备份失败则不上传"""
        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = {
            "success": False,
            "error": "Permission denied",
        }
        mock_create.return_value = mock_compressor

        config = Config(sftp_enabled=True)
        multi = MultiDestBackup(config)
        results = multi.execute_all(self.source_dir, self.target_dir)

        # 只有本地结果，没有远程上传
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "local")
        self.assertFalse(results[0].success)

    @patch("sbackup.compression.create_compressor")
    @patch.object(MultiDestBackup, "upload_to_sftp")
    @patch.object(MultiDestBackup, "upload_to_webdav")
    def test_multiple_remote_targets(self, mock_webdav, mock_sftp, mock_create):
        """多个远程目标并行上传"""
        mock_compressor = MagicMock()
        backup_file = os.path.join(self.target_dir, "backup.zip")
        with open(backup_file, "wb") as f:
            f.write(b"fake zip data")
        mock_compressor.compress.return_value = {
            "success": True,
            "path": backup_file,
            "size_mb": 0.01,
        }
        mock_create.return_value = mock_compressor

        mock_sftp.return_value = DestResult(
            name="sftp", success=True, path=backup_file, size=512, duration=0.5
        )
        mock_webdav.return_value = DestResult(
            name="webdav", success=True, path="/remote/b.zip", size=512, duration=0.3
        )

        config = Config(sftp_enabled=True, webdav_enabled=True)
        multi = MultiDestBackup(config)
        results = multi.execute_all(self.source_dir, self.target_dir)

        self.assertEqual(len(results), 3)
        names = {r.name for r in results}
        self.assertEqual(names, {"local", "sftp", "webdav"})
        self.assertTrue(all(r.success for r in results))


class TestFormatResults(unittest.TestCase):
    """测试 format_results 输出"""

    def test_all_success_zh(self):
        """中文格式 - 全部成功"""
        results = [
            DestResult(
                name="local",
                success=True,
                path="/tmp/b.zip",
                size=1048576,
                duration=1.0,
            ),
            DestResult(
                name="sftp",
                success=True,
                path="/remote/b.zip",
                size=1048576,
                duration=2.0,
            ),
        ]
        config = Config()
        multi = MultiDestBackup(config)
        output = multi.format_results(results, lang="zh_CN")

        self.assertIn("多目标备份结果", output)
        self.assertIn("[OK]", output)
        self.assertIn("本地", output)
        self.assertIn("SFTP", output)
        self.assertIn("1.00 MB", output)
        self.assertIn("成功 2 个", output)
        self.assertIn("失败 0 个", output)

    def test_all_success_en(self):
        """英文格式 - 全部成功"""
        results = [
            DestResult(
                name="local",
                success=True,
                path="/tmp/b.zip",
                size=2097152,
                duration=1.5,
            ),
        ]
        config = Config()
        multi = MultiDestBackup(config)
        output = multi.format_results(results, lang="en_US")

        self.assertIn("Multi-Destination Backup Results", output)
        self.assertIn("[OK]", output)
        self.assertIn("Local", output)
        self.assertIn("2.00 MB", output)
        self.assertIn("1 succeeded", output)
        self.assertIn("0 failed", output)

    def test_mixed_results(self):
        """混合结果"""
        results = [
            DestResult(
                name="local",
                success=True,
                path="/tmp/b.zip",
                size=1048576,
                duration=1.0,
            ),
            DestResult(name="sftp", success=False, error="Timeout"),
        ]
        config = Config()
        multi = MultiDestBackup(config)
        output = multi.format_results(results, lang="en_US")

        self.assertIn("[OK]", output)
        self.assertIn("[FAIL]", output)
        self.assertIn("Timeout", output)
        self.assertIn("1 succeeded", output)
        self.assertIn("1 failed", output)

    def test_only_local(self):
        """只有本地目标"""
        results = [
            DestResult(
                name="local", success=True, path="/tmp/b.zip", size=512000, duration=0.5
            ),
        ]
        config = Config()
        multi = MultiDestBackup(config)
        output = multi.format_results(results, lang="zh_CN")

        self.assertIn("本地", output)
        self.assertIn("成功 1 个", output)
        self.assertIn("失败 0 个", output)


if __name__ == "__main__":
    unittest.main()
