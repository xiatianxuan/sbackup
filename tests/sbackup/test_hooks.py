"""
单元测试 for sbackup.hooks 模块（HookResult / HookRunner）
"""

import os
import sys
import unittest

from sbackup.hooks import HookResult, HookRunner


def _make_python_cmd(script: str) -> str:
    """创建跨平台的 Python 命令，避免引号转义问题"""
    return f"{sys.executable} -c {script}"


_echo_cmd = _make_python_cmd("print(42)")
_fail_cmd = _make_python_cmd("raise SystemExit(1)")
_sleep_cmd = _make_python_cmd("__import__('time').sleep(10)")


class TestHookResult(unittest.TestCase):
    """测试 HookResult 数据类"""

    def test_basic_creation(self):
        """测试基本创建"""
        r = HookResult(
            hook_type="pre",
            command="echo hello",
            return_code=0,
            stdout="hello\n",
            stderr="",
            success=True,
            duration=0.1,
        )
        self.assertEqual(r.hook_type, "pre")
        self.assertEqual(r.command, "echo hello")
        self.assertEqual(r.return_code, 0)
        self.assertTrue(r.success)
        self.assertFalse(r.timed_out)

    def test_timeout_result(self):
        """测试超时结果"""
        r = HookResult(
            hook_type="post",
            command="sleep 999",
            return_code=None,
            stdout="",
            stderr="timed out",
            success=False,
            duration=5.0,
            timed_out=True,
        )
        self.assertIsNone(r.return_code)
        self.assertFalse(r.success)
        self.assertTrue(r.timed_out)


class TestHookRunnerRunSingle(unittest.TestCase):
    """测试 HookRunner.run_single 方法"""

    def test_success_command(self):
        """测试正常执行成功的命令"""
        runner = HookRunner(timeout=10)
        result = runner.run_single(_echo_cmd, "pre")

        self.assertTrue(result.success)
        self.assertEqual(result.return_code, 0)
        self.assertEqual(result.hook_type, "pre")
        self.assertIn("42", result.stdout)
        self.assertFalse(result.timed_out)
        self.assertGreaterEqual(result.duration, 0)

    def test_failure_command(self):
        """测试执行失败的命令（return_code != 0）"""
        runner = HookRunner(timeout=10)
        result = runner.run_single(_fail_cmd, "post")

        self.assertFalse(result.success)
        self.assertNotEqual(result.return_code, 0)
        self.assertEqual(result.hook_type, "post")
        self.assertFalse(result.timed_out)

    def test_timeout_command(self):
        """测试命令超时"""
        runner = HookRunner(timeout=1)
        result = runner.run_single(_sleep_cmd, "pre")

        self.assertFalse(result.success)
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.return_code)
        self.assertLess(result.duration, 5.0)  # Should timeout quickly

    def test_nonexistent_command(self):
        """测试执行不存在的命令"""
        runner = HookRunner(timeout=10)
        result = runner.run_single("this_command_does_not_exist_xyz123", "pre")

        self.assertFalse(result.success)
        self.assertNotEqual(result.return_code, 0)
        self.assertFalse(result.timed_out)
        self.assertTrue(len(result.stderr) > 0 or result.return_code is not None)

    def test_hook_type_preserved(self):
        """测试 hook_type 正确保留"""
        runner = HookRunner(timeout=10)
        result = runner.run_single(_echo_cmd, "post")
        self.assertEqual(result.hook_type, "post")


class TestHookRunnerRunHooks(unittest.TestCase):
    """测试 HookRunner.run_hooks 方法"""

    def test_multiple_hooks(self):
        """测试执行多个 hooks"""
        runner = HookRunner(
            pre_hooks=[_echo_cmd, _echo_cmd],
            timeout=10,
        )
        results = runner.run_hooks("pre")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.success for r in results))
        self.assertEqual(results[0].hook_type, "pre")
        self.assertEqual(results[1].hook_type, "pre")

    def test_empty_hooks_list(self):
        """测试空 hooks 列表"""
        runner = HookRunner(pre_hooks=[], timeout=10)
        results = runner.run_hooks("pre")
        self.assertEqual(len(results), 0)

    def test_pre_hooks_only(self):
        """测试 pre_hooks 单独执行"""
        runner = HookRunner(
            pre_hooks=[_echo_cmd],
            post_hooks=["never runs"],
            timeout=10,
        )
        pre_results = runner.run_pre_hooks()
        self.assertEqual(len(pre_results), 1)
        self.assertIn("42", pre_results[0].stdout)

    def test_post_hooks_only(self):
        """测试 post_hooks 单独执行"""
        runner = HookRunner(
            pre_hooks=["never runs"],
            post_hooks=[_echo_cmd],
            timeout=10,
        )
        post_results = runner.run_post_hooks()
        self.assertEqual(len(post_results), 1)
        self.assertIn("42", post_results[0].stdout)

    def test_mixed_success_and_failure(self):
        """测试混合成功和失败的 hooks"""
        runner = HookRunner(
            pre_hooks=[_echo_cmd, _fail_cmd],
            timeout=10,
        )
        results = runner.run_hooks("pre")
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].success)
        self.assertFalse(results[1].success)

    def test_empty_string_hook_skipped(self):
        """测试空字符串 hook 被跳过"""
        runner = HookRunner(
            pre_hooks=["", _echo_cmd, ""],
            timeout=10,
        )
        results = runner.run_hooks("pre")
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].success)

    def test_none_pre_hooks(self):
        """测试 pre_hooks 为 None"""
        runner = HookRunner(pre_hooks=None, timeout=10)
        results = runner.run_pre_hooks()
        self.assertEqual(len(results), 0)

    def test_none_post_hooks(self):
        """测试 post_hooks 为 None"""
        runner = HookRunner(post_hooks=None, timeout=10)
        results = runner.run_post_hooks()
        self.assertEqual(len(results), 0)


