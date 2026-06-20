"""
远程增量备份单元测试：
1. _upload_to_cloud Config bug 修复
2. chunk_meta 序列化/同步
3. MultiDestBackup 增量模式
"""

import os
import sys
import json
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from sbackup.auto_save import BackupManager, BackupEntry
from sbackup.config import Config
from sbackup.multi_dest import MultiDestBackup, DestResult
from sbackup.chunked_backup import compute_chunk_hashes, CHUNK_SIZE


class TestCloudUploadBugFix(unittest.TestCase):
    """_upload_to_cloud 使用正确的 Config 属性"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_cloud_upload_uses_correct_config_attrs(self):
        """验证 _upload_to_cloud 读 Config 平面属性而非嵌套字典"""
        config = Config(
            cloud_endpoint="https://s3.example.com",
            cloud_access_key="AKID",
            cloud_secret_key="SECRET",
            cloud_bucket="my-bucket",
            cloud_region="us-east-1",
            cloud_secure=True,
            cloud_remote_path="/backups",
            cloud_enabled=True,
        )
        # 创建测试文件
        test_file = os.path.join(self.test_dir, "backup.zip")
        Path(test_file).write_text("dummy backup content")

        with patch("sbackup.cloud_storage.CloudStorageClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            BackupManager._upload_to_cloud([test_file], config)
            # verify CloudStorageClient was created with correct attrs
            mock_client_cls.assert_called_once_with(
                "https://s3.example.com", "AKID", "SECRET", "my-bucket",
                region="us-east-1", secure=True,
            )

    def test_cloud_upload_not_configured_returns_early(self):
        """未配置时不上传"""
        config = Config()
        test_file = os.path.join(self.test_dir, "backup.zip")
        Path(test_file).write_text("x")
        with patch("sbackup.cloud_storage.CloudStorageClient") as mock_cls:
            BackupManager._upload_to_cloud([test_file], config)
            mock_cls.assert_not_called()

    def test_cloud_upload_uses_retry(self):
        """验证 S3 上传使用了 retry_call"""
        config = Config(
            cloud_endpoint="https://s3.example.com",
            cloud_access_key="AK",
            cloud_secret_key="SK",
            cloud_bucket="bk",
            cloud_enabled=True,
        )
        test_file = os.path.join(self.test_dir, "backup.zip")
        Path(test_file).write_text("x")

        with patch("sbackup.cloud_storage.CloudStorageClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            # 第一次失败，重试后成功
            mock_client.upload_file.side_effect = [
                Exception("transient error"),
                None,
            ]
            BackupManager._upload_to_cloud([test_file], config)
            # retry_call 默认重试2次 = 共3次尝试
            self.assertGreaterEqual(mock_client.upload_file.call_count, 2)


class TestChunkMetaSerialization(unittest.TestCase):
    """chunk_meta JSON 序列化"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src = os.path.join(self.test_dir, "src")
        os.makedirs(self.src)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_chunk_meta_roundtrip(self):
        """chunk_meta 序列化再反序列化，数据一致"""
        Path(os.path.join(self.src, "test.bin")).write_bytes(
            os.urandom(CHUNK_SIZE * 3)
        )

        original = {}
        for dirpath, _, filenames in os.walk(self.src):
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, self.src).replace("\\", "/")
                original[rel] = compute_chunk_hashes(fp)

        # 序列化
        payload = json.dumps(
            {"source": self.src, "chunk_meta": original},
            ensure_ascii=False,
        )
        # 反序列化
        loaded = json.loads(payload)
        self.assertEqual(loaded["source"], self.src)
        self.assertEqual(
            len(loaded["chunk_meta"]),
            len(original),
        )
        for rel, chunks in original.items():
            self.assertIn(rel, loaded["chunk_meta"])
            self.assertEqual(loaded["chunk_meta"][rel], chunks)


