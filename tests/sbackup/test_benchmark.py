"""
单元测试 for sbackup.benchmark 模块
"""

import os
import shutil
import tempfile
import unittest

from sbackup.benchmark import (
    BenchmarkResult,
    BenchmarkRunner,
    FORMATS,
    _get_source_info,
)


class TestBenchmarkResult(unittest.TestCase):
    """BenchmarkResult 数据类测试"""

    def test_creation(self):
        """测试 BenchmarkResult 创建"""
        r = BenchmarkResult(
            format="ZIP",
            level=6,
            original_size=1024 * 1024,
            compressed_size=512 * 1024,
            compression_time=0.5,
            decompression_time=0.2,
            compression_ratio=0.5,
            speed_mbps=2.0,
            file_count=10,
        )
        self.assertEqual(r.format, "ZIP")
        self.assertEqual(r.level, 6)
        self.assertEqual(r.original_size, 1024 * 1024)
        self.assertEqual(r.compressed_size, 512 * 1024)
        self.assertAlmostEqual(r.compression_time, 0.5)
        self.assertAlmostEqual(r.decompression_time, 0.2)
        self.assertAlmostEqual(r.compression_ratio, 0.5)
        self.assertAlmostEqual(r.speed_mbps, 2.0)
        self.assertEqual(r.file_count, 10)

    def test_formats_list(self):
        """测试支持的格式列表"""
        self.assertIn("ZIP", FORMATS)
        self.assertIn("TAR", FORMATS)
        self.assertIn("TAR_GZ", FORMATS)
        self.assertIn("TAR_BZ2", FORMATS)
        self.assertIn("TAR_XZ", FORMATS)
        self.assertIn("TAR_ZST", FORMATS)
        self.assertIn("7Z", FORMATS)


