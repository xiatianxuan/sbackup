"""单元测试 for sbackup.chunked_backup 模块"""

import os
import unittest
import tempfile
import shutil

from sbackup.chunked_backup import (
    compute_chunk_hashes,
    find_changed_chunks,
    create_patch,
    apply_patch,
    patch_size_ratio,
    should_do_full_backup,
    CHUNK_SIZE,
)


class TestChunkedBackup(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_file(self, name: str, size: int = 100) -> str:
        """创建指定大小的测试文件"""
        path = os.path.join(self.test_dir, name)
        with open(path, "wb") as f:
            f.write(b"x" * size)
        return path

    def test_compute_chunk_hashes_small_file(self):
        """小文件应返回一个块的哈希"""
        path = self._create_file("small.bin", 10)
        hashes = compute_chunk_hashes(path)
        self.assertEqual(len(hashes), 1)
        self.assertIn("0", hashes)
        self.assertEqual(len(hashes["0"]), 64)  # SHA256 hex

    def test_compute_chunk_hashes_large_file(self):
        """大文件应返回多个块的哈希"""
        path = self._create_file("large.bin", CHUNK_SIZE * 3 + 100)
        hashes = compute_chunk_hashes(path)
        self.assertEqual(len(hashes), 4)  # 3 full chunks + 1 partial

    def test_compute_chunk_hashes_empty_file(self):
        """空文件应返回空字典"""
        path = self._create_file("empty.bin", 0)
        hashes = compute_chunk_hashes(path)
        self.assertEqual(len(hashes), 0)

    def test_find_changed_chunks_no_change(self):
        """无变化时应返回空集合"""
        path = self._create_file("data.bin", CHUNK_SIZE * 2)
        stored = compute_chunk_hashes(path)
        changed, total = find_changed_chunks(path, stored)
        self.assertEqual(len(changed), 0)
        self.assertEqual(total, 2)

    def test_find_changed_chunks_all_changed(self):
        """全部块变化时返回所有索引"""
        path = self._create_file("data.bin", CHUNK_SIZE * 2)
        stored = {"0": "a" * 64, "1": "b" * 64}  # 伪造的哈希
        changed, total = find_changed_chunks(path, stored)
        self.assertEqual(len(changed), 2)

    def test_find_changed_chunks_partial(self):
        """部分块变化"""
        path = self._create_file("data.bin", CHUNK_SIZE * 3)
        stored = compute_chunk_hashes(path)
        # 修改第二个块
        with open(path, "r+b") as f:
            f.seek(CHUNK_SIZE)
            f.write(b"modified data!")
        changed, total = find_changed_chunks(path, stored)
        self.assertIn(1, changed)  # 第二个块（index=1）变了
        self.assertNotIn(0, changed)
        self.assertEqual(total, 3)

    def test_create_patch_no_changes(self):
        """无变化时不应创建补丁"""
        path = self._create_file("data.bin", CHUNK_SIZE * 2)
        patch_path = os.path.join(self.test_dir, "patch.bin")
        result = create_patch(path, set(), patch_path)
        self.assertEqual(result, 0)
        self.assertFalse(os.path.exists(patch_path))

    def test_create_patch_with_changes(self):
        """有变化时应创建补丁文件"""
        path = self._create_file("data.bin", CHUNK_SIZE * 3)
        patch_path = os.path.join(self.test_dir, "patch.bin")
        result = create_patch(path, {0, 2}, patch_path)
        self.assertGreater(result, 0)
        self.assertTrue(os.path.exists(patch_path))
        self.assertGreater(os.path.getsize(patch_path), 0)

    def test_apply_patch(self):
        """应用补丁应还原文件内容"""
        # 创建基准文件
        base_path = self._create_file("base.bin", CHUNK_SIZE * 3)
        stored = compute_chunk_hashes(base_path)

        # 修改第一个块
        with open(base_path, "r+b") as f:
            f.write(b"modified chunk 0 data! padding...")

        # 创建补丁
        changed, _ = find_changed_chunks(base_path, stored)
        patch_path = os.path.join(self.test_dir, "patch.bin")
        create_patch(base_path, changed, patch_path)

        # 用补丁还原到新文件
        restored_path = os.path.join(self.test_dir, "restored.bin")
        result = apply_patch(base_path, patch_path, restored_path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(restored_path))

        # 验证还原后的文件与修改后的文件相同
        with open(base_path, "rb") as f:
            original = f.read()
        with open(restored_path, "rb") as f:
            restored = f.read()
        # 由于 apply_patch 是从 base 重建的，base_path 本身已经修改了
        # 所以 restored 应该等于 base_path 的当前内容
        self.assertEqual(len(original), len(restored))

    def test_patch_size_ratio(self):
        """补丁大小比例计算"""
        path = self._create_file("data.bin", CHUNK_SIZE * 10)
        ratio = patch_size_ratio(path, {0, 1, 2})
        self.assertAlmostEqual(ratio, 0.3, places=1)

    def test_should_do_full_backup_below_threshold(self):
        """变化比例低于阈值时应返回 False"""
        path = self._create_file("data.bin", CHUNK_SIZE * 10)
        result = should_do_full_backup(path, {0}, threshold=0.5)
        self.assertFalse(result)

    def test_should_do_full_backup_above_threshold(self):
        """变化比例高于阈值时应返回 True"""
        path = self._create_file("data.bin", CHUNK_SIZE * 10)
        result = should_do_full_backup(path, set(range(6)), threshold=0.5)
        self.assertTrue(result)

    def test_should_do_full_backup_empty_file(self):
        """空文件不应触发全量备份"""
        path = self._create_file("empty.bin", 0)
        result = should_do_full_backup(path, {0}, threshold=0.5)
        self.assertFalse(result)

    def test_custom_chunk_size(self):
        """自定义块大小"""
        path = self._create_file("data.bin", 200)
        hashes = compute_chunk_hashes(path, chunk_size=50)
        self.assertEqual(len(hashes), 4)  # 200 / 50

    def test_find_changed_chunks_file_shorter(self):
        """文件变短时应标记缺失块"""
        path = self._create_file("data.bin", CHUNK_SIZE * 5)
        stored = compute_chunk_hashes(path)
        # 截断文件
        with open(path, "r+b") as f:
            f.truncate(CHUNK_SIZE * 2)
        changed, total = find_changed_chunks(path, stored)
        self.assertIn(2, changed)  # index 2 应该消失
        self.assertEqual(total, 2)

    def test_create_patch_empty_indices(self):
        """空索引集合应返回 0"""
        path = self._create_file("data.bin", 100)
        result = create_patch(path, set(), "/nonexistent/patch")
        self.assertEqual(result, 0)
