"""
单元测试 for sbackup.compression 模块
"""

import unittest
import os
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from sbackup.config import Config
from sbackup.compression import (
    ZipfileCompression,
    TarfileCompression,
    ZstdCompression,
    SevenZipCompression,
    create_compressor,
    restore_backup,
    list_backup_contents,
    verify_backup,
)
from sbackup.i18n import t


_TEST_ARTIFACTS = [
    "test.zip",
    "test.tar",
    "test.tar.gz",
    "test.tar.bz2",
    "test.tar.xz",
    "test.tar.zst",
    "test.7z",
    "test_output.zip",
    "test_data.zip",
    "test_data.tar.gz",
    "test_data.tar.zst",
    "test.unknown",
    "test_data",
    "test_restore",
]


def tearDownModule():
    """模块级清理：删除所有测试残留文件"""
    for name in _TEST_ARTIFACTS:
        path = Path(name)
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink(missing_ok=True)


class TestCompression(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_data"
        os.makedirs(self.test_dir, exist_ok=True)
        (Path(self.test_dir) / "file1.txt").write_text("test content 1")
        (Path(self.test_dir) / "subdir").mkdir()
        (Path(self.test_dir) / "subdir" / "file2.txt").write_text("test content 2")

        self.zip_path = "test.zip"
        if os.path.exists(self.zip_path):
            os.remove(self.zip_path)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        if os.path.exists(self.zip_path):
            os.remove(self.zip_path)
        for f in [
            "test.tar.gz",
            "test.tar.bz2",
            "test.tar.xz",
            "test_output.zip",
            "test_data.zip",
            "test_data.tar.gz",
        ]:
            if os.path.exists(f):
                os.remove(f)

    def test_zip_folder_basic(self):
        """测试基本 ZIP 压缩功能"""
        config = Config(folder_path=self.test_dir, zipfile_path=self.zip_path)
        compressor = ZipfileCompression(config)
        compressor.compress()
        self.assertTrue(os.path.exists(self.zip_path))
        self.assertGreater(os.path.getsize(self.zip_path), 0)

    def test_zip_internal_path_structure(self):
        """测试 ZIP 内部路径结构正确"""
        config = Config(folder_path=self.test_dir, zipfile_path=self.zip_path)
        compressor = ZipfileCompression(config)
        compressor.compress()
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            for name in zf.namelist():
                self.assertTrue(
                    name.startswith("test_data/"),
                    f"ZIP 内部路径 '{name}' 应以 'test_data/' 开头",
                )

    def test_zip_respects_skip_patterns(self):
        """测试压缩时正确忽略匹配的文件"""
        (Path(self.test_dir) / ".gitignore").write_text("ignore")
        config = Config(
            folder_path=self.test_dir,
            zipfile_path=self.zip_path,
            skip_patterns=[".gitignore"],
        )
        compressor = ZipfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            self.assertNotIn("test_data/.gitignore", zf.namelist())

    @patch("builtins.print")
    def test_compresslevel_out_of_range(self, mock_print):
        """测试压缩级别超出范围时回退到默认值"""
        config = Config(
            folder_path=self.test_dir, zipfile_path=self.zip_path, compression_level=99
        )
        compressor = ZipfileCompression(config)
        self.assertEqual(compressor.compression_level, 6)

    def test_compresslevel_none_for_stored(self):
        """测试 ZIP_STORED 算法不传递 compresslevel"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path=self.zip_path,
            compression_algorithm="ZIP_STORED",
            compression_level=6,
        )
        compressor = ZipfileCompression(config)
        self.assertIsNone(compressor.compression_level)

    @patch("builtins.print")
    def test_zip_overwrite_warning(self, mock_print):
        """测试 ZIP 文件已存在时输出覆盖警告"""
        config = Config(folder_path=self.test_dir, zipfile_path=self.zip_path)
        compressor = ZipfileCompression(config)
        compressor.compress()
        compressor.compress()
        printed = " ".join(str(call) for call in mock_print.call_args_list)
        self.assertIn(t("warn.zip.overwrite").split("{")[0], printed)

    def test_unknown_compression_algorithm_fallback(self):
        """测试未知压缩算法回退到 ZIP_DEFLATED"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path=self.zip_path,
            compression_algorithm="UNKNOWN_ALGO",
        )
        compressor = ZipfileCompression(config)
        self.assertEqual(compressor.compression_algorithm, zipfile.ZIP_DEFLATED)

    def test_zip_folder_with_dir_as_zipfile_path(self):
        """测试 zipfile_path 为目录时自动拼接文件名"""
        config = Config(folder_path=self.test_dir, zipfile_path=self.test_dir)
        compressor = ZipfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        expected = os.path.join(self.test_dir, "test_data.zip")
        self.assertTrue(os.path.exists(expected))
        os.remove(expected)

    def test_zip_folder_without_zip_extension(self):
        """测试 zipfile_path 无 .zip 后缀时自动添加"""
        config = Config(folder_path=self.test_dir, zipfile_path="test_output")
        compressor = ZipfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists("test_output.zip"))
        os.remove("test_output.zip")

    def test_zip_folder_invalid_source(self):
        """测试压缩不存在的文件夹"""
        config = Config(folder_path="/nonexistent/folder", zipfile_path=self.zip_path)
        compressor = ZipfileCompression(config)
        result = compressor.compress()
        self.assertFalse(result["success"])

    @patch("builtins.print")
    def test_zip_folder_permission_error(self, mock_print):
        """测试压缩时权限不足"""
        config = Config(folder_path=self.test_dir, zipfile_path="/root/forbidden.zip")
        compressor = ZipfileCompression(config)
        result = compressor.compress()
        self.assertFalse(result["success"])

    @patch("builtins.print")
    def test_zip_folder_os_error(self, mock_print):
        """测试压缩时系统错误"""
        config = Config(folder_path=self.test_dir, zipfile_path=self.zip_path)
        compressor = ZipfileCompression(config)
        with patch("zipfile.ZipFile", side_effect=OSError("disk error")):
            result = compressor.compress()
        self.assertFalse(result["success"])

    def test_compresslevel_none_for_lzma(self):
        """测试 ZIP_LZMA 算法不传递 compresslevel"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path=self.zip_path,
            compression_algorithm="ZIP_LZMA",
            compression_level=6,
        )
        compressor = ZipfileCompression(config)
        self.assertIsNone(compressor.compression_level)

    def test_zip_bzip2_algorithm(self):
        """测试 ZIP_BZIP2 压缩算法"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path=self.zip_path,
            compression_algorithm="ZIP_BZIP2",
            compression_level=6,
        )
        compressor = ZipfileCompression(config)
        self.assertEqual(compressor.compression_algorithm, zipfile.ZIP_BZIP2)
        self.assertEqual(compressor.compression_level, 6)

    def test_zip_folder_without_zipfile_path(self):
        """测试不指定 zipfile_path 时自动生成"""
        config = Config(folder_path=self.test_dir, zipfile_path=None)
        compressor = ZipfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        expected = os.path.join(
            os.path.dirname(os.path.abspath(self.test_dir)), "test_data.zip"
        )
        self.assertTrue(os.path.exists(expected))
        os.remove(expected)

    @patch("builtins.print")
    def test_zip_folder_unknown_exception(self, mock_print):
        """测试压缩时未知异常"""
        config = Config(folder_path=self.test_dir, zipfile_path=self.zip_path)
        compressor = ZipfileCompression(config)
        with patch("zipfile.ZipFile", side_effect=RuntimeError("unexpected")):
            result = compressor.compress()
        self.assertFalse(result["success"])


