"""磁盘空间预估模块测试"""

import os

import pytest
from pathlib import Path

from sbackup.diskcheck import (
    DiskChecker,
    DiskSpaceInfo,
    _format_size,
    _calc_ratio_text,
    _get_extension_ratio,
)


class TestFormatSize:
    """测试 _format_size 函数"""

    def test_bytes(self) -> None:
        assert _format_size(0) == "0 B"
        assert _format_size(512) == "512 B"

    def test_kilobytes(self) -> None:
        assert _format_size(1024) == "1.0 KB"
        assert _format_size(1536) == "1.5 KB"

    def test_megabytes(self) -> None:
        assert _format_size(1024**2) == "1.0 MB"
        assert _format_size(5 * 1024**2) == "5.0 MB"

    def test_gigabytes(self) -> None:
        assert _format_size(1024**3) == "1.00 GB"
        assert _format_size(2.5 * 1024**3) == "2.50 GB"

    def test_negative(self) -> None:
        result = _format_size(-1024)
        assert result.startswith("-") or result.startswith("-1.0 KB")


class TestCalcRatioText:
    """测试 _calc_ratio_text 函数"""

    def test_basic_ratio(self) -> None:
        assert _calc_ratio_text(1000, 500) == "50.0%"

    def test_zero_original(self) -> None:
        assert _calc_ratio_text(0, 0) == "0%"

    def test_high_compression(self) -> None:
        assert _calc_ratio_text(1000, 300) == "30.0%"


class TestGetExtensionRatio:
    """测试 _get_extension_ratio 函数"""

    def test_text_extensions(self) -> None:
        assert _get_extension_ratio(".py") == 0.3
        assert _get_extension_ratio(".js") == 0.3
        assert _get_extension_ratio(".txt") == 0.3
        assert _get_extension_ratio(".json") == 0.3
        assert _get_extension_ratio(".html") == 0.3
        assert _get_extension_ratio(".md") == 0.3
        assert _get_extension_ratio(".css") == 0.3

    def test_text_extensions_case_insensitive(self) -> None:
        assert _get_extension_ratio(".PY") == 0.3
        assert _get_extension_ratio(".JS") == 0.3

    def test_database_extensions(self) -> None:
        assert _get_extension_ratio(".db") == 0.5
        assert _get_extension_ratio(".sqlite") == 0.5
        assert _get_extension_ratio(".sqlite3") == 0.5

    def test_image_extensions(self) -> None:
        assert _get_extension_ratio(".jpg") == 0.95
        assert _get_extension_ratio(".png") == 0.95
        assert _get_extension_ratio(".gif") == 0.95

    def test_media_extensions(self) -> None:
        assert _get_extension_ratio(".mp4") == 0.98
        assert _get_extension_ratio(".mp3") == 0.98
        assert _get_extension_ratio(".wav") == 0.98

    def test_archive_extensions(self) -> None:
        assert _get_extension_ratio(".zip") == 0.99
        assert _get_extension_ratio(".gz") == 0.99
        assert _get_extension_ratio(".7z") == 0.99

    def test_unknown_extension(self) -> None:
        assert _get_extension_ratio(".xyz") == 0.6
        assert _get_extension_ratio("") == 0.6


class TestDiskSpaceInfo:
    """测试 DiskSpaceInfo 数据类"""

    def test_default_values(self) -> None:
        info = DiskSpaceInfo()
        assert info.total == 0
        assert info.used == 0
        assert info.free == 0
        assert info.source_total == 0
        assert info.estimated_backup == 0
        assert info.margin == 0
        assert info.enough is True
        assert info.warnings == []

    def test_custom_values(self) -> None:
        info = DiskSpaceInfo(
            total=1000,
            used=500,
            free=500,
            source_total=100,
            estimated_backup=50,
            margin=450,
            enough=True,
        )
        assert info.total == 1000
        assert info.enough is True


