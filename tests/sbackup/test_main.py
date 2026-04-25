"""
单元测试 for sbackup.__init__ 模块
"""
import unittest
import sys
from unittest.mock import patch


class TestMain(unittest.TestCase):
    @patch("builtins.print")
    def test_version_command(self, mock_print):
        """测试 version 命令"""
        sys.argv = ["sbackup", "version"]
        from sbackup import run
        run()
        mock_print.assert_called()

if __name__ == "__main__":
    unittest.main()