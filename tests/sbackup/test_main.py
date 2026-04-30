"""
单元测试 for sbackup.__init__ 模块
"""
import unittest
import sys
import os
import logging
import tempfile
import shutil
from unittest.mock import patch
from sbackup.i18n import t


class TestMain(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_argv = sys.argv.copy()
        # 保存并重置 logging 状态
        self._root_handlers = logging.root.handlers[:]
        self._root_level = logging.root.level

    def tearDown(self):
        sys.argv = self.original_argv
        shutil.rmtree(self.test_dir, ignore_errors=True)
        # 恢复 logging 状态
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
        sys.argv = ["sbackup", "--lang", "en_US", "add", "/nonexistent/path", "/tmp"]
        from sbackup import run
        run()
        printed = " ".join(str(call) for call in mock_print.call_args_list)
        self.assertIn(t("err.folder.invalid").split("{")[0].strip(), printed)

    @patch("builtins.print")
    def test_rm_command_nonexistent(self, mock_print):
        """测试 rm 命令删除不存在的策略"""
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


if __name__ == "__main__":
    unittest.main()