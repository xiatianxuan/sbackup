"""
针对性单元测试：覆盖通过深入代码分析发现的 bug
"""

import unittest
import os
import json
import time
import tempfile
import shutil
from pathlib import Path
from sbackup.config import Config, _gitignore_to_fnmatch
from sbackup.compression import (
    ZipfileCompression,
    _resolve_name,
)
from sbackup.auto_save import BackupManager, BackupEntry


class TestDryRunPreviewUnpacking(unittest.TestCase):
    """Bug1: _dry_run_preview 解包错误
    任务元组有 12 个元素但解包只期望 6 个，导致 dry-run 模式崩溃。
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.source_dir = os.path.join(self.test_dir, "source")
        self.target_dir = os.path.join(self.test_dir, "target")
        os.makedirs(self.source_dir)
        os.makedirs(self.target_dir)
        (Path(self.source_dir) / "file.txt").write_text("content")
        self.data_file = os.path.join(self.test_dir, "data.json")
        self.manager = BackupManager(self.data_file)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dry_run_preview_with_12_element_tuples(self):
        """验证 _dry_run_preview 能正确处理 12 元素的任务元组"""
        self.manager.add_folder(self.source_dir, self.target_dir, "")
        abs_source = os.path.abspath(self.source_dir)
        entry = self.manager._get_entry(abs_source)
        assert entry is not None

        config = Config(
            compression_format="ZIP",
            compression_algorithm="ZIP_DEFLATED",
            compression_level=6,
        )

        # 构造 12 元素元组（与 execute_backups 中一致）
        tasks = [
            (
                abs_source,  # key
                entry,  # entry
                0.0,  # current_mtime
                config,  # config
                "",  # password
                "",  # name_template
                False,  # follow_symlinks
                0,  # max_size
                0,  # min_size
                0,  # max_age_seconds
                {},  # file_metadata
                0,  # split_size
            )
        ]

        # 修复前：这会抛出 ValueError: too many values to unpack
        try:
            BackupManager._dry_run_preview(tasks, config)
        except ValueError as e:
            self.fail(f"_dry_run_preview 解包失败: {e}")

    def test_dry_run_preview_empty_tasks(self):
        """验证空任务列表时 _dry_run_preview 不崩溃"""
        config = Config()
        BackupManager._dry_run_preview([], config)

    def test_dry_run_preview_integration(self):
        """集成测试：通过 execute_backups(dry_run=True) 验证完整流程"""
        self.manager.add_folder(self.source_dir, self.target_dir, "")
        time.sleep(0.1)
        (Path(self.source_dir) / "new.txt").write_text("new")

        # 修复前：这会抛出 ValueError
        try:
            self.manager.execute_backups(dry_run=True)
        except ValueError as e:
            self.fail(f"dry-run 模式崩溃: {e}")


class TestShouldIgnoreNegation(unittest.TestCase):
    """Bug2: _should_ignore 取反逻辑错误
    当没有正则模式匹配时，取反模式不应排除文件。
    取反模式（!pattern）只应在文件已被忽略时恢复它。
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _make_compressor(self, skip_patterns):
        config = Config(folder_path=self.test_dir, skip_patterns=skip_patterns)
        return ZipfileCompression(config)

    def test_negation_without_prior_match_should_not_ignore(self):
        """只有取反模式没有正模式时，文件不应被忽略"""
        comp = self._make_compressor(["!important.log"])
        # "readme.txt" 不匹配任何模式（包括取反），应返回 False（不忽略）
        self.assertFalse(comp._should_ignore("readme.txt"))
        # "important.log" 匹配取反模式，但之前没有被忽略，应返回 False
        # 修复前：返回 True（错误地排除了文件）
        self.assertFalse(comp._should_ignore("important.log"))

    def test_negation_restores_previously_ignored_file(self):
        """取反模式正确恢复被正模式忽略的文件"""
        comp = self._make_compressor(["*.log", "!important.log"])
        # "error.log" 匹配 *.log，应被忽略
        self.assertTrue(comp._should_ignore("error.log"))
        # "important.log" 匹配 *.log 但被 !important.log 恢复
        self.assertFalse(comp._should_ignore("important.log"))

    def test_negation_with_regex(self):
        """正则取反模式在无正则匹配时不应排除文件"""
        comp = self._make_compressor([r"!re:important\.log"])
        self.assertFalse(comp._should_ignore("important.log"))
        self.assertFalse(comp._should_ignore("readme.txt"))

    def test_negation_restores_regex_ignored_file(self):
        """正则取反模式正确恢复被正则忽略的文件"""
        comp = self._make_compressor([r"re:.*\.log$", r"!re:important\.log"])
        self.assertTrue(comp._should_ignore("error.log"))
        self.assertFalse(comp._should_ignore("important.log"))

    def test_negation_real_compression(self):
        """集成测试：验证取反模式在实际压缩中正确工作"""
        (Path(self.test_dir) / "keep.txt").write_text("keep")
        (Path(self.test_dir) / "important.log").write_text("important")
        zip_path = os.path.join(self.test_dir, "test.zip")

        # 只有取反模式，不应忽略任何文件
        config = Config(
            folder_path=self.test_dir,
            zipfile_path=zip_path,
            skip_patterns=["!important.log"],
        )
        compressor = ZipfileCompression(config)
        result = compressor.compress()
        self.assertTrue(result["success"])

        import zipfile

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            self.assertTrue(any("keep.txt" in n for n in names))
            # 修复前：important.log 被错误排除
            self.assertTrue(any("important.log" in n for n in names))