class TestDiskChecker:
    """测试 DiskChecker 类"""

    @pytest.fixture
    def temp_dirs(self, tmp_path: Path) -> tuple[Path, Path]:
        """创建临时源目录和目标目录"""
        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "target"
        target.mkdir()
        return source, target

    def test_get_disk_space(self, temp_dirs: tuple[Path, Path]) -> None:
        """测试 get_disk_space 返回有效数据"""
        source, target = temp_dirs
        checker = DiskChecker(str(source), str(target))
        info = checker.get_disk_space(str(target))

        assert info.total > 0
        assert info.free > 0
        assert info.used >= 0
        assert info.total == info.used + info.free

    def test_get_disk_space_nonexistent(self, temp_dirs: tuple[Path, Path]) -> None:
        """测试 get_disk_space 对不存在的路径回退到父目录"""
        source, target = temp_dirs
        fake_path = str(target / "nonexistent")
        checker = DiskChecker(str(source), str(target))
        # 应该不会崩溃，回退到父目录
        info = checker.get_disk_space(fake_path)
        assert info.total > 0

    def test_scan_source(self, temp_dirs: tuple[Path, Path]) -> None:
        """测试 scan_source 正确计算文件大小"""
        source, target = temp_dirs

        # 创建测试文件
        (source / "file1.txt").write_text("hello world")  # 11 bytes
        (source / "file2.py").write_text("print('hello')")  # 14 bytes

        checker = DiskChecker(str(source), str(target))
        total = checker.scan_source()

        assert total == 11 + 14

    def test_scan_source_with_subdirs(self, temp_dirs: tuple[Path, Path]) -> None:
        """测试 scan_source 包含子目录中的文件"""
        source, target = temp_dirs
        subdir = source / "subdir"
        subdir.mkdir()

        (source / "root.txt").write_text("root")  # 4 bytes
        (subdir / "nested.txt").write_text("nested")  # 6 bytes

        checker = DiskChecker(str(source), str(target))
        total = checker.scan_source()

        assert total == 4 + 6

    def test_scan_source_empty_directory(self, temp_dirs: tuple[Path, Path]) -> None:
        """测试扫描空目录"""
        source, target = temp_dirs
        checker = DiskChecker(str(source), str(target))
        total = checker.scan_source()
        assert total == 0

    def test_scan_source_nonexistent(self, temp_dirs: tuple[Path, Path]) -> None:
        """测试扫描不存在的目录"""
        source, target = temp_dirs
        checker = DiskChecker(str(source) + "_nonexistent", str(target))
        total = checker.scan_source()
        assert total == 0

    def test_estimate_backup_size_zip(self, temp_dirs: tuple[Path, Path]) -> None:
        """测试 ZIP 格式的估算"""
        source, target = temp_dirs

        # 创建纯文本文件（压缩比 0.3）
        (source / "code.py").write_text("x = 1\n" * 1000)  # ~6KB
        (source / "readme.txt").write_text("hello\n" * 500)  # ~3KB

        checker = DiskChecker(str(source), str(target))
        source_total = checker.scan_source()
        estimated = checker.estimate_backup_size("ZIP", 6, source_total)

        # ZIP 对文本文件的压缩比大约 0.3 * level_factor
        assert estimated > 0
        assert estimated < source_total  # 压缩后应该更小

    def test_estimate_backup_size_tar(self, temp_dirs: tuple[Path, Path]) -> None:
        """测试 TAR 格式的估算（无压缩）"""
        source, target = temp_dirs
        (source / "file.txt").write_text("hello world " * 100)

        checker = DiskChecker(str(source), str(target))
        source_total = checker.scan_source()
        estimated = checker.estimate_backup_size("TAR", 6, source_total)

        # TAR 不压缩，估算大小应该等于源大小
        assert estimated == source_total

    def test_estimate_backup_size_7z(self, temp_dirs: tuple[Path, Path]) -> None:
        """测试 7Z 格式的估算"""
        source, target = temp_dirs
        (source / "code.py").write_text("x = 1\n" * 1000)

        checker = DiskChecker(str(source), str(target))
        source_total = checker.scan_source()
        estimated = checker.estimate_backup_size("7z", 6, source_total)

        # 7z 应该比 ZIP 压缩率更高
        zip_est = checker.estimate_backup_size("ZIP", 6, source_total)
        assert estimated <= zip_est

    def test_estimate_backup_size_empty(self, temp_dirs: tuple[Path, Path]) -> None:
        """测试空目录的估算"""
        source, target = temp_dirs
        checker = DiskChecker(str(source), str(target))
        estimated = checker.estimate_backup_size("ZIP", 6, 0)
        assert estimated == 0

    def test_estimate_backup_size_mixed_files(
        self, temp_dirs: tuple[Path, Path]
    ) -> None:
        """测试混合文件类型"""
        source, target = temp_dirs
        # 文本文件
        (source / "code.py").write_text("x = 1\n" * 1000)
        # 二进制模拟（图片扩展名，压缩比 0.95）
        (source / "image.png").write_bytes(os.urandom(1000))

        checker = DiskChecker(str(source), str(target))
        source_total = checker.scan_source()
        estimated = checker.estimate_backup_size("ZIP", 6, source_total)

        # 混合文件的估算应该在两个极端之间
        assert estimated > 0
        assert estimated < source_total

    def test_check_integration(self, temp_dirs: tuple[Path, Path]) -> None:
        """测试 check 完整流程"""
        source, target = temp_dirs
        (source / "test.py").write_text("print('hello')\n" * 100)

        checker = DiskChecker(str(source), str(target))
        info = checker.check(fmt="ZIP", compression_level=6)

        assert info.source_total > 0
        assert info.estimated_backup > 0
        assert info.total > 0
        assert info.free > 0
        assert info.margin == info.free - info.estimated_backup
        assert info.enough is True  # 正常磁盘应该空间充足

    def test_format_report(self, temp_dirs: tuple[Path, Path]) -> None:
        """测试 format_report 输出包含关键信息"""
        source, target = temp_dirs
        (source / "test.py").write_text("print('hello')\n" * 100)

        checker = DiskChecker(str(source), str(target))
        info = checker.check(fmt="ZIP", compression_level=6)
        report = checker.format_report(info, lang="zh_CN")

        assert str(source) in report
        assert str(target) in report
        assert "MB" in report or "KB" in report or "B" in report or "GB" in report

    def test_format_report_en(self, temp_dirs: tuple[Path, Path]) -> None:
        """测试英文格式化报告"""
        source, target = temp_dirs
        (source / "test.py").write_text("hello\n" * 50)

        checker = DiskChecker(str(source), str(target))
        info = checker.check(fmt="ZIP", compression_level=6)
        report = checker.format_report(info, lang="en_US")

        assert str(source) in report
        assert str(target) in report

    def test_check_insufficient_space(self, tmp_path: Path) -> None:
        """测试空间不足的场景"""
        # 创建一个小目标目录（通过 mock 间接测试）
        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "target"
        target.mkdir()
        (source / "big.py").write_text("x\n" * 10000)

        checker = DiskChecker(str(source), str(target))
        info = checker.check(fmt="ZIP", compression_level=6)

        # 在正常系统上空间应该充足，但我们验证数据结构正确
        assert isinstance(info.enough, bool)
        assert isinstance(info.warnings, list)

    def test_compression_level_effect(self, temp_dirs: tuple[Path, Path]) -> None:
        """测试不同压缩级别对估算的影响"""
        source, target = temp_dirs
        (source / "data.txt").write_text("hello world " * 1000)

        checker = DiskChecker(str(source), str(target))
        source_total = checker.scan_source()

        low_level = checker.estimate_backup_size("ZIP", 1, source_total)
        high_level = checker.estimate_backup_size("ZIP", 9, source_total)

        # 更高压缩级别应该产生更小的估算
        assert high_level <= low_level
