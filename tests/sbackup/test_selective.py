"""
单元测试 for sbackup.selective 模块
"""

import os
import shutil
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path


class TestSelectiveRestoreZip(unittest.TestCase):
    """ZIP 格式的 SelectiveRestore 测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_test_")
        self.archive_path = os.path.join(self.test_dir, "test_backup.zip")
        self.extract_dir = os.path.join(self.test_dir, "extract")

        # 创建测试文件结构
        self.src_dir = os.path.join(self.test_dir, "src")
        os.makedirs(os.path.join(self.src_dir, "pkg"))
        Path(os.path.join(self.src_dir, "main.py")).write_text("print('hello')")
        Path(os.path.join(self.src_dir, "utils.py")).write_text("# utils")
        Path(os.path.join(self.src_dir, "pkg", "__init__.py")).write_text("")
        Path(os.path.join(self.src_dir, "pkg", "core.py")).write_text("# core")
        Path(os.path.join(self.src_dir, "data.csv")).write_text("a,b,c\n1,2,3")
        Path(os.path.join(self.src_dir, "readme.txt")).write_text("Readme")

        # 创建 ZIP
        with zipfile.ZipFile(self.archive_path, "w") as zf:
            for root, dirs, files in os.walk(self.src_dir):
                for fn in files:
                    full = os.path.join(root, fn)
                    arcname = os.path.relpath(full, self.test_dir).replace("\\", "/")
                    zf.write(full, arcname)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_list_files_all(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        files = sr.list_files()
        names = [f["name"] for f in files]
        self.assertIn("src/main.py", names)
        self.assertIn("src/utils.py", names)
        self.assertIn("src/data.csv", names)
        self.assertIn("src/pkg/core.py", names)

    def test_list_files_with_pattern(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        files = sr.list_files("*.py")
        names = [f["name"] for f in files]
        self.assertIn("src/main.py", names)
        self.assertIn("src/utils.py", names)
        self.assertIn("src/pkg/core.py", names)
        self.assertNotIn("src/data.csv", names)

    def test_list_files_returns_size(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        files = sr.list_files()
        for f in files:
            if not f["is_dir"]:
                self.assertGreaterEqual(f["size"], 0)

    def test_search_keyword(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        results = sr.search("main")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "src/main.py")

    def test_search_case_insensitive(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        results = sr.search("MAIN")
        self.assertEqual(len(results), 1)

    def test_search_no_results(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        results = sr.search("nonexistent")
        self.assertEqual(len(results), 0)

    def test_extract_files(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        count, paths = sr.extract_files(["src/main.py"], self.extract_dir)
        self.assertEqual(count, 1)
        self.assertTrue(
            os.path.exists(os.path.join(self.extract_dir, "src", "main.py"))
        )

    def test_extract_files_glob(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        count, paths = sr.extract_files(["src/*.py"], self.extract_dir)
        # fnmatch * matches / so src/*.py also matches src/pkg/__init__.py, src/pkg/core.py
        self.assertEqual(count, 4)  # main.py, utils.py, pkg/__init__.py, pkg/core.py
        self.assertTrue(
            os.path.exists(os.path.join(self.extract_dir, "src", "main.py"))
        )
        self.assertTrue(
            os.path.exists(os.path.join(self.extract_dir, "src", "utils.py"))
        )

    def test_extract_files_multiple_patterns(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        count, paths = sr.extract_files(["src/*.py", "src/data.csv"], self.extract_dir)
        self.assertEqual(count, 5)  # 4 py files + data.csv

    def test_extract_single(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        result = sr.extract_single("src/main.py", self.extract_dir)
        self.assertIsNotNone(result)
        self.assertTrue(os.path.exists(result))

    def test_extract_single_not_found(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        result = sr.extract_single("nonexistent.txt", self.extract_dir)
        self.assertIsNone(result)

    def test_extract_preserves_directory_structure(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        count, paths = sr.extract_files(["src/pkg/core.py"], self.extract_dir)
        self.assertEqual(count, 1)
        expected = os.path.join(self.extract_dir, "src", "pkg", "core.py")
        self.assertTrue(os.path.exists(expected))

    def test_get_stats(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        stats = sr.get_stats()
        self.assertGreater(stats["total_files"], 0)
        self.assertEqual(stats["total_dirs"], 0)
        self.assertGreater(stats["total_size"], 0)
        self.assertIn(".py", stats["formats"])

    def test_extract_files_no_match(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        count, paths = sr.extract_files(["*.xyz"], self.extract_dir)
        self.assertEqual(count, 0)
        self.assertEqual(paths, [])


class TestSelectiveRestoreTar(unittest.TestCase):
    """tar.gz 格式的 SelectiveRestore 测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_test_")
        self.archive_path = os.path.join(self.test_dir, "test_backup.tar.gz")
        self.extract_dir = os.path.join(self.test_dir, "extract")

        # 创建测试文件
        src_dir = os.path.join(self.test_dir, "src")
        os.makedirs(src_dir)
        Path(os.path.join(src_dir, "file_a.txt")).write_text("content a")
        Path(os.path.join(src_dir, "file_b.py")).write_text("content b")

        with tarfile.open(self.archive_path, "w:gz") as tarf:
            tarf.add(os.path.join(src_dir, "file_a.txt"), arcname="src/file_a.txt")
            tarf.add(os.path.join(src_dir, "file_b.py"), arcname="src/file_b.py")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_list_files_tar(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        files = sr.list_files()
        names = [f["name"] for f in files]
        self.assertIn("src/file_a.txt", names)
        self.assertIn("src/file_b.py", names)

    def test_list_files_tar_with_pattern(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        files = sr.list_files("*.py")
        names = [f["name"] for f in files]
        self.assertIn("src/file_b.py", names)
        self.assertNotIn("src/file_a.txt", names)

    def test_search_tar(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        results = sr.search("file_a")
        self.assertEqual(len(results), 1)

    def test_extract_files_tar(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        count, paths = sr.extract_files(["src/file_b.py"], self.extract_dir)
        self.assertEqual(count, 1)
        self.assertTrue(
            os.path.exists(os.path.join(self.extract_dir, "src", "file_b.py"))
        )

    def test_get_stats_tar(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        stats = sr.get_stats()
        self.assertEqual(stats["total_files"], 2)
        self.assertGreater(stats["total_size"], 0)


class TestSelectiveRestoreTarBz2(unittest.TestCase):
    """tar.bz2 格式的 SelectiveRestore 测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_test_")
        self.archive_path = os.path.join(self.test_dir, "test_backup.tar.bz2")
        self.extract_dir = os.path.join(self.test_dir, "extract")

        src_dir = os.path.join(self.test_dir, "data")
        os.makedirs(src_dir)
        Path(os.path.join(src_dir, "report.csv")).write_text("x,y\n1,2")

        with tarfile.open(self.archive_path, "w:bz2") as tarf:
            tarf.add(os.path.join(src_dir, "report.csv"), arcname="data/report.csv")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_list_files_tar_bz2(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        files = sr.list_files()
        names = [f["name"] for f in files]
        self.assertIn("data/report.csv", names)

    def test_extract_files_tar_bz2(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        count, _ = sr.extract_files(["data/report.csv"], self.extract_dir)
        self.assertEqual(count, 1)
        self.assertTrue(
            os.path.exists(os.path.join(self.extract_dir, "data", "report.csv"))
        )


class TestSelectiveRestoreTarXz(unittest.TestCase):
    """tar.xz 格式的 SelectiveRestore 测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_test_")
        self.archive_path = os.path.join(self.test_dir, "test_backup.tar.xz")
        self.extract_dir = os.path.join(self.test_dir, "extract")

        src_dir = os.path.join(self.test_dir, "docs")
        os.makedirs(src_dir)
        Path(os.path.join(src_dir, "guide.txt")).write_text("guide content")

        with tarfile.open(self.archive_path, "w:xz") as tarf:
            tarf.add(os.path.join(src_dir, "guide.txt"), arcname="docs/guide.txt")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_list_files_tar_xz(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        files = sr.list_files()
        names = [f["name"] for f in files]
        self.assertIn("docs/guide.txt", names)

    def test_extract_files_tar_xz(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        count, _ = sr.extract_files(["docs/guide.txt"], self.extract_dir)
        self.assertEqual(count, 1)


class TestSelectiveRestoreTarZst(unittest.TestCase):
    """tar.zst 格式的 SelectiveRestore 测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_test_")
        self.archive_path = os.path.join(self.test_dir, "test_backup.tar.zst")
        self.extract_dir = os.path.join(self.test_dir, "extract")

        src_dir = os.path.join(self.test_dir, "logs")
        os.makedirs(src_dir)
        Path(os.path.join(src_dir, "app.log")).write_text("log line 1\nlog line 2")

        try:
            import zstandard as zstd

            with open(self.archive_path, "wb") as f_out:
                cctx = zstd.ZstdCompressor(level=3)
                compressor = cctx.stream_writer(f_out)
                with tarfile.open(fileobj=compressor, mode="w") as tarf:
                    tarf.add(os.path.join(src_dir, "app.log"), arcname="logs/app.log")
                compressor.close()
        except ImportError:
            self.skipTest("zstandard not installed")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_list_files_tar_zst(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        files = sr.list_files()
        names = [f["name"] for f in files]
        self.assertIn("logs/app.log", names)

    def test_extract_files_tar_zst(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        count, _ = sr.extract_files(["logs/app.log"], self.extract_dir)
        self.assertEqual(count, 1)
        self.assertTrue(
            os.path.exists(os.path.join(self.extract_dir, "logs", "app.log"))
        )


class TestSelectiveRestore7z(unittest.TestCase):
    """7z 格式的 SelectiveRestore 测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_test_")
        self.archive_path = os.path.join(self.test_dir, "test_backup.7z")
        self.extract_dir = os.path.join(self.test_dir, "extract")

        src_dir = os.path.join(self.test_dir, "project")
        os.makedirs(src_dir)
        Path(os.path.join(src_dir, "main.py")).write_text("x = 1")
        Path(os.path.join(src_dir, "data.txt")).write_text("data")

        try:
            import py7zr

            with py7zr.SevenZipFile(self.archive_path, mode="w") as szf:
                szf.write(os.path.join(src_dir, "main.py"), arcname="project/main.py")
                szf.write(os.path.join(src_dir, "data.txt"), arcname="project/data.txt")
        except ImportError:
            self.skipTest("py7zr not installed")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_list_files_7z(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        files = sr.list_files()
        names = [f["name"] for f in files]
        self.assertIn("project/main.py", names)
        self.assertIn("project/data.txt", names)

    def test_list_files_7z_with_pattern(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        files = sr.list_files("*.py")
        names = [f["name"] for f in files]
        self.assertIn("project/main.py", names)
        self.assertNotIn("project/data.txt", names)

    def test_search_7z(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        results = sr.search("main")
        self.assertEqual(len(results), 1)

    def test_extract_files_7z(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        count, paths = sr.extract_files(["project/main.py"], self.extract_dir)
        self.assertEqual(count, 1)
        self.assertTrue(
            os.path.exists(os.path.join(self.extract_dir, "project", "main.py"))
        )

    def test_get_stats_7z(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        stats = sr.get_stats()
        self.assertEqual(stats["total_files"], 2)


class TestSelectiveRestoreNonexistent(unittest.TestCase):
    """处理不存在的文件"""

    def test_list_files_nonexistent(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore("/nonexistent/path/archive.zip")
        with self.assertRaises(Exception):
            sr.list_files()

    def test_search_nonexistent(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore("/nonexistent/path/archive.zip")
        with self.assertRaises(Exception):
            sr.search("test")

    def test_extract_nonexistent(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore("/nonexistent/path/archive.zip")
        with self.assertRaises(Exception):
            sr.extract_files(["*.py"], "/tmp/output")

    def test_get_stats_nonexistent(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore("/nonexistent/path/archive.zip")
        with self.assertRaises(Exception):
            sr.get_stats()


class TestSelectiveRestoreTarPlain(unittest.TestCase):
    """纯 tar 格式（无压缩）测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_test_")
        self.archive_path = os.path.join(self.test_dir, "test_backup.tar")
        self.extract_dir = os.path.join(self.test_dir, "extract")

        src_dir = os.path.join(self.test_dir, "assets")
        os.makedirs(src_dir)
        Path(os.path.join(src_dir, "style.css")).write_text("body { color: red; }")

        with tarfile.open(self.archive_path, "w") as tarf:
            tarf.add(os.path.join(src_dir, "style.css"), arcname="assets/style.css")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_list_files_tar_plain(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        files = sr.list_files()
        names = [f["name"] for f in files]
        self.assertIn("assets/style.css", names)

    def test_extract_files_tar_plain(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        count, _ = sr.extract_files(["assets/style.css"], self.extract_dir)
        self.assertEqual(count, 1)


class TestSelectiveRestoreDirectoryEntries(unittest.TestCase):
    """测试目录条目处理"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_test_")
        self.archive_path = os.path.join(self.test_dir, "test_dirs.zip")
        self.extract_dir = os.path.join(self.test_dir, "extract")

        # 创建含目录结构的 ZIP
        with zipfile.ZipFile(self.archive_path, "w") as zf:
            zf.writestr("root_dir/", "")
            zf.writestr("root_dir/sub_dir/", "")
            zf.writestr("root_dir/sub_dir/file.txt", "content")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_list_files_marks_dirs(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        files = sr.list_files()
        dirs = [f for f in files if f["is_dir"]]
        regular_files = [f for f in files if not f["is_dir"]]
        self.assertGreater(len(dirs), 0)
        self.assertGreater(len(regular_files), 0)

    def test_extract_files_skips_dirs(self):
        from sbackup.selective import SelectiveRestore

        sr = SelectiveRestore(self.archive_path)
        count, _ = sr.extract_files(["root_dir/sub_dir/file.txt"], self.extract_dir)
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