class TestResolveNameTemplateError(unittest.TestCase):
    """Bug3: _resolve_name 模板 KeyError
    用户模板中包含未知占位符（如 {password}）时应降级到 folder_name，
    而不是抛出 KeyError。
    """

    def test_unknown_placeholder_returns_folder_name(self):
        """未知占位符应回退到 folder_name"""
        result = _resolve_name("{name}_{password}", "myproject")
        # 修复前：抛出 KeyError
        self.assertEqual(result, "myproject")

    def test_valid_template_still_works(self):
        """有效模板仍正常工作"""
        result = _resolve_name("{name}_{date}", "myproject")
        self.assertTrue(result.startswith("myproject_"))
        self.assertIn("-", result)

    def test_empty_template_returns_folder_name(self):
        """空模板返回 folder_name"""
        self.assertEqual(_resolve_name("", "myproject"), "myproject")

    def test_malformed_braces_returns_folder_name(self):
        """格式错误的大括号应回退到 folder_name"""
        result = _resolve_name("{name_}{invalid", "myproject")
        self.assertEqual(result, "myproject")

    def test_valid_template_with_time(self):
        """包含 {time} 变量的模板正常工作"""
        result = _resolve_name("{name}_{date}_{time}", "proj")
        self.assertTrue(result.startswith("proj_"))
        # 应包含日期和时间部分
        parts = result.split("_")
        self.assertGreaterEqual(len(parts), 3)


