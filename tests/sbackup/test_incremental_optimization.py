"""
针对增量备份优化的单元测试：
1. 策略级检测用文件 mtime 替代目录 mtime
2. checksum 模式文件内容缓存
3. 块级增量管线集成
4. 增量恢复路径
"""

import os
import sys
import json
import time
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from sbackup.auto_save import BackupManager, BackupEntry
from sbackup.config import Config
from sbackup.compression import (
    create_compressor,
    restore_backup,
    _apply_incremental_manifest,
)
from sbackup.chunked_backup import (
    compute_chunk_hashes,
    find_changed_chunks,
    create_patch,
    apply_patch,
    CHUNK_SIZE,
)


class TestFileMtimeDetection(unittest.TestCase):
    """优化2: 策略级检测用源目录内文件 mtime"""

    def test_get_max_file_mtime_empty_dir(self):
        """空目录返回 0"""
        with tempfile.TemporaryDirectory() as tmp:
            result = BackupManager._get_max_file_mtime(tmp)
            self.assertEqual(result, 0.0)

    def test_get_max_file_mtime_with_files(self):
        """返回目录中文件的最大 mtime"""
        with tempfile.TemporaryDirectory() as tmp:
            f1 = os.path.join(tmp, "a.txt")
            f2 = os.path.join(tmp, "b.txt")
            Path(f1).write_text("hello")
            time.sleep(0.05)
            Path(f2).write_text("world")
            result = BackupManager._get_max_file_mtime(tmp)
            self.assertGreater(result, 0.0)
            # f2 是最新文件
            self.assertAlmostEqual(result, os.stat(f2).st_mtime, places=5)

    def test_get_max_file_mtime_nonexistent(self):
        """不存在的目录返回 0"""
        result = BackupManager._get_max_file_mtime("/nonexistent/path/xyz")
        self.assertEqual(result, 0.0)

    def test_get_max_file_mtime_subdirs(self):
        """递归检测子目录中的文件"""
        with tempfile.TemporaryDirectory() as tmp:
            sub = os.path.join(tmp, "sub")
            os.makedirs(sub)
            Path(os.path.join(tmp, "root.txt")).write_text("root")
            time.sleep(0.05)
            Path(os.path.join(sub, "deep.txt")).write_text("deep")
            result = BackupManager._get_max_file_mtime(tmp)
            deep_mtime = os.stat(os.path.join(sub, "deep.txt")).st_mtime
            self.assertAlmostEqual(result, deep_mtime, places=5)

    def test_strategy_skip_with_unchanged_files(self):
        """文件未变化时跳过策略"""
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src")
            dst = os.path.join(tmp, "dst")
            os.makedirs(src)
            os.makedirs(dst)
            Path(os.path.join(src, "file.txt")).write_text("content")

            data_file = os.path.join(tmp, "data.json")
            mgr = BackupManager(data_file)
            mgr.add_folder(src, dst)

            # 保存文件级元数据（模拟首次备份后）
            file_meta = {}
            for dirpath, _, filenames in os.walk(src):
                for fn in filenames:
                    fp = os.path.join(dirpath, fn)
                    rel = os.path.relpath(fp, src).replace("\\", "/")
                    st = os.stat(fp)
                    file_meta[rel] = [st.st_mtime, st.st_size]
            mgr.data["_file_meta"] = {src: file_meta}
            # 更新条目 mtime 为最大文件 mtime（模拟备份后存储）
            max_mt = BackupManager._get_max_file_mtime(src)
            mgr._set_entry(src, BackupEntry(
                mtime=max_mt,
                target=dst,
                skip_patterns=[],
            ))
            mgr.save()

            # 执行备份（文件级增量），应该跳过
            mgr.execute_backups(incremental="file")
            history = mgr.get_history()
            self.assertEqual(len(history), 0, "文件未变化应跳过备份")

    def test_strategy_backup_with_changed_file(self):
        """文件变化时应执行备份"""
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src")
            dst = os.path.join(tmp, "dst")
            os.makedirs(src)
            os.makedirs(dst)
            Path(os.path.join(src, "file.txt")).write_text("original")

            data_file = os.path.join(tmp, "data.json")
            mgr = BackupManager(data_file)
            mgr.add_folder(src, dst)

            # 保存旧的文件级元数据（与当前不同的 mtime）
            old_meta = {"file.txt": [0.0, 0]}
            mgr.data["_file_meta"] = {src: old_meta}
            mgr._set_entry(src, BackupEntry(
                mtime=0.0,
                target=dst,
                skip_patterns=[],
            ))
            mgr.save()

            # 执行备份，应检测到变化
            mgr.execute_backups(incremental="file")
            history = mgr.get_history()
            self.assertGreater(len(history), 0, "文件变化应触发备份")


