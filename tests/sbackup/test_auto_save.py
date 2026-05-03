"""
单元测试 for sbackup.auto_save 模块
"""

import unittest
import os
import json
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from sbackup.auto_save import BackupManager
from sbackup.i18n import t


class TestAutoSave(unittest.TestCase):
    def setUp(self):
        """
        设置测试环境
        """
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()

        # 保存原始工作目录并切换到测试目录，以便测试相对路径逻辑
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # 定义测试使用的数据文件
        self.data_file = os.path.join(self.test_dir, "test_sbackup.json")

        # 初始化 BackupManager 实例
        self.manager = BackupManager(self.data_file)

        # 创建测试文件夹
        self.source_folder = os.path.join(self.test_dir, "source")
        self.target_folder = os.path.join(self.test_dir, "target")
        os.makedirs(self.source_folder)
        os.makedirs(self.target_folder)

    def tearDown(self):
        """
        清理测试环境
        """
        # 恢复原始工作目录
        os.chdir(self.original_cwd)
        # 清理临时目录
        shutil.rmtree(self.test_dir)

    def test_add_folder(self):
        """测试添加备份策略"""
        # 添加策略
        result = self.manager.add_folder(self.source_folder, self.target_folder, ".git")

        self.assertTrue(result)

        # 验证数据文件
        self.assertTrue(
            os.path.exists(self.data_file), f"数据文件 {self.data_file} 不存在"
        )

        with open(self.data_file, "r") as f:
            data = json.load(f)
            self.assertIn(
                os.path.abspath(self.source_folder), data, f"数据文件内容: {data}"
            )

    def test_rm_folder(self):
        """测试删除备份策略"""
        # 先添加
        self.manager.add_folder(self.source_folder, self.target_folder)
        self.assertIn(os.path.abspath(self.source_folder), self.manager.data)

        # 再删除
        result = self.manager.rm_folder(self.source_folder)
        self.assertTrue(result)
        self.assertNotIn(os.path.abspath(self.source_folder), self.manager.data)

    def test_save_folder_updates_mtime(self):
        """测试执行备份后时间戳被更新，实现增量备份"""
        # 添加策略
        self.manager.add_folder(self.source_folder, self.target_folder, "")
        abs_source = os.path.abspath(self.source_folder)
        original_mtime = self.manager.data[abs_source][0]

        # 修改源文件夹内容，触发备份条件
        time.sleep(0.1)
        (Path(self.source_folder) / "new_file.txt").write_text("new content")

        # 执行备份（使用新方法名 execute_backups）
        self.manager.execute_backups()

        # 验证 mtime 已更新
        new_mtime = self.manager.data[abs_source][0]
        self.assertNotEqual(original_mtime, new_mtime, "备份后 mtime 应被更新")
        self.assertEqual(new_mtime, os.stat(abs_source).st_mtime)

        # 验证数据已持久化
        self.manager.load()
        self.assertEqual(self.manager.data[abs_source][0], new_mtime)

    def test_execute_backups_alias(self):
        """测试 save_folder 向后兼容别名"""
        self.assertTrue(hasattr(self.manager, "save_folder"))
        # 验证 save_folder 指向 execute_backups 的底层函数
        self.assertIs(
            self.manager.save_folder.__func__, self.manager.execute_backups.__func__
        )

    def test_add_folder_skip_patterns_stripped(self):
        """测试忽略模式中的空格被正确去除"""
        result = self.manager.add_folder(
            self.source_folder, self.target_folder, " .git , node_modules "
        )
        self.assertTrue(result)
        abs_source = os.path.abspath(self.source_folder)
        skip_list = self.manager.data[abs_source][2]
        self.assertEqual(skip_list, [".git", "node_modules"])

    def test_add_duplicate_folder(self):
        """测试重复添加同一文件夹应失败"""
        result1 = self.manager.add_folder(self.source_folder, self.target_folder)
        self.assertTrue(result1)
        result2 = self.manager.add_folder(self.source_folder, self.target_folder)
        self.assertFalse(result2)
        self.assertEqual(len(self.manager.data), 1)

    def test_rm_nonexistent_folder(self):
        """测试删除不存在的策略应失败"""
        result = self.manager.rm_folder("/nonexistent/path")
        self.assertFalse(result)

    def test_add_invalid_source(self):
        """测试添加无效源目录应失败"""
        result = self.manager.add_folder("/nonexistent/path", self.target_folder)
        self.assertFalse(result)

    def test_add_invalid_dest(self):
        """测试添加无效目标目录应失败"""
        result = self.manager.add_folder(self.source_folder, "/nonexistent/path")
        self.assertFalse(result)

    def test_add_source_equals_dest(self):
        """测试源目录与目标目录相同时应失败"""
        result = self.manager.add_folder(self.source_folder, self.source_folder)
        self.assertFalse(result)

    def test_save_missing_source(self):
        """测试源文件夹不存在时的 save 行为"""
        # 手动构造一条源文件夹不存在的记录
        self.manager.data["/nonexistent/source"] = [0.0, self.target_folder, [], ""]
        self.manager.save()
        # save_folder 应打印警告并跳过，不抛出异常
        self.manager.save_folder()
        # 数据应保持不变（不会被删除）
        self.assertIn("/nonexistent/source", self.manager.data)

    def test_list_folder_table_empty(self):
        """测试空策略时表格返回提示文本"""
        text = self.manager.list_folder_table()
        self.assertEqual(text, t("cmd.all.empty"))

    def test_all_folder(self):
        """测试 all_folder 返回正确字典"""
        self.manager.add_folder(self.source_folder, self.target_folder)
        result = self.manager.all_folder()
        abs_source = os.path.abspath(self.source_folder)
        self.assertEqual(result[abs_source], os.path.abspath(self.target_folder))

    def test_list_folder_table_with_data(self):
        """测试有策略时表格渲染"""
        self.manager.add_folder(self.source_folder, self.target_folder, ".git")
        text = self.manager.list_folder_table()
        self.assertIn(os.path.abspath(self.source_folder), text)
        self.assertIn(os.path.abspath(self.target_folder), text)
        self.assertIn(".git", text)

    def test_load_corrupted_file_rename(self):
        """测试损坏文件备份失败时重命名"""
        # 写入损坏的 JSON
        with open(self.data_file, "w") as f:
            f.write("{corrupted!!!")
        # 模拟 shutil.copy2 失败

        original_copy2 = shutil.copy2

        def failing_copy2(*args, **kwargs):
            raise OSError("copy failed")

        shutil.copy2 = failing_copy2
        try:
            mgr = BackupManager(self.data_file)
            # 应重命名损坏文件
            self.assertTrue(os.path.exists(self.data_file + ".corrupted"))
            self.assertFalse(os.path.exists(self.data_file))
            self.assertEqual(mgr.data, {})
        finally:
            shutil.copy2 = original_copy2

    def test_get_entry_and_set_entry(self):
        """测试 _get_entry 和 _set_entry 辅助方法"""
        from sbackup.auto_save import BackupEntry

        self.manager.add_folder(self.source_folder, self.target_folder, ".git")
        abs_source = os.path.abspath(self.source_folder)

        entry = self.manager._get_entry(abs_source)
        assert entry is not None, "entry should not be None"
        self.assertEqual(entry.target, os.path.abspath(self.target_folder))
        self.assertEqual(entry.skip_patterns, [".git"])

        # 测试不存在的 key
        self.assertIsNone(self.manager._get_entry("/nonexistent"))

        # 测试 _set_entry
        new_entry = BackupEntry(
            mtime=999.0, target="/new/target", skip_patterns=["*.log"]
        )
        self.manager._set_entry(abs_source, new_entry)
        retrieved = self.manager._get_entry(abs_source)
        assert retrieved is not None, "retrieved entry should not be None"
        self.assertEqual(retrieved.mtime, 999.0)
        self.assertEqual(retrieved.target, "/new/target")

    def test_execute_backups_skip_uptodate(self):
        """测试所有策略已最新时输出提示"""
        self.manager.add_folder(self.source_folder, self.target_folder, "")
        # 不修改文件，直接执行备份
        self.manager.execute_backups()
        # 应输出"已是最新"（通过检查 data 中 mtime 未变来验证）
        abs_source = os.path.abspath(self.source_folder)
        self.assertEqual(self.manager.data[abs_source][0], os.stat(abs_source).st_mtime)

    def test_execute_backups_oserror_on_stat(self):
        """测试 os.stat 失败时跳过该策略"""
        self.manager.add_folder(self.source_folder, self.target_folder, "")
        abs_source = os.path.abspath(self.source_folder)
        original_mtime = self.manager.data[abs_source][0]

        # 修改文件触发备份条件
        time.sleep(0.1)
        (Path(self.source_folder) / "f.txt").write_text("x")

        # 模拟 os.stat 失败
        original_stat = os.stat

        def failing_stat(path, *args, **kwargs):
            if path == abs_source:
                raise OSError("stat failed")
            return original_stat(path, *args, **kwargs)

        os.stat = failing_stat
        try:
            self.manager.execute_backups()
            # mtime 不应被更新
            self.assertEqual(self.manager.data[abs_source][0], original_mtime)
        finally:
            os.stat = original_stat

    def test_load_corrupted_file_backup_success(self):
        """测试损坏文件成功备份到 .bak"""
        with open(self.data_file, "w") as f:
            f.write("{corrupted!!!")
        mgr = BackupManager(self.data_file)
        self.assertTrue(os.path.exists(self.data_file + ".bak"))
        self.assertEqual(mgr.data, {})

    def test_add_folder_oserror_on_stat(self):
        """测试 add_folder 时 os.stat 失败"""
        # 创建一个无权限的目录场景比较难，直接 mock os.stat
        original_stat = os.stat

        def failing_stat(path, *args, **kwargs):
            raise OSError("stat failed")

        os.stat = failing_stat
        try:
            result = self.manager.add_folder(self.source_folder, self.target_folder)
            self.assertFalse(result)
        finally:
            os.stat = original_stat

    def test_backup_history(self):
        """测试备份历史记录"""
        self.manager.add_folder(self.source_folder, self.target_folder, "")
        abs_source = os.path.abspath(self.source_folder)

        time.sleep(0.1)
        (Path(self.source_folder) / "f.txt").write_text("x")
        self.manager.execute_backups()

        history = self.manager.get_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["source"], abs_source)
        self.assertIn("time", history[0])
        self.assertIn("size_mb", history[0])
        self.assertIn("files_count", history[0])

    def test_backup_history_empty(self):
        """测试无备份时历史为空"""
        history = self.manager.get_history()
        self.assertEqual(history, [])

    def test_cleanup_old_backups(self):
        """测试清理旧备份文件"""
        # 创建多个假备份文件
        target = Path(self.target_folder)
        for i in range(5):
            (target / f"backup_{i}.zip").write_text(f"content{i}")
            import time

            time.sleep(0.05)

        BackupManager._cleanup_old_backups(self.target_folder, keep=2)
        remaining = list(target.glob("*.zip"))
        self.assertLessEqual(len(remaining), 2)

    def test_cleanup_old_backups_none(self):
        """测试 keep=0 时不清理"""
        target = Path(self.target_folder)
        (target / "backup.zip").write_text("data")
        BackupManager._cleanup_old_backups(self.target_folder, keep=0)
        self.assertTrue((target / "backup.zip").exists())

    def test_cleanup_old_backups_invalid_dir(self):
        """测试清理不存在的目录"""
        BackupManager._cleanup_old_backups("/nonexistent", keep=2)
        # 不应抛出异常

    def test_execute_backups_with_keep(self):
        """测试执行备份时保留 N 个文件"""
        self.manager.add_folder(self.source_folder, self.target_folder, "")

        time.sleep(0.1)
        (Path(self.source_folder) / "f1.txt").write_text("x")
        self.manager.execute_backups(keep=3)

        history = self.manager.get_history()
        self.assertGreaterEqual(len(history), 1)

    def test_list_folder_table_skips_history(self):
        """测试 list_folder_table 跳过 _history 键"""
        self.manager.add_folder(self.source_folder, self.target_folder, ".git")
        # 手动添加 _history 数据
        self.manager.data["_history"] = [
            {"time": "2026-01-01", "source": "/x", "size_mb": 1.0, "files_count": 1}
        ]
        text = self.manager.list_folder_table()
        # 不应包含 _history 相关文本
        self.assertNotIn("_history", text)
        # 应正常显示备份策略
        self.assertIn(os.path.abspath(self.source_folder), text)

    def test_execute_backups_skips_history(self):
        """测试 execute_backups 跳过 _history 键"""
        self.manager.add_folder(self.source_folder, self.target_folder, "")
        # 手动添加 _history 数据
        self.manager.data["_history"] = [
            {"time": "2026-01-01", "source": "/x", "size_mb": 1.0, "files_count": 1}
        ]
        self.manager.save()

        time.sleep(0.1)
        (Path(self.source_folder) / "h.txt").write_text("x")
        # 不应因 _history 抛出异常
        self.manager.execute_backups()
        history = self.manager.get_history()
        self.assertGreaterEqual(len(history), 1)

    def test_add_folder_with_format(self):
        """测试添加策略时指定条目级格式"""
        result = self.manager.add_folder(
            self.source_folder, self.target_folder, ".git", "TAR_GZ"
        )
        self.assertTrue(result)
        abs_source = os.path.abspath(self.source_folder)
        entry = self.manager._get_entry(abs_source)
        assert entry is not None, "entry should not be None"
        self.assertEqual(entry.compression_format, "TAR_GZ")

    def test_add_folder_without_format(self):
        """测试添加策略时不指定格式则 compression_format 为空"""
        result = self.manager.add_folder(self.source_folder, self.target_folder, ".git")
        self.assertTrue(result)
        abs_source = os.path.abspath(self.source_folder)
        entry = self.manager._get_entry(abs_source)
        assert entry is not None, "entry should not be None"
        self.assertEqual(entry.compression_format, "")

    def test_entry_format_backward_compatibility(self):
        """测试 from_list 向后兼容旧格式（3元素列表）"""
        from sbackup.auto_save import BackupEntry

        old_data = [1719235200.0, "/path/to/target", [".git"]]
        entry = BackupEntry.from_list(old_data)
        self.assertEqual(entry.mtime, 1719235200.0)
        self.assertEqual(entry.target, "/path/to/target")
        self.assertEqual(entry.skip_patterns, [".git"])
        self.assertEqual(entry.compression_format, "")

    def test_entry_format_new_format(self):
        """测试 from_list 正确读取新格式（4元素列表）"""
        from sbackup.auto_save import BackupEntry

        new_data = [1719235200.0, "/path/to/target", [".git"], "TAR_GZ"]
        entry = BackupEntry.from_list(new_data)
        self.assertEqual(entry.compression_format, "TAR_GZ")

    def test_to_list_includes_format(self):
        """测试 to_list 输出包含 compression_format"""
        from sbackup.auto_save import BackupEntry

        entry = BackupEntry(
            mtime=1.0, target="/t", skip_patterns=[], compression_format="7Z"
        )
        self.assertEqual(entry.to_list(), [1.0, "/t", [], "7Z"])

    def test_execute_backups_entry_format_overrides_global(self):
        """测试条目级格式优先于全局格式"""
        # 添加策略，指定条目级格式为 TAR_GZ
        self.manager.add_folder(self.source_folder, self.target_folder, "", "TAR_GZ")

        time.sleep(0.1)
        (Path(self.source_folder) / "f_fmt.txt").write_text("format test")

        self.manager.execute_backups()

        # 检查生成的备份文件是 .tar.gz
        target_path = Path(self.target_folder)
        gz_files = list(target_path.glob("*.tar.gz"))
        self.assertGreaterEqual(len(gz_files), 1, "应生成 .tar.gz 备份文件")

    def test_execute_backups_global_format_when_entry_empty(self):
        """测试条目级格式为空时使用全局格式"""
        # 添加策略，不指定条目级格式
        self.manager.add_folder(self.source_folder, self.target_folder, "")

        time.sleep(0.1)
        (Path(self.source_folder) / "f_global.txt").write_text("global test")

        # 全局配置为 ZIP（默认）
        self.manager.execute_backups()

        target_path = Path(self.target_folder)
        zip_files = list(target_path.glob("*.zip"))
        self.assertGreaterEqual(len(zip_files), 1, "应生成 .zip 备份文件")

    def test_list_folder_table_shows_format(self):
        """测试表格显示格式列"""
        self.manager.add_folder(
            self.source_folder, self.target_folder, ".git", "TAR_GZ"
        )
        text = self.manager.list_folder_table()
        # 格式列应包含 TAR_GZ
        self.assertIn("TAR_GZ", text)

    def test_list_folder_table_shows_default_when_no_format(self):
        """测试表格中无条目级格式时显示默认"""
        self.manager.add_folder(self.source_folder, self.target_folder, ".git")
        text = self.manager.list_folder_table()
        # 应包含"默认"文本（中文环境）
        self.assertIn(t("table.cell.default"), text)

    def test_display_width_ascii(self):
        """测试 ASCII 字符宽度计算"""
        self.assertEqual(BackupManager._display_width("hello"), 5)

    def test_display_width_cjk(self):
        """测试中文字符宽度计算（每个算2）"""
        self.assertEqual(BackupManager._display_width("你好"), 4)

    def test_display_width_fullwidth(self):
        """测试全角符号宽度计算（U+FF01-FF60 等）"""
        # Ａ 是全角大写 A，宽度应为2
        self.assertEqual(BackupManager._display_width("Ａ"), 2)
        # ！ 是全角感叹号
        self.assertEqual(BackupManager._display_width("！"), 2)

    def test_display_width_mixed(self):
        """测试中英混合字符串宽度"""
        # "hi你好" = 1+1+2+2 = 6
        self.assertEqual(BackupManager._display_width("hi你好"), 6)

    def test_display_width_non_string(self):
        """测试非字符串输入"""
        self.assertEqual(BackupManager._display_width(123), 3)

    def test_display_width_empty(self):
        """测试空字符串"""
        self.assertEqual(BackupManager._display_width(""), 0)

    def test_list_folder_table_only_history(self):
        """测试仅含 _history 数据时返回空提示"""
        self.manager.data["_history"] = [
            {"time": "2026-01-01", "source": "/x", "size_mb": 1.0, "files_count": 1}
        ]
        text = self.manager.list_folder_table()
        self.assertEqual(text, t("cmd.all.empty"))

    def test_format_history_table_empty(self):
        """测试无历史记录时返回提示"""
        text = self.manager.format_history_table()
        self.assertEqual(text, t("cmd.list.empty"))

    def test_format_history_table_with_data(self):
        """测试有历史记录时生成表格"""
        self.manager.add_folder(self.source_folder, self.target_folder, "")
        import time

        time.sleep(0.1)
        (Path(self.source_folder) / "f.txt").write_text("x")
        self.manager.execute_backups()
        text = self.manager.format_history_table()
        self.assertIn(self.source_folder, text)
        self.assertIn(t("table.header.time"), text)

    def test_entry_from_list_invalid_data(self):
        """测试 from_list 输入验证：非列表返回空条目"""
        from sbackup.auto_save import BackupEntry

        entry = BackupEntry.from_list("not a list")
        self.assertEqual(entry.mtime, 0.0)
        self.assertEqual(entry.target, "")

    def test_entry_from_list_too_short(self):
        """测试 from_list 输入验证：少于3元素返回空条目"""
        from sbackup.auto_save import BackupEntry

        entry = BackupEntry.from_list([1.0, "/path"])
        self.assertEqual(entry.mtime, 0.0)
        self.assertEqual(entry.target, "")

    def test_entry_from_list_empty(self):
        """测试 from_list 输入验证：空列表"""
        from sbackup.auto_save import BackupEntry

        entry = BackupEntry.from_list([])
        self.assertEqual(entry.mtime, 0.0)