class TestDiffBackupModifiedDetection(unittest.TestCase):
    """Bug4: diff_backup 修改检测错误
    所有共同文件都被报告为已修改，即使内容未变化。
    修复后：只有 mtime 晚于备份文件的源文件才报告为已修改。
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        self.source_dir = os.path.join(self.test_dir, "source")
        self.target_dir = os.path.join(self.test_dir, "target")
        os.makedirs(self.source_dir)
        os.makedirs(self.target_dir)
        self.data_file = os.path.join(self.test_dir, "data.json")
        self.manager = BackupManager(self.data_file)

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _make_backup(self):
        """创建一次备份并返回备份文件路径"""
        (Path(self.source_dir) / "file1.txt").write_text("content1")
        (Path(self.source_dir) / "file2.txt").write_text("content2")
        self.manager.add_folder(self.source_dir, self.target_dir, "")
        time.sleep(0.1)
        (Path(self.source_dir) / "trigger.txt").write_text("trigger")
        self.manager.execute_backups()
        backups = list(Path(self.target_dir).glob("*.zip"))
        self.assertGreater(len(backups), 0)
        return str(backups[0])

    def test_unchanged_files_not_reported_as_modified(self):
        """未修改的文件不应出现在 modified 列表中"""
        self._make_backup()
        diff = self.manager.diff_backup(self.source_dir)
        self.assertTrue(diff["success"])
        # 修复前：所有共同文件都被报告为 modified
        self.assertEqual(
            len(diff["modified"]),
            0,
            f"未修改的文件不应出现在 modified 中: {diff['modified']}",
        )

    def test_modified_file_detected(self):
        """修改后的文件应出现在 modified 列表中"""
        self._make_backup()
        # 修改一个文件
        time.sleep(0.1)
        (Path(self.source_dir) / "file1.txt").write_text("CHANGED")
        diff = self.manager.diff_backup(self.source_dir)
        self.assertTrue(diff["success"])
        modified_names = [Path(p).name for p in diff["modified"]]
        self.assertIn("file1.txt", modified_names)

    def test_added_file_detected(self):
        """新增文件应出现在 added 列表中"""
        self._make_backup()
        (Path(self.source_dir) / "new_file.txt").write_text("new")
        diff = self.manager.diff_backup(self.source_dir)
        self.assertTrue(diff["success"])
        added_names = [Path(p).name for p in diff["added"]]
        self.assertIn("new_file.txt", added_names)


class TestFormatStatusBrokenSymlink(unittest.TestCase):
    """Bug5: format_status OSError
    目标目录中存在断裂的符号链接时，rglob + stat 会抛出 OSError。
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.data_file = os.path.join(self.test_dir, "data.json")
        self.manager = BackupManager(self.data_file)
        self.source_dir = os.path.join(self.test_dir, "source")
        self.target_dir = os.path.join(self.test_dir, "target")
        os.makedirs(self.source_dir)
        os.makedirs(self.target_dir)
        # 创建一个假备份文件
        (Path(self.target_dir) / "backup.zip").write_bytes(b"fake")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_format_status_with_broken_symlink(self):
        """format_status 在目标目录有断开符号链接时不崩溃"""
        self.manager.add_folder(self.source_dir, self.target_dir, "")

        # 创建一个断开的符号链接（Windows 上可能需要管理员权限）
        broken_link = Path(self.target_dir) / "broken_link"
        try:
            broken_link.symlink_to("/nonexistent/file")
        except (OSError, NotImplementedError):
            self.skipTest("无法创建符号链接（需要管理员权限或不支持）")

        # 修复前：这会抛出 OSError
        try:
            result = self.manager.format_status()
            self.assertIsInstance(result, str)
        except OSError as e:
            self.fail(f"format_status 因断开符号链接崩溃: {e}")

    def test_format_status_normal(self):
        """format_status 在正常目录下工作"""
        self.manager.add_folder(self.source_dir, self.target_dir, "")
        result = self.manager.format_status()
        self.assertIsInstance(result, str)
        self.assertIn(self.source_dir, result)


class TestGitignoreToFnmatchRedundantBranch(unittest.TestCase):
    """Bug6: _gitignore_to_fnmatch 冗余条件
    内层 if-not-startswith-* 条件与外层重复，else 分支是死代码。
    """

    def test_simple_pattern(self):
        """简单模式 'build' 应转换为 '*build'"""
        result = _gitignore_to_fnmatch("build")
        self.assertEqual(result, "*build")

    def test_pattern_already_with_star(self):
        """以 * 开头的模式不添加前缀"""
        result = _gitignore_to_fnmatch("*.log")
        self.assertEqual(result, "*.log")

    def test_pattern_with_slash(self):
        """包含路径分隔符的模式不添加前缀"""
        result = _gitignore_to_fnmatch("src/build")
        self.assertEqual(result, "src/build")

    def test_pattern_with_double_star(self):
        """** 模式正确转换"""
        result = _gitignore_to_fnmatch("**/node_modules")
        self.assertEqual(result, "*node_modules")

    def test_leading_slash_removed(self):
        """开头斜杠被移除"""
        result = _gitignore_to_fnmatch("/build")
        self.assertEqual(result, "*build")

    def test_trailing_slash_removed(self):
        """尾部斜杠被移除"""
        result = _gitignore_to_fnmatch("build/")
        self.assertEqual(result, "*build")

    def test_negation_preserved(self):
        """取反模式中 ! 由 parse_gitignore 处理，_gitignore_to_fnmatch 不处理 !"""
        # 注意：_gitignore_to_fnmatch 本身不处理 ! 前缀
        # parse_gitignore 先剥离 !，再调用 _gitignore_to_fnmatch，最后加回 !
        # 所以直接调用 _gitignore_to_fnmatch 时，! 被视为普通字符
        result = _gitignore_to_fnmatch("!important.log")
        self.assertEqual(result, "*!important.log")


