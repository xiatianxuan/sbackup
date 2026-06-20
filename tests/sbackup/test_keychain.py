"""单元测试 for sbackup.keychain 模块"""

import sys
import unittest
from unittest.mock import patch, MagicMock


class TestKeychainFunctions(unittest.TestCase):
    """测试 keychain 模块的基础功能（mock 平台 API）"""

    @patch("sbackup.keychain._win32_get_password")
    def test_get_password_windows(self, mock_get):
        """Windows 平台 get_password 应调用 win32 实现"""
        mock_get.return_value = "secret123"
        from sbackup.keychain import get_password

        with patch.object(sys, "platform", "win32"):
            result = get_password("sbackup", "test_user")
        self.assertEqual(result, "secret123")
        mock_get.assert_called_once_with("sbackup", "test_user")

    @patch("sbackup.keychain._darwin_set_password")
    def test_set_password_macos(self, mock_set):
        """macOS 平台 set_password 应调用 darwin 实现"""
        mock_set.return_value = True
        from sbackup.keychain import set_password

        with patch.object(sys, "platform", "darwin"):
            result = set_password("sbackup", "test_user", "mypass")
        self.assertTrue(result)
        mock_set.assert_called_once_with("sbackup", "test_user", "mypass")

    @patch("sbackup.keychain._linux_delete_password")
    def test_delete_password_linux(self, mock_del):
        """Linux 平台 delete_password 应调用 linux 实现"""
        mock_del.return_value = True
        from sbackup.keychain import delete_password

        with patch.object(sys, "platform", "linux"):
            result = delete_password("sbackup", "test_user")
        self.assertTrue(result)
        mock_del.assert_called_once_with("sbackup", "test_user")

    def test_is_available_windows(self):
        """Windows 平台 is_available 应返回 True"""
        from sbackup.keychain import is_available

        with patch.object(sys, "platform", "win32"):
            with patch("sbackup.keychain._win32_get_password") as mock_g:
                mock_g.return_value = None
                self.assertTrue(is_available())

    def test_get_password_exception_returns_none(self):
        """异常时应返回 None 而非抛出"""
        from sbackup.keychain import get_password

        with patch.object(sys, "platform", "win32"):
            with patch("sbackup.keychain._win32_get_password") as mock_g:
                mock_g.side_effect = RuntimeError("API failed")
                result = get_password("sbackup", "test")
                self.assertIsNone(result)

    def test_set_password_exception_returns_false(self):
        """异常时应返回 False 而非抛出"""
        from sbackup.keychain import set_password

        with patch.object(sys, "platform", "darwin"):
            with patch("sbackup.keychain._darwin_set_password") as mock_s:
                mock_s.side_effect = RuntimeError("API failed")
                result = set_password("sbackup", "test", "pass")
                self.assertFalse(result)

    def test_delete_password_exception_returns_false(self):
        """异常时应返回 False 而非抛出"""
        from sbackup.keychain import delete_password

        with patch.object(sys, "platform", "linux"):
            with patch("sbackup.keychain._linux_delete_password") as mock_d:
                mock_d.side_effect = RuntimeError("API failed")
                result = delete_password("sbackup", "test")
                self.assertFalse(result)

    @patch("subprocess.run")
    def test_darwin_get_password(self, mock_run):
        """测试 macOS security CLI 调用"""
        mock_run.return_value = MagicMock(returncode=0, stdout="secret\n")
        from sbackup.keychain import _darwin_get_password

        result = _darwin_get_password("sbackup", "user")
        self.assertEqual(result, "secret")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("security", args)
        self.assertIn("find-generic-password", args)

    @patch("subprocess.run")
    def test_darwin_get_password_not_found(self, mock_run):
        """密钥中找不到密码时返回 None"""
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        from sbackup.keychain import _darwin_get_password

        result = _darwin_get_password("sbackup", "user")
        self.assertIsNone(result)

    @patch("subprocess.run")
    def test_darwin_set_password(self, mock_run):
        """测试 macOS security CLI 存储密码"""
        mock_run.return_value = MagicMock(returncode=0)
        from sbackup.keychain import _darwin_set_password

        result = _darwin_set_password("sbackup", "user", "pass")
        self.assertTrue(result)

    @patch("subprocess.run")
    def test_linux_get_password(self, mock_run):
        """测试 Linux secret-tool CLI 调用"""
        mock_run.return_value = MagicMock(returncode=0, stdout="secret\n")
        from sbackup.keychain import _linux_get_password

        result = _linux_get_password("sbackup", "user")
        self.assertEqual(result, "secret")
        args = mock_run.call_args[0][0]
        self.assertIn("secret-tool", args)

    @patch("subprocess.run")
    def test_linux_set_password(self, mock_run):
        """测试 Linux secret-tool 存储密码"""
        mock_run.return_value = MagicMock(returncode=0)
        from sbackup.keychain import _linux_set_password

        result = _linux_set_password("sbackup", "user", "pass")
        self.assertTrue(result)
        self.assertIn("secret-tool", mock_run.call_args[0][0])

    @patch("subprocess.run")
    def test_is_available_darwin(self, mock_run):
        """macOS is_available 应调用 security help"""
        mock_run.return_value = MagicMock(returncode=0)
        from sbackup.keychain import is_available

        with patch.object(sys, "platform", "darwin"):
            result = is_available()
        self.assertTrue(result)

    @patch("subprocess.run")
    def test_is_available_darwin_not_installed(self, mock_run):
        """security 未安装时 is_available 返回 False"""
        mock_run.side_effect = FileNotFoundError()
        from sbackup.keychain import is_available

        with patch.object(sys, "platform", "darwin"):
            result = is_available()
        self.assertFalse(result)
