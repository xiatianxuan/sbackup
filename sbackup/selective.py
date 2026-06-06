"""
选择性恢复模块：支持按模式、关键字提取备份包中的指定文件
"""

import os
import tarfile
import tempfile
import zipfile
from fnmatch import fnmatch
from pathlib import Path


def _detect_format(archive_path: str) -> str:
    """根据文件后缀自动检测压缩格式，返回格式标识符"""
    name_lower = archive_path.lower()
    if name_lower.endswith(".zip"):
        return "zip"
    elif name_lower.endswith(".7z"):
        return "7z"
    elif name_lower.endswith(".tar.zst"):
        return "tar.zst"
    elif name_lower.endswith(".tar.gz") or name_lower.endswith(".tgz"):
        return "tar.gz"
    elif name_lower.endswith(".tar.bz2") or name_lower.endswith(".tbz2"):
        return "tar.bz2"
    elif name_lower.endswith(".tar.xz") or name_lower.endswith(".txz"):
        return "tar.xz"
    elif name_lower.endswith(".tar"):
        return "tar"
    return "unknown"


def _get_tar_mode(fmt: str) -> str:
    """将格式标识符转换为 tarfile 打开模式"""
    return {
        "tar": "r",
        "tar.gz": "r:gz",
        "tar.bz2": "r:bz2",
        "tar.xz": "r:xz",
    }.get(fmt, "r")


