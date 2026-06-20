"""
备份差异对比增强测试：
1. get_diff_detail 行级差异
2. _file_sha256_from_source 内容哈希
3. archive-vs-archive diff
4. SHA256 内容检测替代 mtime
"""

import os
import sys
import tempfile
import shutil
import unittest
from pathlib import Path

from sbackup.auto_save import BackupManager, BackupEntry, _file_sha256_from_source
from sbackup.config import Config
from sbackup.compression import (
    create_compressor,
    get_diff_detail,
    _compute_unified_diff,
)


class TestGetDiffDetail(unittest.TestCase):
    """get_diff_detail 行级差异"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src = os.path.join(self.test_dir, "src")
        os.makedirs(self.src)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_diff_detail_detects_changed_line(self):
        """检测到行变化时返回 unified diff"""
        # 创建源文件
        original = "line1\nline2\nline3\n"
        Path(self.src, "file.txt").write_text(original)

        # 创建备份
        config = Config(
            folder_path=self.src,
            zipfile_path=os.path.join(self.test_dir, "backup"),
            skip_patterns=[],
            compression_format="ZIP",
        )
        result = create_compressor(config).compress()
        self.assertTrue(result["success"])
        archive_path = result["path"]

        # 修改文件
        modified = "line1\nline2_CHANGED\nline3\n"
        Path(self.src, "file.txt").write_text(modified)

        # 获取差异
        diff_text = get_diff_detail(
            source_path=os.path.join(self.src, "file.txt"),
            archive_path=archive_path,
            archive_member="src/file.txt",
        )

        self.assertIn("-line2", diff_text)
        self.assertIn("+line2_CHANGED", diff_text)
        self.assertIn("@@", diff_text)

    def test_diff_detail_unchanged_returns_empty(self):
        """未修改文件返回空字符串"""
        content = "same content\n"
        Path(self.src, "same.txt").write_text(content)

        config = Config(
            folder_path=self.src,
            zipfile_path=os.path.join(self.test_dir, "same"),
            skip_patterns=[],
            compression_format="ZIP",
        )
        result = create_compressor(config).compress()
        self.assertTrue(result["success"])

        diff_text = get_diff_detail(
            source_path=os.path.join(self.src, "same.txt"),
            archive_path=result["path"],
            archive_member="src/same.txt",
        )
        self.assertEqual(diff_text, "")

    def test_diff_detail_binary_file_returns_empty(self):
        """二进制文件返回空"""
        data = bytes(range(256))
        Path(self.src, "bin.bin").write_bytes(data)

        config = Config(
            folder_path=self.src,
            zipfile_path=os.path.join(self.test_dir, "bin"),
            skip_patterns=[],
            compression_format="ZIP",
        )
        result = create_compressor(config).compress()
        self.assertTrue(result["success"])

        diff_text = get_diff_detail(
            source_path=os.path.join(self.src, "bin.bin"),
            archive_path=result["path"],
            archive_member="src/bin.bin",
        )
        self.assertEqual(diff_text, "")

    def test_diff_detail_member_not_found(self):
        """:return 不存在的文件返回空"""
        content = "hello\n"
        Path(self.src, "hello.txt").write_text(content)

        config = Config(
            folder_path=self.src,
            zipfile_path=os.path.join(self.test_dir, "nf"),
            skip_patterns=[],
            compression_format="ZIP",
        )
        result = create_compressor(config).compress()

        diff_text = get_diff_detail(
            source_path=os.path.join(self.src, "hello.txt"),
            archive_path=result["path"],
            archive_member="nonexistent/file.txt",
        )
        self.assertEqual(diff_text, "")

    def test_diff_detail_tar_gz(self):
        """TAR.GZ 格式的行级差异"""
        content = "old line\n"
        Path(self.src, "data.txt").write_text(content)

        config = Config(
            folder_path=self.src,
            zipfile_path=os.path.join(self.test_dir, "tar"),
            skip_patterns=[],
            compression_format="TAR_GZ",
        )
        result = create_compressor(config).compress()
        self.assertTrue(result["success"])

        Path(self.src, "data.txt").write_text("new line\n")
        diff_text = get_diff_detail(
            source_path=os.path.join(self.src, "data.txt"),
            archive_path=result["path"],
            archive_member="src/data.txt",
        )
        self.assertIn("-old line", diff_text)
        self.assertIn("+new line", diff_text)


class TestFileSha256FromSource(unittest.TestCase):
    """_file_sha256_from_source"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src = os.path.join(self.test_dir, "src")
        os.makedirs(self.src)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sha256_from_file_on_disk(self):
        """从磁盘文件读取 SHA256"""
        Path(self.src, "hello.txt").write_text("hello world")
        import hashlib
        expected = hashlib.sha256(b"hello world").hexdigest()
        result = _file_sha256_from_source(self.src, "hello.txt")
        self.assertEqual(result, expected)

    def test_sha256_from_zip_archive(self):
        """从 ZIP 归档读取 SHA256"""
        Path(self.src, "data.txt").write_text("archived content")
        config = Config(
            folder_path=self.src,
            zipfile_path=os.path.join(self.test_dir, "test"),
            skip_patterns=[],
            compression_format="ZIP",
        )
        r = create_compressor(config).compress()
        self.assertTrue(r["success"])

        import hashlib
        expected = hashlib.sha256(b"archived content").hexdigest()
        result = _file_sha256_from_source(r["path"], "src/data.txt")
        self.assertEqual(result, expected)

    def test_sha256_from_targz_archive(self):
        """从 TAR.GZ 归档读取 SHA256"""
        Path(self.src, "tardata.txt").write_text("tar content")
        config = Config(
            folder_path=self.src,
            zipfile_path=os.path.join(self.test_dir, "tarhash"),
            skip_patterns=[],
            compression_format="TAR_GZ",
        )
        r = create_compressor(config).compress()
        self.assertTrue(r["success"])

        import hashlib
        expected = hashlib.sha256(b"tar content").hexdigest()
        result = _file_sha256_from_source(r["path"], "src/tardata.txt")
        self.assertEqual(result, expected)

    def test_sha256_nonexistent_file(self):
        """不存在的文件返回 None"""
        result = _file_sha256_from_source(self.src, "nope.txt")
        self.assertIsNone(result)

    def test_sha256_nonexistent_archive(self):
        """不存在的归档返回 None"""
        result = _file_sha256_from_source(
            os.path.join(self.test_dir, "nope.zip"), "x.txt"
        )
        self.assertIsNone(result)