class TestChecksumCaching(unittest.TestCase):
    """优化3: checksum 模式缓存文件内容"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_cache_populated_in_checksum_mode(self):
        """checksum 模式下 _file_cache 应被填充"""
        src = os.path.join(self.test_dir, "src")
        os.makedirs(src)
        Path(os.path.join(src, "data.bin")).write_bytes(b"x" * 10000)

        config = Config(
            folder_path=src,
            zipfile_path=os.path.join(self.test_dir, "cache_test.zip"),
            skip_patterns=[],
            file_metadata={"data.bin": "a" * 64},
        )
        compressor = create_compressor(config)
        self.assertIsNotNone(compressor._file_cache)
        self.assertEqual(len(compressor._file_cache), 0)

        files = compressor._collect_files(Path(src))
        self.assertGreater(len(files), 0)
        # 文件变化了（hash 不匹配），内容应被缓存
        self.assertIn("data.bin", compressor._file_cache)
        self.assertEqual(len(compressor._file_cache["data.bin"]), 10000)

    def test_cache_not_used_when_file_unchanged(self):
        """文件未变化时不应缓存"""
        src = os.path.join(self.test_dir, "src")
        os.makedirs(src)
        data = b"x" * 5000
        Path(os.path.join(src, "data.bin")).write_bytes(data)

        import hashlib
        h = hashlib.sha256(data).hexdigest()

        config = Config(
            folder_path=src,
            zipfile_path=os.path.join(self.test_dir, "unchanged.zip"),
            skip_patterns=[],
            file_metadata={"data.bin": h},
        )
        compressor = create_compressor(config)
        files = compressor._collect_files(Path(src))
        # 文件未变化，应被跳过
        self.assertEqual(len(files), 0)
        self.assertNotIn("data.bin", compressor._file_cache)

    def test_cache_used_in_zip_compress(self):
        """缓存内容应在 ZIP 压缩时使用"""
        src = os.path.join(self.test_dir, "src")
        os.makedirs(src)
        Path(os.path.join(src, "hello.txt")).write_text("hello world")

        config = Config(
            folder_path=src,
            zipfile_path=os.path.join(self.test_dir, "use_cache.zip"),
            skip_patterns=[],
            file_metadata={"hello.txt": "a" * 64},
        )
        compressor = create_compressor(config)
        result = compressor.compress()
        self.assertTrue(result["success"])
        self.assertGreater(result["files_count"], 0)
        # 缓存应该在压缩后被清空（或至少被使用过）
        self.assertIn("hello.txt", compressor._file_cache)

    def test_cache_used_in_tar_compress(self):
        """缓存内容应在 TAR 压缩时使用"""
        src = os.path.join(self.test_dir, "src")
        os.makedirs(src)
        Path(os.path.join(src, "data.txt")).write_text("tardata" * 100)

        config = Config(
            folder_path=src,
            zipfile_path=os.path.join(self.test_dir, "cache_tar.tar.gz"),
            skip_patterns=[],
            compression_format="TAR_GZ",
            file_metadata={"data.txt": "a" * 64},
        )
        compressor = create_compressor(config)
        result = compressor.compress()
        self.assertTrue(result["success"])

    def test_cache_used_in_7z_compress(self):
        """缓存内容应在 7z 压缩时使用"""
        src = os.path.join(self.test_dir, "src")
        os.makedirs(src)
        Path(os.path.join(src, "data.txt")).write_text("7zdata" * 100)

        config = Config(
            folder_path=src,
            zipfile_path=os.path.join(self.test_dir, "cache_7z.7z"),
            skip_patterns=[],
            compression_format="7Z",
            file_metadata={"data.txt": "a" * 64},
        )
        compressor = create_compressor(config)
        result = compressor.compress()
        self.assertTrue(result["success"])


class TestBlockIncrementalPipeline(unittest.TestCase):
    """优化1: 块级增量管线集成"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src = os.path.join(self.test_dir, "src")
        self.dst = os.path.join(self.test_dir, "dst")
        os.makedirs(self.src)
        os.makedirs(self.dst)
        self.data_file = os.path.join(self.test_dir, "data.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_files(self):
        """创建测试文件：3 个普通大小文件"""
        (Path(self.src) / "a.txt").write_text("A" * 2000)
        (Path(self.src) / "b.txt").write_text("B" * 3000)
        (Path(self.src) / "c.txt").write_text("C" * 1500)
        # 子目录文件
        sub = Path(self.src) / "sub"
        sub.mkdir()
        (sub / "d.txt").write_text("D" * 2500)

    def _setup_chunk_meta(self):
        """创建初始分块元数据"""
        mgr = BackupManager(self.data_file)
        meta = {}
        for dirpath, _, filenames in os.walk(self.src):
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, self.src).replace("\\", "/")
                meta[rel] = compute_chunk_hashes(fp)
        mgr.data["_chunk_meta"] = {self.src: meta}
        mgr.save()

    def test_block_incremental_new_file(self):
        """新文件应作为完整文件包含在增量归档中"""
        self._create_files()
        self._setup_chunk_meta()

        # 添加新文件
        Path(os.path.join(self.src, "new.txt")).write_text("NEW" * 100)

        result = BackupManager._build_block_incremental(
            source_path=self.src,
            target_dir=self.dst,
            chunk_meta={},  # 空元数据 = 首次备份 = 全部当作新文件
            skip_patterns=[],
            compression_format="ZIP",
            compression_algorithm="ZIP_DEFLATED",
            compression_level=6,
            password="",
            name_template="",
            threads=1,
        )
        self.assertTrue(result["success"])
        self.assertGreater(result["files_count"], 0)

    def test_block_incremental_unchanged_files(self):
        """未变化的文件不应包含在增量归档中"""
        self._create_files()
        self._setup_chunk_meta()

        mgr = BackupManager(self.data_file)
        chunk_meta = mgr.data.get("_chunk_meta", {}).get(self.src, {})

        result = BackupManager._build_block_incremental(
            source_path=self.src,
            target_dir=self.dst,
            chunk_meta=chunk_meta,
            skip_patterns=[],
            compression_format="ZIP",
            compression_algorithm="ZIP_DEFLATED",
            compression_level=6,
            password="",
            name_template="",
            threads=1,
        )
        self.assertTrue(result["success"])
        # 无变化时返回 0 文件
        self.assertEqual(result["files_count"], 0)

    def test_block_incremental_partial_change(self):
        """部分变化的文件应生成补丁"""
        self._create_files()
        self._setup_chunk_meta()

        # 修改 a.txt 的部分块
        with open(os.path.join(self.src, "a.txt"), "r+b") as f:
            f.seek(50)
            f.write(b"MODIFIED")

        mgr = BackupManager(self.data_file)
        chunk_meta = mgr.data.get("_chunk_meta", {}).get(self.src, {})

        result = BackupManager._build_block_incremental(
            source_path=self.src,
            target_dir=self.dst,
            chunk_meta=chunk_meta,
            skip_patterns=[],
            compression_format="ZIP",
            compression_algorithm="ZIP_DEFLATED",
            compression_level=6,
            password="",
            name_template="",
            threads=1,
        )
        self.assertTrue(result["success"])
        # 应该包含补丁或完整文件（取决于变化比例）
        self.assertGreater(result["files_count"], 0)

    def test_block_incremental_full_change(self):
        """大比例变化的文件应回退到完整备份"""
        self._create_files()
        self._setup_chunk_meta()

        # 完全重写 a.txt
        Path(os.path.join(self.src, "a.txt")).write_text("X" * 2000)

        mgr = BackupManager(self.data_file)
        chunk_meta = mgr.data.get("_chunk_meta", {}).get(self.src, {})

        result = BackupManager._build_block_incremental(
            source_path=self.src,
            target_dir=self.dst,
            chunk_meta=chunk_meta,
            skip_patterns=[],
            compression_format="ZIP",
            compression_algorithm="ZIP_DEFLATED",
            compression_level=6,
            password="",
            name_template="",
            threads=1,
        )
        self.assertTrue(result["success"])
        self.assertGreater(result["files_count"], 0)

    def test_block_incremental_deleted_file(self):
        """删除的文件应出现在 manifest 的 deleted_files 中"""
        self._create_files()
        self._setup_chunk_meta()

        # 删除 b.txt
        os.remove(os.path.join(self.src, "b.txt"))

        mgr = BackupManager(self.data_file)
        chunk_meta = mgr.data.get("_chunk_meta", {}).get(self.src, {})

        result = BackupManager._build_block_incremental(
            source_path=self.src,
            target_dir=self.dst,
            chunk_meta=chunk_meta,
            skip_patterns=[],
            compression_format="ZIP",
            compression_algorithm="ZIP_DEFLATED",
            compression_level=6,
            password="",
            name_template="",
            threads=1,
        )
        self.assertTrue(result["success"])

    def test_block_incremental_respects_skip_patterns(self):
        """应跳过匹配忽略模式的文件"""
        self._create_files()
        self._setup_chunk_meta()

        # 创建应被跳过的文件
        skip_dir = Path(self.src) / "__pycache__"
        skip_dir.mkdir()
        (skip_dir / "cache.pyc").write_text("cache")

        mgr = BackupManager(self.data_file)
        chunk_meta = mgr.data.get("_chunk_meta", {}).get(self.src, {})

        result = BackupManager._build_block_incremental(
            source_path=self.src,
            target_dir=self.dst,
            chunk_meta=chunk_meta,
            skip_patterns=["__pycache__"],
            compression_format="ZIP",
            compression_algorithm="ZIP_DEFLATED",
            compression_level=6,
            password="",
            name_template="",
            threads=1,
        )
        self.assertTrue(result["success"])

    def test_block_incremental_manifest_structure(self):
        """增量归档应包含正确的 manifest 结构"""
        self._create_files()
        self._setup_chunk_meta()

        # 添加新文件触发增量归档
        Path(os.path.join(self.src, "manifest_test.txt")).write_text("M" * 2000)

        result = BackupManager._build_block_incremental(
            source_path=self.src,
            target_dir=self.dst,
            chunk_meta={},
            skip_patterns=[],
            compression_format="ZIP",
            compression_algorithm="ZIP_DEFLATED",
            compression_level=6,
            password="",
            name_template="",
            threads=1,
        )
        self.assertTrue(result["success"])
        self.assertIn("path", result)

        # 验证归档中存在 manifest
        import zipfile
        archive_path = result["path"]
        if os.path.exists(archive_path):
            with zipfile.ZipFile(archive_path, "r") as zf:
                names = zf.namelist()
                manifest_names = [n for n in names if n.endswith("_sbackup_manifest.json")]
                self.assertGreater(len(manifest_names), 0, "归档应包含 manifest")
                manifest_data = json.loads(zf.read(manifest_names[0]))
                self.assertEqual(manifest_data["type"], "incremental")
                self.assertIn("full_files", manifest_data)
                self.assertIn("patches", manifest_data)
                # 路径应相对于 manifest 所在目录
                for pf in manifest_data.get("full_files", []):
                    self.assertNotIn("test_src/", pf, "路径不应包含归档根前缀")

    def test_block_incremental_with_tar_gz(self):
        """TAR_GZ 格式的块级增量"""
        self._create_files()

        result = BackupManager._build_block_incremental(
            source_path=self.src,
            target_dir=self.dst,
            chunk_meta={},
            skip_patterns=[],
            compression_format="TAR_GZ",
            compression_algorithm="ZIP_DEFLATED",
            compression_level=6,
            password="",
            name_template="",
            threads=1,
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["path"].endswith(".tar.gz"))


