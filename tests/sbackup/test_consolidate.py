"""
增量链合并模块的单元测试
"""

import os
import json
import tempfile
import time
import zipfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from sbackup.consolidate import (
    _extract_base_name,
    _is_backup_file,
    _detect_archive_type,
    _match_source,
    _gather_backups,
    _select_backups,
    consolidate_backups,
    detect_and_list_backups,
)


class TestExtractBaseName(unittest.TestCase):
    """文件名解析"""

    def test_simple_ext(self):
        self.assertEqual(_extract_base_name("myfolder.zip"), ("myfolder", ".zip"))

    def test_compound_ext(self):
        self.assertEqual(
            _extract_base_name("myfolder.tar.gz"), ("myfolder", ".tar.gz")
        )

    def test_with_template(self):
        self.assertEqual(
            _extract_base_name("myfolder_20260705_143022.zip"),
            ("myfolder_20260705_143022", ".zip"),
        )

    def test_unknown_ext(self):
        self.assertEqual(
            _extract_base_name("readme.txt"), ("readme", ".txt")
        )


class TestIsBackupFile(unittest.TestCase):
    """备份文件格式检测"""

    def test_valid_extensions(self):
        for ext in [".zip", ".tar", ".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst", ".7z"]:
            self.assertTrue(_is_backup_file(f"backup{ext}"))
            self.assertTrue(_is_backup_file(f"backup{ext.upper()}"))

    def test_tgz(self):
        self.assertTrue(_is_backup_file("backup.tgz"))

    def test_non_backup(self):
        self.assertFalse(_is_backup_file("readme.txt"))
        self.assertFalse(_is_backup_file("notes.md"))
        self.assertFalse(_is_backup_file("data.csv"))


class TestMatchSource(unittest.TestCase):
    """源名称匹配"""

    def test_exact_match(self):
        self.assertTrue(_match_source("myfolder.zip", "myfolder"))

    def test_template_prefix(self):
        self.assertTrue(
            _match_source("myfolder_20260705_143022.zip", "myfolder")
        )

    def test_consolidated_excluded(self):
        self.assertFalse(
            _match_source("myfolder_consolidated.zip", "myfolder")
        )

    def test_other_source(self):
        self.assertFalse(_match_source("otherfolder.zip", "myfolder"))

    def test_with_name_in_middle(self):
        """源名出现在文件名中间（如 backup_myfolder_20260705.zip）"""
        # 目前只支持前缀匹配，中间匹配不通过
        self.assertFalse(
            _match_source("backup_myfolder_20260705.zip", "myfolder")
        )


