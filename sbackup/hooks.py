"""
Pre/Post Backup Hook 执行模块

提供 HookResult 数据类和 HookRunner 类，用于在备份前后执行用户自定义命令。
"""

import sys
import time
import logging
import subprocess
import shlex
from dataclasses import dataclass

from sbackup.i18n import t

logger = logging.getLogger(__name__)


@dataclass
class HookResult:
    """单个 hook 命令的执行结果"""

    hook_type: str  # "pre" or "post"
    command: str
    return_code: int | None  # None if timeout
    stdout: str
    stderr: str
    success: bool
    duration: float  # seconds
    timed_out: bool = False


class HookRunner:
    """执行 pre/post backup hooks 的运行器"""

    def __init__(
        self,
        pre_hooks: list[str] | None = None,
        post_hooks: list[str] | None = None,
        timeout: int = 300,
    ):
        self.pre_hooks = pre_hooks or []
        self.post_hooks = post_hooks or []
        self.timeout = timeout

    def run_hooks(self, hook_type: str) -> list[HookResult]:
        """执行所有 pre 或 post hooks，返回结果列表"""
        hooks = self.pre_hooks if hook_type == "pre" else self.post_hooks
        results: list[HookResult] = []
        for cmd in hooks:
            if not cmd:
                continue
            results.append(self.run_single(cmd, hook_type))
        return results

    def run_pre_hooks(self) -> list[HookResult]:
        """执行所有 pre-hook"""
        return self.run_hooks("pre")

    def run_post_hooks(self) -> list[HookResult]:
        """执行所有 post-hook"""
        return self.run_hooks("post")

    def run_single(self, command: str, hook_type: str) -> HookResult:
        """执行单个 hook 命令"""
        label = f"cmd.hook.{hook_type}_running"
        print(t(label, command=command))

        start = time.monotonic()
        try:
            # 跨平台命令解析
            # posix=True（默认）：剥离引号，各平台行为一致
            # Windows 上 shlex.split 可能对某些命令格式报 ValueError，回退到 [command]
            try:
                args_list = shlex.split(command)
            except ValueError:
                if sys.platform == "win32":
                    args_list = [command]
                else:
                    raise

            result = subprocess.run(
                args_list,
                shell=False,
                timeout=self.timeout,
                capture_output=True,
                text=True,
            )
            duration = time.monotonic() - start
            success = result.returncode == 0

            if not success:
                logger.warning(
                    t("cmd.hook.failed", command=command, error=result.stderr.strip())
                )

            return HookResult(
                hook_type=hook_type,
                command=command,
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                success=success,
                duration=duration,
            )
        except subprocess.TimeoutExpired as e:
            duration = time.monotonic() - start
            logger.warning(t("cmd.hook.failed", command=command, error="timeout"))
            return HookResult(
                hook_type=hook_type,
                command=command,
                return_code=None,
                stdout=e.stdout or "",
                stderr=e.stderr or "",
                success=False,
                duration=duration,
                timed_out=True,
            )
        except Exception as e:
            duration = time.monotonic() - start
            logger.warning(t("cmd.hook.failed", command=command, error=str(e)))
            return HookResult(
                hook_type=hook_type,
                command=command,
                return_code=None,
                stdout="",
                stderr=str(e),
                success=False,
                duration=duration,
            )

    def format_results(self, results: list[HookResult], lang: str = "zh_CN") -> str:
        """格式化 hook 执行结果"""
        if not results:
            return t("cmd.hooks.no_results")

        lines: list[str] = []
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count

        for r in results:
            status_icon = "ok" if r.success else "FAIL"
            if r.timed_out:
                status_icon = "TIMEOUT"
            line = t(
                "cmd.hooks.result_line",
                status=status_icon,
                command=r.command,
                duration=f"{r.duration:.1f}",
                return_code=str(r.return_code) if r.return_code is not None else "N/A",
            )
            lines.append(line)
            if r.stderr.strip():
                for err_line in r.stderr.strip().splitlines():
                    lines.append(f"  stderr: {err_line}")

        lines.append(
            t(
                "cmd.hooks.summary",
                total=len(results),
                success=success_count,
                fail=fail_count,
            )
        )
        return "\n".join(lines)