class TestBackupEntryRoundTrip(unittest.TestCase):
    """测试 BackupEntry 序列化/反序列化的完整性"""

    def test_full_round_trip(self):
        """完整 5 元素列表的往返"""
        entry = BackupEntry(
            mtime=123.456,
            target="/path/to/target",
            skip_patterns=[".git", "*.log"],
            compression_format="TAR_GZ",
            name_template="{name}_{date}",
        )
        data = entry.to_list()
        self.assertEqual(len(data), 5)
        restored = BackupEntry.from_list(data)
        self.assertEqual(restored.mtime, 123.456)
        self.assertEqual(restored.target, "/path/to/target")
        self.assertEqual(restored.skip_patterns, [".git", "*.log"])
        self.assertEqual(restored.compression_format, "TAR_GZ")
        self.assertEqual(restored.name_template, "{name}_{date}")

    def test_three_element_backward_compat(self):
        """3 元素旧格式向后兼容"""
        entry = BackupEntry.from_list([99.0, "/old/path", [".git"]])
        self.assertEqual(entry.mtime, 99.0)
        self.assertEqual(entry.target, "/old/path")
        self.assertEqual(entry.skip_patterns, [".git"])
        self.assertEqual(entry.compression_format, "")
        self.assertEqual(entry.name_template, "")

    def test_four_element_backward_compat(self):
        """4 元素格式向后兼容"""
        entry = BackupEntry.from_list([99.0, "/old/path", [".git"], "7Z"])
        self.assertEqual(entry.compression_format, "7Z")
        self.assertEqual(entry.name_template, "")

    def test_non_list_input(self):
        """非列表输入返回空条目"""
        entry = BackupEntry.from_list("invalid")
        self.assertEqual(entry.mtime, 0.0)
        self.assertEqual(entry.target, "")

    def test_none_input(self):
        """None 输入返回空条目"""
        entry = BackupEntry.from_list(None)
        self.assertEqual(entry.mtime, 0.0)