class TestGatherBackups(unittest.TestCase):
    """扫描目录收集备份文件"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _touch(self, name: str) -> str:
        path = os.path.join(self.tmpdir, name)
        Path(path).write_text("dummy")
        return path

    def _make_full_zip(self, name: str) -> str:
        path = os.path.join(self.tmpdir, name)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("file1.txt", "hello")
        return path

    def _make_inc_zip(self, name: str, marker_root: str) -> str:
        path = os.path.join(self.tmpdir, name)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(f"{marker_root}/_sbackup_manifest.json", '{"type":"incremental"}')
            zf.writestr(f"{marker_root}/file2.txt.sbackup_patch", "patch_data")
        return path

    def test_empty_dir(self):
        fulls, incs = _gather_backups(self.tmpdir, "myfolder")
        self.assertEqual(fulls, [])
        self.assertEqual(incs, [])

    def test_full_only(self):
        self._make_full_zip("myfolder.zip")
        fulls, incs = _gather_backups(self.tmpdir, "myfolder")
        self.assertEqual(len(fulls), 1)
        self.assertEqual(incs, [])

    def test_incremental_only(self):
        self._make_inc_zip("myfolder_v2.zip", "myfolder")
        fulls, incs = _gather_backups(self.tmpdir, "myfolder")
        self.assertEqual(fulls, [])
        self.assertEqual(len(incs), 1)

    def test_mixed(self):
        self._make_full_zip("myfolder.zip")
        time.sleep(0.05)
        self._make_inc_zip("myfolder_v2.zip", "myfolder")
        fulls, incs = _gather_backups(self.tmpdir, "myfolder")
        self.assertEqual(len(fulls), 1)
        self.assertEqual(len(incs), 1)

    def test_ignores_non_backup(self):
        self._touch("readme.txt")
        self._touch("notes.md")
        fulls, incs = _gather_backups(self.tmpdir, "myfolder")
        self.assertEqual(fulls, [])
        self.assertEqual(incs, [])

    def test_detect_mixed_extensions(self):
        # 用实际扩展名创建归档，确保 _get_archive_member_names 能解析
        self._make_full_zip("myfolder.zip")
        self._make_inc_zip("myfolder_v2.zip", "myfolder")
        fulls, incs = _gather_backups(self.tmpdir, "myfolder")
        self.assertEqual(len(fulls), 1)
        self.assertEqual(len(incs), 1)

    def test_sorted_by_mtime(self):
        # 创建顺序：v1（最旧）→ v2 → v3（最新）
        self._make_full_zip("myfolder_v1.zip")
        time.sleep(0.05)
        self._make_full_zip("myfolder_v2.zip")
        time.sleep(0.05)
        self._make_full_zip("myfolder_v3.zip")
        fulls, incs = _gather_backups(self.tmpdir, "myfolder")
        self.assertEqual(len(fulls), 3)
        names = [os.path.basename(p) for _, p in fulls]
        self.assertEqual(names, ["myfolder_v1.zip", "myfolder_v2.zip", "myfolder_v3.zip"])


class TestDetectArchiveType(unittest.TestCase):
    """归档类型检测"""

    def test_full_zip(self):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            path = f.name
        try:
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("file1.txt", "hello")
            self.assertEqual(_detect_archive_type(path), "full")
        finally:
            os.remove(path)

    def test_incremental_zip(self):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            path = f.name
        try:
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr(
                    "source/_sbackup_manifest.json",
                    '{"type":"incremental"}',
                )
            self.assertEqual(_detect_archive_type(path), "incremental")
        finally:
            os.remove(path)

    def test_incremental_root_manifest(self):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            path = f.name
        try:
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr(
                    "_sbackup_manifest.json",
                    '{"type":"incremental"}',
                )
            self.assertEqual(_detect_archive_type(path), "incremental")
        finally:
            os.remove(path)

    def test_unknown_format(self):
        with tempfile.NamedTemporaryFile(suffix=".bad", delete=False) as f:
            path = f.name
            f.write(b"not an archive")
        try:
            # _get_archive_member_names 对无法识别的扩展名返回空列表，
            # _detect_archive_type 将空列表视为全量
            self.assertEqual(_detect_archive_type(path), "full")
        finally:
            os.remove(path)


class TestSelectBackups(unittest.TestCase):
    """备份选择逻辑"""

    def test_select_all(self):
        fulls = [(100.0, "/full1.zip"), (200.0, "/full2.zip")]
        incs = [(150.0, "/inc1.zip"), (250.0, "/inc2.zip")]
        result = _select_backups(fulls, incs, count=0)
        self.assertEqual(len(result), 4)

    def test_select_last_two(self):
        fulls = [(100.0, "/full1.zip"), (200.0, "/full2.zip")]
        incs = [(250.0, "/inc1.zip"), (300.0, "/inc2.zip")]
        result = _select_backups(fulls, incs, count=2)
        # 最新的2个是 inc1(250) 和 inc2(300)，都不是全量
        # 会自动包含最近的全量 full2(200)
        self.assertEqual(len(result), 3)
        self.assertIn("/full2.zip", result)
        self.assertIn("/inc1.zip", result)
        self.assertIn("/inc2.zip", result)

    def test_auto_include_base_full(self):
        """当最新的N个中最旧的不是全量时，自动包含前面的全量"""
        fulls = [(100.0, "/full1.zip")]
        incs = [(150.0, "/inc1.zip"), (200.0, "/inc2.zip")]
        # 取最新2个：inc2, inc1 — inc1 不是全量
        result = _select_backups(fulls, incs, count=2)
        # 应包含 full1 + inc1 + inc2
        self.assertEqual(len(result), 3)
        self.assertIn("/full1.zip", result)
        self.assertIn("/inc1.zip", result)
        self.assertIn("/inc2.zip", result)

    def test_no_full_backup(self):
        fulls = []
        incs = [(150.0, "/inc1.zip")]
        result = _select_backups(fulls, incs, count=0)
        self.assertEqual(result, [])

    def test_single_full(self):
        fulls = [(100.0, "/full1.zip")]
        incs = []
        result = _select_backups(fulls, incs, count=1)
        self.assertEqual(result, ["/full1.zip"])


class TestDetectAndListBackups(unittest.TestCase):
    """列表检测"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_full_zip(self, name: str) -> str:
        path = os.path.join(self.tmpdir, name)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("f.txt", "data")
        return path

    def _make_inc_zip(self, name: str) -> str:
        path = os.path.join(self.tmpdir, name)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("src/_sbackup_manifest.json", '{"type":"incremental"}')
        return path

    def test_list_mixed(self):
        self._make_full_zip("myfolder_v1.zip")
        self._make_inc_zip("myfolder_v2.zip")
        result = detect_and_list_backups(self.tmpdir, "myfolder")
        self.assertEqual(len(result["full"]), 1)
        self.assertEqual(len(result["incremental"]), 1)

    def test_list_empty(self):
        result = detect_and_list_backups(self.tmpdir, "myfolder")
        self.assertEqual(len(result["full"]), 0)
        self.assertEqual(len(result["incremental"]), 0)


