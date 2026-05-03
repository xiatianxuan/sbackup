"""
WebDAV 远程备份模块：基于 HTTP 的文件上传（支持坚果云、NextCloud、群晖等）
使用 Python 标准库 urllib，零额外依赖。
"""

import os
import logging
import urllib.request
import urllib.error
from base64 import b64encode

from sbackup.i18n import t

logger = logging.getLogger(__name__)


class WebDAVError(Exception):
    """WebDAV 操作异常"""

    pass


class WebDAVClient:
    """WebDAV 客户端，基于 urllib 实现，零额外依赖"""

    def __init__(self, url: str, user: str, password: str):
        self.url = url.rstrip("/")
        self.user = user
        self.password = password
        self._auth_header = self._make_auth()

    def _make_auth(self) -> str:
        """生成 Basic Auth 头"""
        credentials = f"{self.user}:{self.password}"
        encoded = b64encode(credentials.encode("utf-8")).decode("utf-8")
        return f"Basic {encoded}"

    def _build_url(self, path: str = "") -> str:
        """构建完整 URL"""
        path = path.strip("/")
        if path:
            return f"{self.url}/{path}"
        return self.url

    def _build_request(
        self,
        method: str,
        path: str = "",
        data: bytes | None = None,
        content_type: str = "application/octet-stream",
    ) -> urllib.request.Request:
        """构建 HTTP 请求对象"""
        url = self._build_url(path)
        req = urllib.request.Request(url, method=method)
        req.add_header("Authorization", self._auth_header)
        if data is not None:
            req.add_header("Content-Length", str(len(data)))
        if content_type:
            req.add_header("Content-Type", content_type)
        return req

    def _ensure_remote_dir(self, path: str) -> None:
        """递归创建远程目录（MKCOL）"""
        if not path:
            return
        parts = [p for p in path.strip("/").split("/") if p]
        current = ""
        for part in parts:
            current = f"{current}/{part}" if current else part
            try:
                req = self._build_request("MKCOL", current)
                urllib.request.urlopen(req, timeout=30)
                logger.debug("创建远程目录: %s", current)
            except urllib.error.HTTPError as e:
                if e.code == 405:
                    # 405 Method Not Allowed = 目录已存在
                    pass
                elif e.code == 401:
                    raise WebDAVError(t("err.webdav.auth", host=self.url))
                else:
                    raise WebDAVError(t("err.webdav.mkdir", path=current, error=str(e)))
            except OSError as e:
                raise WebDAVError(t("err.webdav.connect", url=self.url, error=str(e)))

    def connect(self) -> None:
        """测试 WebDAV 连接（PROPFIND）"""
        try:
            req = self._build_request(
                "PROPFIND",
                data=b'<?xml version="1.0"?>'
                b'<D:propfind xmlns:D="DAV:"><D:allprop/></D:propfind>',
                content_type="application/xml",
            )
            req.add_header("Depth", "0")
            urllib.request.urlopen(req, timeout=15)
            logger.debug("WebDAV 连接成功: %s", self.url)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise WebDAVError(t("err.webdav.auth", host=self.url))
            raise WebDAVError(t("err.webdav.connect", url=self.url, error=str(e)))
        except OSError as e:
            raise WebDAVError(t("err.webdav.connect", url=self.url, error=str(e)))

    def upload_file(self, local_path: str, remote_path: str) -> int:
        """
        上传文件到 WebDAV 服务器
        :param local_path: 本地文件路径
        :param remote_path: 远程文件路径
        :return: 上传的字节数
        """
        if not os.path.isfile(local_path):
            raise WebDAVError(t("err.webdav.local_not_found", path=local_path))

        # 确保远程目录存在
        remote_dir = os.path.dirname(remote_path).replace("\\", "/")
        self._ensure_remote_dir(remote_dir)

        file_size = os.path.getsize(local_path)
        logger.debug(
            "开始上传: %s -> %s (%d bytes)", local_path, remote_path, file_size
        )

        try:
            # 流式上传：不将整个文件读入内存
            url = self._build_url(remote_path)
            with open(local_path, "rb") as f:
                req = urllib.request.Request(url, data=f, method="PUT")
                req.add_header("Authorization", self._auth_header)
                req.add_header("Content-Length", str(file_size))
                urllib.request.urlopen(req, timeout=300)
            logger.debug("上传成功: %s", remote_path)
            return file_size
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise WebDAVError(t("err.webdav.auth", host=self.url))
            raise WebDAVError(t("err.webdav.upload", path=remote_path, error=str(e)))
        except OSError as e:
            raise WebDAVError(t("err.webdav.upload", path=remote_path, error=str(e)))

    def test_connection(self) -> bool:
        """测试连接是否可用"""
        try:
            self.connect()
            return True
        except WebDAVError:
            return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
