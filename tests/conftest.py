"""全局测试配置：确保工作目录始终有效"""

import os
import tempfile
import pytest

# 启动时保存一个安全的工作目录
_SAFE_CWD = os.getcwd()


@pytest.fixture(autouse=True)
def _restore_cwd():
    """每个测试前后确保 cwd 有效"""
    yield
    try:
        os.getcwd()
    except FileNotFoundError:
        os.chdir(_SAFE_CWD)