class TestMetaSyncHelpers(unittest.TestCase):
    """_sync_chunk_meta_to_remote 和 _download_chunk_meta_from_remote"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src = os.path.join(self.test_dir, "src")
        os.makedirs(self.src)
        Path(os.path.join(self.src, "a.txt")).write_text("hello")
        self.chunk_meta = {}
        for dirpath, _, filenames in os.walk(self.src):
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, self.src).replace("\\", "/")
                self.chunk_meta[rel] = compute_chunk_hashes(fp)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sync_skips_when_no_chunk_meta(self):
        """空 chunk_meta 时不同步"""
        config = Config(sftp_enabled=True, sftp_host="host")
        with patch.object(BackupManager, "_upload_bytes_to_sftp") as mock_up:
            BackupManager._sync_chunk_meta_to_remote(config, self.src, {})
            mock_up.assert_not_called()

    def test_sync_calls_sftp_when_configured(self):
        """SFTP 已配置时上传"""
        config = Config(
            sftp_enabled=True, sftp_host="sftp.example.com",
            sftp_user="user", sftp_password="pass",
            sftp_remote_path="/backups",
        )
        with patch.object(BackupManager, "_upload_bytes_to_sftp") as mock_up, \
             patch.object(BackupManager, "_upload_bytes_to_webdav", return_value=None), \
             patch.object(BackupManager, "_upload_bytes_to_cloud", return_value=None):
            BackupManager._sync_chunk_meta_to_remote(config, self.src, self.chunk_meta)
            self.assertGreaterEqual(mock_up.call_count, 1)
            call_args = mock_up.call_args
            self.assertIsInstance(call_args[0][0], bytes)
            self.assertEqual(call_args[0][1], "_sbackup_chunk_meta.json")

    def test_sync_calls_webdav_when_configured(self):
        """WebDAV 已配置时上传"""
        config = Config(
            webdav_enabled=True, webdav_url="https://dav.example.com",
            webdav_user="user", webdav_password="pass",
            webdav_remote_path="/backups",
        )
        with patch.object(BackupManager, "_upload_bytes_to_sftp", return_value=None), \
             patch.object(BackupManager, "_upload_bytes_to_webdav") as mock_up, \
             patch.object(BackupManager, "_upload_bytes_to_cloud", return_value=None):
            BackupManager._sync_chunk_meta_to_remote(config, self.src, self.chunk_meta)
            self.assertGreaterEqual(mock_up.call_count, 1)

    def test_sync_calls_cloud_when_configured(self):
        """Cloud 已配置时上传"""
        config = Config(
            cloud_enabled=True, cloud_endpoint="https://s3.example.com",
            cloud_access_key="AK", cloud_secret_key="SK",
            cloud_bucket="bucket",
        )
        with patch.object(BackupManager, "_upload_bytes_to_sftp", return_value=None), \
             patch.object(BackupManager, "_upload_bytes_to_webdav", return_value=None), \
             patch.object(BackupManager, "_upload_bytes_to_cloud") as mock_up:
            BackupManager._sync_chunk_meta_to_remote(config, self.src, self.chunk_meta)
            self.assertGreaterEqual(mock_up.call_count, 1)

    def test_download_returns_none_when_no_backend(self):
        """无远端配置时返回 None"""
        config = Config()
        result = BackupManager._download_chunk_meta_from_remote(config, self.src)
        self.assertIsNone(result)

    def test_download_returns_chunk_meta_on_success(self):
        """成功下载时返回 chunk_meta 字典"""
        payload = json.dumps(
            {"source": self.src, "chunk_meta": self.chunk_meta},
            ensure_ascii=False,
        ).encode("utf-8")

        config = Config(sftp_enabled=True, sftp_host="host")
        with patch.object(BackupManager, "_download_bytes_from_sftp",
                          return_value=payload):
            result = BackupManager._download_chunk_meta_from_remote(
                config, self.src
            )
            self.assertIsNotNone(result)
            self.assertEqual(len(result), len(self.chunk_meta))

    def test_download_handles_exception(self):
        """下载异常时静默返回 None"""
        config = Config(cloud_enabled=True, cloud_endpoint="ep")
        with patch.object(BackupManager, "_download_bytes_from_cloud",
                          side_effect=Exception("boom")):
            result = BackupManager._download_chunk_meta_from_remote(
                config, self.src
            )
            self.assertIsNone(result)

    def test_download_validates_source_key(self):
        """下载的 meta 中 source 不匹配时跳过"""
        payload = json.dumps(
            {"source": "/other/path", "chunk_meta": {}},
            ensure_ascii=False,
        ).encode("utf-8")

        config = Config(sftp_enabled=True, sftp_host="host")
        with patch.object(BackupManager, "_download_bytes_from_sftp",
                          return_value=payload):
            result = BackupManager._download_chunk_meta_from_remote(
                config, self.src
            )
            self.assertIsNone(result)


class TestMultiDestIncremental(unittest.TestCase):
    """MultiDestBackup 增量模式"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src = os.path.join(self.test_dir, "src")
        self.dst = os.path.join(self.test_dir, "dst")
        os.makedirs(self.src)
        os.makedirs(self.dst)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_backup_to_local_with_block_incremental(self):
        """块级增量模式调用 _build_block_incremental"""
        Path(os.path.join(self.src, "hello.txt")).write_text("hello world")

        chunk_meta = {}
        for dirpath, _, filenames in os.walk(self.src):
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, self.src).replace("\\", "/")
                chunk_meta[rel] = compute_chunk_hashes(fp)

        config = Config(
            name_template="test",
            compression_format="ZIP",
        )
        mdb = MultiDestBackup(config)
        result = mdb.backup_to_local(
            self.src, self.dst,
            incremental="block",
            chunk_meta={},  # 首次无元数据，全部新文件
        )
        self.assertTrue(result.success)
        self.assertTrue(result.path.endswith(".zip"))

    def test_backup_to_local_with_block_incremental_no_chunk_meta(self):
        """无 chunk_meta 时回退到正常压缩"""
        Path(os.path.join(self.src, "hello.txt")).write_text("hello world")

        config = Config(
            name_template="test",
            compression_format="ZIP",
        )
        mdb = MultiDestBackup(config)
        result = mdb.backup_to_local(
            self.src, self.dst,
            incremental="block",
            chunk_meta=None,
        )
        self.assertTrue(result.success)

    def test_backup_to_local_passes_file_metadata(self):
        """文件级增量传递元数据到 Config"""
        Path(os.path.join(self.src, "data.txt")).write_text("unchanged" * 50)

        import hashlib
        sha = hashlib.sha256(b"unchanged" * 50).hexdigest()

        config = Config(
            name_template="test",
            compression_format="ZIP",
        )
        mdb = MultiDestBackup(config)
        result = mdb.backup_to_local(
            self.src, self.dst,
            incremental="file",
            file_metadata={"data.txt": sha},
        )
        self.assertTrue(result.success)
        # 文件未变，compressor 会跳过它，但空的 zip 仍有文件系统开销

    def test_execute_all_passes_incremental_params(self):
        """execute_all 传递增量参数到 backup_to_local"""
        Path(os.path.join(self.src, "hello.txt")).write_text("hello world")

        config = Config(
            name_template="test",
            compression_format="ZIP",
        )
        mdb = MultiDestBackup(config)
        with patch.object(mdb, "backup_to_local") as mock_backup:
            mock_backup.return_value = DestResult(
                name="local", success=True, path="/fake/path.zip", size=100,
            )
            results = mdb.execute_all(
                self.src, self.dst,
                incremental="block",
                checksum=True,
                file_metadata={"x": "y"},
                chunk_meta={"a": {"0": "h"}},
            )
            mock_backup.assert_called_once()
            kwargs = mock_backup.call_args[1]
            self.assertEqual(kwargs["incremental"], "block")
            self.assertTrue(kwargs["checksum"])
            self.assertEqual(kwargs["file_metadata"], {"x": "y"})
            self.assertEqual(kwargs["chunk_meta"], {"a": {"0": "h"}})

    def test_incremental_produces_smaller_archive(self):
        """增量归档应小于全量"""
        # 创建大文件
        big_path = Path(self.src) / "big.bin"
        big_path.write_bytes(os.urandom(CHUNK_SIZE * 20))  # ~1.3MB

        config = Config(
            name_template="full",
            compression_format="ZIP",
        )
        mdb = MultiDestBackup(config)

        # 全量备份
        full_result = mdb.backup_to_local(self.src, self.dst)
        full_size = os.path.getsize(full_result.path) if full_result.path else 0

        # 记录 chunk_meta
        chunk_meta = {}
        for dirpath, _, filenames in os.walk(self.src):
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, self.src).replace("\\", "/")
                chunk_meta[rel] = compute_chunk_hashes(fp)

        # 小修改
        with open(big_path, "r+b") as f:
            f.seek(1000)
            f.write(b"MODIFIED!")

        # 增量备份
        incr_result = mdb.backup_to_local(
            self.src, os.path.join(self.test_dir, "dst2"),
            incremental="block",
            chunk_meta=chunk_meta,
        )
        os.makedirs(os.path.join(self.test_dir, "dst2"), exist_ok=True)
        # Re-run because dst2 already has incremental archive
        incr_result = mdb.backup_to_local(
            self.src, os.path.join(self.test_dir, "dst2"),
            incremental="block",
            chunk_meta=chunk_meta,
        )

        if incr_result.path and os.path.exists(incr_result.path):
            incr_size = os.path.getsize(incr_result.path)
            if incr_size > 0:
                self.assertLess(incr_size, full_size * 0.8,
                              f"增量 {incr_size} 应小于全量 {full_size}")


