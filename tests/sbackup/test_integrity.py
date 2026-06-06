"""
单元测试 for sbackup.integrity 模块
"""

import json
import os
import shutil
import tempfile
import unittest

from sbackup.integrity import (
    compute_checksum,
    generate_checksum_file,
    verify_checksum_file,
    generate_backup_integrity,
    verify_backup_integrity,
)


class TestComputeChecksum(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.tmp_dir, "test.txt")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_checksum_correctness(self):
        """验证 SHA256 校验和的正确性"""
        content = b"Hello, sbackup integrity check!"
        with open(self.test_file, "wb") as f:
            f.write(content)

        checksum = compute_checksum(self.test_file)
        self.assertEqual(len(checksum), 64, "SHA256 hex digest should be 64 chars")
        self.assertEqual(
            checksum,
            "a7678d4a50336602c62bd7d23a9968cbe54a82a3d219f14f65c9328e6f421234",
        )

    def test_checksum_known_value(self):
        """用已知内容验证 SHA256 值"""
        content = b"abc"
        with open(self.test_file, "wb") as f:
            f.write(content)

        checksum = compute_checksum(self.test_file)
        # SHA256("abc") = ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
        self.assertEqual(
            checksum,
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )

    def test_checksum_empty_file(self):
        """空文件的校验和"""
        with open(self.test_file, "wb"):
            pass

        checksum = compute_checksum(self.test_file)
        self.assertEqual(len(checksum), 64)

    def test_checksum_file_not_found(self):
        """文件不存在时抛出 FileNotFoundError"""
        with self.assertRaises(FileNotFoundError):
            compute_checksum(os.path.join(self.tmp_dir, "nonexistent.txt"))

    def test_checksum_deterministic(self):
        """同一文件多次计算结果一致"""
        with open(self.test_file, "wb") as f:
            f.write(b"consistent")

        c1 = compute_checksum(self.test_file)
        c2 = compute_checksum(self.test_file)
        self.assertEqual(c1, c2)

    def test_checksum_different_files(self):
        """不同内容产生不同校验和"""
        with open(self.test_file, "wb") as f:
            f.write(b"content_a")

        other_file = os.path.join(self.tmp_dir, "other.txt")
        with open(other_file, "wb") as f:
            f.write(b"content_b")

        self.assertNotEqual(
            compute_checksum(self.test_file), compute_checksum(other_file)
        )


class TestChecksumFile(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.tmp_dir, "archive.zip")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_generate_and_verify(self):
        """生成 .sha256 文件后验证通过"""
        with open(self.test_file, "wb") as f:
            f.write(b"backup data here")

        checksum_path = generate_checksum_file(self.test_file)
        self.assertTrue(os.path.isfile(checksum_path))
        self.assertEqual(checksum_path, self.test_file + ".sha256")

        # 验证文件内容格式
        with open(checksum_path, "r", encoding="utf-8") as f:
            line = f.readline().strip()
        parts = line.split("  ", 1)
        self.assertEqual(len(parts), 2)
        self.assertEqual(len(parts[0]), 64, "Hash should be 64 hex chars")
        self.assertEqual(parts[1], "archive.zip")

        # 验证
        ok, msg = verify_checksum_file(self.test_file)
        self.assertTrue(ok)
        self.assertIn("verified", msg.lower())

    def test_verify_tampered_file(self):
        """文件被篡改后验证失败"""
        with open(self.test_file, "wb") as f:
            f.write(b"original content")

        generate_checksum_file(self.test_file)

        # 篡改文件
        with open(self.test_file, "wb") as f:
            f.write(b"tampered content")

        ok, msg = verify_checksum_file(self.test_file)
        self.assertFalse(ok)
        self.assertIn("mismatch", msg.lower())

    def test_verify_no_checksum_file(self):
        """缺少 .sha256 文件时返回失败"""
        with open(self.test_file, "wb") as f:
            f.write(b"data")

        ok, msg = verify_checksum_file(self.test_file)
        self.assertFalse(ok)
        self.assertIn("not found", msg.lower())

    def test_verify_missing_source_file(self):
        """源文件缺失时返回失败"""
        # 创建一个 .sha256 文件但不创建源文件
        checksum_path = self.test_file + ".sha256"
        with open(checksum_path, "w", encoding="utf-8") as f:
            f.write(
                "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  archive.zip\n"
            )

        ok, msg = verify_checksum_file(self.test_file)
        self.assertFalse(ok)
        self.assertIn("not found", msg.lower())

    def test_generate_file_not_found(self):
        """为不存在的文件生成校验文件时抛出异常"""
        with self.assertRaises(FileNotFoundError):
            generate_checksum_file(os.path.join(self.tmp_dir, "nope.zip"))


class TestBackupIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_backup_files(self, names: dict[str, bytes]) -> None:
        """创建模拟备份文件"""
        for name, content in names.items():
            with open(os.path.join(self.tmp_dir, name), "wb") as f:
                f.write(content)

    def test_generate_integrity(self):
        """生成 integrity.json 包含所有备份文件"""
        self._create_backup_files(
            {
                "backup1.zip": b"zip content",
                "backup2.tar.gz": b"tar.gz content",
                "readme.txt": b"this should be ignored",
            }
        )

        integrity_path = generate_backup_integrity(self.tmp_dir)
        self.assertTrue(os.path.isfile(integrity_path))
        self.assertEqual(integrity_path, os.path.join(self.tmp_dir, "integrity.json"))

        with open(integrity_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("created", data)
        self.assertIn("files", data)
        self.assertIn("backup1.zip", data["files"])
        self.assertIn("backup2.tar.gz", data["files"])
        self.assertNotIn("readme.txt", data["files"])
        self.assertEqual(len(data["files"]), 2)

    def test_verify_integrity_ok(self):
        """文件未被修改时验证通过"""
        self._create_backup_files(
            {
                "backup1.zip": b"content1",
                "backup2.tar.gz": b"content2",
            }
        )
        generate_backup_integrity(self.tmp_dir)

        ok, messages = verify_backup_integrity(self.tmp_dir)
        self.assertTrue(ok)
        self.assertTrue(all(m.startswith("OK:") for m in messages))

    def test_verify_integrity_tampered(self):
        """文件被篡改后验证失败"""
        self._create_backup_files({"backup1.zip": b"original"})
        generate_backup_integrity(self.tmp_dir)

        # 篡改文件
        with open(os.path.join(self.tmp_dir, "backup1.zip"), "wb") as f:
            f.write(b"tampered")

        ok, messages = verify_backup_integrity(self.tmp_dir)
        self.assertFalse(ok)
        failed_msgs = [m for m in messages if m.startswith("FAILED:")]
        self.assertEqual(len(failed_msgs), 1)

    def test_verify_integrity_missing_file(self):
        """文件被删除后验证失败"""
        self._create_backup_files(
            {
                "backup1.zip": b"data",
                "backup2.tar.gz": b"data",
            }
        )
        generate_backup_integrity(self.tmp_dir)

        # 删除一个文件
        os.remove(os.path.join(self.tmp_dir, "backup1.zip"))

        ok, messages = verify_backup_integrity(self.tmp_dir)
        self.assertFalse(ok)
        missing_msgs = [m for m in messages if m.startswith("MISSING:")]
        self.assertEqual(len(missing_msgs), 1)
        self.assertIn("backup1.zip", missing_msgs[0])

    def test_verify_integrity_no_manifest(self):
        """缺少 integrity.json 时验证失败"""
        ok, messages = verify_backup_integrity(self.tmp_dir)
        self.assertFalse(ok)
        self.assertTrue(any("not found" in m.lower() for m in messages))

    def test_verify_integrity_empty_manifest(self):
        """空的 integrity.json 通过验证"""
        with open(os.path.join(self.tmp_dir, "integrity.json"), "w") as f:
            json.dump({"created": "2026-01-01T00:00:00", "files": {}}, f)

        ok, messages = verify_backup_integrity(self.tmp_dir)
        self.assertTrue(ok)
        self.assertTrue(any("No files" in m for m in messages))

    def test_generate_integrity_not_a_directory(self):
        """路径不是目录时抛出异常"""
        file_path = os.path.join(self.tmp_dir, "not_a_dir")
        with open(file_path, "w") as f:
            f.write("data")
        with self.assertRaises(NotADirectoryError):
            generate_backup_integrity(file_path)

    def test_integrity_preserves_checksums(self):
        """生成的 integrity.json 中的校验和与 compute_checksum 一致"""
        self._create_backup_files({"test.zip": b"verify me"})
        generate_backup_integrity(self.tmp_dir)

        with open(os.path.join(self.tmp_dir, "integrity.json"), "r") as f:
            data = json.load(f)

        actual = compute_checksum(os.path.join(self.tmp_dir, "test.zip"))
        self.assertEqual(data["files"]["test.zip"], actual)

    def test_generate_idempotent(self):
        """多次生成 integrity.json 结果一致"""
        self._create_backup_files({"backup.zip": b"stable content"})
        generate_backup_integrity(self.tmp_dir)
        with open(os.path.join(self.tmp_dir, "integrity.json"), "r") as f:
            data1 = json.load(f)

        generate_backup_integrity(self.tmp_dir)
        with open(os.path.join(self.tmp_dir, "integrity.json"), "r") as f:
            data2 = json.load(f)

        self.assertEqual(data1["files"], data2["files"])


if __name__ == "__main__":
    unittest.main()