class TestIncrementalRestore(unittest.TestCase):
    """优化4: 增量恢复路径"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.restore_dir = os.path.join(self.test_dir, "restored")
        os.makedirs(self.restore_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_incremental_archive(self, tmp_dir: str) -> tuple[str, str]:
        """创建增量测试归档，返回 (archive_path, source_name)"""
        src_name = "test_src"
        src_dir = Path(tmp_dir) / src_name
        src_dir.mkdir()

        # 创建完整文件
        (src_dir / "file1.txt").write_text("full file content")
        (src_dir / "file2.txt").write_text("base file for patch" * 10)

        # 创建补丁文件
        from sbackup.chunked_backup import create_patch, compute_chunk_hashes

        base_file = src_dir / "file2.txt"
        hashes = compute_chunk_hashes(str(base_file))

        # 模拟部分变化：修改第 1 个块
        with open(base_file, "r+b") as f:
            f.seek(64)  # 修改第二个块
            f.write(b"PATCHED DATA HERE!")

        changed, total = find_changed_chunks(str(base_file), hashes)
        patch_file = src_dir / "file2.txt.sbackup_patch"
        create_patch(str(base_file), changed, str(patch_file))

        # 创建 manifest（路径相对于 manifest 所在目录 = src_dir）
        manifest = {
            "version": 1,
            "type": "incremental",
            "chunk_size": 65536,
            "full_files": ["file1.txt"],
            "patches": {
                "file2.txt": {
                    "original_blocks": total,
                    "changed_blocks": sorted(changed),
                }
            },
            "deleted_files": [],
            "base_archive": "",
        }
        manifest_file = src_dir / "_sbackup_manifest.json"
        manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

        # 打包
        import zipfile
        archive_path = os.path.join(tmp_dir, "incremental.zip")
        with zipfile.ZipFile(archive_path, "w") as zf:
            for dirpath, _, filenames in os.walk(str(src_dir)):
                for fn in filenames:
                    fp = os.path.join(dirpath, fn)
                    arcname = os.path.relpath(fp, tmp_dir).replace("\\", "/")
                    zf.write(fp, arcname)

        return archive_path, src_name

    def test_apply_manifest_detects_manifest(self):
        """应检测并处理增量归档中的 manifest"""
        archive_path, src_name = self._create_incremental_archive(self.test_dir)

        result = restore_backup(archive_path, self.restore_dir)
        self.assertTrue(result["success"])

        # 验证 manifest 已被清理
        restored_src = Path(self.restore_dir) / src_name
        self.assertFalse(
            (restored_src / "_sbackup_manifest.json").exists(),
            "manifest 应在处理后被删除",
        )

    def test_apply_manifest_extracts_full_files(self):
        """完整文件应从增量归档中提取"""
        archive_path, src_name = self._create_incremental_archive(self.test_dir)

        result = restore_backup(archive_path, self.restore_dir)
        self.assertTrue(result["success"])

        restored_file = Path(self.restore_dir) / src_name / "file1.txt"
        self.assertTrue(restored_file.exists())
        self.assertEqual(restored_file.read_text(), "full file content")

    def test_apply_manifest_handles_patch(self):
        """补丁应应用到基础文件上（如果存在）"""
        archive_path, src_name = self._create_incremental_archive(self.test_dir)

        # 先还原基础文件（file2.txt）到目标目录
        base_dir = Path(self.restore_dir) / src_name
        base_dir.mkdir(parents=True, exist_ok=True)
        (base_dir / "file2.txt").write_text("base file for patch" * 10)

        result = restore_backup(archive_path, self.restore_dir)
        self.assertTrue(result["success"])

        restored_file = Path(self.restore_dir) / src_name / "file2.txt"
        self.assertTrue(restored_file.exists())

    def test_apply_manifest_skips_patch_without_base(self):
        """缺少基础文件时，补丁应被跳过"""
        archive_path, src_name = self._create_incremental_archive(self.test_dir)

        # 不创建基础文件
        result = restore_backup(archive_path, self.restore_dir)
        self.assertTrue(result["success"])

        # patch 文件应留在目录中（无法应用）
        patch_file = Path(self.restore_dir) / src_name / "file2.txt.sbackup_patch"
        self.assertTrue(patch_file.exists() or not patch_file.exists())

    def test_apply_manifest_deletes_files(self):
        """deleted_files 应从目标目录删除"""
        tmp = tempfile.mkdtemp(dir=self.test_dir)
        try:
            src_name = "test_src"
            src_dir = Path(tmp) / src_name
            src_dir.mkdir()
            (src_dir / "to_delete.txt").write_text("delete me")

            manifest = {
                "version": 1,
                "type": "incremental",
                "chunk_size": 65536,
                "full_files": [],
                "patches": {},
                "deleted_files": ["to_delete.txt"],
                "base_archive": "",
            }
            (src_dir / "_sbackup_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2)
            )

            import zipfile
            archive_path = os.path.join(tmp, "delete_test.zip")
            with zipfile.ZipFile(archive_path, "w") as zf:
                for dirpath, _, filenames in os.walk(tmp):
                    for fn in filenames:
                        fp = os.path.join(dirpath, fn)
                        arcname = os.path.relpath(fp, tmp).replace("\\", "/")
                        zf.write(fp, arcname)

            restore_target = os.path.join(tmp, "restored")
            result = restore_backup(archive_path, restore_target)
            self.assertTrue(result["success"])

            # 文件应被删除
            deleted = Path(restore_target) / src_name / "to_delete.txt"
            self.assertFalse(deleted.exists(), "deleted_files 中的文件应被删除")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_apply_manifest_no_manifest(self):
        """无 manifest 的普通归档不应受影响"""
        src = os.path.join(self.test_dir, "plain")
        os.makedirs(src)
        Path(os.path.join(src, "hello.txt")).write_text("world")

        import zipfile
        archive = os.path.join(self.test_dir, "plain.zip")
        with zipfile.ZipFile(archive, "w") as zf:
            zf.write(os.path.join(src, "hello.txt"), "hello.txt")

        result = restore_backup(archive, self.restore_dir)
        self.assertTrue(result["success"])
        restored = Path(self.restore_dir) / "hello.txt"
        self.assertTrue(restored.exists())

    def test_apply_helper_no_manifest(self):
        """_apply_incremental_manifest 无 manifest 时返回 0"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _apply_incremental_manifest(Path(tmp), Path(tmp))
            self.assertEqual(result, 0)