class TestGetSourceInfo(unittest.TestCase):
    """_get_source_info 函数测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_bench_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_empty_directory(self):
        """测试空目录"""
        size, count = _get_source_info(self.test_dir)
        self.assertEqual(size, 0)
        self.assertEqual(count, 0)

    def test_with_files(self):
        """测试有文件的目录"""
        content = b"hello world"
        for i in range(5):
            fpath = os.path.join(self.test_dir, f"file{i}.txt")
            with open(fpath, "wb") as f:
                f.write(content)

        size, count = _get_source_info(self.test_dir)
        self.assertEqual(count, 5)
        self.assertGreater(size, 0)

    def test_nested_directories(self):
        """测试嵌套目录"""
        content = b"nested content"
        subdir = os.path.join(self.test_dir, "sub")
        os.makedirs(subdir)
        with open(os.path.join(self.test_dir, "root.txt"), "wb") as f:
            f.write(content)
        with open(os.path.join(subdir, "nested.txt"), "wb") as f:
            f.write(content)

        size, count = _get_source_info(self.test_dir)
        self.assertEqual(count, 2)
        self.assertEqual(size, len(content) * 2)


class TestBenchmarkRunner(unittest.TestCase):
    """BenchmarkRunner 测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_bench_test_")
        # 创建测试文件
        content = b"x" * 1024  # 1KB 的重复数据（易于压缩）
        for i in range(10):
            fpath = os.path.join(self.test_dir, f"file{i}.txt")
            with open(fpath, "wb") as f:
                f.write(content)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_run_single_zip(self):
        """测试单个 ZIP 格式压缩"""
        runner = BenchmarkRunner(self.test_dir)
        result = runner.run_single("ZIP", level=6)

        self.assertIsInstance(result, BenchmarkResult)
        self.assertEqual(result.format, "ZIP")
        self.assertEqual(result.level, 6)
        self.assertGreater(result.original_size, 0)
        self.assertGreater(result.compressed_size, 0)
        self.assertGreaterEqual(result.compression_time, 0)
        self.assertGreaterEqual(result.decompression_time, 0)
        self.assertGreater(result.compression_ratio, 0)
        self.assertGreaterEqual(result.speed_mbps, 0)
        self.assertEqual(result.file_count, 10)

    def test_run_single_tar_gz(self):
        """测试单个 TAR_GZ 格式压缩"""
        runner = BenchmarkRunner(self.test_dir)
        result = runner.run_single("TAR_GZ", level=6)

        self.assertEqual(result.format, "TAR_GZ")
        self.assertGreater(result.original_size, 0)

    def test_run_single_tar(self):
        """测试 TAR 格式（不压缩）"""
        runner = BenchmarkRunner(self.test_dir)
        result = runner.run_single("TAR", level=6)

        self.assertEqual(result.format, "TAR")
        self.assertEqual(result.level, 6)
        # TAR 不压缩，compressed 应该 >= original（因为 tar 开销）
        self.assertGreaterEqual(result.compressed_size, result.original_size)

    def test_run_all(self):
        """测试 run_all 多格式测试"""
        runner = BenchmarkRunner(self.test_dir)
        results = runner.run_all(levels=[1, 6])

        self.assertGreater(len(results), 0)
        # 确保每个结果都是 BenchmarkResult
        for r in results:
            self.assertIsInstance(r, BenchmarkResult)
            self.assertGreater(r.original_size, 0)

        # TAR 格式应该只有一个结果（level=6）
        tar_results = [r for r in results if r.format == "TAR"]
        self.assertEqual(len(tar_results), 1)
        self.assertEqual(tar_results[0].level, 6)

        # 其他格式在 levels=[1,6] 下应各有两个结果
        zip_results = [r for r in results if r.format == "ZIP"]
        self.assertEqual(len(zip_results), 2)

    def test_run_all_default_levels(self):
        """测试 run_all 默认级别"""
        runner = BenchmarkRunner(self.test_dir)
        results = runner.run_all()

        self.assertGreater(len(results), 0)
        # 默认级别 [1, 6, 9]
        zip_levels = sorted(r.level for r in results if r.format == "ZIP")
        self.assertEqual(zip_levels, [1, 6, 9])

    def test_run_quick(self):
        """测试 run_quick 快速测试"""
        runner = BenchmarkRunner(self.test_dir)
        results = runner.run_quick()

        self.assertEqual(len(results), len(FORMATS))
        for r in results:
            self.assertIsInstance(r, BenchmarkResult)
            self.assertGreater(r.original_size, 0)

    def test_get_recommended(self):
        """测试推荐逻辑"""
        runner = BenchmarkRunner(self.test_dir)
        runner.run_quick()

        recommended = runner.get_recommended()
        self.assertIsInstance(recommended, BenchmarkResult)
        self.assertIn(recommended.format, FORMATS)

    def test_get_recommended_auto_run(self):
        """测试未运行时自动运行快速测试"""
        runner = BenchmarkRunner(self.test_dir)
        recommended = runner.get_recommended()
        self.assertIsInstance(recommended, BenchmarkResult)
        self.assertGreater(len(runner.results), 0)

    def test_format_results(self):
        """测试格式化输出"""
        runner = BenchmarkRunner(self.test_dir)
        results = runner.run_quick()

        output = runner.format_results(results, lang="zh_CN")
        self.assertIsInstance(output, str)
        self.assertIn("ZIP", output)
        self.assertIn("7Z", output)
        # 输出应包含格式名和级别信息
        self.assertIn("MB/s", output)
        self.assertIn("level", output)

    def test_format_results_en(self):
        """测试英文格式化输出"""
        runner = BenchmarkRunner(self.test_dir)
        results = runner.run_quick()

        output = runner.format_results(results, lang="en_US")
        self.assertIsInstance(output, str)
        self.assertIn("ZIP", output)


class TestBenchmarkEmptySource(unittest.TestCase):
    """空目录基准测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_bench_empty_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_run_single_empty_dir(self):
        """测试空目录压缩（不应崩溃）"""
        runner = BenchmarkRunner(self.test_dir)
        # 空目录也可以压缩，只是没有文件
        result = runner.run_single("ZIP", level=6)
        self.assertEqual(result.file_count, 0)
        self.assertEqual(result.original_size, 0)


class TestBenchmarkPassword(unittest.TestCase):
    """密码加密基准测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sbackup_bench_pwd_")
        content = b"secret data " * 100
        with open(os.path.join(self.test_dir, "secret.txt"), "wb") as f:
            f.write(content)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_run_single_with_password(self):
        """测试 7z 带密码压缩"""
        runner = BenchmarkRunner(self.test_dir, password="test123")
        result = runner.run_single("7Z", level=6)

        self.assertEqual(result.format, "7Z")
        self.assertGreater(result.compressed_size, 0)
        self.assertGreater(result.file_count, 0)


if __name__ == "__main__":
    unittest.main()
