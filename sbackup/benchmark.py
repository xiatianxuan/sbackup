"""
压缩基准测试模块：测试不同压缩格式和级别的性能
"""

import os
import shutil
import tempfile
import time
from dataclasses import dataclass

from sbackup.compression import create_compressor, restore_backup
from sbackup.config import Config
from sbackup.i18n import t

# 支持的格式列表及其默认压缩级别
FORMATS = ["ZIP", "TAR", "TAR_GZ", "TAR_BZ2", "TAR_XZ", "TAR_ZST", "7Z"]

# 各格式的有效压缩级别范围
_FORMAT_LEVEL_RANGES: dict[str, tuple[int, int]] = {
    "ZIP": (0, 9),
    "TAR": (0, 0),
    "TAR_GZ": (0, 9),
    "TAR_BZ2": (0, 9),
    "TAR_XZ": (0, 9),
    "TAR_ZST": (1, 22),
    "7Z": (0, 9),
}


@dataclass
class BenchmarkResult:
    """基准测试结果"""

    format: str
    level: int
    original_size: int
    compressed_size: int
    compression_time: float  # 秒
    decompression_time: float  # 秒
    compression_ratio: float  # compressed / original
    speed_mbps: float  # MB/s 压缩速度
    file_count: int


def _get_source_info(source_path: str) -> tuple[int, int]:
    """统计源目录的总大小和文件数"""
    total_size = 0
    file_count = 0
    for dirpath, _dirnames, filenames in os.walk(source_path):
        for filename in filenames:
            fp = os.path.join(dirpath, filename)
            try:
                total_size += os.path.getsize(fp)
                file_count += 1
            except OSError:
                pass
    return total_size, file_count