class TestCollectFilesIncrementalMetadata(unittest.TestCase):
    """测试增量备份的文件元数据比较逻辑"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        (Path(self.test_dir) / "file.txt").write_text("content")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_metadata_mode_skip_unchanged_file(self):
        """元数据模式下未变化的文件应被跳过"""
        file_path = Path(self.test_dir) / "file.txt"
        stat = file_path.stat()
        metadata = {"file.txt": [stat.st_mtime, stat.st_size]}

        config = Config(
            folder_path=self.test_dir,
            skip_patterns=[],
            file_metadata=metadata,
        )
        compressor = ZipfileCompression(config)
        files = compressor._collect_files(Path(self.test_dir))
        self.assertEqual(len(files), 0, "未变化的文件应被跳过")

    def test_metadata_mode_include_changed_file(self):
        """元数据模式下变化的文件不应被跳过"""
        file_path = Path(self.test_dir) / "file.txt"
        stat = file_path.stat()
        # 故意使用不同的 mtime
        metadata = {"file.txt": [stat.st_mtime + 100, stat.st_size]}

        config = Config(
            folder_path=self.test_dir,
            skip_patterns=[],
            file_metadata=metadata,
        )
        compressor = ZipfileCompression(config)
        files = compressor._collect_files(Path(self.test_dir))
        self.assertEqual(len(files), 1, "变化的文件不应被跳过")

    def test_checksum_mode_skip_unchanged_file(self):
        """校验和模式下内容未变化的文件应被跳过"""
        import hashlib

        sha = hashlib.sha256()
        file_path = Path(self.test_dir) / "file.txt"
        sha.update(file_path.read_bytes())
        metadata = {"file.txt": sha.hexdigest()}

        config = Config(
            folder_path=self.test_dir,
            skip_patterns=[],
            file_metadata=metadata,
        )
        compressor = ZipfileCompression(config)
        files = compressor._collect_files(Path(self.test_dir))
        self.assertEqual(len(files), 0, "内容未变化的文件应被跳过")

    def test_checksum_mode_include_changed_file(self):
        """校验和模式下内容变化的文件不应被跳过"""
        metadata = {"file.txt": "a" * 64}  # 假的校验和

        config = Config(
            folder_path=self.test_dir,
            skip_patterns=[],
            file_metadata=metadata,
        )
        compressor = ZipfileCompression(config)
        files = compressor._collect_files(Path(self.test_dir))
        self.assertEqual(len(files), 1, "内容变化的文件不应被跳过")


class TestEncryptionRoundTrip(unittest.TestCase):
    """测试文件加密/解密往返"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_encrypt_decrypt_round_trip(self):
        """加密后解密应恢复原始内容"""
        from sbackup.compression import _encrypt_file, _decrypt_file

        original_content = b"Hello, this is test content for encryption!"
        file_path = os.path.join(self.test_dir, "test.bin")
        with open(file_path, "wb") as f:
            f.write(original_content)

        password = "test_password_123"
        encrypted_path = _encrypt_file(file_path, password)

        self.assertTrue(encrypted_path.endswith(".enc"))
        self.assertFalse(os.path.exists(file_path))  # 原文件应被删除
        self.assertTrue(os.path.exists(encrypted_path))

        decrypted_path = _decrypt_file(encrypted_path, password)
        self.assertEqual(decrypted_path, file_path)

        with open(decrypted_path, "rb") as f:
            decrypted_content = f.read()
        self.assertEqual(decrypted_content, original_content)

    def test_decrypt_wrong_password(self):
        """错误密码解密应产生不同的内容"""
        from sbackup.compression import _encrypt_file, _decrypt_file

        original_content = b"Secret data"
        file_path = os.path.join(self.test_dir, "secret.bin")
        with open(file_path, "wb") as f:
            f.write(original_content)

        encrypted_path = _encrypt_file(file_path, "correct_password")

        decrypted_path = _decrypt_file(encrypted_path, "wrong_password")
        with open(decrypted_path, "rb") as f:
            decrypted_content = f.read()
        self.assertNotEqual(decrypted_content, original_content)


class TestSplitAndMergeFiles(unittest.TestCase):
    """测试文件分卷和合并功能"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_split_and_merge_round_trip(self):
        """分卷后合并应恢复原始内容"""
        from sbackup.compression import split_file, merge_files

        original_content = b"A" * 1000 + b"B" * 500
        file_path = os.path.join(self.test_dir, "large.bin")
        with open(file_path, "wb") as f:
            f.write(original_content)

        parts = split_file(file_path, 512)
        self.assertGreater(len(parts), 1)
        self.assertFalse(os.path.exists(file_path))  # 原文件应被删除

        output_path = os.path.join(self.test_dir, "merged.bin")
        result = merge_files(parts, output_path)
        self.assertTrue(result)

        with open(output_path, "rb") as f:
            merged_content = f.read()
        self.assertEqual(merged_content, original_content)

    def test_split_small_file_no_split(self):
        """小于分卷大小的文件不分割"""
        from sbackup.compression import split_file

        file_path = os.path.join(self.test_dir, "small.bin")
        with open(file_path, "wb") as f:
            f.write(b"small")

        parts = split_file(file_path, 1024)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0], file_path)
        self.assertTrue(os.path.exists(file_path))  # 原文件保留

    def test_split_zero_chunk_size(self):
        """chunk_size=0 不分割"""
        from sbackup.compression import split_file

        file_path = os.path.join(self.test_dir, "test.bin")
        with open(file_path, "wb") as f:
            f.write(b"data")

        parts = split_file(file_path, 0)
        self.assertEqual(len(parts), 1)

    def test_merge_empty_list(self):
        """空列表合并创建空文件"""
        from sbackup.compression import merge_files

        output_path = os.path.join(self.test_dir, "empty.bin")
        result = merge_files([], output_path)
        self.assertTrue(result)
        self.assertEqual(os.path.getsize(output_path), 0)


class TestWebhookPreset(unittest.TestCase):
    """测试 Webhook 预设配置"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_setup_webhook_preset_dingtalk(self):
        """测试钉钉预设"""
        from sbackup.config import setup_webhook_preset

        template = setup_webhook_preset("dingtalk", self.config_file)
        self.assertIn("{status}", template)
        self.assertTrue(os.path.exists(self.config_file))

    def test_setup_webhook_preset_unknown(self):
        """测试未知预设返回空字符串"""
        from sbackup.config import setup_webhook_preset

        template = setup_webhook_preset("unknown_preset", self.config_file)
        self.assertEqual(template, "")


