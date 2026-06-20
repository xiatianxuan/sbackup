"""单元测试 for sbackup.cross_search 模块"""

import os
import shutil
import tarfile
import tempfile
import time
import unittest
import zipfile
from pathlib import Path


class TestCrossSearcherScanArchives(unittest.TestCase):
    """测试 scan_archives 方法"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_xsearch_test_")
        self.scan_dir = os.path.join(self.test_dir, "archives")
        os.makedirs(self.scan_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_zip(self, name: str, files: dict[str, str]) -> str:
        path = os.path.join(self.scan_dir, name)
        with zipfile.ZipFile(path, "w") as zf:
            for arcname, content in files.items():
                zf.writestr(arcname, content)
        return path

    def _create_tar(self, name: str, files: dict[str, str]) -> str:
        path = os.path.join(self.scan_dir, name)
        with tarfile.open(path, "w") as tarf:
            for arcname, content in files.items():
                import io

                data = content.encode("utf-8")
                info = tarfile.TarInfo(name=arcname)
                info.size = len(data)
                tarf.addfile(info, io.BytesIO(data))
        return path

    def _create_tar_gz(self, name: str, files: dict[str, str]) -> str:
        path = os.path.join(self.scan_dir, name)
        with tarfile.open(path, "w:gz") as tarf:
            for arcname, content in files.items():
                import io

                data = content.encode("utf-8")
                info = tarfile.TarInfo(name=arcname)
                info.size = len(data)
                tarf.addfile(info, io.BytesIO(data))
        return path

    def test_scan_finds_zip(self):
        self._create_zip("backup1.zip", {"a.txt": "hello", "b.py": "code"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        archives = searcher.scan_archives()
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0]["format"], "ZIP")
        self.assertTrue(archives[0]["path"].endswith("backup1.zip"))

    def test_scan_finds_tar(self):
        self._create_tar("backup2.tar", {"x.log": "log"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        archives = searcher.scan_archives()
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0]["format"], "TAR")

    def test_scan_finds_tar_gz(self):
        self._create_tar_gz("backup3.tar.gz", {"data.csv": "a,b"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        archives = searcher.scan_archives()
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0]["format"], "TAR_GZ")

    def test_scan_finds_multiple_formats(self):
        self._create_zip("a.zip", {"f1.txt": "1"})
        self._create_tar("b.tar", {"f2.txt": "2"})
        self._create_tar_gz("c.tar.gz", {"f3.txt": "3"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        archives = searcher.scan_archives()
        self.assertEqual(len(archives), 3)
        formats = {a["format"] for a in archives}
        self.assertEqual(formats, {"ZIP", "TAR", "TAR_GZ"})

    def test_scan_ignores_non_archive(self):
        self._create_zip("good.zip", {"a.txt": "1"})
        Path(os.path.join(self.scan_dir, "readme.txt")).write_text("nope")
        Path(os.path.join(self.scan_dir, "data.csv")).write_text("nope")
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        archives = searcher.scan_archives()
        self.assertEqual(len(archives), 1)

    def test_scan_sorted_by_mtime_desc(self):
        path1 = self._create_zip("old.zip", {"a.txt": "1"})
        # ensure different mtime
        old_time = time.time() - 100
        os.utime(path1, (old_time, old_time))
        self._create_zip("new.zip", {"b.txt": "2"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        archives = searcher.scan_archives()
        self.assertEqual(len(archives), 2)
        self.assertTrue(archives[0]["path"].endswith("new.zip"))
        self.assertTrue(archives[1]["path"].endswith("old.zip"))

    def test_scan_nonexistent_dir(self):
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher(["/nonexistent/path/xyz"])
        archives = searcher.scan_archives()
        self.assertEqual(archives, [])


class TestCrossSearcherSearch(unittest.TestCase):
    """测试 search 关键字搜索"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_xsearch_test_")
        self.scan_dir = os.path.join(self.test_dir, "archives")
        os.makedirs(self.scan_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_zip(self, name: str, files: dict[str, str]) -> str:
        path = os.path.join(self.scan_dir, name)
        with zipfile.ZipFile(path, "w") as zf:
            for arcname, content in files.items():
                zf.writestr(arcname, content)
        return path

    def test_keyword_search_basic(self):
        self._create_zip(
            "backup.zip",
            {
                "src/main.py": "code",
                "src/utils.py": "utils",
                "docs/readme.txt": "readme",
            },
        )
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search("main")
        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0].members), 1)
        self.assertEqual(results[0].members[0]["name"], "src/main.py")

    def test_keyword_search_case_insensitive(self):
        self._create_zip("backup.zip", {"LOG/Error.log": "err"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search("error")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].members[0]["name"], "LOG/Error.log")

    def test_keyword_search_no_match(self):
        self._create_zip("backup.zip", {"a.txt": "1"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search("zzz_nonexistent_zzz")
        self.assertEqual(results, [])

    def test_keyword_search_across_archives(self):
        self._create_zip("a.zip", {"file_main.py": "1"})
        self._create_zip("b.zip", {"file_main.txt": "2"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search("main")
        self.assertEqual(len(results), 2)

    def test_keyword_search_result_metadata(self):
        self._create_zip("backup.zip", {"test.py": "code"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search("test")
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertTrue(r.archive.endswith("backup.zip"))
        self.assertGreater(r.archive_size, 0)
        self.assertNotEqual(r.archive_mtime, "")


class TestCrossSearcherSearchByPattern(unittest.TestCase):
    """测试 search_by_pattern glob 搜索"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_xsearch_test_")
        self.scan_dir = os.path.join(self.test_dir, "archives")
        os.makedirs(self.scan_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_zip(self, name: str, files: dict[str, str]) -> str:
        path = os.path.join(self.scan_dir, name)
        with zipfile.ZipFile(path, "w") as zf:
            for arcname, content in files.items():
                zf.writestr(arcname, content)
        return path

    def test_pattern_match_glob(self):
        self._create_zip(
            "backup.zip",
            {"src/main.py": "code", "src/utils.py": "u", "docs/readme.txt": "r"},
        )
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search_by_pattern("*.py")
        self.assertEqual(len(results), 1)
        names = {m["name"] for m in results[0].members}
        self.assertEqual(names, {"src/main.py", "src/utils.py"})

    def test_pattern_match_with_path(self):
        self._create_zip(
            "backup.zip",
            {"logs/app.log": "log1", "logs/error.log": "log2", "src/main.py": "code"},
        )
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search_by_pattern("*.log")
        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0].members), 2)

    def test_pattern_no_match(self):
        self._create_zip("backup.zip", {"a.txt": "1"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search_by_pattern("*.xyz")
        self.assertEqual(results, [])


class TestCrossSearcherSearchByExtension(unittest.TestCase):
    """测试 search_by_extension 扩展名搜索"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_xsearch_test_")
        self.scan_dir = os.path.join(self.test_dir, "archives")
        os.makedirs(self.scan_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_zip(self, name: str, files: dict[str, str]) -> str:
        path = os.path.join(self.scan_dir, name)
        with zipfile.ZipFile(path, "w") as zf:
            for arcname, content in files.items():
                zf.writestr(arcname, content)
        return path

    def test_ext_search(self):
        self._create_zip(
            "backup.zip",
            {"src/main.py": "code", "docs/readme.txt": "r", "src/utils.py": "u"},
        )
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search_by_extension(".py")
        self.assertEqual(len(results), 1)
        names = {m["name"] for m in results[0].members}
        self.assertEqual(names, {"src/main.py", "src/utils.py"})

    def test_ext_search_case_insensitive(self):
        self._create_zip("backup.zip", {"File.LOG": "log"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search_by_extension(".log")
        self.assertEqual(len(results), 1)

    def test_ext_search_without_dot(self):
        self._create_zip("backup.zip", {"main.py": "code"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search_by_extension("py")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].members[0]["name"], "main.py")

    def test_ext_no_match(self):
        self._create_zip("backup.zip", {"a.txt": "1"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search_by_extension(".xyz")
        self.assertEqual(results, [])


class TestCrossSearcherGetSummary(unittest.TestCase):
    """测试 get_summary 统计"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_xsearch_test_")
        self.scan_dir = os.path.join(self.test_dir, "archives")
        os.makedirs(self.scan_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_zip(self, name: str, files: dict[str, str]) -> str:
        path = os.path.join(self.scan_dir, name)
        with zipfile.ZipFile(path, "w") as zf:
            for arcname, content in files.items():
                zf.writestr(arcname, content)
        return path

    def test_summary_with_results(self):
        self._create_zip("a.zip", {"a.py": "1", "b.py": "2", "c.txt": "3"})
        self._create_zip("b.zip", {"d.py": "4", "e.txt": "5"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search_by_extension(".py")
        summary = searcher.get_summary(results)
        self.assertEqual(summary["total_archives"], 2)
        self.assertEqual(summary["matched_archives"], 2)
        self.assertEqual(summary["total_matches"], 3)

    def test_summary_empty_results(self):
        self._create_zip("a.zip", {"a.txt": "1"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search_by_extension(".py")
        summary = searcher.get_summary(results)
        self.assertEqual(summary["total_archives"], 1)
        self.assertEqual(summary["matched_archives"], 0)
        self.assertEqual(summary["total_matches"], 0)

    def test_summary_no_archives(self):
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search("anything")
        summary = searcher.get_summary(results)
        self.assertEqual(summary["total_archives"], 0)
        self.assertEqual(summary["matched_archives"], 0)
        self.assertEqual(summary["total_matches"], 0)


class TestCrossSearcherFormatResults(unittest.TestCase):
    """测试 format_results 输出"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_xsearch_test_")
        self.scan_dir = os.path.join(self.test_dir, "archives")
        os.makedirs(self.scan_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_zip(self, name: str, files: dict[str, str]) -> str:
        path = os.path.join(self.scan_dir, name)
        with zipfile.ZipFile(path, "w") as zf:
            for arcname, content in files.items():
                zf.writestr(arcname, content)
        return path

    def test_format_results_zh(self):
        self._create_zip("backup.zip", {"main.py": "code"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search_by_extension(".py")
        output = searcher.format_results(results, lang="zh_CN")
        self.assertIn("搜索结果", output)
        self.assertIn("main.py", output)
        self.assertIn("1/1", output)

    def test_format_results_en(self):
        self._create_zip("backup.zip", {"main.py": "code"})
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search_by_extension(".py")
        output = searcher.format_results(results, lang="en_US")
        self.assertIn("Search results", output)
        self.assertIn("main.py", output)

    def test_format_results_empty_zh(self):
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        output = searcher.format_results([], lang="zh_CN")
        self.assertIn("未找到", output)

    def test_format_results_empty_en(self):
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        output = searcher.format_results([], lang="en_US")
        self.assertIn("No matching", output)


class TestCrossSearcherEdgeCases(unittest.TestCase):
    """测试边界情况"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_xsearch_test_")
        self.scan_dir = os.path.join(self.test_dir, "archives")
        os.makedirs(self.scan_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_empty_directory(self):
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search("anything")
        self.assertEqual(results, [])

    def test_nonexistent_directory(self):
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher(["/nonexistent/path"])
        results = searcher.search("anything")
        self.assertEqual(results, [])

    def test_multiple_directories(self):
        dir1 = os.path.join(self.test_dir, "d1")
        dir2 = os.path.join(self.test_dir, "d2")
        os.makedirs(dir1)
        os.makedirs(dir2)
        path1 = os.path.join(dir1, "a.zip")
        with zipfile.ZipFile(path1, "w") as zf:
            zf.writestr("file1.py", "code")
        path2 = os.path.join(dir2, "b.zip")
        with zipfile.ZipFile(path2, "w") as zf:
            zf.writestr("file2.py", "code")

        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([dir1, dir2])
        results = searcher.search("file")
        self.assertEqual(len(results), 2)

    def test_search_result_dataclass(self):
        from sbackup.cross_search import SearchResult

        r = SearchResult(
            archive="/path/to/backup.zip",
            members=[{"name": "a.txt", "size": 100}],
            archive_size=1024,
            archive_mtime="2026-01-01 00:00:00",
        )
        self.assertEqual(r.archive, "/path/to/backup.zip")
        self.assertEqual(len(r.members), 1)
        self.assertEqual(r.archive_size, 1024)
        self.assertEqual(r.archive_mtime, "2026-01-01 00:00:00")

    def test_empty_zip(self):
        path = os.path.join(self.scan_dir, "empty.zip")
        with zipfile.ZipFile(path, "w"):
            pass
        from sbackup.cross_search import CrossSearcher

        searcher = CrossSearcher([self.scan_dir])
        results = searcher.search("anything")
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