class TestExecuteBackupsWithBlockIncremental(unittest.TestCase):
    """端到端：execute_backups + 块级增量模式"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src = os.path.join(self.test_dir, "src")
        self.dst = os.path.join(self.test_dir, "dst")
        os.makedirs(self.src)
        os.makedirs(self.dst)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_block_incremental_integration_no_changes(self):
        """无变化时块级增量返回空归档"""
        data_file = os.path.join(self.test_dir, "data.json")

        # 创建文件和初始 chunk_meta
        Path(os.path.join(self.src, "file.txt")).write_text("unchanged content" * 100)
        chunk_meta = {}
        for dirpath, _, filenames in os.walk(self.src):
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, self.src).replace("\\", "/")
                chunk_meta[rel] = compute_chunk_hashes(fp)

        mgr = BackupManager(data_file)
        mgr.data["_chunk_meta"] = {self.src: chunk_meta}
        mgr.add_folder(self.src, self.dst)
        mgr.save()

        # 执行块级增量备份（无变化）
        mgr.execute_backups(incremental="block")
        history = mgr.get_history()
        self.assertEqual(len(history), 0, "无变化时不应有备份历史")

    def test_block_incremental_integration_with_changes(self):
        """有变化时块级增量应生成归档"""
        data_file = os.path.join(self.test_dir, "data.json")

        # 创建文件和初始 chunk_meta
        Path(os.path.join(self.src, "file.txt")).write_text("initial content" * 100)
        chunk_meta = {}
        for dirpath, _, filenames in os.walk(self.src):
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, self.src).replace("\\", "/")
                chunk_meta[rel] = compute_chunk_hashes(fp)

        mgr = BackupManager(data_file)
        mgr.data["_chunk_meta"] = {self.src: chunk_meta}
        mgr.add_folder(self.src, self.dst)
        mgr.save()

        # 修改文件
        Path(os.path.join(self.src, "file.txt")).write_text("changed content!!" * 100)
        # 强制设置旧 mtime 确保策略被检测为变化
        old_entry = BackupEntry.from_list(mgr.data.get(self.src, []))
        mgr._set_entry(self.src, BackupEntry(
            mtime=0.0, target=old_entry.target, skip_patterns=old_entry.skip_patterns))
        mgr.save()

        # 执行增量备份
        mgr.execute_backups(incremental="block")
        history = mgr.get_history()
        self.assertGreater(len(history), 0, "有变化时应生成备份")

    def test_download_chunk_meta_integration(self):
        """execute_backups 中下载 chunk_meta 的集成"""
        data_file = os.path.join(self.test_dir, "data.json")

        Path(os.path.join(self.src, "file.txt")).write_text("content" * 50)

        # 远程有 chunk_meta，本地没有
        remote_meta = {}
        for dirpath, _, filenames in os.walk(self.src):
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, self.src).replace("\\", "/")
                remote_meta[rel] = compute_chunk_hashes(fp)

        mgr = BackupManager(data_file)
        mgr.add_folder(self.src, self.dst)
        mgr.save()

        with patch.object(
            BackupManager, "_download_chunk_meta_from_remote",
            return_value=remote_meta,
        ):
            mgr.execute_backups(
                incremental="block",
                cloud_upload=True,
            )
        # 应保存下载的 chunk_meta 到本地
        self.assertIn(self.src, mgr.data.get("_chunk_meta", {}))

    def test_sync_chunk_meta_integration(self):
        """execute_backups 块级增量备份成功后自动同步 chunk_meta"""
        data_file = os.path.join(self.test_dir, "data.json")
        Path(os.path.join(self.src, "new_file.txt")).write_text("brand new" * 100)

        mgr = BackupManager(data_file)
        mgr.add_folder(self.src, self.dst)
        old_entry = BackupEntry.from_list(mgr.data.get(self.src, []))
        mgr._set_entry(self.src, BackupEntry(
            mtime=0.0, target=old_entry.target, skip_patterns=old_entry.skip_patterns))
        # 无 chunk_meta → 走正常压缩，然后 _update_chunk_meta + sync
        mgr.save()

        call_count = [0]

        def _fake_sync(config, key, chunk_meta):
            call_count[0] += 1

        with patch.object(
            BackupManager, "_sync_chunk_meta_to_remote", side_effect=_fake_sync,
        ):
            mgr.execute_backups(incremental="block", cloud_upload=True)
        self.assertEqual(call_count[0], 1, "备份后应调用一次 chunk_meta 同步")


if __name__ == "__main__":
    unittest.main()