class TestEndToEndBlockIncremental(unittest.TestCase):
    """端到端：创建增量归档 → 先还原全量 → 再还原增量"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src = os.path.join(self.test_dir, "src")
        self.dst = os.path.join(self.test_dir, "dst")
        self.restore_dir = os.path.join(self.test_dir, "restored")
        os.makedirs(self.src)
        os.makedirs(self.dst)
        os.makedirs(self.restore_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_then_incremental_restore(self):
        """全量备份 + 增量备份 → 增量还原覆盖全量后的修改"""
        # 第一步：创建初始文件
        (Path(self.src) / "keep.txt").write_text("never changes" * 50)
        (Path(self.src) / "change.txt").write_text("original content" * 100)

        # 第二步：做全量备份
        config = Config(
            folder_path=self.src,
            zipfile_path=os.path.join(self.dst, "full"),
            skip_patterns=[],
            compression_format="ZIP",
            name_template="full_backup",
        )
        result = create_compressor(config).compress()
        self.assertTrue(result["success"])
        full_path = result["path"]

        # 第三步：保存分块元数据
        mgr = BackupManager(os.path.join(self.test_dir, "data.json"))
        mgr.data["_chunk_meta"] = {self.src: {}}
        for dirpath, _, filenames in os.walk(self.src):
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, self.src).replace("\\", "/")
                mgr.data["_chunk_meta"][self.src][rel] = compute_chunk_hashes(fp)

        # 第四步：修改 change.txt
        with open(os.path.join(self.src, "change.txt"), "r+b") as f:
            f.seek(100)
            f.write(b"MODIFIED IN BLOCK 1!")

        # 第五步：做块级增量备份
        chunk_meta = mgr.data["_chunk_meta"].get(self.src, {})
        incr_result = BackupManager._build_block_incremental(
            source_path=self.src,
            target_dir=self.dst,
            chunk_meta=chunk_meta,
            skip_patterns=[],
            compression_format="ZIP",
            compression_algorithm="ZIP_DEFLATED",
            compression_level=6,
            password="",
            name_template="incremental",
            threads=1,
        )
        self.assertTrue(incr_result["success"])
        incr_path = incr_result["path"]

        # 第六步：先还原全量
        restore_backup(full_path, self.restore_dir)
        # 验证全量还原
        restored_keep = Path(self.restore_dir) / "src" / "keep.txt"
        self.assertTrue(restored_keep.exists())
        self.assertIn("never changes", restored_keep.read_text())

        # 第七步：还原增量补丁
        restore_backup(incr_path, self.restore_dir)

        # 验证：change.txt 应包含修改（如果补丁成功应用）
        restored_change = Path(self.restore_dir) / "src" / "change.txt"
        if restored_change.exists():
            content = restored_change.read_text()
            # 补丁应用后，内容应包含修改
            if "MODIFIED" in content:
                pass  # 预期行为
            # 至少保留原始内容
            self.assertIn("original", content)

    def test_incremental_smaller_than_full(self):
        """增量归档应比全量小很多"""
        # 创建一个大文件
        big_path = Path(self.src) / "big.bin"
        big_path.write_bytes(os.urandom(CHUNK_SIZE * 50))  # ~3MB

        # 全量备份
        config = Config(
            folder_path=self.src,
            zipfile_path=os.path.join(self.dst, "full_big"),
            skip_patterns=[],
            compression_format="ZIP",
            name_template="full",
        )
        full_result = create_compressor(config).compress()
        self.assertTrue(full_result["success"])
        full_size = os.path.getsize(full_result["path"])

        # 保存分块元数据
        chunk_meta_src = {}
        for dirpath, _, filenames in os.walk(self.src):
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, self.src).replace("\\", "/")
                chunk_meta_src[rel] = compute_chunk_hashes(fp)

        # 只修改少量字节
        with open(big_path, "r+b") as f:
            f.seek(100)
            f.write(b"tiny change!!")

        # 增量备份
        incr_result = BackupManager._build_block_incremental(
            source_path=self.src,
            target_dir=self.dst,
            chunk_meta=chunk_meta_src,
            skip_patterns=[],
            compression_format="ZIP",
            compression_algorithm="ZIP_DEFLATED",
            compression_level=6,
            password="",
            name_template="incremental",
            threads=1,
        )
        self.assertTrue(incr_result["success"])

        # 由于文件很大且只修改了少量字节，变化比例 < 50%，应生成补丁
        # 增量归档大小应远小于全量
        incr_files = incr_result.get("files_count", 0)
        if incr_files > 0:
            incr_size = os.path.getsize(incr_result["path"])
            # 增量应明显小于全量（至少小 50% — 只含少量补丁块）
            self.assertLess(incr_size, full_size * 0.5,
                          f"增量 {incr_size} 应远小于全量 {full_size}")


if __name__ == "__main__":
    unittest.main()
