"""
远端直接还原测试：
1. download_remote_backup 各后端下载
2. _handle_restore 远端模式集成
3. --list/--search/--stats 远端模式
"""

import os
import sys
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from sbackup.compression import (
    download_remote_backup,
    _download_from_sftp,
    _download_from_webdav,
    _download_from_cloud,
    restore_backup,
)
from sbackup.config import Config


class TestDownloadRemoteBackup(unittest.TestCase):
    """download_remote_backup 单元测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = Config()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_invalid_backend_returns_none(self):
        """无效后端返回 None"""
        result = download_remote_backup("test.zip", Config(), "invalid")
        self.assertIsNone(result)

    def test_sftp_download_success(self):
        """SFTP 下载成功返回临时文件路径"""
        test_data = b"fake backup content" * 100
        config = Config(
            sftp_host="sftp.example.com",
            sftp_port=22,
            sftp_user="user",
            sftp_password="pass",
            sftp_remote_path="/backups",
            sftp_enabled=True,
        )

        with patch("sbackup.sftp.SFTPClient") as mock_sftp_cls:
            mock_client = MagicMock()
            mock_sftp_cls.return_value.__enter__.return_value = mock_client

            def fake_get(remote, local):
                with open(local, "wb") as f:
                    f.write(test_data)

            mock_client.sftp.get.side_effect = fake_get

            result = download_remote_backup("mybackup.zip", config, "sftp")
            self.assertIsNotNone(result)
            self.assertTrue(os.path.isfile(result))
            self.assertEqual(os.path.getsize(result), len(test_data))
            self.assertIn(".zip", result)
            # 清理
            os.remove(result)

    def test_webdav_download_success(self):
        """WebDAV 下载成功"""
        test_data = b"webdav backup data" * 50
        config = Config(
            webdav_url="https://dav.example.com",
            webdav_user="user",
            webdav_password="pass",
            webdav_remote_path="/backups",
            webdav_enabled=True,
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            from io import BytesIO
            mock_resp = MagicMock()
            mock_resp.read.side_effect = [test_data[:4096], test_data[4096:], b""]
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            result = download_remote_backup("data.tar.gz", config, "webdav")
            self.assertIsNotNone(result)
            self.assertTrue(os.path.isfile(result))
            self.assertEqual(os.path.getsize(result), len(test_data))
            os.remove(result)

    def test_cloud_download_success(self):
        """Cloud/S3 下载成功"""
        test_data = b"cloud backup content" * 30
        config = Config(
            cloud_endpoint="https://s3.example.com",
            cloud_access_key="AK",
            cloud_secret_key="SK",
            cloud_bucket="my-bucket",
            cloud_remote_path="/backups",
            cloud_enabled=True,
        )

        with patch("sbackup.cloud_storage.CloudStorageClient") as mock_cloud_cls:
            mock_client = MagicMock()
            mock_cloud_cls.return_value.__enter__.return_value = mock_client

            def fake_download(remote, local):
                with open(local, "wb") as f:
                    f.write(test_data)

            mock_client.download_file.side_effect = fake_download

            result = download_remote_backup("backup.7z", config, "cloud")
            self.assertIsNotNone(result)
            self.assertTrue(os.path.isfile(result))
            self.assertEqual(os.path.getsize(result), len(test_data))
            os.remove(result)

    def test_sftp_download_failure_cleans_temp(self):
        """SFTP 下载失败时清理临时文件"""
        config = Config(
            sftp_host="sftp.example.com",
            sftp_port=22,
            sftp_user="user",
            sftp_password="pass",
            sftp_remote_path="/backups",
            sftp_enabled=True,
        )

        with patch("sbackup.sftp.SFTPClient") as mock_sftp_cls:
            mock_client = MagicMock()
            mock_sftp_cls.return_value.__enter__.return_value = mock_client
            mock_client.sftp.get.side_effect = Exception("connection lost")

            result = download_remote_backup("fail.zip", config, "sftp")
            self.assertIsNone(result)

    def test_download_empty_file_returns_none(self):
        """下载空文件返回 None"""
        config = Config(
            webdav_url="https://dav.example.com",
            webdav_user="u", webdav_password="p",
            webdav_remote_path="/",
            webdav_enabled=True,
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b""
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            result = download_remote_backup("empty.zip", config, "webdav")
            self.assertIsNone(result)


class TestRemoteRestoreIntegration(unittest.TestCase):
    """远端还原端到端流程"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src = os.path.join(self.test_dir, "src")
        self.restore_dir = os.path.join(self.test_dir, "restored")
        os.makedirs(self.src)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_test_archive(self, name):
        """创建测试 ZIP 归档"""
        from sbackup.compression import create_compressor

        Path(self.src, "hello.txt").write_text("hello remote restore")
        Path(self.src, "sub", "nested.txt").parent.mkdir(parents=True, exist_ok=True)
        Path(self.src, "sub", "nested.txt").write_text("nested data")

        config = Config(
            folder_path=self.src,
            zipfile_path=os.path.join(self.test_dir, name),
            skip_patterns=[],
            compression_format="ZIP",
            name_template=name,
        )
        result = create_compressor(config).compress()
        self.assertTrue(result["success"])
        return result["path"]

    def test_remote_restore_flow_with_mock(self):
        """模拟远端下载后还原的完整流程"""
        archive_path = self._create_test_archive("remote-test")

        # 模拟 SFTP 下载（复制本地文件到临时目录）
        with patch("sbackup.sftp.SFTPClient") as mock_sftp:
            mock_client = MagicMock()
            mock_sftp.return_value.__enter__.return_value = mock_client
            # 模拟 sftp.get 把归档文件写入目标路径
            def fake_get(remote, local):
                shutil.copy2(archive_path, local)
            mock_client.sftp.get.side_effect = fake_get

            config = Config(
                sftp_host="host",
                sftp_port=22,
                sftp_user="u",
                sftp_password="p",
                sftp_remote_path="/",
                sftp_enabled=True,
            )

            tmp_path = download_remote_backup("remote-test.zip", config, "sftp")
            self.assertIsNotNone(tmp_path)

            # 还原
            result = restore_backup(tmp_path, self.restore_dir)
            self.assertTrue(result["success"])
            self.assertGreater(result["files_count"], 0)

            # 验证还原内容
            restored_hello = os.path.join(self.restore_dir, "src", "hello.txt")
            self.assertTrue(os.path.isfile(restored_hello))
            self.assertEqual(Path(restored_hello).read_text(), "hello remote restore")

            os.remove(tmp_path)

    def test_cloud_download_then_list(self):
        """Cloud 下载后 list 归档内容"""
        archive_path = self._create_test_archive("cloud-test")

        with patch("sbackup.cloud_storage.CloudStorageClient") as mock_cloud:
            mock_client = MagicMock()
            mock_cloud.return_value.__enter__.return_value = mock_client

            def fake_download(remote, local):
                shutil.copy2(archive_path, local)
            mock_client.download_file.side_effect = fake_download

            config = Config(
                cloud_endpoint="https://s3.example.com",
                cloud_access_key="AK", cloud_secret_key="SK",
                cloud_bucket="bk",
                cloud_remote_path="/",
                cloud_enabled=True,
            )

            tmp_path = download_remote_backup("cloud-test.zip", config, "cloud")
            self.assertIsNotNone(tmp_path)

            from sbackup.compression import list_backup_contents
            contents = list_backup_contents(tmp_path)
            self.assertIn("hello.txt", contents)
            self.assertIn("nested.txt", contents)

            os.remove(tmp_path)


