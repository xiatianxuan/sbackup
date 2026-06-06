"""
针对性单元测试：覆盖 4 个新功能
"""

import os
import sys
import time
import tempfile
import shutil
import unittest
from pathlib import Path
from sbackup.config import Config
from sbackup.compression import (
    create_compressor,
    restore_backup,
    split_file,
    _match_select_pattern,
)
from sbackup.auto_save import BackupManager


class TestSelectiveRestore(unittest.TestCase):
    """功能1: 选择性还原 restore --select"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.source_dir = os.path.join(self.test_dir, "source")
        self.restore_dir = os.path.join(self.test_dir, "restored")
        os.makedirs(self.source_dir)
        (Path(self.source_dir) / "main.py").write_text("print('hello')")
        (Path(self.source_dir) / "utils.py").write_text("def helper(): pass")
        (Path(self.source_dir) / "readme.txt").write_text("readme")
        (Path(self.source_dir) / "sub").mkdir()
        (Path(self.source_dir) / "sub" / "data.csv").write_text("a,b,c")
        self.zip_path = os.path.join(self.test_dir, "backup.zip")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _make_backup(self, fmt="ZIP", ext=".zip"):
        path = os.path.join(self.test_dir, f"backup{ext}")
        config = Config(
            folder_path=self.source_dir,
            zipfile_path=path,
            compression_format=fmt,
            skip_patterns=[],
        )
        result = create_compressor(config).compress()
        self.assertTrue(result["success"])
        return result["path"]

    def test_select_glob_pattern_zip(self):
        """ZIP 选择性还原: *.py 只还原 Python 文件"""
        self._make_backup("ZIP", ".zip")
        result = restore_backup(self.zip_path, self.restore_dir, select_pattern="*.py")
        self.assertTrue(result["success"])
        self.assertEqual(result["files_count"], 2)
        # 检查只有 .py 文件被还原
        restored = Path(self.restore_dir)
        py_files = list(restored.rglob("*.py"))
        txt_files = list(restored.rglob("*.txt"))
        self.assertEqual(len(py_files), 2)
        self.assertEqual(len(txt_files), 0)

    def test_select_specific_file(self):
        """选择性还原特定文件"""
        self._make_backup("ZIP", ".zip")
        result = restore_backup(
            self.zip_path, self.restore_dir, select_pattern="*readme.txt"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["files_count"], 1)

    def test_select_no_match(self):
        """无匹配文件时返回 0"""
        self._make_backup("ZIP", ".zip")
        result = restore_backup(self.zip_path, self.restore_dir, select_pattern="*.xyz")
        self.assertTrue(result["success"])
        self.assertEqual(result["files_count"], 0)

    def test_select_empty_pattern_restores_all(self):
        """空模式还原全部文件"""
        self._make_backup("ZIP", ".zip")
        result = restore_backup(self.zip_path, self.restore_dir, select_pattern="")
        self.assertTrue(result["success"])
        self.assertGreater(result["files_count"], 2)

    def test_select_tar_gz(self):
        """tar.gz 选择性还原"""
        self._make_backup("TAR_GZ", ".tar.gz")
        tar_path = os.path.join(self.test_dir, "backup.tar.gz")
        result = restore_backup(tar_path, self.restore_dir, select_pattern="*.py")
        self.assertTrue(result["success"])
        self.assertEqual(result["files_count"], 2)

    def test_select_7z(self):
        """7z 选择性还原"""
        self._make_backup("7Z", ".7z")
        sz_path = os.path.join(self.test_dir, "backup.7z")
        result = restore_backup(sz_path, self.restore_dir, select_pattern="*.py")
        self.assertTrue(result["success"])
        self.assertEqual(result["files_count"], 2)

    def test_match_select_pattern(self):
        """测试 _match_select_pattern 辅助函数"""
        self.assertTrue(_match_select_pattern("src/main.py", "*.py"))
        self.assertTrue(_match_select_pattern("src/main.py", "src/main.py"))
        self.assertFalse(_match_select_pattern("src/main.py", "*.txt"))
        self.assertTrue(_match_select_pattern("any/path", ""))


class TestWindowsSchtasks(unittest.TestCase):
    """功能2: Windows 计划任务 schtasks 导出"""

    def test_generate_schtasks(self):
        """测试 schtasks 生成"""
        from sbackup.handlers import _generate_schtasks

        content = _generate_schtasks(60)
        self.assertIn("schtasks /create", content)
        self.assertIn("SbackupBackup", content)
        self.assertIn("/sc MINUTE /mo 60", content)
        self.assertIn("<?xml", content)
        self.assertIn("PT1H", content)

    def test_generate_schtasks_interval_with_minutes(self):
        """测试非整小时间隔"""
        from sbackup.handlers import _generate_schtasks

        content = _generate_schtasks(90)
        self.assertIn("PT1H30M", content)

    def test_generate_schtasks_short_interval(self):
        """测试短间隔"""
        from sbackup.handlers import _generate_schtasks

        content = _generate_schtasks(15)
        self.assertIn("PT15M", content)
        self.assertIn("/mo 15", content)

    def test_schedule_export_schtasks_type(self):
        """测试 schedule export --type=schtasks 参数解析"""
        from sbackup import get_parser

        parser = get_parser()
        args = parser.parse_args(
            ["schedule", "export", "--type", "schtasks", "--interval", "30"]
        )
        self.assertEqual(args.type, "schtasks")
        self.assertEqual(args.interval, 30)


class TestSplitFileAutoMergeRestore(unittest.TestCase):
    """功能3: 分卷自动合并还原"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.source_dir = os.path.join(self.test_dir, "source")
        self.restore_dir = os.path.join(self.test_dir, "restored")
        os.makedirs(self.source_dir)
        # 创建足够大的内容以产生多个分卷
        (Path(self.source_dir) / "big.txt").write_text("x" * 2000)
        (Path(self.source_dir) / "small.txt").write_text("y")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_split_and_restore_from_001(self):
        """分卷后从 .001 文件还原"""
        config = Config(
            folder_path=self.source_dir,
            zipfile_path=os.path.join(self.test_dir, "backup.zip"),
            skip_patterns=[],
        )
        result = create_compressor(config).compress()
        self.assertTrue(result["success"])
        zip_path = result["path"]

        # 分卷（极小分卷大小以产生多个分卷）
        parts = split_file(zip_path, 64)
        self.assertGreater(len(parts), 1, "应产生多个分卷")

        # 从 .001 还原
        result = restore_backup(parts[0], self.restore_dir)
        self.assertTrue(result["success"])
        self.assertGreater(result["files_count"], 0)

        # 验证还原的文件内容正确
        restored_big = Path(self.restore_dir) / "source" / "big.txt"
        if restored_big.exists():
            self.assertEqual(restored_big.read_text(), "x" * 2000)

    def test_restore_non_split_file_still_works(self):
        """非分卷文件的还原不受影响"""
        config = Config(
            folder_path=self.source_dir,
            zipfile_path=os.path.join(self.test_dir, "normal.zip"),
            skip_patterns=[],
        )
        result = create_compressor(config).compress()
        self.assertTrue(result["success"])
        result = restore_backup(result["path"], self.restore_dir)
        self.assertTrue(result["success"])


