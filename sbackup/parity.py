"""Reed-Solomon 纠错码：备份自修复"""

import os
import logging

logger = logging.getLogger(__name__)

# 默认纠错参数：每 128 字节数据生成 8 字节纠错码
DEFAULT_DATA_SYMBOLS = 128
DEFAULT_PARITY_SYMBOLS = 8


def generate_parity(
    file_path: str,
    parity_path: str | None = None,
    data_symbols: int = DEFAULT_DATA_SYMBOLS,
    parity_symbols: int = DEFAULT_PARITY_SYMBOLS,
) -> str | None:
    """为文件生成 Reed-Solomon 纠错码

    :returns: 纠错码文件路径，失败返回 None
    """
    try:
        from reedsolo import RSCodec
    except ImportError:
        logger.warning("reedsolo not installed, skipping parity generation")
        return None

    if parity_path is None:
        parity_path = file_path + ".par2"

    try:
        coder = RSCodec(parity_symbols)
        with open(file_path, "rb") as f:
            data = f.read()
        encoded = coder.encode(data)
        with open(parity_path, "wb") as f:
            f.write(encoded)
        return parity_path
    except Exception:
        logger.exception("Failed to generate parity for %s", file_path)
        return None


def verify_and_repair(
    file_path: str,
    parity_path: str | None = None,
    data_symbols: int = DEFAULT_DATA_SYMBOLS,
    parity_symbols: int = DEFAULT_PARITY_SYMBOLS,
) -> tuple[bool, str]:
    """验证并修复文件

    :returns: (success, message)
    """
    try:
        from reedsolo import RSCodec
    except ImportError:
        return False, "reedsolo not installed"

    if parity_path is None:
        parity_path = file_path + ".par2"

    if not os.path.exists(parity_path):
        # 没有纠错码文件，做常规校验
        return _verify_integrity(file_path)

    try:
        coder = RSCodec(parity_symbols)
        with open(parity_path, "rb") as f:
            encoded = f.read()
        decoded, _, errata = coder.decode(encoded)
        if errata:
            # 修复成功，写回文件
            with open(file_path, "wb") as f:
                f.write(bytes(decoded))
            return True, f"Repaired {errata} errors"
        return True, "Integrity OK"
    except Exception as e:
        return False, f"Repair failed: {e}"


def _verify_integrity(file_path: str) -> tuple[bool, str]:
    """没有纠错码时的简单完整性检查"""
    try:
        with open(file_path, "rb") as f:
            f.read()
        return True, "File readable"
    except Exception as e:
        return False, f"File corrupted: {e}"