class TestParseGitignore(unittest.TestCase):
    """测试 .gitignore 解析"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_parse_gitignore_basic(self):
        """测试基本 gitignore 解析"""
        from sbackup.config import parse_gitignore

        gitignore_path = os.path.join(self.test_dir, ".gitignore")
        with open(gitignore_path, "w") as f:
            f.write("*.log\n# comment\n\n/node_modules\n!important.log\n")

        patterns = parse_gitignore(gitignore_path)
        # *.log 已以 * 开头，不添加前缀
        self.assertIn("*.log", patterns)
        self.assertIn("*node_modules", patterns)
        self.assertIn("!*important.log", patterns)
        # 注释和空行应被跳过
        self.assertEqual(len([p for p in patterns if "comment" in p]), 0)

    def test_parse_gitignore_nonexistent(self):
        """不存在的文件返回空列表"""
        from sbackup.config import parse_gitignore

        result = parse_gitignore("/nonexistent/.gitignore")
        self.assertEqual(result, [])


class TestConfigEncryptDecrypt(unittest.TestCase):
    """测试配置文件加密/解密"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_encrypt_decrypt_round_trip(self):
        """加密后解密应恢复原始敏感字段"""
        from sbackup.config import encrypt_config, decrypt_config, is_config_encrypted

        config_data = {
            "password": "my_backup_password",
            "sftp": {"password": "sftp_pass", "key_passphrase": "key_pass"},
            "webdav": {"password": "webdav_pass"},
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        self.assertFalse(is_config_encrypted(self.config_file))

        result = encrypt_config("master_key", self.config_file)
        self.assertTrue(result)
        self.assertTrue(is_config_encrypted(self.config_file))

        # 加密后密码应被替换
        with open(self.config_file, "r", encoding="utf-8") as f:
            encrypted_data = json.load(f)
        self.assertTrue(encrypted_data["password"].startswith("enc:"))

        # 解密
        result = decrypt_config("master_key", self.config_file)
        self.assertTrue(result)
        self.assertFalse(is_config_encrypted(self.config_file))

        with open(self.config_file, "r", encoding="utf-8") as f:
            decrypted_data = json.load(f)
        self.assertEqual(decrypted_data["password"], "my_backup_password")
        self.assertEqual(decrypted_data["sftp"]["password"], "sftp_pass")
        self.assertEqual(decrypted_data["webdav"]["password"], "webdav_pass")

    def test_decrypt_wrong_password(self):
        """错误密码解密应返回 False"""
        from sbackup.config import encrypt_config, decrypt_config

        config_data = {"password": "secret"}
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        encrypt_config("master", self.config_file)
        result = decrypt_config("wrong_master", self.config_file)
        self.assertFalse(result)

    def test_decrypt_unencrypted_config(self):
        """解密未加密的配置应返回 True"""
        from sbackup.config import decrypt_config

        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump({"password": "plain"}, f)

        result = decrypt_config("any_password", self.config_file)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
