"""
WebDAV 模块测试：WebDAVClient 连接/上传/测试
"""

import os
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock
from sbackup.webdav import WebDAVClient, WebDAVError


class TestWebDAVClient(unittest.TestCase):
    """测试 WebDAVClient"""

    def setUp(self):
        self.url = "https://dav.jianguoyun.com/dav/"
        self.user = "test@example.com"
        self.password = "secret"
        self.client = WebDAVClient(self.url, self.user, self.password)
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")
        with open(self.test_file, "w") as f:
            f.write("hello webdav")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_url(self):
        """测试 URL 构建"""
        self.assertEqual(self.client._build_url(), "https://dav.jianguoyun.com/dav")
        self.assertEqual(
            self.client._build_url("backups"), "https://dav.jianguoyun.com/dav/backups"
        )
        self.assertEqual(
            self.client._build_url("/backups/"),
            "https://dav.jianguoyun.com/dav/backups",
        )

    def test_make_auth(self):
        """测试 Basic Auth 生成"""
        auth = self.client._make_auth()
        self.assertTrue(auth.startswith("Basic "))

    @patch("urllib.request.urlopen")
    def test_connect_success(self, mock_urlopen):
        """测试连接成功"""
        mock_urlopen.return_value = MagicMock()
        self.client.connect()
        mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_connect_auth_failure(self, mock_urlopen):
        """测试连接认证失败"""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            self.url, 401, "Unauthorized", {}, None
        )
        with self.assertRaises(WebDAVError) as ctx:
            self.client.connect()
        self.assertIn("auth", str(ctx.exception).lower())

    @patch("urllib.request.urlopen")
    def test_connect_network_error(self, mock_urlopen):
        """测试连接网络错误"""
        mock_urlopen.side_effect = OSError("Connection refused")
        with self.assertRaises(WebDAVError):
            self.client.connect()

    @patch("urllib.request.urlopen")
    def test_upload_file_success(self, mock_urlopen):
        """测试文件上传成功"""
        mock_urlopen.return_value = MagicMock()
        mock_urlopen.return_value.read.return_value = b""
        size = self.client.upload_file(self.test_file, "backups/test.txt")
        self.assertEqual(size, os.path.getsize(self.test_file))

    def test_upload_file_not_found(self):
        """测试上传不存在的文件"""
        with self.assertRaises(WebDAVError) as ctx:
            self.client.upload_file("/nonexistent/file.txt", "remote.txt")
        self.assertIn("not found", str(ctx.exception).lower())

    @patch("urllib.request.urlopen")
    def test_upload_file_http_error(self, mock_urlopen):
        """测试上传 HTTP 错误"""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            self.url, 500, "Server Error", {}, None
        )
        with self.assertRaises(WebDAVError) as ctx:
            self.client.upload_file(self.test_file, "remote.txt")
        self.assertIn("failed", str(ctx.exception).lower())

    @patch("urllib.request.urlopen")
    def test_ensure_remote_dir_creates(self, mock_urlopen):
        """测试递归创建远程目录"""
        mock_urlopen.return_value = MagicMock()
        self.client._ensure_remote_dir("a/b/c")
        # 应该调用 3 次 MKCOL
        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("urllib.request.urlopen")
    def test_ensure_remote_dir_exists(self, mock_urlopen):
        """测试目录已存在（405）"""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            self.url, 405, "Method Not Allowed", {}, None
        )
        self.client._ensure_remote_dir("existing")  # 不应抛出异常

    @patch("urllib.request.urlopen")
    def test_ensure_remote_dir_empty(self, mock_urlopen):
        """测试空路径不操作"""
        self.client._ensure_remote_dir("")
        mock_urlopen.assert_not_called()

    @patch("urllib.request.urlopen")
    def test_test_connection_success(self, mock_urlopen):
        """测试连接测试成功"""
        mock_urlopen.return_value = MagicMock()
        result = self.client.test_connection()
        self.assertTrue(result)

    @patch("urllib.request.urlopen")
    def test_test_connection_failure(self, mock_urlopen):
        """测试连接测试失败"""
        mock_urlopen.side_effect = OSError("timeout")
        result = self.client.test_connection()
        self.assertFalse(result)

    @patch("urllib.request.urlopen")
    def test_ensure_remote_dir_401(self, mock_urlopen):
        """测试 MKCOL 认证失败"""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            self.url, 401, "Unauthorized", {}, None
        )
        with self.assertRaises(WebDAVError) as ctx:
            self.client._ensure_remote_dir("secret")
        self.assertIn("auth", str(ctx.exception).lower())

    @patch("urllib.request.urlopen")
    def test_ensure_remote_dir_other_error(self, mock_urlopen):
        """测试 MKCOL 其他 HTTP 错误"""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            self.url, 500, "Server Error", {}, None
        )
        with self.assertRaises(WebDAVError):
            self.client._ensure_remote_dir("bad_dir")

    @patch("urllib.request.urlopen")
    def test_ensure_remote_dir_os_error(self, mock_urlopen):
        """测试 MKCOL 网络错误"""
        mock_urlopen.side_effect = OSError("Connection refused")
        with self.assertRaises(WebDAVError):
            self.client._ensure_remote_dir("offline_dir")

    @patch("urllib.request.urlopen")
    def test_upload_file_401(self, mock_urlopen):
        """测试上传时认证失败"""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            self.url, 401, "Unauthorized", {}, None
        )
        with self.assertRaises(WebDAVError) as ctx:
            self.client.upload_file(self.test_file, "backups/test.txt")
        self.assertIn("auth", str(ctx.exception).lower())

    @patch("urllib.request.urlopen")
    def test_upload_file_os_error(self, mock_urlopen):
        """测试上传时网络错误"""
        # 首次调用 (_ensure_remote_dir 的 MKCOL) 成功，第二次 (PUT) 失败
        mock_urlopen.side_effect = [
            MagicMock(),  # MKCOL 成功
            OSError("Network unreachable"),  # PUT 失败
        ]
        with self.assertRaises(WebDAVError) as ctx:
            self.client.upload_file(self.test_file, "backups/test.txt")
        self.assertIn("backups/test.txt", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_connect_non_auth_http_error(self, mock_urlopen):
        """测试连接时非认证 HTTP 错误"""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            self.url, 502, "Bad Gateway", {}, None
        )
        with self.assertRaises(WebDAVError):
            self.client.connect()

    def test_context_manager(self):
        """测试上下文管理器"""
        with WebDAVClient(self.url, self.user, self.password) as client:
            self.assertIsInstance(client, WebDAVClient)

    def test_build_request(self):
        """测试 _build_request 构建请求对象"""
        req = self.client._build_request("GET", "test/path")
        self.assertEqual(req.get_method(), "GET")
        self.assertIn("Basic", req.get_header("Authorization"))

    def test_build_request_with_data(self):
        """测试 _build_request 带数据时正确设置"""
        data = b"test data"
        req = self.client._build_request("PUT", "upload.txt", data=data)
        self.assertEqual(req.get_method(), "PUT")
        self.assertEqual(req.full_url, "https://dav.jianguoyun.com/dav/upload.txt")


if __name__ == "__main__":
    unittest.main()
