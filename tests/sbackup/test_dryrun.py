"""单元测试 for sbackup.dryrun 模块"""

import os
import shutil
import tempfile
import unittest
from sbackup.config import Config
from sbackup.dryrun import DryRunResult, DryRunScanner


class TestDryRunResult(unittest.TestCase):
    """DryRunResult 数据类测试"""

    def test_default_values(self):
        result = DryRunResult()
        self.assertEqual(result.total_files, 0)
        self.assertEqual(result.included_files, 0)
        self.assertEqual(result.excluded_files, 0)
        self.assertEqual(result.total_size, 0)
        self.assertEqual(result.included_size, 0)
        self.assertEqual(result.excluded_size, 0)
        self.assertEqual(result.skip_patterns_matched, {})
        self.assertEqual(result.large_files, [])
        self.assertEqual(result.file_types, {})
        self.assertEqual(result.warnings, [])

    def test_accumulation(self):
        result = DryRunResult()
        result.total_files = 10
        result.included_files = 7
        result.excluded_files = 3
        result.total_size = 1000
        result.included_size = 700
        result.excluded_size = 300
        # included + excluded should equal total
        self.assertEqual(
            result.included_files + result.excluded_files,
            result.total_files,
        )


class TestDryRunScanner(unittest.TestCase):
    """DryRunScanner 扫描逻辑测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_dryrun_test_")
        self.config = Config()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_file(self, rel_path: str, size: int = 100) -> str:
        """在测试目录中创建指定大小的文件"""
        file_path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(b"x" * size)
        return file_path

    def test_scan_empty_directory(self):
        """空目录应返回零统计"""
        scanner = DryRunScanner(self.test_dir, self.config)
        result = scanner.scan()
        self.assertEqual(result.total_files, 0)
        self.assertEqual(result.included_files, 0)
        self.assertEqual(result.excluded_files, 0)

    def test_scan_includes_all_files(self):
        """没有过滤规则时，所有文件应被包含"""
        self._create_file("a.txt", 100)
        self._create_file("b.py", 200)
        self._create_file("sub/c.json", 300)

        scanner = DryRunScanner(self.test_dir, self.config)
        result = scanner.scan()

        self.assertEqual(result.total_files, 3)
        self.assertEqual(result.included_files, 3)
        self.assertEqual(result.excluded_files, 0)
        self.assertEqual(result.total_size, 600)
        self.assertEqual(result.included_size, 600)

    def test_skip_patterns_filter(self):
        """skip_patterns 应排除匹配的目录（目录被剪枝，内部文件不遍历）"""
        self._create_file("code.py", 100)
        self._create_file(".git/config", 50)
        self._create_file("__pycache__/module.pyc", 200)

        config = Config(skip_patterns=[".git", "__pycache__"])
        scanner = DryRunScanner(self.test_dir, config)
        result = scanner.scan()

        # skip_patterns 剪枝目录，.git 和 __pycache__ 下的文件不被遍历
        self.assertEqual(result.total_files, 1)
        self.assertEqual(result.included_files, 1)
        self.assertEqual(result.excluded_files, 0)

    def test_include_patterns_filter(self):
        """include_patterns 应只保留匹配的文件"""
        self._create_file("code.py", 100)
        self._create_file("data.json", 200)
        self._create_file("readme.txt", 300)

        config = Config(include_patterns=["*.py"])
        scanner = DryRunScanner(self.test_dir, config)
        result = scanner.scan()

        self.assertEqual(result.total_files, 3)
        self.assertEqual(result.included_files, 1)
        self.assertEqual(result.excluded_files, 2)

    def test_exclude_patterns_filter(self):
        """exclude_patterns 应排除匹配的文件"""
        self._create_file("code.py", 100)
        self._create_file("debug.log", 200)
        self._create_file("error.log", 300)

        config = Config(exclude_patterns=["*.log"])
        scanner = DryRunScanner(self.test_dir, config)
        result = scanner.scan()

        self.assertEqual(result.total_files, 3)
        self.assertEqual(result.included_files, 1)
        self.assertEqual(result.excluded_files, 2)

    def test_max_size_filter(self):
        """max_size 应排除超过大小限制的文件"""
        self._create_file("small.txt", 100)
        self._create_file("medium.txt", 500)
        self._create_file("large.txt", 1000)

        config = Config(max_size=600)
        scanner = DryRunScanner(self.test_dir, config)
        result = scanner.scan()

        self.assertEqual(result.total_files, 3)
        self.assertEqual(result.included_files, 2)
        self.assertEqual(result.excluded_files, 1)
        # 验证被排除的是最大的文件
        excluded_paths = [f for f, _, _ in result.excluded_list]
        self.assertTrue(any("large.txt" in p for p in excluded_paths))

    def test_min_size_filter(self):
        """min_size 应排除小于大小限制的文件"""
        self._create_file("tiny.txt", 10)
        self._create_file("small.txt", 100)
        self._create_file("big.txt", 1000)

        config = Config(min_size=50)
        scanner = DryRunScanner(self.test_dir, config)
        result = scanner.scan()

        self.assertEqual(result.total_files, 3)
        self.assertEqual(result.included_files, 2)
        self.assertEqual(result.excluded_files, 1)
        excluded_paths = [f for f, _, _ in result.excluded_list]
        self.assertTrue(any("tiny.txt" in p for p in excluded_paths))

    def test_file_types统计(self):
        """应正确统计文件类型分布"""
        self._create_file("a.py", 100)
        self._create_file("b.py", 200)
        self._create_file("c.json", 300)
        self._create_file("d.txt", 400)

        scanner = DryRunScanner(self.test_dir, self.config)
        result = scanner.scan()

        self.assertEqual(result.file_types[".py"], 2)
        self.assertEqual(result.file_types[".json"], 1)
        self.assertEqual(result.file_types[".txt"], 1)

    def test_large_files_sorted(self):
        """最大文件应按大小降序排列"""
        self._create_file("tiny.txt", 10)
        self._create_file("medium.txt", 500)
        self._create_file("big.txt", 1000)
        self._create_file("huge.bin", 5000)

        scanner = DryRunScanner(self.test_dir, self.config)
        result = scanner.scan()

        self.assertEqual(len(result.large_files), 4)
        # 验证降序排列
        sizes = [size for _, size in result.large_files]
        self.assertEqual(sizes, sorted(sizes, reverse=True))
        # 第一个应该是最大的文件
        self.assertTrue(result.large_files[0][0].endswith("huge.bin"))

    def test_large_files_limited_to_10(self):
        """最大文件列表应限制为 10 个"""
        for i in range(15):
            self._create_file(f"file_{i:02d}.txt", 100 + i * 10)

        scanner = DryRunScanner(self.test_dir, self.config)
        result = scanner.scan()

        self.assertEqual(len(result.large_files), 10)

    def test_invalid_directory(self):
        """无效目录应返回带警告的结果"""
        scanner = DryRunScanner("/nonexistent/path", self.config)
        result = scanner.scan()

        self.assertEqual(result.total_files, 0)
        self.assertTrue(len(result.warnings) > 0)

    def test_format_summary_contains_key_info(self):
        """format_summary 应包含关键信息"""
        self._create_file("code.py", 100)
        self._create_file(".git/config", 50)

        config = Config(skip_patterns=[".git"])
        scanner = DryRunScanner(self.test_dir, config)
        result = scanner.scan()
        summary = scanner.format_summary(result)

        self.assertIn(self.test_dir, summary)
        self.assertIn(
            "1", summary
        )  # total_files (.git dir is pruned, only code.py counted)

    def test_format_file_list_included(self):
        """format_file_list 应列出包含的文件"""
        self._create_file("a.py", 100)
        self._create_file("b.txt", 200)

        scanner = DryRunScanner(self.test_dir, self.config)
        result = scanner.scan()
        file_list = scanner.format_file_list(result, show_excluded=False)

        self.assertIn("a.py", file_list)
        self.assertIn("b.txt", file_list)

    def test_format_file_list_excluded(self):
        """format_file_list 应列出排除的文件"""
        self._create_file("code.py", 100)
        self._create_file("debug.log", 200)

        config = Config(exclude_patterns=["*.log"])
        scanner = DryRunScanner(self.test_dir, config)
        result = scanner.scan()
        file_list = scanner.format_file_list(result, show_excluded=True)

        self.assertIn("debug.log", file_list)
        self.assertNotIn("code.py", file_list)

    def test_format_file_list_limit(self):
        """format_file_list 应遵守 limit 参数"""
        for i in range(60):
            self._create_file(f"file_{i:02d}.txt", 100)

        scanner = DryRunScanner(self.test_dir, self.config)
        result = scanner.scan()
        file_list = scanner.format_file_list(result, limit=10)

        self.assertIn("...", file_list)

    def test_dry_run_creates_no_files(self):
        """DryRunScanner 不应创建或修改任何文件"""
        self._create_file("existing.txt", 100)
        before = set(os.listdir(self.test_dir))

        scanner = DryRunScanner(self.test_dir, self.config)
        scanner.scan()

        after = set(os.listdir(self.test_dir))
        self.assertEqual(before, after)

    def test_combined_include_exclude(self):
        """同时设置 include_patterns 和 exclude_patterns"""
        self._create_file("main.py", 100)
        self._create_file("test.py", 200)
        self._create_file("data.json", 300)

        config = Config(include_patterns=["*.py"], exclude_patterns=["test.py"])
        scanner = DryRunScanner(self.test_dir, config)
        result = scanner.scan()

        self.assertEqual(result.included_files, 1)
        self.assertEqual(result.excluded_files, 2)

    def test_size_accounting(self):
        """包含和排除的大小之和应等于总大小"""
        self._create_file("a.txt", 100)
        self._create_file("b.log", 200)

        config = Config(exclude_patterns=["*.log"])
        scanner = DryRunScanner(self.test_dir, config)
        result = scanner.scan()

        self.assertEqual(result.total_size, result.included_size + result.excluded_size)

    def test_subdirectory_traversal(self):
        """应递归遍历子目录"""
        self._create_file("root.txt", 10)
        self._create_file("sub1/a.txt", 20)
        self._create_file("sub1/sub2/b.txt", 30)

        scanner = DryRunScanner(self.test_dir, self.config)
        result = scanner.scan()

        self.assertEqual(result.total_files, 3)

    def test_skip_pattern_no_negation(self):
        """当 skip_patterns 中有 ! 取反模式时，取反应生效"""
        self._create_file("code.py", 100)
        self._create_file(".gitignore", 50)
        self._create_file("__pycache__/cache.pyc", 200)

        # skip .git, __pycache__ 但排除 .gitignore
        config = Config(skip_patterns=[".git", "__pycache__", "!.gitignore"])
        scanner = DryRunScanner(self.test_dir, config)
        result = scanner.scan()

        # __pycache__ 目录被剪枝不遍历，.gitignore 取反保留
        self.assertEqual(result.total_files, 2)
        # .gitignore 应被保留（取反），code.py 正常
        self.assertEqual(result.included_files, 2)
        self.assertEqual(result.excluded_files, 0)

    def test_format_size_helper(self):
        """_format_size 应正确格式化各种大小"""
        self.assertEqual(DryRunScanner._format_size(0), "0 B")
        self.assertEqual(DryRunScanner._format_size(512), "512 B")
        self.assertIn("KB", DryRunScanner._format_size(2048))
        self.assertIn("MB", DryRunScanner._format_size(5 * 1024 * 1024))
        self.assertIn("GB", DryRunScanner._format_size(3 * 1024 * 1024 * 1024))


if __name__ == "__main__":
    unittest.main()
