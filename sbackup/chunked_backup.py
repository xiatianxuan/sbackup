"""块级增量备份模块

将文件切分为固定大小的块（默认64KB），通过比较 SHA256 哈希
识别变化的块，仅备份变更部分，大幅减少增量备份的数据量。

使用场景：巨量 VM 镜像 / 数据库文件 / 日志文件，每次只改了一小部分。
"""

import os
import hashlib
import struct
import shutil
import logging

logger = logging.getLogger(__name__)

CHUNK_SIZE = 64 * 1024  # 64KB

# 块级增量有三种模式
MODE_DISABLED = ""
MODE_FILE = "file"  # 文件级增量（现有行为）
MODE_BLOCK = "block"  # 块级增量（新）


def compute_chunk_hashes(filepath: str, chunk_size: int = CHUNK_SIZE) -> dict[str, str]:
    """计算文件所有块的哈希，返回 {index_str: sha256}"""
    hashes: dict[str, str] = {}
    with open(filepath, "rb") as f:
        index = 0
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            hashes[str(index)] = hashlib.sha256(data).hexdigest()
            index += 1
    return hashes


def find_changed_chunks(
    filepath: str,
    stored_hashes: dict[str, str],
    chunk_size: int = CHUNK_SIZE,
) -> tuple[set[int], int]:
    """找出变化的块索引集合和总块数。

    :returns: (changed_indices_set, total_chunks)
    """
    current = compute_chunk_hashes(filepath, chunk_size)
    total = len(current)
    changed: set[int] = set()
    for idx_str, current_hash in current.items():
        if stored_hashes.get(idx_str) != current_hash:
            changed.add(int(idx_str))
    # 如果文件变短了，标记缺失的块为变化
    for idx_str in stored_hashes:
        idx = int(idx_str)
        if idx_str not in current:
            changed.add(idx)
    return changed, total


def create_patch(
    filepath: str,
    changed_indices: set[int],
    target_path: str,
    chunk_size: int = CHUNK_SIZE,
) -> int:
    """创建块级补丁文件。

    格式：[chunk_count:int32] [[chunk_index:int32][chunk_size:int32][data:bytes]]*

    :returns: patch 文件字节数，0 表示没有变化
    """
    if not changed_indices:
        return 0

    with open(filepath, "rb") as src, open(target_path, "wb") as dst:
        changed_list = sorted(changed_indices)
        dst.write(struct.pack("<i", len(changed_list)))

        for chunk_idx in changed_list:
            offset = chunk_idx * chunk_size
            src.seek(offset)
            data = src.read(chunk_size)
            dst.write(struct.pack("<ii", chunk_idx, len(data)))
            dst.write(data)

    return os.path.getsize(target_path)


def apply_patch(
    base_path: str,
    patch_path: str,
    output_path: str,
    chunk_size: int = CHUNK_SIZE,
) -> bool:
    """将补丁应用到基准文件，生成还原后的文件。

    对于补丁中包含的块索引，使用补丁中的数据；
    对于补丁中不包含的索引，从基准文件中读取。
    """
    try:
        # 读取补丁中的所有块
        patch_chunks: dict[int, bytes] = {}
        with open(patch_path, "rb") as pf:
            count = struct.unpack("<i", pf.read(4))[0]
            for _ in range(count):
                idx, size = struct.unpack("<ii", pf.read(8))
                data = pf.read(size)
                patch_chunks[idx] = data

        # 从基准文件读取完整内容（按块填充）
        max_index = max(patch_chunks.keys())
        base_size = os.path.getsize(base_path)
        total_chunks = max(max_index + 1, (base_size + chunk_size - 1) // chunk_size)

        with open(output_path, "wb") as out:
            with open(base_path, "rb") as base:
                for idx in range(total_chunks):
                    if idx in patch_chunks:
                        out.write(patch_chunks[idx])
                    else:
                        base.seek(idx * chunk_size)
                        data = base.read(chunk_size)
                        out.write(data)

        return True
    except Exception:
        logger.exception("Failed to apply patch")
        return False


def patch_size_ratio(
    filepath: str,
    changed_indices: set[int],
    chunk_size: int = CHUNK_SIZE,
) -> float:
    """计算变化的块占文件大小的比例"""
    total_size = os.path.getsize(filepath)
    if total_size == 0:
        return 0.0
    changed_size = len(changed_indices) * chunk_size
    return min(changed_size / total_size, 1.0)


def should_do_full_backup(
    filepath: str,
    changed_indices: set[int],
    threshold: float = 0.5,
) -> bool:
    """判断是否应该做全量备份（变化比例超过阈值时回退到全量）"""
    ratio = patch_size_ratio(filepath, changed_indices)
    return ratio >= threshold