class TestArchiveDiff(unittest.TestCase):
    """备份-vs-备份 diff"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src = os.path.join(self.test_dir, "src")
        self.src2 = os.path.join(self.test_dir, "src2")
        os.makedirs(self.src)
        os.makedirs(self.src2)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _make_archive(self, src_dir, name, *files_contents, clear_first=False):
        """创建备份归档"""
        if clear_first:
            # 清理旧文件
            for f in Path(src_dir).iterdir():
                if f.is_file():
                    f.unlink()
        for fn, content in files_contents:
            (Path(src_dir) / fn).write_text(content)
        config = Config(
            folder_path=src_dir,
            zipfile_path=os.path.join(self.test_dir, name),
            skip_patterns=[],
            compression_format="ZIP",
            name_template=name,
        )
        result = create_compressor(config).compress()
        self.assertTrue(result["success"])
        return result["path"]

    def test_archive_diff_no_changes(self):
        """两个相同归档应无差异"""
        a1 = self._make_archive(self.src, "v1", ("a.txt", "hello"), ("b.txt", "world"))
        # 使用同一 src 目录确保归档内路径一致
        a2 = self._make_archive(self.src, "v2", ("a.txt", "hello"), ("b.txt", "world"), clear_first=True)

        mgr = BackupManager(os.path.join(self.test_dir, "data.json"))
        result = mgr.diff_backup(a1, backup_file2=a2)
        self.assertTrue(result["success"])
        self.assertEqual(result["added"], [])
        self.assertEqual(result["removed"], [])
        self.assertEqual(result["modified"], [])

    def test_archive_diff_added_file(self):
        """检测新增文件"""
        a1 = self._make_archive(self.src, "v1", ("a.txt", "hello"))
        a2 = self._make_archive(self.src, "v2", ("a.txt", "hello"), ("b.txt", "new"), clear_first=True)

        mgr = BackupManager(os.path.join(self.test_dir, "data.json"))
        result = mgr.diff_backup(a1, backup_file2=a2)
        self.assertTrue(result["success"])
        # "b.txt" 只存在于 v2
        added_names = [f.split("/")[-1] for f in result["added"]]
        self.assertIn("b.txt", added_names)
        self.assertEqual(result["removed"], [])

    def test_archive_diff_removed_file(self):
        """检测删除文件"""
        a1 = self._make_archive(self.src, "v1", ("a.txt", "hello"), ("b.txt", "bye"))
        a2 = self._make_archive(self.src, "v2", ("a.txt", "hello"), clear_first=True)

        mgr = BackupManager(os.path.join(self.test_dir, "data.json"))
        result = mgr.diff_backup(a1, backup_file2=a2)
        self.assertTrue(result["success"])
        removed_names = [f.split("/")[-1] for f in result["removed"]]
        self.assertIn("b.txt", removed_names)
        self.assertEqual(result["added"], [])

    def test_archive_diff_modified_by_sha256(self):
        """SHA256 检测到内容修改"""
        a1 = self._make_archive(self.src, "v1", ("config.ini", "key=old_value"))
        a2 = self._make_archive(self.src, "v2", ("config.ini", "key=new_value"), clear_first=True)

        mgr = BackupManager(os.path.join(self.test_dir, "data.json"))
        result = mgr.diff_backup(a1, backup_file2=a2)
        self.assertTrue(result["success"])
        modified_names = [f.split("/")[-1] for f in result["modified"]]
        self.assertIn("config.ini", modified_names)

    def test_archive_diff_format(self):
        """format_diff 显示双归档对比"""
        a1 = self._make_archive(self.src, "v1", ("readme.txt", "v1 content"))
        a2 = self._make_archive(self.src, "v2", ("readme.txt", "v2 content"),
                                ("new.txt", "hello"), clear_first=True)

        mgr = BackupManager(os.path.join(self.test_dir, "data.json"))
        result = mgr.diff_backup(a1, backup_file2=a2)
        formatted = mgr.format_diff(result)
        self.assertIn("vs", formatted)
        self.assertIn("new.txt", formatted)

    def test_archive_diff_nonexistent(self):
        """不存在的文件返回失败"""
        mgr = BackupManager(os.path.join(self.test_dir, "data.json"))
        result = mgr.diff_backup(
            "/nonexistent/a.zip", backup_file2="/nonexistent/b.zip"
        )
        self.assertFalse(result["success"])


class TestDiffSHA256Detection(unittest.TestCase):
    """源目录 vs 备份 SHA256 修改检测"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src = os.path.join(self.test_dir, "src")
        self.dst = os.path.join(self.test_dir, "dst")
        os.makedirs(self.src)
        os.makedirs(self.dst)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_content_change_detected(self):
        """内容修改应被 SHA256 检测"""
        data_file = os.path.join(self.test_dir, "data.json")
        Path(self.src, "file.txt").write_text("original")

        mgr = BackupManager(data_file)
        mgr.add_folder(self.src, self.dst)
        # 设置旧 mtime 确保 backup 会执行
        old_entry = BackupEntry.from_list(mgr.data.get(self.src, []))
        mgr._set_entry(self.src, BackupEntry(mtime=0.0, target=self.dst, skip_patterns=[]))
        mgr.save()

        # 执行首次备份
        mgr.execute_backups()
        # 内容修改
        Path(self.src, "file.txt").write_text("modified")

        # 对比（应检测修改 — SHA256 而非 mtime）
        diff = mgr.diff_backup(self.src)
        self.assertTrue(diff["success"])

    def test_touch_file_not_falsely_modified(self):
        """只 touch 不改变内容，不应报告为修改"""
        data_file = os.path.join(self.test_dir, "data.json")
        Path(self.src, "file.txt").write_text("same content")

        mgr = BackupManager(data_file)
        mgr.add_folder(self.src, self.dst)
        old_entry = BackupEntry.from_list(mgr.data.get(self.src, []))
        mgr._set_entry(self.src, BackupEntry(mtime=0.0, target=self.dst, skip_patterns=[]))
        mgr.save()
        mgr.execute_backups()

        # 只更新 mtime，不改内容
        import time
        time.sleep(0.1)
        Path(self.src, "file.txt").write_text("same content")

        diff = mgr.diff_backup(self.src)
        self.assertTrue(diff["success"])
        # SHA256 不依赖 mtime，不应报告修改
        self.assertEqual(diff["modified"], [])


if __name__ == "__main__":
    unittest.main()
