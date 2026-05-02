"""
单元测试 for sbackup.sftp 模块
"""

import unittest
import os
import tempfile
from unittest.mock import patch, MagicMock
from sbackup.sftp import SFTPClient, SFTPError


class TestSFTPClient(unittest.TestCase):
    def setUp(self):
        self.host = "test.example.com"
        self.port = 22
        self.user = "testuser"
        self.password = "testpass"
        self.key_file = "/path/to/id_rsa"
        self.key_passphrase = "keypass"

    def test_init_stores_credentials(self):
        """测试初始化存储凭据"""
        client = SFTPClient(self.host, self.port, self.user, self.password)
        self.assertEqual(client.host, self.host)
        self.assertEqual(client.port, self.port)
        self.assertEqual(client.user, self.user)
        self.assertEqual(client.password, self.password)
        self.assertIsNone(client._transport)
        self.assertIsNone(client._sftp)

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    def test_connect_success(self, mock_sftp_cls, mock_transport_cls):
        """测试成功连接"""
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        mock_sftp_cls.from_transport.return_value = mock_sftp

        client = SFTPClient(self.host, self.port, self.user, self.password)
        client.connect()

        mock_transport_cls.assert_called_once_with((self.host, self.port))
        mock_transport.connect.assert_called_once_with(
            username=self.user, password=self.password
        )
        mock_sftp_cls.from_transport.assert_called_once_with(mock_transport)

    @patch("paramiko.Transport")
    def test_connect_auth_failure(self, mock_transport_cls):
        """测试认证失败"""
        import paramiko

        mock_transport = MagicMock()
        mock_transport.connect.side_effect = paramiko.AuthenticationException()
        mock_transport_cls.return_value = mock_transport

        client = SFTPClient(self.host, self.port, self.user, self.password)
        with self.assertRaises(SFTPError) as cm:
            client.connect()
        self.assertIn("SFTP", str(cm.exception))

    @patch("paramiko.Transport")
    def test_connect_ssh_error(self, mock_transport_cls):
        """测试 SSH 连接错误"""
        import paramiko

        mock_transport = MagicMock()
        mock_transport.connect.side_effect = paramiko.SSHException("Connection refused")
        mock_transport_cls.return_value = mock_transport

        client = SFTPClient(self.host, self.port, self.user, self.password)
        with self.assertRaises(SFTPError):
            client.connect()

    @patch("paramiko.Transport")
    def test_connect_os_error(self, mock_transport_cls):
        """测试网络不可达"""
        mock_transport_cls.side_effect = OSError("Network unreachable")

        client = SFTPClient(self.host, self.port, self.user, self.password)
        with self.assertRaises(SFTPError):
            client.connect()

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    def test_disconnect(self, mock_sftp_cls, mock_transport_cls):
        """测试断开连接"""
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        mock_sftp_cls.from_transport.return_value = mock_sftp

        client = SFTPClient(self.host, self.port, self.user, self.password)
        client.connect()
        client.disconnect()

        mock_sftp.close.assert_called_once()
        mock_transport.close.assert_called_once()
        self.assertIsNone(client._sftp)
        self.assertIsNone(client._transport)

    def test_disconnect_without_connect(self):
        """测试未连接时断开不报错"""
        client = SFTPClient(self.host, self.port, self.user, self.password)
        client.disconnect()  # 不应抛出异常

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    def test_context_manager(self, mock_sftp_cls, mock_transport_cls):
        """测试上下文管理器"""
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        mock_sftp_cls.from_transport.return_value = mock_sftp

        with SFTPClient(self.host, self.port, self.user, self.password) as client:
            self.assertIsNotNone(client._transport)
            self.assertIsNotNone(client._sftp)

        # 退出上下文后应断开
        self.assertIsNone(client._sftp)
        self.assertIsNone(client._transport)

    def test_upload_not_connected(self):
        """测试未连接时上传报错"""
        client = SFTPClient(self.host, self.port, self.user, self.password)
        with self.assertRaises(SFTPError):
            client.upload_file("/local/file.zip", "/remote/")

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    def test_upload_local_not_found(self, mock_sftp_cls, mock_transport_cls):
        """测试本地文件不存在"""
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        mock_sftp_cls.from_transport.return_value = mock_sftp

        client = SFTPClient(self.host, self.port, self.user, self.password)
        client.connect()
        with self.assertRaises(SFTPError):
            client.upload_file("/nonexistent/file.zip", "/remote/")

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    def test_upload_success(self, mock_sftp_cls, mock_transport_cls):
        """测试成功上传"""
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        mock_sftp_cls.from_transport.return_value = mock_sftp

        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(b"test data")
            temp_path = f.name

        try:
            client = SFTPClient(self.host, self.port, self.user, self.password)
            client.connect()
            client.upload_file(temp_path, "/remote/backups/")

            # 验证 sftp.put 被调用
            mock_sftp.put.assert_called_once()
            call_args = mock_sftp.put.call_args
            self.assertEqual(call_args[0][0], temp_path)
            self.assertIn(os.path.basename(temp_path), call_args[0][1])
            self.assertTrue(call_args[1]["confirm"])
        finally:
            os.unlink(temp_path)

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    def test_upload_with_progress(self, mock_sftp_cls, mock_transport_cls):
        """测试带进度回调的上传"""
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        mock_sftp_cls.from_transport.return_value = mock_sftp

        progress_values = []

        def progress_cb(sent, total):
            progress_values.append((sent, total))

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(b"x" * 1000)
            temp_path = f.name

        try:
            client = SFTPClient(self.host, self.port, self.user, self.password)
            client.connect()
            client.upload_file(temp_path, "/remote/", progress_callback=progress_cb)

            mock_sftp.put.assert_called_once()
            # 验证 callback 参数被传递
            self.assertEqual(mock_sftp.put.call_args[1]["callback"], progress_cb)
        finally:
            os.unlink(temp_path)

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    def test_upload_creates_remote_dir(self, mock_sftp_cls, mock_transport_cls):
        """测试上传时自动创建远程目录"""
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        # 第一次 stat 抛出 FileNotFoundError（目录不存在）
        mock_sftp.stat.side_effect = FileNotFoundError()
        mock_sftp_cls.from_transport.return_value = mock_sftp

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(b"test")
            temp_path = f.name

        try:
            client = SFTPClient(self.host, self.port, self.user, self.password)
            client.connect()
            client.upload_file(temp_path, "/remote/newdir/")

            # 验证 mkdir 被调用
            mock_sftp.mkdir.assert_called_with("/remote/newdir")
        finally:
            os.unlink(temp_path)

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    def test_upload_os_error(self, mock_sftp_cls, mock_transport_cls):
        """测试上传时 OS 错误"""
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        mock_sftp.put.side_effect = OSError("Disk full")
        mock_sftp_cls.from_transport.return_value = mock_sftp

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(b"test")
            temp_path = f.name

        try:
            client = SFTPClient(self.host, self.port, self.user, self.password)
            client.connect()
            with self.assertRaises(SFTPError):
                client.upload_file(temp_path, "/remote/")
        finally:
            os.unlink(temp_path)

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    def test_test_connection_success(self, mock_sftp_cls, mock_transport_cls):
        """测试连接测试成功"""
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        mock_sftp_cls.from_transport.return_value = mock_sftp

        client = SFTPClient(self.host, self.port, self.user, self.password)
        result = client.test_connection()
        self.assertTrue(result)
        mock_sftp.listdir.assert_called_once_with(".")

    @patch("paramiko.Transport")
    def test_test_connection_failure(self, mock_transport_cls):
        """测试连接测试失败"""
        import paramiko

        mock_transport = MagicMock()
        mock_transport.connect.side_effect = paramiko.AuthenticationException()
        mock_transport_cls.return_value = mock_transport

        client = SFTPClient(self.host, self.port, self.user, self.password)
        result = client.test_connection()
        self.assertFalse(result)

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    def test_ensure_remote_dir_root(self, mock_sftp_cls, mock_transport_cls):
        """测试远程根目录不需要创建"""
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        mock_sftp_cls.from_transport.return_value = mock_sftp

        client = SFTPClient(self.host, self.port, self.user, self.password)
        client.connect()
        client._ensure_remote_dir("/")
        # 根目录不应调用 stat 或 mkdir
        mock_sftp.stat.assert_not_called()
        mock_sftp.mkdir.assert_not_called()

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    def test_ensure_remote_dir_exists(self, mock_sftp_cls, mock_transport_cls):
        """测试远程目录已存在"""
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        mock_sftp_cls.from_transport.return_value = mock_sftp

        client = SFTPClient(self.host, self.port, self.user, self.password)
        client.connect()
        client._ensure_remote_dir("/existing/dir")
        # 目录存在，不应调用 mkdir
        mock_sftp.stat.assert_called_once_with("/existing/dir")
        mock_sftp.mkdir.assert_not_called()

    # ========== 私钥认证测试 ==========

    def test_init_with_key_file(self):
        """测试初始化存储私钥路径"""
        client = SFTPClient(
            self.host,
            self.port,
            self.user,
            key_file=self.key_file,
            key_passphrase=self.key_passphrase,
        )
        self.assertEqual(client.key_file, self.key_file)
        self.assertEqual(client.key_passphrase, self.key_passphrase)

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    @patch("os.path.isfile", return_value=True)
    @patch("os.path.expanduser", return_value="/home/user/.ssh/id_rsa")
    @patch("paramiko.RSAKey")
    def test_connect_with_key_auth(
        self, mock_rsa, mock_expanduser, mock_isfile, mock_sftp_cls, mock_transport_cls
    ):
        """测试私钥认证连接"""
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        mock_sftp_cls.from_transport.return_value = mock_sftp
        mock_pkey = MagicMock()
        mock_rsa.from_private_key_file.return_value = mock_pkey

        client = SFTPClient(
            self.host,
            self.port,
            self.user,
            key_file=self.key_file,
            key_passphrase=self.key_passphrase,
        )
        client.connect()

        # 验证 expanduser 被调用
        mock_expanduser.assert_called_once_with(self.key_file)
        mock_transport.connect.assert_called_once_with(
            username=self.user, pkey=mock_pkey
        )

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    @patch("os.path.isfile", return_value=True)
    @patch("os.path.expanduser", return_value="/home/user/.ssh/id_rsa")
    @patch("paramiko.RSAKey")
    def test_connect_key_auth_no_passphrase(
        self, mock_rsa, mock_expanduser, mock_isfile, mock_sftp_cls, mock_transport_cls
    ):
        """测试无密码短语的私钥认证"""
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        mock_sftp_cls.from_transport.return_value = mock_sftp
        mock_pkey = MagicMock()
        mock_rsa.from_private_key_file.return_value = mock_pkey

        client = SFTPClient(
            self.host,
            self.port,
            self.user,
            key_file=self.key_file,
            key_passphrase="",
        )
        client.connect()

        mock_rsa.from_private_key_file.assert_called_once_with(
            "/home/user/.ssh/id_rsa", password=None
        )

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    @patch("os.path.isfile", return_value=False)
    @patch("os.path.expanduser", return_value="/nonexistent/key")
    def test_connect_falls_back_to_password(
        self, mock_expanduser, mock_isfile, mock_sftp_cls, mock_transport_cls
    ):
        """测试私钥文件不存在时回退到密码认证"""
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        mock_sftp_cls.from_transport.return_value = mock_sftp

        client = SFTPClient(
            self.host,
            self.port,
            self.user,
            self.password,
            key_file="/nonexistent/key",
        )
        client.connect()

        mock_transport.connect.assert_called_once_with(
            username=self.user, password=self.password
        )

    @patch("paramiko.RSAKey")
    @patch("paramiko.Ed25519Key")
    @patch("paramiko.ECDSAKey")
    def test_load_private_key_tries_all_formats(
        self, mock_ecdsa, mock_ed25519, mock_rsa
    ):
        """测试 _load_private_key 依次尝试所有密钥格式"""
        import paramiko

        mock_rsa.from_private_key_file.side_effect = paramiko.SSHException("bad")
        mock_ed25519.from_private_key_file.side_effect = paramiko.SSHException("bad")
        mock_pkey = MagicMock()
        mock_ecdsa.from_private_key_file.return_value = mock_pkey

        result = SFTPClient._load_private_key("/path/to/key")
        self.assertEqual(result, mock_pkey)

    @patch("paramiko.RSAKey")
    @patch("paramiko.Ed25519Key")
    @patch("paramiko.ECDSAKey")
    def test_load_private_key_all_fail(self, mock_ecdsa, mock_ed25519, mock_rsa):
        """测试所有密钥格式都失败时抛出异常"""
        import paramiko

        mock_rsa.from_private_key_file.side_effect = paramiko.SSHException("bad")
        mock_ed25519.from_private_key_file.side_effect = paramiko.SSHException("bad")
        mock_ecdsa.from_private_key_file.side_effect = paramiko.SSHException("bad")

        with self.assertRaises(SFTPError):
            SFTPClient._load_private_key("/path/to/bad_key")

    # ========== 默认私钥检测测试 ==========

    @patch("os.path.expanduser")
    @patch("os.path.isfile")
    def test_try_default_key_found_ed25519(self, mock_isfile, mock_expanduser):
        """测试检测到默认 Ed25519 私钥"""
        mock_expanduser.side_effect = lambda p: p.replace("~", "/home/user")
        mock_isfile.side_effect = lambda p: p == "/home/user/.ssh/id_ed25519"

        result = SFTPClient.try_default_key()
        self.assertEqual(result, "/home/user/.ssh/id_ed25519")

    @patch("os.path.expanduser")
    @patch("os.path.isfile")
    def test_try_default_key_found_rsa(self, mock_isfile, mock_expanduser):
        """测试检测到默认 RSA 私钥（Ed25519 不存在时）"""
        mock_expanduser.side_effect = lambda p: p.replace("~", "/home/user")
        mock_isfile.side_effect = lambda p: p == "/home/user/.ssh/id_rsa"

        result = SFTPClient.try_default_key()
        self.assertEqual(result, "/home/user/.ssh/id_rsa")

    @patch("os.path.expanduser")
    @patch("os.path.isfile")
    def test_try_default_key_not_found(self, mock_isfile, mock_expanduser):
        """测试没有找到默认私钥"""
        mock_expanduser.side_effect = lambda p: p.replace("~", "/home/user")
        mock_isfile.return_value = False

        result = SFTPClient.try_default_key()
        self.assertIsNone(result)

    @patch("os.path.expanduser")
    @patch("os.path.isfile")
    def test_try_default_key_priority(self, mock_isfile, mock_expanduser):
        """测试默认私钥优先级（Ed25519 > RSA > ECDSA）"""
        mock_expanduser.side_effect = lambda p: p.replace("~", "/home/user")
        # Ed25519 和 RSA 都存在，应该返回 Ed25519
        mock_isfile.side_effect = lambda p: (
            p
            in [
                "/home/user/.ssh/id_ed25519",
                "/home/user/.ssh/id_rsa",
            ]
        )

        result = SFTPClient.try_default_key()
        self.assertEqual(result, "/home/user/.ssh/id_ed25519")

    # ========== 密码短语检测测试 ==========

    def test_is_passphrase_error_true(self):
        """测试检测到密码短语相关错误"""
        self.assertTrue(SFTPClient._is_passphrase_error("password is required"))
        self.assertTrue(SFTPClient._is_passphrase_error("bad decrypt"))
        self.assertTrue(SFTPClient._is_passphrase_error("no decrypt"))
        self.assertTrue(SFTPClient._is_passphrase_error("passphrase"))
        self.assertTrue(SFTPClient._is_passphrase_error("encrypted key"))

    def test_is_passphrase_error_false(self):
        """测试非密码短语相关错误"""
        self.assertFalse(SFTPClient._is_passphrase_error("not a valid key"))
        self.assertFalse(SFTPClient._is_passphrase_error("format error"))
        self.assertFalse(SFTPClient._is_passphrase_error(""))

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    @patch("os.path.isfile", return_value=True)
    @patch("os.path.expanduser", return_value="/home/user/.ssh/id_rsa")
    @patch("paramiko.RSAKey")
    @patch("paramiko.Ed25519Key")
    @patch("paramiko.ECDSAKey")
    def test_connect_key_needs_passphrase(
        self,
        mock_ecdsa,
        mock_ed25519,
        mock_rsa,
        mock_expanduser,
        mock_isfile,
        mock_sftp_cls,
        mock_transport_cls,
    ):
        """测试私钥需要密码短语时抛出明确错误"""
        import paramiko

        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        mock_sftp_cls.from_transport.return_value = mock_sftp
        # 所有密钥格式都模拟需要密码短语的错误
        mock_rsa.from_private_key_file.side_effect = paramiko.SSHException(
            "not a valid RSA private key file (password is required)"
        )
        mock_ed25519.from_private_key_file.side_effect = paramiko.SSHException(
            "not a valid Ed25519 private key file (password is required)"
        )
        mock_ecdsa.from_private_key_file.side_effect = paramiko.SSHException(
            "not a valid ECDSA private key file (password is required)"
        )

        client = SFTPClient(
            self.host,
            self.port,
            self.user,
            key_file=self.key_file,
            key_passphrase="",
        )
        with self.assertRaises(SFTPError) as ctx:
            client.connect()
        self.assertIn("passphrase", str(ctx.exception).lower())

    @patch("paramiko.Transport")
    @patch("paramiko.SFTPClient")
    @patch("os.path.isfile", return_value=True)
    @patch("os.path.expanduser", return_value="/home/user/.ssh/id_rsa")
    @patch("paramiko.RSAKey")
    def test_connect_key_with_passphrase_ok(
        self, mock_rsa, mock_expanduser, mock_isfile, mock_sftp_cls, mock_transport_cls
    ):
        """测试提供正确密码短语时连接成功"""
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_sftp = MagicMock()
        mock_sftp_cls.from_transport.return_value = mock_sftp
        mock_pkey = MagicMock()
        mock_rsa.from_private_key_file.return_value = mock_pkey

        client = SFTPClient(
            self.host,
            self.port,
            self.user,
            key_file=self.key_file,
            key_passphrase="correct_passphrase",
        )
        client.connect()

        mock_rsa.from_private_key_file.assert_called_once_with(
            "/home/user/.ssh/id_rsa", password="correct_passphrase"
        )
        mock_transport.connect.assert_called_once_with(
            username=self.user, pkey=mock_pkey
        )


if __name__ == "__main__":
    unittest.main()