class SelectiveRestore:
    """选择性恢复工具：支持按模式、关键字从备份包中提取指定文件"""

    def __init__(self, archive_path: str, password: str = ""):
        self.archive_path = archive_path
        self.password = password

    def list_files(self, pattern: str = "") -> list[dict]:
        """列出备份包内文件，可选 glob 过滤

        返回 [{"name": str, "size": int, "is_dir": bool}]
        """
        fmt = _detect_format(self.archive_path)

        if fmt == "zip":
            return self._list_zip(pattern)
        elif fmt == "7z":
            return self._list_7z(pattern)
        elif fmt.startswith("tar"):
            return self._list_tar(pattern, fmt)
        return []

    def _list_zip(self, pattern: str = "") -> list[dict]:
        """列出 ZIP 备份包内文件"""
        results: list[dict] = []
        with zipfile.ZipFile(self.archive_path, "r") as zf:
            for info in zf.infolist():
                name = info.filename
                is_dir = name.endswith("/")
                size = info.file_size if not is_dir else 0
                entry = {"name": name, "size": size, "is_dir": is_dir}
                if pattern:
                    basename = os.path.basename(name.rstrip("/"))
                    if fnmatch(name, pattern) or fnmatch(basename, pattern):
                        results.append(entry)
                else:
                    results.append(entry)
        return results

    def _list_7z(self, pattern: str = "") -> list[dict]:
        """列出 7z 备份包内文件"""
        import py7zr

        results: list[dict] = []
        szf_kwargs: dict = {"file": self.archive_path, "mode": "r"}
        if self.password:
            szf_kwargs["password"] = self.password
        with py7zr.SevenZipFile(**szf_kwargs) as szf:
            all_names = szf.getnames()
            # 获取文件大小信息
            contents = szf.list()
            size_map: dict[str, int] = {}
            for entry in contents:
                size_map[entry.filename] = entry.uncompressed

            for name in all_names:
                is_dir = name.endswith("/")
                size = size_map.get(name, 0) if not is_dir else 0
                entry = {"name": name, "size": size, "is_dir": is_dir}
                if pattern:
                    basename = os.path.basename(name.rstrip("/"))
                    if fnmatch(name, pattern) or fnmatch(basename, pattern):
                        results.append(entry)
                else:
                    results.append(entry)
        return results

    def _list_tar(self, pattern: str = "", fmt: str = "tar") -> list[dict]:
        """列出 tar 系列备份包内文件"""
        mode = _get_tar_mode(fmt)
        results: list[dict] = []
        if fmt == "tar.zst":
            results = self._list_tar_zst(pattern)
        else:
            with tarfile.open(self.archive_path, mode) as tarf:
                for member in tarf.getmembers():
                    name = member.name
                    is_dir = member.isdir()
                    size = member.size if not is_dir else 0
                    entry = {"name": name, "size": size, "is_dir": is_dir}
                    if pattern:
                        basename = os.path.basename(name.rstrip("/"))
                        if fnmatch(name, pattern) or fnmatch(basename, pattern):
                            results.append(entry)
                    else:
                        results.append(entry)
        return results

    def _list_tar_zst(self, pattern: str = "") -> list[dict]:
        """列出 tar.zst 备份包内文件"""
        import zstandard as zstd

        results: list[dict] = []
        dctx = zstd.ZstdDecompressor()
        with tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024) as tmp:
            with open(self.archive_path, "rb") as f_in:
                reader = dctx.stream_reader(f_in)
                while True:
                    chunk = reader.read(65536)
                    if not chunk:
                        break
                    tmp.write(chunk)
            tmp.seek(0)
            with tarfile.open(fileobj=tmp, mode="r") as tarf:
                for member in tarf.getmembers():
                    name = member.name
                    is_dir = member.isdir()
                    size = member.size if not is_dir else 0
                    entry = {"name": name, "size": size, "is_dir": is_dir}
                    if pattern:
                        basename = os.path.basename(name.rstrip("/"))
                        if fnmatch(name, pattern) or fnmatch(basename, pattern):
                            results.append(entry)
                    else:
                        results.append(entry)
        return results

    def search(self, keyword: str) -> list[dict]:
        """按关键字搜索文件名（不区分大小写）"""
        all_files = self.list_files()
        keyword_lower = keyword.lower()
        return [f for f in all_files if keyword_lower in f["name"].lower()]

    def extract_files(
        self, patterns: list[str], target_dir: str
    ) -> tuple[int, list[str]]:
        """提取匹配 patterns 的文件到目标目录

        支持 glob 模式：*.py, src/**/*.txt, data/report.csv
        保留原始目录结构
        返回 (extracted_count, extracted_paths)
        """
        fmt = _detect_format(self.archive_path)
        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)

        # 收集所有匹配的文件名
        all_files = self.list_files()
        matched_names: list[str] = []
        for f in all_files:
            if f["is_dir"]:
                continue
            name = f["name"]
            basename = os.path.basename(name.rstrip("/"))
            for pat in patterns:
                if fnmatch(name, pat) or fnmatch(basename, pat):
                    matched_names.append(name)
                    break

        if not matched_names:
            return 0, []

        if fmt == "zip":
            return self._extract_zip(matched_names, target)
        elif fmt == "7z":
            return self._extract_7z(matched_names, target)
        elif fmt.startswith("tar"):
            return self._extract_tar(matched_names, target, fmt)
        return 0, []

    def _extract_zip(self, names: list[str], target: Path) -> tuple[int, list[str]]:
        """从 ZIP 中提取指定文件"""
        extracted: list[str] = []
        with zipfile.ZipFile(self.archive_path, "r") as zf:
            for name in names:
                try:
                    zf.extract(name, target)
                    extracted.append(str(target / name))
                except (KeyError, OSError):
                    continue
        return len(extracted), extracted

    def _extract_7z(self, names: list[str], target: Path) -> tuple[int, list[str]]:
        """从 7z 中提取指定文件"""
        import py7zr

        extracted: list[str] = []
        szf_kwargs: dict = {"file": self.archive_path, "mode": "r"}
        if self.password:
            szf_kwargs["password"] = self.password
        with py7zr.SevenZipFile(**szf_kwargs) as szf:
            szf.extract(path=target, targets=names)
            for name in names:
                dest = target / name
                if dest.exists():
                    extracted.append(str(dest))
        return len(extracted), extracted

    def _extract_tar(
        self, names: list[str], target: Path, fmt: str
    ) -> tuple[int, list[str]]:
        """从 tar 系列中提取指定文件"""
        extracted: list[str] = []
        name_set = set(names)

        if fmt == "tar.zst":
            return self._extract_tar_zst(names, target)

        mode = _get_tar_mode(fmt)
        with tarfile.open(self.archive_path, mode) as tarf:
            for member in tarf.getmembers():
                if member.name in name_set:
                    try:
                        tarf.extract(member, path=str(target), filter="data")
                        extracted.append(str(target / member.name))
                    except OSError:
                        continue
        return len(extracted), extracted

    def _extract_tar_zst(self, names: list[str], target: Path) -> tuple[int, list[str]]:
        """从 tar.zst 中提取指定文件"""
        import zstandard as zstd

        extracted: list[str] = []
        name_set = set(names)

        dctx = zstd.ZstdDecompressor()
        with tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024) as tmp:
            with open(self.archive_path, "rb") as f_in:
                reader = dctx.stream_reader(f_in)
                while True:
                    chunk = reader.read(65536)
                    if not chunk:
                        break
                    tmp.write(chunk)
            tmp.seek(0)
            with tarfile.open(fileobj=tmp, mode="r") as tarf:
                for member in tarf.getmembers():
                    if member.name in name_set:
                        try:
                            tarf.extract(member, path=str(target), filter="data")
                            extracted.append(str(target / member.name))
                        except OSError:
                            continue
        return len(extracted), extracted

    def extract_single(self, member_name: str, target_dir: str) -> str | None:
        """提取单个文件，返回提取后的路径"""
        result, paths = self.extract_files([member_name], target_dir)
        if result > 0 and paths:
            return paths[0]
        return None

    def get_stats(self) -> dict:
        """获取备份包统计信息

        返回 {"total_files": int, "total_dirs": int, "total_size": int, "formats": dict}
        """
        all_files = self.list_files()
        total_files = 0
        total_dirs = 0
        total_size = 0

        ext_count: dict[str, int] = {}
        for f in all_files:
            if f["is_dir"]:
                total_dirs += 1
            else:
                total_files += 1
                total_size += f["size"]
                # 统计扩展名
                basename = os.path.basename(f["name"])
                ext = os.path.splitext(basename)[1].lower() or "(no ext)"
                ext_count[ext] = ext_count.get(ext, 0) + 1

        return {
            "total_files": total_files,
            "total_dirs": total_dirs,
            "total_size": total_size,
            "formats": ext_count,
        }