class TestHookRunnerFormatResults(unittest.TestCase):
    """测试 HookRunner.format_results 方法"""

    def test_format_empty_results(self):
        """测试格式化空结果"""
        runner = HookRunner()
        output = runner.format_results([])
        self.assertIn("钩子", output)

    def test_format_with_results(self):
        """测试格式化有结果的情况"""
        runner = HookRunner()
        results = [
            HookResult(
                hook_type="pre",
                command="echo ok",
                return_code=0,
                stdout="ok\n",
                stderr="",
                success=True,
                duration=0.1,
            ),
        ]
        output = runner.format_results(results)
        self.assertIn("echo ok", output)

    def test_format_with_failure(self):
        """测试格式化包含失败结果"""
        runner = HookRunner()
        results = [
            HookResult(
                hook_type="pre",
                command="bad_cmd",
                return_code=1,
                stdout="",
                stderr="error msg",
                success=False,
                duration=0.5,
            ),
        ]
        output = runner.format_results(results)
        self.assertIn("bad_cmd", output)
        self.assertIn("stderr: error msg", output)

    def test_format_summary(self):
        """测试格式化摘要行"""
        runner = HookRunner()
        results = [
            HookResult(
                hook_type="pre",
                command="a",
                return_code=0,
                stdout="",
                stderr="",
                success=True,
                duration=0.1,
            ),
            HookResult(
                hook_type="pre",
                command="b",
                return_code=1,
                stdout="",
                stderr="",
                success=False,
                duration=0.1,
            ),
        ]
        output = runner.format_results(results)
        self.assertIn("2", output)  # total
        self.assertIn("1", output)  # success/fail

    def test_format_timeout_status(self):
        """测试格式化超时状态"""
        runner = HookRunner()
        results = [
            HookResult(
                hook_type="pre",
                command="sleep 999",
                return_code=None,
                stdout="",
                stderr="",
                success=False,
                duration=1.0,
                timed_out=True,
            ),
        ]
        output = runner.format_results(results)
        self.assertIn("TIMEOUT", output)
        self.assertIn("N/A", output)


class TestHookRunnerWithConfig(unittest.TestCase):
    """测试 HookRunner 与 Config 的集成"""

    def test_config_hooks_fields(self):
        """测试 Config 包含 hooks 字段"""
        from sbackup.config import Config

        cfg = Config()
        self.assertEqual(cfg.pre_hooks, [])
        self.assertEqual(cfg.post_hooks, [])
        self.assertEqual(cfg.hook_timeout, 300)

    def test_config_load_hooks(self):
        """测试从配置文件加载 hooks"""
        import json
        import tempfile
        import shutil

        from sbackup.config import load_config

        test_dir = tempfile.mkdtemp()
        try:
            config_file = os.path.join(test_dir, "config.json")
            config_data = {
                "hooks": {
                    "pre": ["echo Starting", "python -c pass"],
                    "post": ["echo Done"],
                    "timeout": 60,
                }
            }
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f)

            cfg = load_config(config_file)
            self.assertEqual(cfg.pre_hooks, ["echo Starting", "python -c pass"])
            self.assertEqual(cfg.post_hooks, ["echo Done"])
            self.assertEqual(cfg.hook_timeout, 60)
        finally:
            shutil.rmtree(test_dir)

    def test_config_load_hooks_defaults(self):
        """测试配置中无 hooks 段时使用默认值"""
        import json
        import tempfile
        import shutil

        from sbackup.config import load_config

        test_dir = tempfile.mkdtemp()
        try:
            config_file = os.path.join(test_dir, "config.json")
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump({"lang": "zh_CN"}, f)

            cfg = load_config(config_file)
            self.assertEqual(cfg.pre_hooks, [])
            self.assertEqual(cfg.post_hooks, [])
            self.assertEqual(cfg.hook_timeout, 300)
        finally:
            shutil.rmtree(test_dir)


if __name__ == "__main__":
    unittest.main()