class TestPrePostHooks(unittest.TestCase):
    """功能4: Pre/Post 备份钩子脚本"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self.data_file = os.path.join(self.test_dir, "data.json")
        self.manager = BackupManager(self.data_file)
        self.source_dir = os.path.join(self.test_dir, "source")
        self.target_dir = os.path.join(self.test_dir, "target")
        os.makedirs(self.source_dir)
        os.makedirs(self.target_dir)
        (Path(self.source_dir) / "file.txt").write_text("content")
        self.hook_marker = os.path.join(self.test_dir, "hook_executed.txt")

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_pre_hook_executed(self):
        """前置钩子在备份前执行"""
        self.manager.add_folder(self.source_dir, self.target_dir, "")
        time.sleep(0.1)
        (Path(self.source_dir) / "new.txt").write_text("new")

        # 使用 Python 创建标记文件（shlex.split + shell=False 兼容）
        hook_cmd = (
            '"'
            + sys.executable
            + '" -c "open(r\''
            + self.hook_marker
            + "', 'w').write('done')\""
        )

        self.manager.execute_backups(pre_hooks=[hook_cmd])
        self.assertTrue(os.path.exists(self.hook_marker), "前置钩子应被执行")

    def test_post_hook_executed(self):
        """后置钩子在备份后执行"""
        self.manager.add_folder(self.source_dir, self.target_dir, "")
        time.sleep(0.1)
        (Path(self.source_dir) / "new.txt").write_text("new")

        # 使用 Python 创建标记文件（shlex.split + shell=False 兼容）
        hook_cmd = (
            '"'
            + sys.executable
            + '" -c "open(r\''
            + self.hook_marker
            + "', 'w').write('done')\""
        )

        self.manager.execute_backups(post_hooks=[hook_cmd])
        self.assertTrue(os.path.exists(self.hook_marker), "后置钩子应被执行")

    def test_hook_failure_does_not_stop_backup(self):
        """钩子失败不应阻止备份执行"""
        self.manager.add_folder(self.source_dir, self.target_dir, "")
        time.sleep(0.1)
        (Path(self.source_dir) / "new.txt").write_text("new")

        # 使用不存在的命令作为钩子
        self.manager.execute_backups(
            pre_hooks=["nonexistent_command_12345"],
            post_hooks=["nonexistent_command_12345"],
        )
        # 备份应仍然成功
        target_path = Path(self.target_dir)
        backups = list(target_path.glob("*.zip"))
        self.assertGreater(len(backups), 0, "备份应仍然成功")

    def test_empty_hooks_no_effect(self):
        """空钩子列表不影响备份"""
        self.manager.add_folder(self.source_dir, self.target_dir, "")
        time.sleep(0.1)
        (Path(self.source_dir) / "new.txt").write_text("new")

        self.manager.execute_backups(pre_hooks=[], post_hooks=[])
        target_path = Path(self.target_dir)
        backups = list(target_path.glob("*.zip"))
        self.assertGreater(len(backups), 0)

    def test_multiple_hooks(self):
        """多个钩子按顺序执行"""
        self.manager.add_folder(self.source_dir, self.target_dir, "")
        time.sleep(0.1)
        (Path(self.source_dir) / "new.txt").write_text("new")

        marker1 = os.path.join(self.test_dir, "hook1.txt")
        marker2 = os.path.join(self.test_dir, "hook2.txt")

        # 使用 Python 创建标记文件（shlex.split + shell=False 兼容）
        hook1 = (
            '"' + sys.executable + '" -c "open(r\'' + marker1 + "', 'w').write('1')\""
        )
        hook2 = (
            '"' + sys.executable + '" -c "open(r\'' + marker2 + "', 'w').write('2')\""
        )

        self.manager.execute_backups(pre_hooks=[hook1, hook2])
        self.assertTrue(os.path.exists(marker1))
        self.assertTrue(os.path.exists(marker2))


class TestRunHooks(unittest.TestCase):
    """测试 _run_hooks 静态方法"""

    def test_run_hooks_with_valid_command(self):
        """有效命令执行成功"""
        with tempfile.TemporaryDirectory() as tmpdir:
            marker = os.path.join(tmpdir, "marker.txt")
            # 使用 Python 创建标记文件（shlex.split + shell=False 兼容）
            hook_cmd = (
                '"'
                + sys.executable
                + '" -c "open(r\''
                + marker
                + "', 'w').write('ok')\""
            )
            BackupManager._run_hooks([hook_cmd], "pre")
            self.assertTrue(os.path.exists(marker))

    def test_run_hooks_with_empty_list(self):
        """空列表不执行任何操作"""
        BackupManager._run_hooks([], "pre")
        # 不应抛出异常

    def test_run_hooks_with_empty_string(self):
        """空字符串命令被跳过"""
        BackupManager._run_hooks(["", ""], "pre")
        # 不应抛出异常


if __name__ == "__main__":
    unittest.main()
