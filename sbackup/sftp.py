"""
SFTP 远程备份模块：连接管理、文件上传、连接测试
"""

import os
import logging
from sbackup.i18n import t

logger = logging.getLogger(__name__)

# 默认 SSH 私钥位置（按优先级排序）
DEFAULT_KEY_FILES = [
    "~/.ssh/id_ed25519",  # Ed25519（现代推荐）
    "~/.ssh/id_rsa",  # RSA（最常用）
    "~/.ssh/id_ecdsa",  # ECDSA
]


class SFTPError(Exception):
    """SFTP 操作异常"""

    pass


class SFTPClient:
    """SFTP 客户端，封装 paramiko 连接和文件传输"""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str = "",
        key_file: str = "",
        key_passphrase: str = "",
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.key_file = key_file
        self.key_passphrase = key_passphrase
        self._transport = None
        self._sftp = None

    def connect(self) -> None:
        """建立 SFTP 连接（优先使用私钥认证，验证主机密钥）"""
        import paramiko

        # 展开 ~ 为用户目录（跨平台兼容）
        key_file_expanded = os.path.expanduser(self.key_file) if self.key_file else ""

        try:
            self._transport = paramiko.Transport((self.host, self.port))

            # 主机密钥验证：加载系统 known_hosts
            host_keys = paramiko.HostKeys()
            known_hosts_paths = [
                os.path.expanduser("~/.ssh/known_hosts"),
                "/etc/ssh/ssh_known_hosts",
            ]
            for kh_path in known_hosts_paths:
                if os.path.isfile(kh_path):
                    try:
                        host_keys.load(kh_path)
                    except OSError:
                        pass

            if host_keys:
                # 有已知主机密钥，使用严格验证
                remote_key = self._transport.get_remote_server_key()
                if remote_key is None:
                    self.disconnect()
                    raise SFTPError(t("err.sftp.no_host_key", host=self.host))
                host_key_entry = host_keys.lookup(self.host)
                if host_key_entry is None:
                    # 主机不在已知列表中，警告但允许连接（首次连接）
                    logger.warning(
                        "SFTP: 主机 %s 不在 known_hosts 中（首次连接）", self.host
                    )
                else:
                    try:
                        host_keys.check(self.host, remote_key)
                    except paramiko.SSHException:
                        self.disconnect()
                        raise SFTPError(t("err.sftp.host_key_mismatch", host=self.host))
            else:
                # 没有 known_hosts 文件，跳过验证（向后兼容）
                logger.debug("SFTP: 未找到 known_hosts 文件，跳过主机密钥验证")
                import sys

                print(
                    t("warn.sftp.no_known_hosts", host=self.host),
                    file=sys.stderr,
                )
            if key_file_expanded and os.path.isfile(key_file_expanded):
                # 私钥认证
                pkey = self._load_private_key(key_file_expanded, self.key_passphrase)
                self._transport.connect(username=self.user, pkey=pkey)
                logger.debug(
                    "SFTP 私钥连接成功: %s@%s:%d (key=%s)",
                    self.user,
                    self.host,
                    self.port,
                    key_file_expanded,
                )
            else:
                # 密码认证
                self._transport.connect(username=self.user, password=self.password)
                logger.debug(
                    "SFTP 密码连接成功: %s@%s:%d", self.user, self.host, self.port
                )
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)
        except paramiko.AuthenticationException:
            self.disconnect()
            raise SFTPError(t("err.sftp.auth", host=self.host))
        except paramiko.SSHException as e:
            self.disconnect()
            raise SFTPError(t("err.sftp.ssh", error=str(e)))
        except OSError as e:
            self.disconnect()
            raise SFTPError(
                t("err.sftp.connect", host=self.host, port=self.port, error=str(e))
            )

    @staticmethod
    def _is_passphrase_error(error_msg: str) -> bool:
        """判断 SSH 异常是否由缺少密码短语引起"""
        keywords = [
            "password",
            "passphrase",
            "decrypt",
            "encrypted",
            "required",
            "bad decrypt",
            "no decrypt",
        ]
        return any(kw in error_msg.lower() for kw in keywords)

    @staticmethod
    def _load_private_key(key_file: str, passphrase: str = ""):
        """尝试加载各种格式的私钥"""
        import paramiko

        key_pass = passphrase if passphrase else None
        key_classes = [
            paramiko.RSAKey,
            paramiko.Ed25519Key,
            paramiko.ECDSAKey,
        ]
        last_error = None
        for key_cls in key_classes:
            try:
                return key_cls.from_private_key_file(key_file, password=key_pass)
            except paramiko.SSHException as e:
                last_error = e
                continue
        # 所有格式都失败，检查是否因缺少密码短语
        if last_error and SFTPClient._is_passphrase_error(str(last_error)):
            raise SFTPError(t("err.sftp.key_needs_passphrase", path=key_file))
        raise SFTPError(t("err.sftp.key_load", path=key_file))

    @staticmethod
    def try_default_key() -> str | None:
        """
        尝试查找默认 SSH 私钥文件
        :return: 找到的私钥文件路径，或 None
        """
        for key_path in DEFAULT_KEY_FILES:
            expanded = os.path.expanduser(key_path)
            if os.path.isfile(expanded):
                logger.debug("发现默认私钥: %s", expanded)
                return expanded
        return None

    def disconnect(self) -> None:
        """断开 SFTP 连接（确保每个资源都被清理）"""
        try:
            if self._sftp is not None:
                self._sftp.close()
        except Exception:
            pass
        finally:
            self._sftp = None

        try:
            if self._transport is not None:
                self._transport.close()
        except Exception:
            pass
        finally:
            self._transport = None

        # 清除敏感凭据，防止内存泄漏
        self.password = ""
        self.key_passphrase = ""

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

    def upload_file(
        self, local_path: str, remote_path: str, progress_callback=None
    ) -> None:
        """
        上传单个文件到远程服务器
        :param local_path: 本地文件路径
        :param remote_path: 远程目标路径
        :param progress_callback: 进度回调函数 callback(bytes_transferred, total_bytes)
        """
        if self._sftp is None:
            raise SFTPError(t("err.sftp.not_connected"))

        if not os.path.isfile(local_path):
            raise SFTPError(t("err.sftp.local_not_found", path=local_path))

        filename = os.path.basename(local_path)
        remote_full = os.path.join(remote_path, filename).replace("\\", "/")

        # 确保远程目录存在
        self._ensure_remote_dir(remote_path)

        try:
            self._sftp.put(
                local_path,
                remote_full,
                callback=progress_callback,
                confirm=True,
            )
            logger.debug("SFTP 上传成功: %s -> %s", local_path, remote_full)
        except OSError as e:
            raise SFTPError(t("err.sftp.upload", path=filename, error=str(e)))

    def _ensure_remote_dir(self, remote_path: str, max_depth: int = 50) -> None:
        """确保远程目录存在，不存在则逐级创建"""
        if self._sftp is None:
            return
        remote_path = remote_path.replace("\\", "/").rstrip("/")
        if remote_path == "/" or remote_path == "":
            return
        try:
            self._sftp.stat(remote_path)
        except FileNotFoundError:
            # 递归创建父目录
            parent = os.path.dirname(remote_path).replace("\\", "/")
            if parent and parent != remote_path:
                if max_depth <= 0:
                    raise SFTPError(t("err.sftp.mkdir_max_depth", path=remote_path))
                self._ensure_remote_dir(parent, max_depth - 1)
            try:
                self._sftp.mkdir(remote_path)
            except OSError as e:
                raise SFTPError(t("err.sftp.mkdir", path=remote_path, error=str(e)))

    @staticmethod
    def resolve_key_passphrase(key_file: str) -> str | None:
        """
        检测私钥是否需要密码短语，需要时交互式提示输入
        :return: 密码短语（空字符串表示不需要），None 表示用户放弃输入
        """
        import getpass

        try:
            SFTPClient._load_private_key(key_file, "")
            return ""
        except SFTPError:
            while True:
                passphrase = getpass.getpass(t("cli.prompt.sftp.key_passphrase") + " ")
                if not passphrase:
                    return None  # 用户放弃输入，回退到密码认证
                # 验证密码短语是否正确
                try:
                    SFTPClient._load_private_key(key_file, passphrase)
                    return passphrase
                except SFTPError:
                    print(t("err.sftp.wrong_passphrase"))

    def list_remote_files(self, remote_path: str = "/") -> list[dict]:
        """
        列出远程目录下的文件
        :return: 包含 name, size, mtime 的字典列表
        """
        if self._sftp is None:
            raise SFTPError(t("err.sftp.not_connected"))

        remote_path = remote_path.replace("\\", "/").rstrip("/")
        if not remote_path:
            remote_path = "/"

        try:
            entries = self._sftp.listdir_attr(remote_path)
        except FileNotFoundError:
            raise SFTPError(t("err.sftp.remote_not_found", path=remote_path))

        files = []
        for entry in entries:
            if entry.filename.startswith("."):
                continue
            # 跳过目录
            if entry.st_mode is not None and entry.st_mode & 0o170000 == 0o040000:
                continue
            files.append(
                {
                    "name": entry.filename,
                    "size": entry.st_size or 0,
                    "mtime": entry.st_mtime or 0,
                }
            )
        return files

    def delete_remote_file(self, remote_path: str) -> None:
        """删除远程文件"""
        if self._sftp is None:
            raise SFTPError(t("err.sftp.not_connected"))

        try:
            self._sftp.remove(remote_path)
            logger.debug("SFTP 删除文件: %s", remote_path)
        except FileNotFoundError:
            raise SFTPError(t("err.sftp.remote_not_found", path=remote_path))
        except OSError as e:
            raise SFTPError(t("err.sftp.delete", path=remote_path, error=str(e)))

    def test_connection(self) -> bool:
        """测试 SFTP 连接是否可用"""
        try:
            self.connect()
            if self._sftp is not None:
                self._sftp.listdir(".")
            return True
        except SFTPError:
            return False
        finally:
            self.disconnect()