class TestUploadSftp(unittest.TestCase):
    """测试 _upload_to_sftp 静态方法"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "backup.zip")
        with open(self.test_file, "w") as f:
            f.write("fake backup")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("sbackup.sftp.SFTPClient")
    def test_upload_not_configured(self, mock_sftp_cls):
        """测试 SFTP 未配置时打印错误"""
        from sbackup.config import Config

        config = Config(sftp_enabled=False)
        with patch("builtins.print") as mock_print:
            BackupManager._upload_to_sftp([self.test_file], config)
            mock_print.assert_called()

    @patch("sbackup.sftp.SFTPClient")
    def test_upload_no_credentials(self, mock_sftp_cls):
        """测试无凭据时打印提示"""
        from sbackup.config import Config

        mock_sftp_cls.try_default_key.return_value = None
        config = Config(sftp_enabled=True, sftp_host="host", sftp_password="")
        with patch("builtins.print") as mock_print:
            BackupManager._upload_to_sftp([self.test_file], config)
            printed = " ".join(str(c) for c in mock_print.call_args_list)
            # 无默认私钥时应打印提示
            self.assertIn(t("cmd.sftp.no_default_key"), printed)

    @patch("sbackup.sftp.SFTPClient")
    def test_upload_success(self, mock_sftp_cls):
        """测试 SFTP 上传成功"""
        from sbackup.config import Config

        mock_client = MagicMock()
        mock_sftp_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_sftp_cls.return_value.__exit__ = MagicMock(return_value=False)

        config = Config(
            sftp_enabled=True,
            sftp_host="host",
            sftp_user="user",
            sftp_password="pass",
        )
        with patch("builtins.print"):
            BackupManager._upload_to_sftp([self.test_file], config)
        mock_client.upload_file.assert_called_once()

    @patch("sbackup.sftp.SFTPClient")
    def test_upload_sftp_error(self, mock_sftp_cls):
        """测试 SFTP 上传失败"""
        from sbackup.config import Config
        from sbackup.sftp import SFTPError

        mock_client = MagicMock()
        mock_client.upload_file.side_effect = SFTPError("upload failed")
        mock_sftp_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_sftp_cls.return_value.__exit__ = MagicMock(return_value=False)

        config = Config(
            sftp_enabled=True,
            sftp_host="host",
            sftp_user="user",
            sftp_password="pass",
        )
        with patch("builtins.print") as mock_print:
            BackupManager._upload_to_sftp([self.test_file], config)
            printed = " ".join(str(c) for c in mock_print.call_args_list)
            self.assertIn("upload failed", printed)


class TestUploadWebdav(unittest.TestCase):
    """测试 _upload_to_webdav 静态方法"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "backup.zip")
        with open(self.test_file, "w") as f:
            f.write("fake backup")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("sbackup.webdav.WebDAVClient")
    def test_upload_not_configured(self, mock_wdav_cls):
        """测试 WebDAV 未配置时打印错误"""
        from sbackup.config import Config

        config = Config(webdav_enabled=False)
        with patch("builtins.print") as mock_print:
            BackupManager._upload_to_webdav([self.test_file], config)
            mock_print.assert_called()

    @patch("sbackup.webdav.WebDAVClient")
    def test_upload_success(self, mock_wdav_cls):
        """测试 WebDAV 上传成功"""
        from sbackup.config import Config

        mock_client = MagicMock()
        mock_wdav_cls.return_value = mock_client

        config = Config(
            webdav_enabled=True,
            webdav_url="https://dav.example.com",
            webdav_user="user",
            webdav_password="pass",
        )
        with patch("builtins.print"):
            BackupManager._upload_to_webdav([self.test_file], config)
        mock_client.connect.assert_called_once()
        mock_client.upload_file.assert_called_once()

    @patch("sbackup.webdav.WebDAVClient")
    def test_upload_webdav_error(self, mock_wdav_cls):
        """测试 WebDAV 上传失败"""
        from sbackup.config import Config
        from sbackup.webdav import WebDAVError

        mock_client = MagicMock()
        mock_client.upload_file.side_effect = WebDAVError("upload failed")
        mock_wdav_cls.return_value = mock_client

        config = Config(
            webdav_enabled=True,
            webdav_url="https://dav.example.com",
            webdav_user="user",
            webdav_password="pass",
        )
        with patch("builtins.print") as mock_print:
            BackupManager._upload_to_webdav([self.test_file], config)
            printed = " ".join(str(c) for c in mock_print.call_args_list)
            self.assertIn("upload failed", printed)

    @patch("sbackup.webdav.WebDAVClient")
    def test_upload_connect_error(self, mock_wdav_cls):
        """测试 WebDAV 连接失败"""
        from sbackup.config import Config
        from sbackup.webdav import WebDAVError

        mock_wdav_cls.return_value.connect.side_effect = WebDAVError("connect failed")

        config = Config(
            webdav_enabled=True,
            webdav_url="https://dav.example.com",
            webdav_user="user",
            webdav_password="pass",
        )
        with patch("builtins.print") as mock_print:
            BackupManager._upload_to_webdav([self.test_file], config)
            printed = " ".join(str(c) for c in mock_print.call_args_list)
            self.assertIn("connect failed", printed)


if __name__ == "__main__":
    unittest.main()
