"""文件级去重：基于 SHA256 内容哈希的跨策略去重存储"""

import os
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

# 去重存储的子目录名
DEDUP_DIR = ".dedup"
INDEX_FILE = "index.json"


class DedupStore:
    """内容寻址去重存储

    文件存储路径: {store_dir}/{hash[:2]}/{hash[2:]}
    index 格式: {hash: refcount}

    记录每个文件内容的 SHA256 哈希和引用次数，当多个策略包含相同内容的文件时，
    哈希会被复用，从而实现跨策略去重统计。
    """

    def __init__(self, store_dir: str):
        self.store_dir = os.path.join(store_dir, DEDUP_DIR)
        self.index_path = os.path.join(self.store_dir, INDEX_FILE)
        self._index: dict[str, int] = {}
        self._load_index()

    def _load_index(self) -> None:
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, encoding="utf-8") as f:
                    self._index = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._index = {}

    def _save_index(self) -> None:
        os.makedirs(self.store_dir, exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)

    def _hash_path(self, content_hash: str) -> str:
        return os.path.join(self.store_dir, content_hash[:2], content_hash[2:])

    def store(self, source_path: str) -> tuple[str, bool]:
        """存储文件到去重池

        :returns: (content_hash, is_new) — is_new 表示这是首次存储
        """
        content_hash = self._compute_hash(source_path)
        target = self._hash_path(content_hash)

        if os.path.exists(target):
            # 文件已存在，增加引用计数
            self._index[content_hash] = self._index.get(content_hash, 0) + 1
            self._save_index()
            return content_hash, False

        # 首次存储
        os.makedirs(os.path.dirname(target), exist_ok=True)
        # 优先使用硬链接（同一文件系统），否则复制
        try:
            os.link(source_path, target)
        except OSError:
            try:
                import shutil

                shutil.copy2(source_path, target)
            except OSError as e:
                logger.warning("Failed to copy file to dedup store: %s", e)
                return content_hash, False

        self._index[content_hash] = self._index.get(content_hash, 0) + 1
        self._save_index()
        return content_hash, True

    def release(self, content_hash: str) -> bool:
        """释放文件引用。引用计数归零时删除文件。

        :returns: True 如果文件被实际删除
        """
        if content_hash not in self._index:
            return False

        self._index[content_hash] -= 1
        if self._index[content_hash] <= 0:
            del self._index[content_hash]
            target = self._hash_path(content_hash)
            try:
                os.remove(target)
            except OSError:
                pass
        self._save_index()
        return True

    def get_path(self, content_hash: str) -> str | None:
        """获取已去重文件的路径"""
        target = self._hash_path(content_hash)
        if os.path.exists(target):
            return target
        return None

    def has(self, content_hash: str) -> bool:
        """检查哈希是否已存储"""
        return content_hash in self._index

    @staticmethod
    def _compute_hash(filepath: str) -> str:
        """计算文件的 SHA256 哈希"""
        sha = hashlib.sha256()
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                sha.update(chunk)
        return sha.hexdigest()

    def scan_directory(self, directory: str) -> dict[str, int]:
        """扫描目录，计算所有文件的哈希并存入去重池

        :returns: {content_hash: file_count} 的字典
        """
        seen = {}  # hash -> count of files with this hash
        for dirpath, _dirnames, filenames in os.walk(directory):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                try:
                    if not os.path.isfile(file_path):
                        continue
                    content_hash, is_new = self.store(file_path)
                    if content_hash in seen:
                        seen[content_hash] += 1
                    else:
                        seen[content_hash] = 1
                except (OSError, PermissionError):
                    continue
        return seen

    def count_duplicates(self, hash_counts: dict[str, int]) -> tuple[int, int]:
        """统计跨策略的重复文件数量和节省的估算大小

        :param hash_counts: scan_directory 返回的哈希计数
        :returns: (duplicate_count, approximate_saved_bytes)
        """
        dup_count = 0
        saved_bytes = 0
        for content_hash, count in hash_counts.items():
            if self._index.get(content_hash, 0) > count:
                # 该哈希已经被其他策略存储过
                dup_count += count
                target = self._hash_path(content_hash)
                if os.path.exists(target):
                    saved_bytes += os.path.getsize(target) * count
        return dup_count, saved_bytes
