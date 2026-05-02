"""
单元测试 for sbackup.__init__ 模块
"""

import unittest
import sys
import os
import json
import logging
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from sbackup.i18n import t


class TestMain(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_argv = sys.argv.copy()
        self._root_handlers = logging.root.handlers[:]
        self._root_level = logging.root.level
        # 创建 config.json 指向测试目录的数据文件
        self.data_path = os.path.join(self.test_dir, "sbackup.json")
        with open(os.path.join(self.test_dir, "config.json"), "w") as f:
            json.dump({"data_file": self.data_path}, f)

    def tearDown(self):
        sys.argv = self.original_argv
        shutil.rmtree(self.test_dir, ignore_errors=True)
        logging.root.handlers = self._root_handlers
        logging.root.setLevel(self._root_level)

    @patch("builtins.print")
    def test_version_command(self, mock_print):
        """测试 version 命令"""
        sys.argv = ["sbackup", "version"]
        from sbackup import run

        run()
        mock_print.assert_called()

    @patch("argparse.ArgumentParser.print_help")
    def test_no_command_shows_help(self, mock_help):
        """测试无命令时显示帮助"""
        sys.argv = ["sbackup"]
        from sbackup import run

        run()
        mock_help.assert_called_once()

    @patch("builtins.print")
    def test_add_command_invalid_source(self, mock_print):
        """测试 add 命令传入无效源目录"""
        os.chdir(self.test_dir)
        sys.argv = ["sbackup", "--lang", "en_US", "add", "/nonexistent/path", "/tmp"]
        from sbackup import run

        run()
        printed = " ".join(str(call) for call in mock_print.call_args_list)
        self.assertIn(t("err.folder.invalid").split("{")[0].strip(), printed)

    @patch("builtins.print")
    def test_rm_command_nonexistent(self, mock_print):
        """测试 rm 命令删除不存在的策略"""
        os.chdir(self.test_dir)
        sys.argv = ["sbackup", "--lang", "en_US", "rm", "/nonexistent/path"]
        from sbackup import run

        run()
        printed = " ".join(str(call) for call in mock_print.call_args_list)
        self.assertIn(t("warn.no.strategy.found").split("{")[0].strip(), printed)

    @patch("builtins.print")
    def test_all_command_empty(self, mock_print):
        """测试 all 命令在无策略时输出提示"""
        os.chdir(self.test_dir)
        sys.argv = ["sbackup", "--lang", "en_US", "all"]
        from sbackup import run

        run()
        printed = " ".join(str(call) for call in mock_print.call_args_list)
        self.assertIn(t("cmd.all.empty"), printed)

    @patch("builtins.print")
    def test_lang_switch(self, mock_print):
        """测试 --lang 参数切换语言"""
        os.chdir(self.test_dir)
        sys.argv = ["sbackup", "--lang", "en_US", "all"]
        from sbackup import run

        run()
        printed = " ".join(str(call) for call in mock_print.call_args_list)
        self.assertIn("No backup strategies configured", printed)

    @patch("builtins.print")
    def test_debug_mode_sets_logging(self, mock_print):
        """测试 --debug 参数开启 DEBUG 日志级别"""
        os.chdir(self.test_dir)
        sys.argv = ["sbackup", "--debug", "--lang", "en_US", "all"]
        from sbackup import run

        run()
        self.assertEqual(logging.root.level, logging.DEBUG)

    @patch("builtins.print")
    def test_no_debug_keeps_default_logging(self, mock_print):
        """测试无 --debug 时日志级别保持默认"""
        os.chdir(self.test_dir)
        logging.root.setLevel(logging.WARNING)
        sys.argv = ["sbackup", "--lang", "en_US", "all"]
        from sbackup import run

        run()
        self.assertEqual(logging.root.level, logging.WARNING)

    @patch("builtins.print")
    def test_rm_command_success(self, mock_print):
        """测试 rm 命令成功删除策略"""
        os.chdir(self.test_dir)
        sys.argv = ["sbackup", "--lang", "en_US", "add", self.test_dir, self.test_dir]
        from sbackup import run

        result1 = run()
        self.assertEqual(result1, 0, f"add failed with {result1}")
        sys.argv = ["sbackup", "--lang", "en_US", "rm", self.test_dir]
        result2 = run()
        self.assertEqual(result2, 0)

    @patch("builtins.print")
    def test_save_command(self, mock_print):
        """测试 save 命令执行"""
        os.chdir(self.test_dir)
        sys.argv = ["sbackup", "--lang", "en_US", "save"]
        from sbackup import run

        result = run()
        self.assertEqual(result, 0)

    @patch("builtins.print")
    def test_format_option(self, mock_print):
        """测试 --format 参数"""
        os.chdir(self.test_dir)
        sys.argv = ["sbackup", "--lang", "en_US", "--format", "tar.gz", "all"]
        from sbackup import run

        result = run()
        self.assertEqual(result, 0)

    @patch("builtins.print")
    def test_restore_command_invalid(self, mock_print):
        """测试 restore 命令传入无效文件"""
        os.chdir(self.test_dir)
        sys.argv = ["sbackup", "--lang", "en_US", "restore", "/nonexistent.zip", "/tmp"]
        from sbackup import run

        result = run()
        self.assertEqual(result, 1)

    @patch("builtins.print")
    @patch("time.sleep", return_value=None)
    def test_watch_command(self, mock_sleep, mock_print):
        """测试 watch 命令启动"""
        os.chdir(self.test_dir)
        sys.argv = ["sbackup", "--lang", "en_US", "watch", "--interval", "1"]
        from sbackup import run
        import sbackup.__init__ as init_module

        original_execute = init_module.BackupManager.execute_backups

        def mock_execute(self, *args, **kwargs):
            raise KeyboardInterrupt()

        init_module.BackupManager.execute_backups = mock_execute
        try:
            result = run()
            self.assertEqual(result, 0)
        finally:
            init_module.BackupManager.execute_backups = original_execute

    @patch("builtins.print")
    def test_add_with_format(self, mock_print):
        """测试 add 命令指定条目级格式"""
        os.chdir(self.test_dir)
        sys.argv = [
            "sbackup",
            "--lang",
            "en_US",
            "add",
            self.test_dir,
            self.test_dir,
            "--format",
            "tar.gz",
        ]
        from sbackup import run
        from sbackup.auto_save import BackupManager

        result = run()
        self.assertEqual(result, 0)
        # 验证数据中条目级格式已持久化
        manager = BackupManager(data_file=os.path.join(self.test_dir, "sbackup.json"))
        abs_path = os.path.abspath(self.test_dir)
        entry = manager._get_entry(abs_path)
        assert entry is not None, "entry should not be None"
        self.assertEqual(entry.compression_format, "TAR_GZ")

    def test_interval_accepts_float(self):
        """测试 --interval 接受浮点数值"""
        from sbackup import get_parser

        parser = get_parser()
        # 解析 float 间隔值
        args = parser.parse_args(["watch", "--interval", "0.5"])
        self.assertEqual(args.interval, 0.5)
        self.assertEqual(args.command, "watch")

        # 解析整数间隔值也应正常工作
        args = parser.parse_args(["watch", "--interval", "30"])
        self.assertEqual(args.interval, 30)

    def test_argparse_invalid_choice_localized(self):
        """测试 argparse 无效选择错误被本地化"""
        from sbackup import get_parser
        from sbackup.i18n import set_locale
        from io import StringIO

        # 确保 zh_CN 语言包已加载
        set_locale("zh_CN")
        parser = get_parser()
        old_stderr = sys.stderr
        sys.stderr = StringIO()
        try:
            with self.assertRaises(SystemExit) as cm:
                parser.parse_args(["--format", "rar", "save"])
            self.assertEqual(cm.exception.code, 2)
            stderr_output = sys.stderr.getvalue()
            # 检查本地化文本存在（zh_CN 默认）
            self.assertIn("无效的选择", stderr_output)
        finally:
            sys.stderr = old_stderr

    def test_argparse_invalid_float_localized(self):
        """测试 argparse 无效浮点数错误被本地化"""
        from sbackup import get_parser
        from sbackup.i18n import set_locale
        from io import StringIO

        # 确保 zh_CN 语言包已加载
        set_locale("zh_CN")
        parser = get_parser()
        old_stderr = sys.stderr
        sys.stderr = StringIO()
        try:
            with self.assertRaises(SystemExit) as cm:
                parser.parse_args(["watch", "--interval", "abc"])
            self.assertEqual(cm.exception.code, 2)
            stderr_output = sys.stderr.getvalue()
            # 检查本地化文本存在（zh_CN 默认）
            self.assertIn("无效的浮点数值", stderr_output)
        finally:
            sys.stderr = old_stderr

    @patch("builtins.print")
    def test_save_with_sftp_flag(self, mock_print):
        """测试 save --sftp 参数传递"""
        os.chdir(self.test_dir)
        sys.argv = ["sbackup", "--lang", "en_US", "save", "--sftp"]
        from sbackup import run
        from sbackup.auto_save import BackupManager

        original_execute = BackupManager.execute_backups

        def mock_execute(
            self, keep=0, password="", sftp_upload=False, webdav_upload=False
        ):
            self._sftp_called = sftp_upload

        BackupManager.execute_backups = mock_execute
        try:
            result = run()
            self.assertEqual(result, 0)
        finally:
            BackupManager.execute_backups = original_execute

    @patch("builtins.print")
    def test_sftp_test_not_configured(self, mock_print):
        """测试 sftp test 未配置时报错"""
        os.chdir(self.test_dir)
        sys.argv = ["sbackup", "--lang", "en_US", "sftp", "test"]
        from sbackup import run

        result = run()
        self.assertEqual(result, 1)
        printed = " ".join(str(call) for call in mock_print.call_args_list)
        self.assertIn("not configured", printed)

    @patch("builtins.print")
    @patch("builtins.input")
    @patch("getpass.getpass")
    @patch("sbackup.sftp.SFTPClient.try_default_key", return_value=None)
    def test_sftp_config_interactive(
        self, mock_try_key, mock_getpass, mock_input, mock_print
    ):
        """测试 sftp config 交互式配置"""
        mock_input.side_effect = [
            "testhost",
            "2222",
            "admin",
            "",  # key_file (空，使用密码)
            "/backups",
        ]
        mock_getpass.side_effect = [
            "secret",  # password
        ]
        os.chdir(self.test_dir)
        sys.argv = ["sbackup", "--lang", "en_US", "sftp", "config"]
        from sbackup import run

        result = run()
        self.assertEqual(result, 0)
        printed = " ".join(str(call) for call in mock_print.call_args_list)
        self.assertIn("saved", printed)

    @patch("builtins.print")
    def test_sftp_config_with_args(self, mock_print):
        """测试 sftp config 通过命令行参数配置"""
        os.chdir(self.test_dir)
        sys.argv = [
            "sbackup",
            "--lang",
            "en_US",
            "sftp",
            "config",
            "--host",
            "myhost",
            "--port",
            "2222",
            "--user",
            "admin",
            "--password",
            "secret",
            "--key-file",
            "/path/to/id_rsa",
            "--key-passphrase",
            "keypass",
            "--remote-path",
            "/backups",
        ]
        from sbackup import run

        result = run()
        self.assertEqual(result, 0)
        printed = " ".join(str(call) for call in mock_print.call_args_list)
        self.assertIn("saved", printed)

    @patch("builtins.print")
    def test_sftp_test_with_config(self, mock_print):
        """测试 sftp test 连接成功"""
        os.chdir(self.test_dir)
        # 先配置 SFTP
        from sbackup.config import save_sftp_config

        save_sftp_config(
            "testhost",
            22,
            "user",
            "pass",
            "/",
            key_file="/path/to/key",
            key_passphrase="keypass",
            config_file=os.path.join(self.test_dir, "config.json"),
        )

        sys.argv = ["sbackup", "--lang", "en_US", "sftp", "test"]
        from sbackup import run
        from sbackup.sftp import SFTPClient

        original_connect = SFTPClient.connect

        def mock_connect(self):
            pass

        SFTPClient.connect = mock_connect
        try:
            result = run()
            self.assertEqual(result, 0)
        finally:
            SFTPClient.connect = original_connect

    @patch("builtins.print")
    @patch("getpass.getpass")
    def test_sftp_test_with_key_no_passphrase(self, mock_getpass, mock_print):
        """测试 sftp test 已配置私钥但无密码短语"""
        os.chdir(self.test_dir)
        from sbackup.config import save_sftp_config

        save_sftp_config(
            "testhost",
            22,
            "user",
            "",
            "/",
            key_file="/path/to/key",
            key_passphrase="",
            config_file=os.path.join(self.test_dir, "config.json"),
        )

        sys.argv = ["sbackup", "--lang", "en_US", "sftp", "test"]
        from sbackup import run
        from sbackup.sftp import SFTPClient, SFTPError

        # 模拟私钥需要密码短语，用户直接回车放弃
        mock_getpass.side_effect = [""]

        original_load = SFTPClient._load_private_key

        def mock_load(key_file, passphrase):
            if passphrase == "":
                raise SFTPError("needs passphrase")
            return MagicMock()

        SFTPClient._load_private_key = staticmethod(mock_load)
        try:
            result = run()
            self.assertEqual(result, 1)
        finally:
            SFTPClient._load_private_key = staticmethod(original_load)

    @patch("builtins.print")
    @patch("builtins.input")
    @patch("getpass.getpass")
    @patch("sbackup.sftp.SFTPClient.try_default_key")
    def test_sftp_config_auto_key_needs_passphrase(
        self, mock_try_key, mock_getpass, mock_input, mock_print
    ):
        """测试 sftp config 自动检测私钥需密码短语"""
        mock_try_key.return_value = "/home/user/.ssh/id_ed25519"
        mock_input.side_effect = [
            "testhost",
            "2222",
            "admin",
            "",  # key_file 为空，触发自动检测
            "/backups",  # remote_path
        ]
        # 自动检测到私钥后进入 if 分支，getpass 被调用一次后返回 None
        # 然后回退到密码认证，getpass 再被调用一次
        mock_getpass.side_effect = ["", "correct_passphrase"]
        os.chdir(self.test_dir)
        sys.argv = ["sbackup", "--lang", "en_US", "sftp", "config"]
        from sbackup import run
        from sbackup.sftp import SFTPClient, SFTPError

        original_load = SFTPClient._load_private_key

        def mock_load(key_file, passphrase):
            if passphrase == "":
                raise SFTPError("needs passphrase")
            return MagicMock()

        SFTPClient._load_private_key = staticmethod(mock_load)
        try:
            result = run()
            self.assertEqual(result, 0)
        finally:
            SFTPClient._load_private_key = staticmethod(original_load)


if __name__ == "__main__":
    unittest.main()