class TestTarCompression(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_data"
        os.makedirs(self.test_dir, exist_ok=True)
        (Path(self.test_dir) / "file1.txt").write_text("test content 1")
        (Path(self.test_dir) / "subdir").mkdir()
        (Path(self.test_dir) / "subdir" / "file2.txt").write_text("test content 2")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        for f in ["test.tar.gz", "test.tar.bz2", "test.tar.xz", "test_data.tar.gz"]:
            if os.path.exists(f):
                os.remove(f)

    def test_tar_gz_basic(self):
        """测试 tar.gz 基本压缩"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.tar.gz",
            compression_format="TAR_GZ",
        )
        compressor = TarfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists("test.tar.gz"))
        self.assertGreater(os.path.getsize("test.tar.gz"), 0)

    def test_tar_bz2_basic(self):
        """测试 tar.bz2 基本压缩"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.tar.bz2",
            compression_format="TAR_BZ2",
        )
        compressor = TarfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists("test.tar.bz2"))

    def test_tar_xz_basic(self):
        """测试 tar.xz 基本压缩"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.tar.xz",
            compression_format="TAR_XZ",
        )
        compressor = TarfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists("test.tar.xz"))

    def test_tar_internal_path_structure(self):
        """测试 TAR 内部路径结构正确"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.tar.gz",
            compression_format="TAR_GZ",
        )
        compressor = TarfileCompression(config)
        compressor.compress()
        with tarfile.open("test.tar.gz", "r:gz") as tarf:
            names = tarf.getnames()
            for name in names:
                self.assertTrue(
                    name.startswith("test_data/"),
                    f"TAR 内部路径 '{name}' 应以 'test_data/' 开头",
                )

    def test_tar_respects_skip_patterns(self):
        """测试 TAR 压缩时正确忽略匹配的文件"""
        (Path(self.test_dir) / ".gitignore").write_text("ignore")
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.tar.gz",
            compression_format="TAR_GZ",
            skip_patterns=[".gitignore"],
        )
        compressor = TarfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        with tarfile.open("test.tar.gz", "r:gz") as tarf:
            self.assertNotIn("test_data/.gitignore", tarf.getnames())

    def test_tar_without_zipfile_path(self):
        """测试不指定路径时自动生成 tar.gz"""
        config = Config(
            folder_path=self.test_dir, zipfile_path=None, compression_format="TAR_GZ"
        )
        compressor = TarfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        expected = os.path.join(
            os.path.dirname(os.path.abspath(self.test_dir)), "test_data.tar.gz"
        )
        self.assertTrue(os.path.exists(expected))
        os.remove(expected)

    def test_tar_compresslevel_out_of_range(self):
        """测试 TAR 压缩级别超出范围"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.tar.gz",
            compression_format="TAR_GZ",
            compression_level=99,
        )
        compressor = TarfileCompression(config)
        self.assertEqual(compressor.compression_level, 6)

    def test_tar_invalid_source(self):
        """测试 TAR 压缩不存在的文件夹"""
        config = Config(
            folder_path="/nonexistent/folder",
            zipfile_path="test.tar.gz",
            compression_format="TAR_GZ",
        )
        compressor = TarfileCompression(config)
        result = compressor.compress()
        self.assertFalse(result["success"])

    def test_create_compressor_zip(self):
        """测试工厂函数创建 ZIP 压缩器"""
        config = Config(folder_path=self.test_dir, compression_format="ZIP")
        compressor = create_compressor(config)
        self.assertIsInstance(compressor, ZipfileCompression)

    def test_create_compressor_tar_gz(self):
        """测试工厂函数创建 TAR_GZ 压缩器"""
        config = Config(folder_path=self.test_dir, compression_format="TAR_GZ")
        compressor = create_compressor(config)
        self.assertIsInstance(compressor, TarfileCompression)

    def test_create_compressor_tar_bz2(self):
        """测试工厂函数创建 TAR_BZ2 压缩器"""
        config = Config(folder_path=self.test_dir, compression_format="TAR_BZ2")
        compressor = create_compressor(config)
        self.assertIsInstance(compressor, TarfileCompression)

    def test_create_compressor_tar_xz(self):
        """测试工厂函数创建 TAR_XZ 压缩器"""
        config = Config(folder_path=self.test_dir, compression_format="TAR_XZ")
        compressor = create_compressor(config)
        self.assertIsInstance(compressor, TarfileCompression)


class TestRestore(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_data"
        os.makedirs(self.test_dir, exist_ok=True)
        (Path(self.test_dir) / "file1.txt").write_text("test content 1")
        (Path(self.test_dir) / "subdir").mkdir()
        (Path(self.test_dir) / "subdir" / "file2.txt").write_text("test content 2")
        self.restore_dir = "test_restore"

    def tearDown(self):
        for d in [self.test_dir, self.restore_dir]:
            if os.path.exists(d):
                shutil.rmtree(d)
        for f in ["test.zip", "test.tar.gz"]:
            if os.path.exists(f):
                os.remove(f)

    def test_restore_zip(self):
        """测试从 ZIP 还原"""
        config = Config(folder_path=self.test_dir, zipfile_path="test.zip")
        ZipfileCompression(config).compress()
        result = restore_backup("test.zip", self.restore_dir)
        self.assertTrue(result["success"])
        self.assertTrue(
            os.path.exists(os.path.join(self.restore_dir, "test_data", "file1.txt"))
        )

    def test_restore_tar_gz(self):
        """测试从 tar.gz 还原"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.tar.gz",
            compression_format="TAR_GZ",
        )
        TarfileCompression(config).compress()
        result = restore_backup("test.tar.gz", self.restore_dir)
        self.assertTrue(result["success"])
        self.assertTrue(
            os.path.exists(os.path.join(self.restore_dir, "test_data", "file1.txt"))
        )

    def test_restore_nonexistent_file(self):
        """测试还原不存在的文件"""
        result = restore_backup("/nonexistent/backup.zip", self.restore_dir)
        self.assertFalse(result["success"])

    def test_restore_unknown_format(self):
        """测试还原未知格式"""
        Path("test.unknown").write_text("data")
        result = restore_backup("test.unknown", self.restore_dir)
        self.assertFalse(result["success"])
        os.remove("test.unknown")

    def test_restore_7z(self):
        """测试从 7z 还原"""
        config = Config(
            folder_path=self.test_dir, zipfile_path="test.7z", compression_format="7Z"
        )
        SevenZipCompression(config).compress()
        result = restore_backup("test.7z", self.restore_dir)
        self.assertTrue(result["success"])
        self.assertTrue(
            os.path.exists(os.path.join(self.restore_dir, "test_data", "file1.txt"))
        )
        os.remove("test.7z")

    def test_restore_tar_zst(self):
        """测试从 tar.zst 还原"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.tar.zst",
            compression_format="TAR_ZST",
        )
        ZstdCompression(config).compress()
        result = restore_backup("test.tar.zst", self.restore_dir)
        self.assertTrue(result["success"])
        self.assertTrue(
            os.path.exists(os.path.join(self.restore_dir, "test_data", "file1.txt"))
        )
        os.remove("test.tar.zst")

    @patch("builtins.print")
    def test_restore_permission_error(self, mock_print):
        """测试还原时权限不足"""
        config = Config(folder_path=self.test_dir, zipfile_path="test.zip")
        ZipfileCompression(config).compress()
        with patch("zipfile.ZipFile") as mock_zf:
            mock_zf.return_value.__enter__ = MagicMock(
                side_effect=PermissionError("denied")
            )
            mock_zf.return_value.__exit__ = MagicMock(return_value=False)
            result = restore_backup("test.zip", self.restore_dir)
        self.assertFalse(result["success"])

    @patch("builtins.print")
    def test_restore_os_error(self, mock_print):
        """测试还原时 OS 错误"""
        config = Config(folder_path=self.test_dir, zipfile_path="test.zip")
        ZipfileCompression(config).compress()
        with patch("zipfile.ZipFile") as mock_zf:
            mock_zf.return_value.__enter__ = MagicMock(
                side_effect=OSError("disk error")
            )
            mock_zf.return_value.__exit__ = MagicMock(return_value=False)
            result = restore_backup("test.zip", self.restore_dir)
        self.assertFalse(result["success"])

    @patch("builtins.print")
    def test_restore_7z_permission_error(self, mock_print):
        """测试 7z 还原时权限不足"""
        config = Config(
            folder_path=self.test_dir, zipfile_path="test.7z", compression_format="7Z"
        )
        SevenZipCompression(config).compress()
        with patch("py7zr.SevenZipFile") as mock_7z:
            mock_7z.return_value.__enter__ = MagicMock(
                side_effect=PermissionError("denied")
            )
            mock_7z.return_value.__exit__ = MagicMock(return_value=False)
            result = restore_backup("test.7z", self.restore_dir)
        self.assertFalse(result["success"])
        os.remove("test.7z")


class TestPathMatching(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_data"
        os.makedirs(self.test_dir, exist_ok=True)
        (Path(self.test_dir) / "file1.txt").write_text("a")
        (Path(self.test_dir) / "subdir").mkdir()
        (Path(self.test_dir) / "subdir" / "file2.log").write_text("b")
        (Path(self.test_dir) / "subdir" / "file3.txt").write_text("c")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        for f in ["test.zip"]:
            if os.path.exists(f):
                os.remove(f)

    def test_path_pattern_matching(self):
        """测试路径级忽略模式 subdir/*.log"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.zip",
            skip_patterns=["subdir/*.log"],
        )
        compressor = ZipfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        with zipfile.ZipFile("test.zip", "r") as zf:
            names = zf.namelist()
            self.assertIn("test_data/file1.txt", names)
            self.assertIn("test_data/subdir/file3.txt", names)
            self.assertNotIn("test_data/subdir/file2.log", names)

    def test_basename_pattern_still_works(self):
        """测试基础文件名模式仍然有效"""
        config = Config(
            folder_path=self.test_dir, zipfile_path="test.zip", skip_patterns=["*.log"]
        )
        compressor = ZipfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        with zipfile.ZipFile("test.zip", "r") as zf:
            names = zf.namelist()
            self.assertNotIn("test_data/subdir/file2.log", names)


class TestTarNoCompression(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_data"
        os.makedirs(self.test_dir, exist_ok=True)
        (Path(self.test_dir) / "file1.txt").write_text("test")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        for f in ["test.tar"]:
            if os.path.exists(f):
                os.remove(f)

    def test_tar_no_compression(self):
        """测试不压缩的 tar 格式"""
        config = Config(
            folder_path=self.test_dir, zipfile_path="test.tar", compression_format="TAR"
        )
        compressor = TarfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists("test.tar"))

    @patch("builtins.print")
    def test_tar_permission_error(self, mock_print):
        """测试 tar 压缩时权限不足"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="/root/test.tar",
            compression_format="TAR",
        )
        compressor = TarfileCompression(config)
        result = compressor.compress()
        self.assertFalse(result["success"])

    @patch("builtins.print")
    def test_tar_os_error(self, mock_print):
        """测试 tar 压缩时系统错误"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.tar",
            compression_format="TAR",
        )
        compressor = TarfileCompression(config)
        with patch("tarfile.open", side_effect=OSError("disk error")):
            result = compressor.compress()
        self.assertFalse(result["success"])

    @patch("builtins.print")
    def test_tar_unknown_exception(self, mock_print):
        """测试 tar 压缩时未知异常"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.tar",
            compression_format="TAR",
        )
        compressor = TarfileCompression(config)
        with patch("tarfile.open", side_effect=RuntimeError("unexpected")):
            result = compressor.compress()
        self.assertFalse(result["success"])


class TestZstdCompression(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_data"
        os.makedirs(self.test_dir, exist_ok=True)
        (Path(self.test_dir) / "file1.txt").write_text("test content")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        for f in ["test.tar.zst"]:
            if os.path.exists(f):
                os.remove(f)

    def test_zstd_basic(self):
        """测试 tar.zst 基本压缩"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.tar.zst",
            compression_format="TAR_ZST",
        )
        compressor = ZstdCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists("test.tar.zst"))

    def test_zstd_compresslevel_out_of_range(self):
        """测试 zstd 压缩级别超出范围"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.tar.zst",
            compression_format="TAR_ZST",
            compression_level=99,
        )
        compressor = ZstdCompression(config)
        self.assertEqual(compressor.compression_level, 3)

    def test_create_compressor_zstd(self):
        """测试工厂函数创建 Zstd 压缩器"""
        config = Config(folder_path=self.test_dir, compression_format="TAR_ZST")
        compressor = create_compressor(config)
        self.assertIsInstance(compressor, ZstdCompression)

    def test_zstd_invalid_source(self):
        """测试 zstd 压缩不存在的文件夹"""
        config = Config(
            folder_path="/nonexistent",
            zipfile_path="test.tar.zst",
            compression_format="TAR_ZST",
        )
        compressor = ZstdCompression(config)
        result = compressor.compress()
        self.assertFalse(result["success"])

    @patch("builtins.print")
    def test_zstd_permission_error(self, mock_print):
        """测试 zstd 压缩权限不足"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="/root/test.tar.zst",
            compression_format="TAR_ZST",
        )
        compressor = ZstdCompression(config)
        result = compressor.compress()
        self.assertFalse(result["success"])

    @patch("builtins.print")
    def test_zstd_os_error(self, mock_print):
        """测试 zstd 压缩系统错误"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.tar.zst",
            compression_format="TAR_ZST",
        )
        compressor = ZstdCompression(config)
        with patch("zstandard.ZstdCompressor", side_effect=OSError("error")):
            result = compressor.compress()
        self.assertFalse(result["success"])

    @patch("builtins.print")
    def test_zstd_unknown_exception(self, mock_print):
        """测试 zstd 压缩未知异常"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.tar.zst",
            compression_format="TAR_ZST",
        )
        compressor = ZstdCompression(config)
        with patch("zstandard.ZstdCompressor", side_effect=RuntimeError("unexpected")):
            result = compressor.compress()
        self.assertFalse(result["success"])


class TestSevenZipCompression(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_data"
        os.makedirs(self.test_dir, exist_ok=True)
        (Path(self.test_dir) / "file1.txt").write_text("test content")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        for f in ["test.7z"]:
            if os.path.exists(f):
                os.remove(f)

    def test_7z_basic(self):
        """测试 7z 基本压缩"""
        config = Config(
            folder_path=self.test_dir, zipfile_path="test.7z", compression_format="7Z"
        )
        compressor = SevenZipCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists("test.7z"))

    def test_7z_compresslevel_out_of_range(self):
        """测试 7z 压缩级别超出范围"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.7z",
            compression_format="7Z",
            compression_level=99,
        )
        compressor = SevenZipCompression(config)
        self.assertEqual(compressor.compression_level, 6)

    def test_create_compressor_7z(self):
        """测试工厂函数创建 7z 压缩器"""
        config = Config(folder_path=self.test_dir, compression_format="7Z")
        compressor = create_compressor(config)
        self.assertIsInstance(compressor, SevenZipCompression)

    def test_7z_invalid_source(self):
        """测试 7z 压缩不存在的文件夹"""
        config = Config(
            folder_path="/nonexistent", zipfile_path="test.7z", compression_format="7Z"
        )
        compressor = SevenZipCompression(config)
        result = compressor.compress()
        self.assertFalse(result["success"])

    @patch("builtins.print")
    def test_7z_permission_error(self, mock_print):
        """测试 7z 压缩权限不足"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="/root/test.7z",
            compression_format="7Z",
        )
        compressor = SevenZipCompression(config)
        result = compressor.compress()
        self.assertFalse(result["success"])

    @patch("builtins.print")
    def test_7z_os_error(self, mock_print):
        """测试 7z 压缩系统错误"""
        config = Config(
            folder_path=self.test_dir, zipfile_path="test.7z", compression_format="7Z"
        )
        compressor = SevenZipCompression(config)
        with patch("py7zr.SevenZipFile", side_effect=OSError("error")):
            result = compressor.compress()
        self.assertFalse(result["success"])

    def test_7z_with_password(self):
        """测试 7z 加密压缩"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path="test.7z",
            compression_format="7Z",
            password="secret123",
        )
        compressor = SevenZipCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists("test.7z"))
        import py7zr

        with py7zr.SevenZipFile("test.7z", "r", password="secret123") as szf:
            names = szf.getnames()
            self.assertGreater(len(names), 0)

    @patch("builtins.print")
    def test_7z_unknown_exception(self, mock_print):
        """测试 7z 压缩未知异常"""
        config = Config(
            folder_path=self.test_dir, zipfile_path="test.7z", compression_format="7Z"
        )
        compressor = SevenZipCompression(config)
        with patch("py7zr.SevenZipFile", side_effect=RuntimeError("unexpected")):
            result = compressor.compress()
        self.assertFalse(result["success"])


class TestCreateCompressor(unittest.TestCase):
    """测试工厂函数 create_compressor 的各种格式"""

    def test_create_compressor_tar(self):
        """测试工厂函数创建 TAR 压缩器"""
        config = Config(folder_path=".", compression_format="TAR")
        compressor = create_compressor(config)
        self.assertIsInstance(compressor, TarfileCompression)

    def test_create_compressor_tar_gz_with_dot(self):
        """测试 tar.gz（带点号）格式正确匹配 TarfileCompression"""
        config = Config(folder_path=".", compression_format="tar.gz")
        compressor = create_compressor(config)
        self.assertIsInstance(compressor, TarfileCompression)

    def test_create_compressor_tar_bz2_with_dot(self):
        """测试 tar.bz2（带点号）格式正确匹配"""
        config = Config(folder_path=".", compression_format="tar.bz2")
        compressor = create_compressor(config)
        self.assertIsInstance(compressor, TarfileCompression)

    def test_create_compressor_tar_xz_with_dot(self):
        """测试 tar.xz（带点号）格式正确匹配"""
        config = Config(folder_path=".", compression_format="tar.xz")
        compressor = create_compressor(config)
        self.assertIsInstance(compressor, TarfileCompression)

    def test_create_compressor_tar_zst_with_dot(self):
        """测试 tar.zst（带点号）格式正确匹配"""
        config = Config(folder_path=".", compression_format="tar.zst")
        compressor = create_compressor(config)
        self.assertIsInstance(compressor, ZstdCompression)


class TestShouldIgnore(unittest.TestCase):
    """测试 _should_ignore 模式匹配"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.test_dir, "sub"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_should_ignore_directory_pattern(self):
        """测试忽略目录模式"""
        config = Config(folder_path=self.test_dir, skip_patterns=["sub"])
        compressor = ZipfileCompression(config)
        self.assertTrue(compressor._should_ignore("sub"))

    def test_should_ignore_no_match(self):
        """测试不匹配时不忽略"""
        config = Config(folder_path=self.test_dir, skip_patterns=["*.log"])
        compressor = ZipfileCompression(config)
        self.assertFalse(compressor._should_ignore("readme.txt"))

    def test_should_ignore_basename_match(self):
        """测试 basename 匹配"""
        config = Config(folder_path=self.test_dir, skip_patterns=["*.log"])
        compressor = ZipfileCompression(config)
        self.assertTrue(compressor._should_ignore("subdir/error.log"))


class TestListBackupContents(unittest.TestCase):
    """测试 list_backup_contents 函数"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        (Path(self.test_dir) / "file1.txt").write_text("content1")
        (Path(self.test_dir) / "sub").mkdir()
        (Path(self.test_dir) / "sub" / "file2.txt").write_text("content2")
        self.zip_path = os.path.join(self.test_dir, "test.zip")
        config = Config(folder_path=self.test_dir, zipfile_path=self.zip_path)
        ZipfileCompression(config).compress()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_list_zip_contents(self):
        """测试列出 ZIP 文件内容"""
        result = list_backup_contents(self.zip_path)
        self.assertIn("file1.txt", result)
        self.assertIn("file2.txt", result)
        self.assertIn("2 files", result)

    def test_list_nonexistent_file(self):
        """测试列出不存在的文件"""
        result = list_backup_contents("/nonexistent/file.zip")
        self.assertIn("/nonexistent/file.zip", result)

    def test_list_unknown_format(self):
        """测试列出未知格式文件（返回空列表提示）"""
        unknown = os.path.join(self.test_dir, "test.xyz")
        Path(unknown).write_text("data")
        result = list_backup_contents(unknown)
        self.assertIn("test.xyz", result)


class TestVerifyBackup(unittest.TestCase):
    """测试 verify_backup 函数"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        (Path(self.test_dir) / "file1.txt").write_text("content1")
        (Path(self.test_dir) / "sub").mkdir()
        (Path(self.test_dir) / "sub" / "file2.txt").write_text("content2")
        self.zip_path = os.path.join(self.test_dir, "test.zip")
        config = Config(folder_path=self.test_dir, zipfile_path=self.zip_path)
        ZipfileCompression(config).compress()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_verify_valid_zip(self):
        """测试校验有效 ZIP 文件"""
        result = verify_backup(self.zip_path)
        self.assertTrue(result["success"])
        self.assertEqual(result["files_count"], 2)

    def test_verify_nonexistent(self):
        """测试校验不存在的文件"""
        result = verify_backup("/nonexistent/file.zip")
        self.assertFalse(result["success"])


class TestSbackupIgnore(unittest.TestCase):
    """测试 .sbackupignore 文件支持"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        (Path(self.test_dir) / "keep.txt").write_text("keep")
        (Path(self.test_dir) / "skip.log").write_text("skip")
        (Path(self.test_dir) / "sub").mkdir()
        (Path(self.test_dir) / "sub" / "data.txt").write_text("data")
        self.zip_path = os.path.join(self.test_dir, "test.zip")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_ignore_file_loaded(self):
        """测试 .sbackupignore 文件中的规则生效"""
        (Path(self.test_dir) / ".sbackupignore").write_text("*.log\n# comment\n")
        config = Config(
            folder_path=self.test_dir,
            zipfile_path=self.zip_path,
            skip_patterns=[],
        )
        compressor = ZipfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            names = zf.namelist()
            self.assertTrue(any(n.endswith("keep.txt") for n in names))
            self.assertFalse(any(n.endswith("skip.log") for n in names))

    def test_ignore_file_not_present(self):
        """测试没有 .sbackupignore 时不影响正常压缩"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path=self.zip_path,
            skip_patterns=[],
        )
        compressor = ZipfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            names = zf.namelist()
            self.assertTrue(any(n.endswith("keep.txt") for n in names))
            self.assertTrue(any(n.endswith("skip.log") for n in names))


class TestPatternNegation(unittest.TestCase):
    """测试 ! 取反模式"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        (Path(self.test_dir) / "a.log").write_text("log")
        (Path(self.test_dir) / "b.log").write_text("log")
        (Path(self.test_dir) / "important.log").write_text("important")
        self.zip_path = os.path.join(self.test_dir, "test.zip")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_negation_restores_file(self):
        """测试 ! 模式恢复被忽略的文件"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path=self.zip_path,
            skip_patterns=["*.log", "!important.log"],
        )
        compressor = ZipfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            names = zf.namelist()
            self.assertFalse(any(n.endswith("a.log") for n in names))
            self.assertFalse(any(n.endswith("b.log") for n in names))
            self.assertTrue(any(n.endswith("important.log") for n in names))


if __name__ == "__main__":
    unittest.main()
