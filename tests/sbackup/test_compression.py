"""
单元测试 for sbackup.compression 模块
"""
import unittest
import os
import shutil
import zipfile
from pathlib import Path
from unittest.mock import patch
from sbackup.config import Config
from sbackup.compression import ZipfileCompression
from sbackup.i18n import t


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

    def test_zip_internal_path_structure(self):
        """测试 ZIP 内部路径结构正确（以文件夹名开头，而非绝对路径）"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path=self.zip_path,
        )
        compressor = ZipfileCompression(config)
        compressor.zip_folder()

        with zipfile.ZipFile(self.zip_path, "r") as zf:
            namelist = zf.namelist()
            for name in namelist:
                self.assertTrue(
                    name.startswith("test_data/"),
                    f"ZIP 内部路径 '{name}' 应以 'test_data/' 开头"
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
        result = compressor.zip_folder()

        self.assertTrue(result["success"])
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            namelist = zf.namelist()
            self.assertNotIn("test_data/.gitignore", namelist)

    @patch("builtins.print")
    def test_compresslevel_out_of_range(self, mock_print):
        """测试压缩级别超出范围时回退到默认值"""
        config = Config(
            folder_path=self.test_dir,
            zipfile_path=self.zip_path,
            compression_level=99,
        )
        compressor = ZipfileCompression(config)
        # compresslevel 应回退到 6
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
        config = Config(
            folder_path=self.test_dir,
            zipfile_path=self.zip_path,
        )
        compressor = ZipfileCompression(config)
        # 第一次压缩
        compressor.zip_folder()
        # 第二次压缩（文件已存在）
        compressor.zip_folder()
        printed = " ".join(str(call) for call in mock_print.call_args_list)
        self.assertIn(t("warn.zip.overwrite").split("{")[0], printed)


if __name__ == "__main__":
    unittest.main()