class TestConsolidateIntegration(unittest.TestCase):
    """端到端合并测试（使用真实文件）"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_full_backup(self, name: str, files: dict[str, str]) -> str:
        """创建一个模拟全量备份的 ZIP"""
        path = os.path.join(self.tmpdir, name)
        with zipfile.ZipFile(path, "w") as zf:
            for relpath, content in files.items():
                zf.writestr(relpath, content)
        return path

    def test_no_full_backup(self):
        """没有全量备份时返回错误"""
        result = consolidate_backups("myfolder", self.tmpdir)
        self.assertFalse(result["success"])
        self.assertTrue(result.get("error", ""))

    def test_no_incremental(self):
        """只有全量没有增量时，返回成功且不需要合并"""
        self._make_full_backup("myfolder.zip", {"src/f1.txt": "hello"})
        result = consolidate_backups("myfolder", self.tmpdir)
        self.assertTrue(result["success"])
        # note 不为空说明有提示信息（翻译后的文本）
        self.assertTrue(result.get("note", ""))

    def test_invalid_source(self):
        """源名称不存在时返回错误"""
        self._make_full_backup("myfolder.zip", {"src/f1.txt": "hello"})
        result = consolidate_backups("otherfolder", self.tmpdir)
        self.assertFalse(result["success"])

    def test_consolidate_with_source_root(self):
        """验证合并后的归档包含正确的源目录根"""
        self._make_full_backup(
            "myfolder.zip",
            {"myfolder/f1.txt": "hello", "myfolder/f2.txt": "world"},
        )
        result = consolidate_backups("myfolder", self.tmpdir)
        self.assertTrue(result["success"])
        self.assertIn("path", result)


class TestConsolidateEdgeCases(unittest.TestCase):
    """边界条件"""

    def test_extract_base_name_order(self):
        """复合扩展名优先于简单扩展名"""
        base, ext = _extract_base_name("file.tar.gz")
        self.assertEqual(ext, ".tar.gz")
        self.assertEqual(base, "file")

    def test_is_backup_file_case(self):
        """扩展名大小写不敏感"""
        self.assertTrue(_is_backup_file("BACKUP.ZIP"))
        self.assertTrue(_is_backup_file("backup.TAR.GZ"))

    def test_match_source_empty_name(self):
        """空源名不匹配"""
        self.assertFalse(_match_source("myfolder.zip", ""))

    def test_match_source_consolidated_exact(self):
        """显式排除 _consolidated 后缀"""
        self.assertFalse(
            _match_source("myfolder_consolidated.tar.gz", "myfolder")
        )

    def test_gather_backups_nonexistent_dir(self):
        """不存在的目录返回空"""
        fulls, incs = _gather_backups("/nonexistent/path", "myfolder")
        self.assertEqual(fulls, [])
        self.assertEqual(incs, [])

    def test_detect_archive_type_no_file(self):
        """不存在的文件返回 unknown"""
        result = _detect_archive_type("/nonexistent/file.zip")
        self.assertEqual(result, "unknown")


if __name__ == "__main__":
    unittest.main()
