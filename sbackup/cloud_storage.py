"""S3 兼容云存储客户端"""

import logging

logger = logging.getLogger(__name__)


class CloudStorageError(Exception):
    """云存储操作异常"""

    pass


class CloudStorageClient:
    """S3 兼容云存储客户端，基于 minio 库"""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "",
        secure: bool = True,
    ):
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self.region = region
        self.secure = secure
        self._client = None

    def connect(self) -> None:
        """建立连接"""
        from minio import Minio

        self._client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            region=self.region or None,
            secure=self.secure,
        )
        # 检查 bucket 是否存在，不存在则创建
        if not self._client.bucket_exists(self.bucket):
            self._client.make_bucket(self.bucket)

    def upload_file(self, local_path: str, remote_path: str) -> None:
        """上传文件到云存储"""
        if self._client is None:
            self.connect()
        self._client.fput_object(self.bucket, remote_path, local_path)

    def download_file(self, remote_path: str, local_path: str) -> None:
        """从云存储下载文件"""
        if self._client is None:
            self.connect()
        self._client.fget_object(self.bucket, remote_path, local_path)

    def list_files(self, prefix: str = "") -> list[str]:
        """列出云存储中的文件"""
        if self._client is None:
            self.connect()
        objects = self._client.list_objects(self.bucket, prefix=prefix, recursive=True)
        return [obj.object_name for obj in objects]

    def delete_file(self, remote_path: str) -> None:
        """从云存储删除文件"""
        if self._client is None:
            self.connect()
        self._client.remove_object(self.bucket, remote_path)

    def close(self) -> None:
        """关闭连接"""
        self._client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()
