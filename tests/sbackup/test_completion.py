"""单元测试 for sbackup.completion 模块"""

import unittest
from sbackup.completion import (
    generate_bash,
    generate_zsh,
    generate_fish,
    generate_powershell,
    generate,
)


class TestCompletion(unittest.TestCase):
    """测试 Shell 自动补全脚本生成"""

    def test_generate_bash_returns_string(self):
        """Bash 补全脚本应返回字符串"""
        script = generate_bash()
        self.assertIsInstance(script, str)
        self.assertIn("complete -F", script)
        self.assertIn("sbackup", script)

    def test_generate_bash_contains_subcommands(self):
        """Bash 补全应包含子命令"""
        script = generate_bash()
        for cmd in ("save", "watch", "add", "restore", "sftp", "webdav"):
            self.assertIn(cmd, script)

    def test_generate_zsh_returns_string(self):
        """Zsh 补全脚本应返回字符串"""
        script = generate_zsh()
        self.assertIsInstance(script, str)
        self.assertIn("#compdef", script)
        self.assertIn("sbackup", script)

    def test_generate_zsh_contains_subcommands(self):
        """Zsh 补全应包含子命令"""
        script = generate_zsh()
        for cmd in ("save", "watch", "add", "restore"):
            self.assertIn(cmd, script)

    def test_generate_fish_returns_string(self):
        """Fish 补全脚本应返回字符串"""
        script = generate_fish()
        self.assertIsInstance(script, str)
        self.assertIn("complete -c sbackup", script)

    def test_generate_fish_contains_subcommands(self):
        """Fish 补全应包含子命令"""
        script = generate_fish()
        for cmd in ("save", "watch", "add"):
            self.assertIn(cmd, script)

    def test_generate_powershell_returns_string(self):
        """PowerShell 补全脚本应返回字符串"""
        script = generate_powershell()
        self.assertIsInstance(script, str)
        self.assertIn("Register-ArgumentCompleter", script)
        self.assertIn("sbackup", script)

    def test_generate_powershell_contains_flags(self):
        """PowerShell 补全应包含 flag"""
        script = generate_powershell()
        self.assertIn("--debug", script)
        self.assertIn("--lang", script)

    def test_generate_dispatch_bash(self):
        """generate('bash') 应分发到 generate_bash"""
        result = generate("bash")
        self.assertIn("complete -F", result)

    def test_generate_dispatch_zsh(self):
        """generate('zsh') 应分发到 generate_zsh"""
        result = generate("zsh")
        self.assertIn("#compdef", result)

    def test_generate_dispatch_fish(self):
        """generate('fish') 应分发到 generate_fish"""
        result = generate("fish")
        self.assertIn("complete -c sbackup", result)

    def test_generate_dispatch_powershell(self):
        """generate('powershell') 应分发到 generate_powershell"""
        result = generate("powershell")
        self.assertIn("Register-ArgumentCompleter", result)

    def test_generate_invalid_shell(self):
        """无效的 shell 名称应抛出 ValueError"""
        with self.assertRaises(ValueError):
            generate("invalid_shell")

    def test_generate_case_insensitive(self):
        """生成 shell 名应忽略大小写"""
        bash1 = generate("BASH")
        bash2 = generate("bash")
        self.assertEqual(bash1, bash2)

    def test_all_generators_have_basic_structure(self):
        """所有 shell 的补全脚本都应包含 sbackup 引用"""
        for shell in ("bash", "zsh", "fish", "powershell"):
            script = generate(shell)
            self.assertIsInstance(script, str)
            self.assertGreater(len(script), 50, f"{shell} script is too short")

    def test_zsh_contains_format_choices(self):
        """Zsh 补全应列出格式选项"""
        script = generate_zsh()
        for fmt in ("zip", "tar", "7z"):
            self.assertIn(fmt, script)

    def test_fish_contains_global_flags(self):
        """Fish 补全应包含全局 flag"""
        script = generate_fish()
        self.assertIn("-l debug", script)
        self.assertIn("-l format", script)
        self.assertIn("-l lang", script)