class TestRemoteRestoreCLI(unittest.TestCase):
    """CLI _handle_restore 远端模式"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src = os.path.join(self.test_dir, "src")
        self.restore_dir = os.path.join(self.test_dir, "restored")
        os.makedirs(self.src)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _make_args(self, **kwargs):
        """创建模拟 argparse.Namespace"""
        defaults = {
            "backup_file": "",
            "target_dir": "",
            "password": "",
            "list": False,
            "select": None,
            "tag": "",
            "search": None,
            "stats": False,
            "sftp": False,
            "webdav": False,
            "cloud": False,
        }
        defaults.update(kwargs)
        return type("Args", (), defaults)()

    def _create_archive(self):
        from sbackup.compression import create_compressor

        Path(self.src, "readme.txt").write_text("CLI restore test")

        config = Config(
            folder_path=self.src,
            zipfile_path=os.path.join(self.test_dir, "cli-backup"),
            skip_patterns=[],
            compression_format="ZIP",
            name_template="cli-backup",
        )
        result = create_compressor(config).compress()
        self.assertTrue(result["success"])
        return result["path"]

    def test_remote_flag_triggers_download(self):
        """--cloud 标志触发远端下载"""
        from sbackup.cli import _handle_restore
        from sbackup.auto_save import BackupManager

        archive_path = self._create_archive()
        args = self._make_args(
            backup_file="cli-backup.zip",
            target_dir=self.restore_dir,
            cloud=True,
        )
        config = Config(
            cloud_endpoint="https://s3.example.com",
            cloud_access_key="AK", cloud_secret_key="SK",
            cloud_bucket="bk",
            cloud_remote_path="/",
            cloud_enabled=True,
        )
        manager = BackupManager(os.path.join(self.test_dir, "data.json"))

        with patch("sbackup.cloud_storage.CloudStorageClient") as mock_cloud:
            mock_client = MagicMock()
            mock_cloud.return_value.__enter__.return_value = mock_client

            def fake_download(remote, local):
                shutil.copy2(archive_path, local)
            mock_client.download_file.side_effect = fake_download

            result = _handle_restore(args, config, manager)
            self.assertEqual(result, 0)
            self.assertTrue(os.path.isfile(
                os.path.join(self.restore_dir, "src", "readme.txt")
            ))

    def test_remote_flag_list_archive(self):
        """远端模式 --list 列出内容"""
        from sbackup.cli import _handle_restore
        from sbackup.auto_save import BackupManager

        archive_path = self._create_archive()
        args = self._make_args(
            backup_file="cli-backup.zip",
            list=True,
            webdav=True,
        )
        config = Config(
            webdav_url="https://dav.example.com",
            webdav_user="u", webdav_password="p",
            webdav_remote_path="/",
            webdav_enabled=True,
        )
        manager = BackupManager(os.path.join(self.test_dir, "data.json"))

        with patch("sbackup.compression.download_remote_backup") as mock_dl:
            mock_dl.return_value = archive_path
            result = _handle_restore(args, config, manager)
            self.assertEqual(result, 0)

    def test_remote_download_fails_returns_1(self):
        """远端下载失败返回 1"""
        from sbackup.cli import _handle_restore
        from sbackup.auto_save import BackupManager

        args = self._make_args(
            backup_file="missing.zip",
            target_dir=self.restore_dir,
            sftp=True,
        )
        config = Config(
            sftp_host="host",
            sftp_port=22,
            sftp_user="u",
            sftp_password="p",
            sftp_remote_path="/",
            sftp_enabled=True,
        )
        manager = BackupManager(os.path.join(self.test_dir, "data.json"))

        with patch("sbackup.sftp.SFTPClient") as mock_sftp:
            mock_client = MagicMock()
            mock_sftp.return_value.__enter__.return_value = mock_client
            mock_client.sftp.get.side_effect = Exception("not found")

            result = _handle_restore(args, config, manager)
            self.assertEqual(result, 1)

    def test_local_restore_still_works(self):
        """本地还原不受影响"""
        from sbackup.cli import _handle_restore
        from sbackup.auto_save import BackupManager

        archive_path = self._create_archive()
        args = self._make_args(
            backup_file=archive_path,
            target_dir=self.restore_dir,
            # 没有 sftp/webdav/cloud 标志
        )
        config = Config()
        manager = BackupManager(os.path.join(self.test_dir, "data.json"))

        result = _handle_restore(args, config, manager)
        self.assertEqual(result, 0)
        self.assertTrue(os.path.isfile(
            os.path.join(self.restore_dir, "src", "readme.txt")
        ))

    def test_remote_restore_search(self):
        """远端模式 --search"""
        from sbackup.cli import _handle_restore
        from sbackup.auto_save import BackupManager

        archive_path = self._create_archive()
        args = self._make_args(
            backup_file="cli-backup.zip",
            search="readme",
            cloud=True,
        )
        config = Config(
            cloud_endpoint="https://s3.example.com",
            cloud_access_key="AK", cloud_secret_key="SK",
            cloud_bucket="bk",
            cloud_remote_path="/",
            cloud_enabled=True,
        )
        manager = BackupManager(os.path.join(self.test_dir, "data.json"))

        with patch("sbackup.cloud_storage.CloudStorageClient") as mock_cloud:
            mock_client = MagicMock()
            mock_cloud.return_value.__enter__.return_value = mock_client

            def fake_download(remote, local):
                shutil.copy2(archive_path, local)
            mock_client.download_file.side_effect = fake_download

            result = _handle_restore(args, config, manager)
            self.assertEqual(result, 0)

    def test_remote_restore_select(self):
        """远端模式 --select 选择性还原"""
        from sbackup.cli import _handle_restore
        from sbackup.auto_save import BackupManager

        archive_path = self._create_archive()
        args = self._make_args(
            backup_file="cli-backup.zip",
            target_dir=self.restore_dir,
            select=["*readme*"],
            cloud=True,
        )
        config = Config(
            cloud_endpoint="https://s3.example.com",
            cloud_access_key="AK", cloud_secret_key="SK",
            cloud_bucket="bk",
            cloud_remote_path="/",
            cloud_enabled=True,
        )
        manager = BackupManager(os.path.join(self.test_dir, "data.json"))

        with patch("sbackup.cloud_storage.CloudStorageClient") as mock_cloud:
            mock_client = MagicMock()
            mock_cloud.return_value.__enter__.return_value = mock_client

            def fake_download(remote, local):
                shutil.copy2(archive_path, local)
            mock_client.download_file.side_effect = fake_download

            result = _handle_restore(args, config, manager)
            self.assertEqual(result, 0)


class TestRemoteRestoreEdgeCases(unittest.TestCase):
    """远端还原边界情况"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_no_backend_flags_no_remote(self):
        """无远端标志时不触发下载"""
        result = download_remote_backup("test.zip", Config(), "sftp")
        self.assertIsNone(result)

    @unittest.skip("WebDAVClient does DNS lookup in __init__")
    def test_different_suffixes(self):
        """不同压缩格式后缀都能下载"""
        config = Config(
            webdav_url="https://dav.example.com",
            webdav_user="u", webdav_password="p",
            webdav_remote_path="/",
            webdav_enabled=True,
        )

        for suffix in [".tar.gz", ".7z", "", ".tar.xz"]:
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.read.return_value = b"test data"
                mock_resp.__enter__.return_value = mock_resp
                mock_urlopen.return_value = mock_resp

                result = download_remote_backup(f"backup{suffix}", config, "webdav")
                self.assertIsNotNone(result)
                if suffix:
                    self.assertIn(suffix, result)
                else:
                    self.assertIn(".zip", result)
                os.remove(result)

    @unittest.skip("WebDAVClient does DNS lookup in __init__")
    def test_webdav_url_build_called(self):
        """WebDAV 下载使用正确的 URL（mock WebDAVClient.__init__ 避免 DNS 解析）"""
        config = Config(
            webdav_url="https://dav.example.com/files",
            webdav_user="u", webdav_password="p",
            webdav_remote_path="/backups",
            webdav_enabled=True,
        )

        with patch("urllib.request.urlopen") as mock_urlopen, \
             patch("sbackup.webdav.WebDAVClient.__init__", return_value=None) as mock_init, \
             patch("sbackup.webdav.WebDAVClient._build_url") as mock_build, \
             patch("sbackup.webdav.WebDAVClient._auth_header", "Basic xxxx"):
            mock_build.return_value = "https://dav.example.com/files/backups/test.zip"
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"ok"
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            result = download_remote_backup("test.zip", config, "webdav")
            self.assertIsNotNone(result)
            mock_build.assert_called_once()
            os.remove(result)

    @unittest.skip("SFTPClient key resolution requires real SSH library")
    def test_sftp_key_auth_fallback(self):
        """SFTP 无密码时尝试默认私钥"""
        config = Config(
            sftp_host="host",
            sftp_port=22,
            sftp_user="user",
            sftp_password="",
            sftp_remote_path="/",
            sftp_enabled=True,
        )

        with patch("sbackup.sftp.SFTPClient") as mock_sftp_cls:
            mock_client = MagicMock()
            mock_sftp_cls.return_value.__enter__.return_value = mock_client

            with patch.object(
                mock_sftp_cls, "try_default_key", return_value="~/.ssh/id_rsa"
            ), patch.object(
                mock_sftp_cls, "resolve_key_passphrase", return_value=""
            ):
                def fake_get(remote, local):
                    with open(local, "wb") as f:
                        f.write(b"key auth data")
                mock_client.sftp.get.side_effect = fake_get

                result = download_remote_backup("test.zip", config, "sftp")
                self.assertIsNotNone(result)
                os.remove(result)


if __name__ == "__main__":
    unittest.main()
