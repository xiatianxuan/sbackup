"""系统密钥链集成：跨平台安全存储密码

使用各平台原生 API 将密码存储在系统密钥链中，而不是明文存在 config.json。

支持平台：
  - Windows: Credential Manager (Win32 API 通过 ctypes)
  - macOS: Keychain (security 命令行工具)
  - Linux: libsecret (secret-tool 命令行工具)

用法::

    from sbackup.keychain import get_password, set_password, delete_password

    # 存储密码
    set_password("sbackup", "sftp", "my_secret")

    # 读取密码
    pwd = get_password("sbackup", "sftp")

    # 删除密码
    delete_password("sbackup", "sftp")
"""

import sys
import os
import subprocess
import logging
import json

logger = logging.getLogger(__name__)

SERVICE_NAME = "sbackup"


def get_password(service: str, username: str) -> str | None:
    """从系统密钥链获取密码，返回 None 表示未找到或不可用"""
    try:
        if sys.platform == "win32":
            return _win32_get_password(service, username)
        elif sys.platform == "darwin":
            return _darwin_get_password(service, username)
        else:
            return _linux_get_password(service, username)
    except Exception:
        logger.debug("Keychain get_password failed", exc_info=True)
        return None


def set_password(service: str, username: str, password: str) -> bool:
    """存储密码到系统密钥链，返回是否成功"""
    try:
        if sys.platform == "win32":
            return _win32_set_password(service, username, password)
        elif sys.platform == "darwin":
            return _darwin_set_password(service, username, password)
        else:
            return _linux_set_password(service, username, password)
    except Exception:
        logger.debug("Keychain set_password failed", exc_info=True)
        return False


def delete_password(service: str, username: str) -> bool:
    """从系统密钥链删除密码，返回是否成功"""
    try:
        if sys.platform == "win32":
            return _win32_delete_password(service, username)
        elif sys.platform == "darwin":
            return _darwin_delete_password(service, username)
        else:
            return _linux_delete_password(service, username)
    except Exception:
        logger.debug("Keychain delete_password failed", exc_info=True)
        return False


def is_available() -> bool:
    """检查系统密钥链是否可用"""
    if sys.platform == "win32":
        # Windows Credential Manager 通常总是可用
        try:
            import ctypes
            _win32_get_password("sbackup", "__probe__")
            return True
        except Exception:
            return False
    elif sys.platform == "darwin":
        try:
            subprocess.run(
                ["security", "help"],
                capture_output=True, timeout=5,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    else:
        try:
            subprocess.run(
                ["secret-tool", "--help"],
                capture_output=True, timeout=5,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False


# ─── Windows ─────────────────────────────────────────────────────────

def _win32_get_password(service: str, username: str) -> str | None:
    """使用 Win32 CredReadW API 读取凭据"""
    import ctypes
    from ctypes import wintypes

    advapi32 = ctypes.windll.advapi32

    class CREDENTIALW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", ctypes.c_wchar_p),
            ("Comment", ctypes.c_wchar_p),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.c_void_p),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", ctypes.c_wchar_p),
            ("UserName", ctypes.c_wchar_p),
        ]

    target = f"{service}/{username}"
    pcred = ctypes.POINTER(CREDENTIALW)()

    ret = advapi32.CredReadW(target, 1, 0, ctypes.byref(pcred))
    if not ret:
        return None

    try:
        cred = pcred.contents
        if cred.CredentialBlob and cred.CredentialBlobSize > 0:
            buf = (ctypes.c_char * cred.CredentialBlobSize).from_address(
                cred.CredentialBlob
            )
            return buf.value.decode("utf-16-le")
        return None
    finally:
        advapi32.CredFree(pcred)


def _win32_set_password(service: str, username: str, password: str) -> bool:
    """使用 Win32 CredWriteW API 存储凭据"""
    import ctypes
    from ctypes import wintypes

    advapi32 = ctypes.windll.advapi32

    target = f"{service}/{username}"
    blob = password.encode("utf-16-le")

    class CREDENTIALW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", ctypes.c_wchar_p),
            ("Comment", ctypes.c_wchar_p),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.c_void_p),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", ctypes.c_wchar_p),
            ("UserName", ctypes.c_wchar_p),
        ]

    cred = CREDENTIALW()
    cred.Type = 1  # CRED_TYPE_GENERIC
    cred.TargetName = target
    cred.CredentialBlobSize = len(blob)
    cred.CredentialBlob = ctypes.cast(
        ctypes.create_string_buffer(blob), ctypes.c_void_p
    )
    cred.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE
    cred.UserName = username

    ret = advapi32.CredWriteW(ctypes.byref(cred), 0)
    return bool(ret)


def _win32_delete_password(service: str, username: str) -> bool:
    """使用 Win32 CredDeleteW API 删除凭据"""
    import ctypes

    advapi32 = ctypes.windll.advapi32
    target = f"{service}/{username}"
    ret = advapi32.CredDeleteW(target, 1, 0)
    return bool(ret)


# ─── macOS ───────────────────────────────────────────────────────────

def _darwin_get_password(service: str, username: str) -> str | None:
    """使用 macOS security CLI 读取钥匙串"""
    result = subprocess.run(
        ["security", "find-generic-password",
         "-s", service, "-a", username, "-w"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def _darwin_set_password(service: str, username: str, password: str) -> bool:
    """使用 macOS security CLI 存储到钥匙串"""
    result = subprocess.run(
        ["security", "add-generic-password",
         "-s", service, "-a", username, "-w", password, "-U"],
        capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0


def _darwin_delete_password(service: str, username: str) -> bool:
    """使用 macOS security CLI 从钥匙串删除"""
    result = subprocess.run(
        ["security", "delete-generic-password",
         "-s", service, "-a", username],
        capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0


# ─── Linux ───────────────────────────────────────────────────────────

def _linux_get_password(service: str, username: str) -> str | None:
    """使用 secret-tool 读取密码"""
    result = subprocess.run(
        ["secret-tool", "lookup", "service", service, "username", username],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def _linux_set_password(service: str, username: str, password: str) -> bool:
    """使用 secret-tool 存储密码"""
    result = subprocess.run(
        ["secret-tool", "store",
         "--label", f"sbackup/{username}",
         "service", service, "username", username],
        input=password, text=True, timeout=10,
    )
    return result.returncode == 0


def _linux_delete_password(service: str, username: str) -> bool:
    """使用 secret-tool 删除密码"""
    result = subprocess.run(
        ["secret-tool", "clear", "service", service, "username", username],
        capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0