class BenchmarkRunner:
    """压缩基准测试运行器"""

    def __init__(self, source_path: str, password: str = "") -> None:
        self.source_path = os.path.abspath(source_path)
        self.password = password
        self.results: list[BenchmarkResult] = []

    def _build_config(self, fmt: str, level: int, output_dir: str) -> Config:
        """为指定格式和级别构建 Config 对象"""
        return Config(
            folder_path=self.source_path,
            zipfile_path=output_dir,
            compression_format=fmt,
            compression_level=level,
            password=self.password,
            skip_patterns=[],
        )

    def run_single(self, fmt: str, level: int = 6) -> BenchmarkResult:
        """测试单个格式+级别的压缩性能"""
        tmp = tempfile.mkdtemp(prefix="sbackup_bench_")
        try:
            restore_dir = os.path.join(tmp, "restored")
            os.makedirs(restore_dir)

            config = self._build_config(fmt, level, output_dir=tmp)
            compressor = create_compressor(config)

            # 压缩
            t0 = time.perf_counter()
            compressor.compress()
            t_compress = time.perf_counter() - t0

            # 找到压缩器实际写入的归档文件
            ext_map = {
                "ZIP": ".zip",
                "TAR": ".tar",
                "TAR_GZ": ".tar.gz",
                "TAR_BZ2": ".tar.bz2",
                "TAR_XZ": ".tar.xz",
                "TAR_ZST": ".tar.zst",
                "7Z": ".7z",
            }
            ext = ext_map.get(fmt, ".zip")
            archive_path = None
            for fname in os.listdir(tmp):
                if fname.endswith(ext):
                    archive_path = os.path.join(tmp, fname)
                    break

            if archive_path is None or not os.path.isfile(archive_path):
                # 归档文件不存在，返回零值结果
                original_size, file_count = _get_source_info(self.source_path)
                return BenchmarkResult(
                    format=fmt,
                    level=level,
                    original_size=original_size,
                    compressed_size=0,
                    compression_time=t_compress,
                    decompression_time=0.0,
                    compression_ratio=0.0,
                    speed_mbps=0.0,
                    file_count=file_count,
                )

            # 解压
            t0 = time.perf_counter()
            restore_backup(archive_path, restore_dir, self.password, quiet=True)
            t_decompress = time.perf_counter() - t0

            # 统计
            original_size, file_count = _get_source_info(self.source_path)
            compressed_size = os.path.getsize(archive_path)

            compression_ratio = (
                compressed_size / original_size if original_size > 0 else 0.0
            )
            original_mb = original_size / (1024 * 1024)
            speed_mbps = (
                original_mb / t_compress
                if t_compress > 0 and original_size > 0
                else 0.0
            )

            return BenchmarkResult(
                format=fmt,
                level=level,
                original_size=original_size,
                compressed_size=compressed_size,
                compression_time=t_compress,
                decompression_time=t_decompress,
                compression_ratio=compression_ratio,
                speed_mbps=speed_mbps,
                file_count=file_count,
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def run_all(self, levels: list[int] | None = None) -> list[BenchmarkResult]:
        """测试所有格式在不同级别下的性能"""
        if levels is None:
            levels = [1, 6, 9]

        self.results = []
        for fmt in FORMATS:
            # TAR 格式只测 level=6（不压缩）
            if fmt == "TAR":
                result = self.run_single(fmt, level=6)
                self.results.append(result)
            else:
                lo, hi = _FORMAT_LEVEL_RANGES.get(fmt, (0, 9))
                for level in levels:
                    if lo <= level <= hi:
                        result = self.run_single(fmt, level=level)
                        self.results.append(result)
        return self.results

    def run_quick(self) -> list[BenchmarkResult]:
        """快速测试：只测试每个格式的默认级别"""
        default_levels = {
            "ZIP": 6,
            "TAR": 6,
            "TAR_GZ": 6,
            "TAR_BZ2": 6,
            "TAR_XZ": 6,
            "TAR_ZST": 3,
            "7Z": 6,
        }
        self.results = []
        for fmt in FORMATS:
            level = default_levels.get(fmt, 6)
            result = self.run_single(fmt, level=level)
            self.results.append(result)
        return self.results

    def get_recommended(self) -> BenchmarkResult:
        """推荐最佳格式：在压缩比和速度之间取平衡"""
        if not self.results:
            self.run_quick()

        # 优先选择压缩比低的（压缩效果好），速度作为次要因素
        # score = compression_ratio * 1000 + 1/speed（越低越好）
        def _score(r: BenchmarkResult) -> float:
            speed_factor = 1.0 / r.speed_mbps if r.speed_mbps > 0 else 1e6
            return r.compression_ratio * 1000 + speed_factor

        return min(self.results, key=_score)

    def format_results(
        self, results: list[BenchmarkResult], lang: str = "zh_CN"
    ) -> str:
        """格式化结果为表格"""
        source_size, file_count = _get_source_info(self.source_path)
        source_mb = source_size / (1024 * 1024)

        lines = [
            t("benchmark.header"),
            t(
                "benchmark.source_info",
                path=self.source_path,
                size=f"{source_mb:.1f} MB",
                count=file_count,
            ),
            "",
        ]

        # 表头
        lines.append(
            f"{'format':<10} {'level':<6} {'compressed':<12} "
            f"{'ratio':<8} {'speed':<12} {'decompress':<12}"
        )
        lines.append("-" * 72)

        for r in results:
            comp_mb = r.compressed_size / (1024 * 1024)
            ratio_pct = r.compression_ratio * 100

            # 计算解压速度
            decomp_speed = (
                r.original_size / (1024 * 1024) / r.decompression_time
                if r.decompression_time > 0
                else 0.0
            )

            lines.append(
                f"{r.format:<10} {r.level:<6} {comp_mb:>8.1f} MB  "
                f"{ratio_pct:>5.1f}%  {r.speed_mbps:>8.1f} MB/s  "
                f"{decomp_speed:>8.1f} MB/s"
            )

        # 推荐
        recommended = self.get_recommended()
        rec_comp_mb = recommended.compressed_size / (1024 * 1024)
        lines.append("")
        lines.append(
            t(
                "benchmark.recommended",
                format=recommended.format,
                level=recommended.level,
                size=f"{rec_comp_mb:.1f} MB",
            )
        )

        return "\n".join(lines)
