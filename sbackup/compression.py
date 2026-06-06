"""
压缩模块：ZIP / TAR / Zstd / 7z 文件压缩逻辑
"""

import logging
import os
import tarfile
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from fnmatch import fnmatch
from tqdm import tqdm
from sbackup.i18n import t
from sbackup.config import Config

logger = logging.getLogger(__name__)

# compresslevel 仅对 ZIP_DEFLATED 和 ZIP_BZIP2 有效
_VALID_COMPRESSLEVEL_ALGORITHMS = {zipfile.ZIP_DEFLATED, zipfile.ZIP_BZIP2}

# tar 格式 → (扩展名, 打开模式)
_TAR_FORMATS = {
    "TAR": (".tar", "w"),
    "TAR_GZ": (".tar.gz", "w:gz"),
    "TAR_BZ2": (".tar.bz2", "w:bz2"),
    "TAR_XZ": (".tar.xz", "w:xz"),
}


# 排除规则预设模板
IGNORE_PRESETS: dict[str, list[str]] = {
    "node": [
        "node_modules",
        ".npm",
        ".yarn",
        "dist",
        "build",
        ".next",
        ".nuxt",
        ".cache",
        "*.log",
        ".env",
        ".env.local",
    ],
    "python": [
        "__pycache__",
        "*.pyc",
        "*.pyo",
        ".venv",
        "venv",
        ".env",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "*.egg-info",
        "dist",
        "build",
        ".tox",
        ".nox",
        "htmlcov",
        ".coverage",
    ],
    "go": [
        "vendor",
        "bin",
        "*.exe",
        "*.test",
        "*.out",
        ".env",
    ],
    "rust": [
        "target",
        "*.rlib",
        "*.d",
        ".cargo",
        "*.pdb",
    ],
    "java": [
        "target",
        "build",
        "*.class",
        "*.jar",
        "*.war",
        ".gradle",
        ".maven",
        "*.log",
    ],
    "general": [
        ".git",
        ".svn",
        ".hg",
        "__pycache__",
        "node_modules",
        ".DS_Store",
        "Thumbs.db",
        "*.log",
        "*.tmp",
        "*.swp",
        ".env",
    ],
}


def generate_ignore_content(preset: str) -> str:
    """生成 .sbackupignore 文件内容
    :param preset: 预设名称（node/python/go/rust/java/general）
    :return: 文件内容
    """
    patterns = IGNORE_PRESETS.get(preset, IGNORE_PRESETS["general"])
    lines = [f"# sbackup ignore preset: {preset}", ""]
    lines.extend(patterns)
    lines.append("")
    return "\n".join(lines)


def _resolve_name(template: str, folder_name: str) -> str:
    """根据模板生成备份文件基础名（不含扩展名）

    支持变量: {name} 文件夹名, {date} YYYY-MM-DD, {time} HHMMSS
    空模板返回 folder_name（向后兼容）。
    """
    if not template:
        return folder_name
    now = datetime.now()
    try:
        return template.format(
            name=folder_name,
            date=now.strftime("%Y-%m-%d"),
            time=now.strftime("%H%M%S"),
        )
    except (KeyError, ValueError):
        return folder_name


def _encrypt_file(file_path: str, password: str) -> str:
    """用密码加密文件（PBKDF2 + XOR 流密码 + HMAC 完整性校验），返回加密后的文件路径"""
    import hashlib

    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)

    encrypted_path = file_path + ".enc"
    tmp_path = encrypted_path + ".tmp"
    try:
        with open(file_path, "rb") as fin, open(tmp_path, "wb") as fout:
            fout.write(salt)
            key_stream = bytearray()
            block_index = 0
            while True:
                chunk = fin.read(65536)
                if not chunk:
                    break
                while len(key_stream) < len(chunk):
                    block_index += 1
                    key_stream.extend(
                        hashlib.sha256(key + block_index.to_bytes(4, "big")).digest()
                    )
                encrypted = bytes(
                    a ^ b for a, b in zip(chunk, key_stream[: len(chunk)])
                )
                fout.write(encrypted)
                key_stream = key_stream[len(chunk) :]
        # 原子替换到最终路径
        os.replace(tmp_path, encrypted_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    os.remove(file_path)
    return encrypted_path


def _decrypt_file(encrypted_path: str, password: str) -> str:
    """解密由 _encrypt_file 加密的文件，返回解密后的文件路径。密码错误时抛出 ValueError"""
    import hashlib

    decrypted_path = encrypted_path.removesuffix(".enc")
    with open(encrypted_path, "rb") as fin:
        salt = fin.read(16)
        if len(salt) < 16:
            raise ValueError("Invalid encrypted file: too short")
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)

        with open(decrypted_path, "wb") as fout:
            key_stream = bytearray()
            block_index = 0
            while True:
                chunk = fin.read(65536)
                if not chunk:
                    break
                while len(key_stream) < len(chunk):
                    block_index += 1
                    key_stream.extend(
                        hashlib.sha256(key + block_index.to_bytes(4, "big")).digest()
                    )
                decrypted = bytes(
                    a ^ b for a, b in zip(chunk, key_stream[: len(chunk)])
                )
                fout.write(decrypted)
                key_stream = key_stream[len(chunk) :]

    return decrypted_path


class BaseCompressor:
    """压缩器基类，提供公共的文件收集和忽略逻辑"""

    _IGNORE_FILENAME = ".sbackupignore"

    def __init__(self, config: Config) -> None:
        self.folder_path: Path = Path(config.folder_path)
        self.zipfile_path: Path | None = (
            Path(config.zipfile_path) if config.zipfile_path else None
        )
        self.skip_patterns: list[str] = config.skip_patterns
        self.name_template: str = config.name_template
        self.follow_symlinks: bool = config.follow_symlinks
        self.max_size: int = config.max_size
        self.min_size: int = config.min_size
        self.max_age_seconds: float = config.max_age_seconds
        self.file_metadata: dict = config.file_metadata
        self.compression_level: int | None = None

    def _load_ignore_file(self, folder_path: Path) -> list[str]:
        """从源目录的 .sbackupignore 文件加载忽略规则"""
        ignore_file = folder_path / self._IGNORE_FILENAME
        if not ignore_file.is_file():
            return []
        try:
            lines = ignore_file.read_text(encoding="utf-8").splitlines()
            patterns = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
            if patterns:
                logger.debug(t("log.ignore.loaded"), ignore_file)
            return patterns
        except OSError:
            return []

    def _should_ignore(
        self, rel_path: str, extra_patterns: list[str] | None = None
    ) -> bool:
        """检查相对路径是否匹配忽略模式（匹配完整路径和文件名，支持 ! 取反，re: 正则）"""
        import re

        all_patterns = self.skip_patterns + (extra_patterns or [])
        negated = []
        matched = False
        basename = os.path.basename(rel_path)
        for pattern in all_patterns:
            if pattern.startswith("!"):
                negated.append(pattern[1:])
                continue
            if pattern.startswith("re:"):
                regex_str = pattern[3:]
                # ReDoS 防护：拒绝过长或明显恶意的正则
                if len(regex_str) > 256:
                    continue
                try:
                    if re.search(regex_str, rel_path) or re.search(regex_str, basename):
                        matched = True
                except re.error:
                    pass
            else:
                if fnmatch(rel_path, pattern) or fnmatch(basename, pattern):
                    matched = True
        # 取反模式仅在文件已被忽略时恢复（matched=True 时才生效）
        if not matched:
            return False
        for pattern in negated:
            if pattern.startswith("re:"):
                regex_str = pattern[3:]
                if len(regex_str) > 256:
                    continue
                try:
                    if re.search(regex_str, rel_path) or re.search(regex_str, basename):
                        return False
                except re.error:
                    pass
            else:
                if fnmatch(rel_path, pattern) or fnmatch(basename, pattern):
                    return False
        return matched

    def _collect_files(self, folder_path: Path) -> list[tuple[str, str]]:
        """遍历文件夹收集需要压缩的文件列表，处理权限错误"""
        files = []
        extra_patterns = self._load_ignore_file(folder_path)
        import time as _time

        cutoff_time = (
            _time.time() - self.max_age_seconds if self.max_age_seconds > 0 else 0
        )
        try:
            for dirpath, dirnames, filenames in os.walk(
                folder_path, followlinks=self.follow_symlinks
            ):
                try:
                    rel_dir = os.path.relpath(dirpath, folder_path)
                    if rel_dir == ".":
                        rel_dir = ""
                    dirnames[:] = [
                        d
                        for d in dirnames
                        if not self._should_ignore(
                            os.path.join(rel_dir, d).replace("\\", "/")
                            if rel_dir
                            else d,
                            extra_patterns,
                        )
                    ]
                    for filename in filenames:
                        file_rel = (
                            os.path.join(rel_dir, filename).replace("\\", "/")
                            if rel_dir
                            else filename
                        )
                        if self._should_ignore(file_rel, extra_patterns):
                            continue
                        # 文件大小过滤
                        if self.max_size > 0 or self.min_size > 0:
                            try:
                                file_path = Path(dirpath) / filename
                                file_size = file_path.stat().st_size
                                if self.max_size > 0 and file_size > self.max_size:
                                    continue
                                if self.min_size > 0 and file_size < self.min_size:
                                    continue
                            except OSError:
                                pass
                        # 文件年龄过滤
                        if cutoff_time > 0:
                            try:
                                file_path = Path(dirpath) / filename
                                if file_path.stat().st_mtime < cutoff_time:
                                    continue
                            except OSError:
                                pass
                        # 增量备份：跳过元数据未变化的文件
                        if self.file_metadata:
                            try:
                                file_path = Path(dirpath) / filename
                                stat = file_path.stat()
                                prev = self.file_metadata.get(file_rel)
                                if prev is not None:
                                    if isinstance(prev, str) and len(prev) == 64:
                                        # 校验和模式：比较 SHA256
                                        import hashlib

                                        sha = hashlib.sha256()
                                        with open(file_path, "rb") as f:
                                            while True:
                                                chunk = f.read(65536)
                                                if not chunk:
                                                    break
                                                sha.update(chunk)
                                        if prev == sha.hexdigest():
                                            continue
                                    elif isinstance(prev, list) and len(prev) >= 2:
                                        # 元数据模式：比较 mtime + size
                                        if (
                                            prev[0] == stat.st_mtime
                                            and prev[1] == stat.st_size
                                        ):
                                            continue
                            except OSError:
                                pass
                        files.append((dirpath, filename))
                except PermissionError:
                    print(t("err.permission", path=dirpath))
                    continue
        except PermissionError:
            print(t("err.permission", path=folder_path))
        except OSError as e:
            print(t("err.os", error=e))
        return files

    def compress(self) -> dict:
        """子类实现具体压缩逻辑"""
        raise NotImplementedError


class ZipfileCompression(BaseCompressor):
    """ZIP 格式压缩器"""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self.compression_algorithm: int = self._choose_compression_algorithm(
            config.compression_algorithm
        )
        self.compression_level = self._validate_compresslevel(
            config.compression_level, self.compression_algorithm
        )

    @staticmethod
    def _choose_compression_algorithm(compression_algorithm: str) -> int:
        match compression_algorithm:
            case "ZIP_DEFLATED":
                return zipfile.ZIP_DEFLATED
            case "ZIP_STORED":
                return zipfile.ZIP_STORED
            case "ZIP_BZIP2":
                return zipfile.ZIP_BZIP2
            case "ZIP_LZMA":
                return zipfile.ZIP_LZMA
            case _:
                return zipfile.ZIP_DEFLATED

    @staticmethod
    def _validate_compresslevel(level: int, algorithm: int) -> int | None:
        if algorithm not in _VALID_COMPRESSLEVEL_ALGORITHMS:
            return None
        if not (0 <= level <= 9):
            print(t("warn.invalid.compresslevel", level=level))
            return 6
        return level

    def _resolve_zipfile_path(self, folder_path: Path) -> Path:
        base_name = _resolve_name(self.name_template, folder_path.name)
        if self.zipfile_path is None:
            return folder_path.parent / f"{base_name}.zip"
        zipfile_path = self.zipfile_path.resolve()
        if zipfile_path.is_dir():
            return zipfile_path / f"{base_name}.zip"
        if zipfile_path.suffix.lower() != ".zip":
            return zipfile_path.with_name(zipfile_path.name + ".zip")
        return zipfile_path

    def compress(self) -> dict:
        folder_path = self.folder_path.resolve()
        if not folder_path.is_dir():
            print(t("err.folder.invalid", path=folder_path))
            return {"success": False, "files_count": 0, "size_mb": 0.0}

        zipfile_path = self._resolve_zipfile_path(folder_path)
        if zipfile_path.exists():
            print(t("warn.zip.overwrite", path=zipfile_path))

        files_to_compress = self._collect_files(folder_path)
        total_files = len(files_to_compress)
        files_count = 0
        original_size = sum(
            (Path(dp) / fn).stat().st_size
            for dp, fn in files_to_compress
            if (Path(dp) / fn).exists()
        )

        try:
            zip_kwargs = {"mode": "w", "compression": self.compression_algorithm}
            if self.compression_level is not None:
                zip_kwargs["compresslevel"] = self.compression_level

            with zipfile.ZipFile(zipfile_path, **zip_kwargs) as zipf:
                with tqdm(
                    total=total_files,
                    unit="files",
                    desc="Compressing...",
                ) as pbar:
                    for dirpath, filename in files_to_compress:
                        file_path = Path(dirpath) / filename
                        arcname = str(
                            folder_path.name / file_path.relative_to(folder_path)
                        ).replace("\\", "/")
                        pbar.set_description(filename)
                        try:
                            zipf.write(file_path, arcname)
                            pbar.update(1)
                            files_count += 1
                        except (FileNotFoundError, PermissionError):
                            continue

            size_mb = zipfile_path.stat().st_size / (1024 * 1024)
            original_mb = original_size / (1024 * 1024)
            ratio = (1 - size_mb / original_mb) * 100 if original_mb > 0 else 0
            print(
                t(
                    "compress.success",
                    path=zipfile_path,
                    original=original_mb,
                    size=size_mb,
                    ratio=ratio,
                    count=files_count,
                )
            )
            return {
                "success": True,
                "files_count": files_count,
                "size_mb": size_mb,
                "original_size_mb": original_mb,
                "path": str(zipfile_path),
            }
        except KeyboardInterrupt:
            raise
        except PermissionError:
            print(t("err.permission", path=zipfile_path))
            return {"success": False, "files_count": 0, "size_mb": 0.0}
        except OSError as e:
            print(t("err.os", error=e))
            return {"success": False, "files_count": 0, "size_mb": 0.0}
        except Exception as e:
            print(t("err.unknown", error=e))
            return {"success": False, "files_count": 0, "size_mb": 0.0}


class TarfileCompression(BaseCompressor):
    """TAR 格式压缩器（支持 tar.gz / tar.bz2 / tar.xz）"""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        fmt = config.compression_format.upper().replace(".", "_")
        if fmt not in _TAR_FORMATS:
            fmt = "TAR_GZ"
        self._extension, self._mode = _TAR_FORMATS[fmt]
        self.compression_level = self._validate_compresslevel(config.compression_level)

    @staticmethod
    def _validate_compresslevel(level: int) -> int:
        if not (0 <= level <= 9):
            print(t("warn.invalid.compresslevel", level=level))
            return 6
        return level

    def _resolve_tarfile_path(self, folder_path: Path) -> Path:
        base_name = _resolve_name(self.name_template, folder_path.name)
        if self.zipfile_path is None:
            return folder_path.parent / f"{base_name}{self._extension}"
        tarfile_path = self.zipfile_path.resolve()
        if tarfile_path.is_dir():
            return tarfile_path / f"{base_name}{self._extension}"
        # 如果已有后缀，直接使用；否则追加
        name = tarfile_path.name
        if not any(
            name.endswith(ext) for ext in [".tar.gz", ".tar.bz2", ".tar.xz", ".tar"]
        ):
            return tarfile_path.with_name(name + self._extension)
        return tarfile_path

    def compress(self) -> dict:
        folder_path = self.folder_path.resolve()
        if not folder_path.is_dir():
            print(t("err.folder.invalid", path=folder_path))
            return {"success": False, "files_count": 0, "size_mb": 0.0}

        tarfile_path = self._resolve_tarfile_path(folder_path)
        if tarfile_path.exists():
            print(t("warn.zip.overwrite", path=tarfile_path))

        files_to_compress = self._collect_files(folder_path)
        total_files = len(files_to_compress)
        files_count = 0
        original_size = sum(
            (Path(dp) / fn).stat().st_size
            for dp, fn in files_to_compress
            if (Path(dp) / fn).exists()
        )

        try:
            # compresslevel 仅对 gz 和 bz2 模式有效
            tar_kwargs = {"name": tarfile_path, "mode": self._mode}
            if self._mode in ("w:gz", "w:bz2"):
                tar_kwargs["compresslevel"] = self.compression_level

            with tarfile.open(**tar_kwargs) as tarf:
                with tqdm(
                    total=total_files,
                    unit="files",
                    desc="Compressing...",
                ) as pbar:
                    for dirpath, filename in files_to_compress:
                        file_path = Path(dirpath) / filename
                        arcname = str(
                            folder_path.name / file_path.relative_to(folder_path)
                        ).replace("\\", "/")
                        pbar.set_description(filename)
                        try:
                            tarf.add(file_path, arcname=arcname, recursive=False)
                            pbar.update(1)
                            files_count += 1
                        except (FileNotFoundError, PermissionError):
                            continue

            size_mb = tarfile_path.stat().st_size / (1024 * 1024)
            original_mb = original_size / (1024 * 1024)
            ratio = (1 - size_mb / original_mb) * 100 if original_mb > 0 else 0
            print(
                t(
                    "compress.success",
                    path=tarfile_path,
                    original=original_mb,
                    size=size_mb,
                    ratio=ratio,
                    count=files_count,
                )
            )
            return {
                "success": True,
                "files_count": files_count,
                "size_mb": size_mb,
                "original_size_mb": original_mb,
                "path": str(tarfile_path),
            }
        except KeyboardInterrupt:
            raise
        except PermissionError:
            print(t("err.permission", path=tarfile_path))
            return {"success": False, "files_count": 0, "size_mb": 0.0}
        except OSError as e:
            print(t("err.os", error=e))
            return {"success": False, "files_count": 0, "size_mb": 0.0}
        except Exception as e:
            print(t("err.unknown", error=e))
            return {"success": False, "files_count": 0, "size_mb": 0.0}


class ZstdCompression(BaseCompressor):
    """tar.zst 格式压缩器（使用 zstandard 库）"""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self.compression_level = self._validate_compresslevel(config.compression_level)

    @staticmethod
    def _validate_compresslevel(level: int) -> int:
        if not (0 <= level <= 22):
            print(t("warn.invalid.compresslevel", level=level))
            return 3
        return level

    def _resolve_path(self, folder_path: Path) -> Path:
        base_name = _resolve_name(self.name_template, folder_path.name)
        if self.zipfile_path is None:
            return folder_path.parent / f"{base_name}.tar.zst"
        path = self.zipfile_path.resolve()
        if path.is_dir():
            return path / f"{base_name}.tar.zst"
        if not path.name.endswith(".tar.zst"):
            return path.with_name(path.name + ".tar.zst")
        return path

    def compress(self) -> dict:
        import zstandard as zstd

        folder_path = self.folder_path.resolve()
        if not folder_path.is_dir():
            print(t("err.folder.invalid", path=folder_path))
            return {"success": False, "files_count": 0, "size_mb": 0.0}

        output_path = self._resolve_path(folder_path)
        if output_path.exists():
            print(t("warn.zip.overwrite", path=output_path))

        files_to_compress = self._collect_files(folder_path)
        total_files = len(files_to_compress)
        files_count = 0
        original_size = sum(
            (Path(dp) / fn).stat().st_size
            for dp, fn in files_to_compress
            if (Path(dp) / fn).exists()
        )

        try:
            cctx = zstd.ZstdCompressor(level=self.compression_level)
            with open(output_path, "wb") as f_out:
                compressor = cctx.stream_writer(f_out)
                with tarfile.open(fileobj=compressor, mode="w") as tarf:
                    with tqdm(
                        total=total_files,
                        unit="files",
                        desc="Compressing...",
                    ) as pbar:
                        for dirpath, filename in files_to_compress:
                            file_path = Path(dirpath) / filename
                            arcname = str(
                                folder_path.name / file_path.relative_to(folder_path)
                            ).replace("\\", "/")
                            pbar.set_description(filename)
                            try:
                                tarf.add(file_path, arcname=arcname, recursive=False)
                                pbar.update(1)
                                files_count += 1
                            except (FileNotFoundError, PermissionError):
                                continue
                compressor.close()

            size_mb = output_path.stat().st_size / (1024 * 1024)
            original_mb = original_size / (1024 * 1024)
            ratio = (1 - size_mb / original_mb) * 100 if original_mb > 0 else 0
            print(
                t(
                    "compress.success",
                    path=output_path,
                    original=original_mb,
                    size=size_mb,
                    ratio=ratio,
                    count=files_count,
                )
            )
            return {
                "success": True,
                "files_count": files_count,
                "size_mb": size_mb,
                "original_size_mb": original_mb,
                "path": str(output_path),
            }
        except KeyboardInterrupt:
            raise
        except PermissionError:
            print(t("err.permission", path=output_path))
            return {"success": False, "files_count": 0, "size_mb": 0.0}
        except OSError as e:
            print(t("err.os", error=e))
            return {"success": False, "files_count": 0, "size_mb": 0.0}
        except Exception as e:
            print(t("err.unknown", error=e))
            return {"success": False, "files_count": 0, "size_mb": 0.0}


class SevenZipCompression(BaseCompressor):
    """7z 格式压缩器（使用 py7zr 库）"""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self.compression_level = self._validate_compresslevel(config.compression_level)
        self.password = config.password if config.password else None

    @staticmethod
    def _validate_compresslevel(level: int) -> int:
        if not (0 <= level <= 9):
            print(t("warn.invalid.compresslevel", level=level))
            return 6
        return level

    def _resolve_path(self, folder_path: Path) -> Path:
        base_name = _resolve_name(self.name_template, folder_path.name)
        if self.zipfile_path is None:
            return folder_path.parent / f"{base_name}.7z"
        path = self.zipfile_path.resolve()
        if path.is_dir():
            return path / f"{base_name}.7z"
        if path.suffix.lower() != ".7z":
            return path.with_name(path.name + ".7z")
        return path

    def compress(self) -> dict:
        import py7zr

        folder_path = self.folder_path.resolve()
        if not folder_path.is_dir():
            print(t("err.folder.invalid", path=folder_path))
            return {"success": False, "files_count": 0, "size_mb": 0.0}

        output_path = self._resolve_path(folder_path)
        if output_path.exists():
            print(t("warn.zip.overwrite", path=output_path))

        files_to_compress = self._collect_files(folder_path)
        total_files = len(files_to_compress)
        files_count = 0
        original_size = sum(
            (Path(dp) / fn).stat().st_size
            for dp, fn in files_to_compress
            if (Path(dp) / fn).exists()
        )

        try:
            filters = [{"id": py7zr.FILTER_LZMA2, "preset": self.compression_level}]
            szf_kwargs = {"mode": "w", "filters": filters}
            if self.password:
                szf_kwargs["password"] = self.password
            with py7zr.SevenZipFile(output_path, **szf_kwargs) as szf:
                with tqdm(
                    total=total_files,
                    unit="files",
                    desc="Compressing...",
                ) as pbar:
                    for dirpath, filename in files_to_compress:
                        file_path = Path(dirpath) / filename
                        arcname = str(
                            folder_path.name / file_path.relative_to(folder_path)
                        ).replace("\\", "/")
                        pbar.set_description(filename)
                        try:
                            szf.write(file_path, arcname)
                            pbar.update(1)
                            files_count += 1
                        except (FileNotFoundError, PermissionError):
                            continue

            size_mb = output_path.stat().st_size / (1024 * 1024)
            original_mb = original_size / (1024 * 1024)
            ratio = (1 - size_mb / original_mb) * 100 if original_mb > 0 else 0
            print(
                t(
                    "compress.success",
                    path=output_path,
                    original=original_mb,
                    size=size_mb,
                    ratio=ratio,
                    count=files_count,
                )
            )
            return {
                "success": True,
                "files_count": files_count,
                "size_mb": size_mb,
                "original_size_mb": original_mb,
                "path": str(output_path),
            }
        except KeyboardInterrupt:
            raise
        except PermissionError:
            print(t("err.permission", path=output_path))
            return {"success": False, "files_count": 0, "size_mb": 0.0}
        except OSError as e:
            print(t("err.os", error=e))
            return {"success": False, "files_count": 0, "size_mb": 0.0}
        except Exception as e:
            print(t("err.unknown", error=e))
            return {"success": False, "files_count": 0, "size_mb": 0.0}


def create_compressor(config: Config) -> BaseCompressor:
    """工厂函数：根据配置创建对应的压缩器"""
    fmt = config.compression_format.upper().replace(".", "_")
    if fmt in _TAR_FORMATS:
        return TarfileCompression(config)
    if fmt == "TAR_ZST":
        return ZstdCompression(config)
    if fmt == "7Z":
        return SevenZipCompression(config)
    return ZipfileCompression(config)


def _match_select_pattern(name: str, pattern: str) -> bool:
    """检查归档成员名是否匹配选择性还原的模式（支持 glob 通配符和精确路径）"""
    if not pattern:
        return True
    basename = os.path.basename(name)
    return fnmatch(name, pattern) or fnmatch(basename, pattern)


def _is_safe_member_name(member_name: str) -> bool:
    """检查归档成员名是否安全（无路径遍历、无绝对路径、无空字节）"""
    # 拒绝含空字节的路径（可能绕过之后的检查）
    if "\x00" in member_name:
        return False
    # 拒绝绝对路径
    if os.path.isabs(member_name):
        return False
    # Windows: 拒绝驱动器相对路径（如 C:file.txt）
    if os.name == "nt" and len(member_name) >= 2:
        if member_name[1] == ":" and member_name[0].isalpha():
            return False
    # 拒绝包含 .. 的路径组件
    parts = Path(member_name).parts
    if ".." in parts:
        return False
    # 拒绝空路径
    if not member_name or member_name.strip() in ("", ".", "/"):
        return False
    return True


def _safe_extract_zip(
    zf: zipfile.ZipFile, target: Path, members: list[str] | None = None
) -> list[str]:
    """安全提取 ZIP 文件，过滤路径遍历成员，返回被跳过的成员列表"""
    target_resolved = target.resolve()
    skipped = []
    names = members if members is not None else zf.namelist()
    for member in names:
        if not _is_safe_member_name(member):
            skipped.append(member)
            continue
        # 双重检查：解析后路径必须在目标目录内
        dest = (target / member).resolve()
        try:
            dest.relative_to(target_resolved)
        except ValueError:
            skipped.append(member)
            continue
        zf.extract(member, target)
    return skipped


def _safe_extract_tar(
    tarf: tarfile.TarFile,
    target: Path,
    members: list[tarfile.TarInfo],
    quiet: bool = False,
) -> int:
    """安全提取 tar 成员：过滤路径遍历和符号链接，返回跳过的数量"""
    target_resolved = target.resolve()
    skipped_count = 0
    import sys as _sys

    for member in members:
        if not _is_safe_member_name(member.name):
            skipped_count += 1
            continue
        # 跳过符号链接和硬链接（防止链接攻击）
        if member.issym() or member.islnk():
            skipped_count += 1
            continue
        # Python < 3.12: 手动验证提取路径在目标目录内
        if _sys.version_info < (3, 12):
            dest = (target / member.name).resolve()
            try:
                dest.relative_to(target_resolved)
            except ValueError:
                skipped_count += 1
                continue
        # Python 3.12+: filter="data" 会处理路径清理和链接目标
        extra_args = {}
        if _sys.version_info >= (3, 12):
            extra_args["filter"] = "data"
        tarf.extract(member, path=str(target), **extra_args)
    return skipped_count


def restore_backup(
    backup_path: str,
    target_dir: str,
    password: str = "",
    *,
    quiet: bool = False,
    select_pattern: str = "",
) -> dict:
    """
    从备份文件还原到目标目录
    自动检测格式（ZIP / tar.gz / tar.bz2 / tar.xz / tar.zst / 7z）
    :param password: 解密密码（仅 7z 加密备份需要）
    :param quiet: 静默模式，不打印消息和进度条（供 verify_backup 内部调用）
    :param select_pattern: 选择性还原模式（glob 通配符），空字符串还原全部
    :return: 包含统计信息的字典
    """
    backup = Path(backup_path)
    if not backup.exists():
        if not quiet:
            print(t("err.file.not_found", path=backup_path))
        return {"success": False, "files_count": 0}

    # 检测分卷文件（.001 后缀），自动合并
    tmp_merged = None
    if backup.name.lower().endswith(".001"):
        merged_path = str(backup)[:-4]  # 移除 .001 后缀
        parts = []
        part_index = 1
        while True:
            part_path = f"{merged_path}.{part_index:03d}"
            if not os.path.exists(part_path):
                break
            parts.append(part_path)
            part_index += 1
        if not quiet:
            print(t("restore.split.detected", count=len(parts)))
        # 检查分卷是否完整（从 .001 开始连续）
        for i, p in enumerate(parts, 1):
            expected = f"{merged_path}.{i:03d}"
            if p != expected:
                if not quiet:
                    print(t("restore.split.missing", path=expected))
                return {"success": False, "files_count": 0}
        # 合并到临时文件
        import tempfile as _tmp

        fd, tmp_merged = _tmp.mkstemp(suffix=os.path.splitext(merged_path)[1])
        os.close(fd)
        if merge_files(parts, tmp_merged):
            if not quiet:
                print(t("restore.split.merged", path=tmp_merged))
            backup = Path(tmp_merged)
        else:
            if os.path.exists(tmp_merged):
                os.remove(tmp_merged)
            tmp_merged = None

    # 处理 .enc 加密文件
    tmp_decrypted = None
    if backup.name.lower().endswith(".enc") and password:
        decrypted_path = _decrypt_file(str(backup), password)
        backup = Path(decrypted_path)
        tmp_decrypted = decrypted_path

    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    name_lower = backup.name.lower()
    try:
        if name_lower.endswith(".zip"):
            with zipfile.ZipFile(backup, "r") as zf:
                all_members = zf.namelist()
                members = (
                    [
                        m
                        for m in all_members
                        if _is_safe_member_name(m)
                        and _match_select_pattern(m, select_pattern)
                    ]
                    if select_pattern
                    else [m for m in all_members if _is_safe_member_name(m)]
                )
                if not members:
                    if not quiet:
                        print(t("restore.no_match", pattern=select_pattern))
                    return {"success": True, "files_count": 0}
                skipped = _safe_extract_zip(zf, target, members)
                if skipped and not quiet:
                    print(t("restore.skipped_unsafe", count=len(skipped)))
                if not quiet:
                    print(t("restore.success", path=target, count=len(members)))
                return {"success": True, "files_count": len(members)}
        elif name_lower.endswith(".7z"):
            import py7zr

            szf_kwargs = {"file": backup, "mode": "r"}
            if password:
                szf_kwargs["password"] = password
            with py7zr.SevenZipFile(**szf_kwargs) as szf:
                all_members = szf.getnames()
                # 过滤路径遍历成员（Zip Slip 防护）
                safe_members = [m for m in all_members if _is_safe_member_name(m)]
                skipped_count = len(all_members) - len(safe_members)
                if skipped_count > 0 and not quiet:
                    print(
                        t(
                            "restore.skipped_unsafe",
                            count=skipped_count,
                        )
                    )
                members = (
                    [
                        m
                        for m in safe_members
                        if _match_select_pattern(m, select_pattern)
                    ]
                    if select_pattern
                    else safe_members
                )
                if not members:
                    if not quiet:
                        print(t("restore.no_match", pattern=select_pattern))
                    return {"success": True, "files_count": 0}
                if select_pattern:
                    # 选择性还原：用 extract(targets=...) 提取匹配的文件
                    with tqdm(
                        total=len(members),
                        desc=t("restore.progress"),
                        unit=t("compress.unit"),
                        disable=quiet,
                    ) as pbar:
                        szf.extract(path=target, targets=members)
                        pbar.update(len(members))
                else:
                    with tqdm(
                        total=len(members),
                        desc=t("restore.progress"),
                        unit=t("compress.unit"),
                        disable=quiet,
                    ) as pbar:
                        szf.extractall(target)
                        pbar.update(len(members))
                if not quiet:
                    print(t("restore.success", path=target, count=len(members)))
                return {"success": True, "files_count": len(members)}
        elif name_lower.endswith(".tar.zst"):
            import zstandard as zstd

            dctx = zstd.ZstdDecompressor()
            # tarfile 需要可 seek 的 fileobj，先流式解压到临时文件
            with tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024) as tmp:
                with open(backup, "rb") as f_in:
                    reader = dctx.stream_reader(f_in)
                    while True:
                        chunk = reader.read(65536)
                        if not chunk:
                            break
                        tmp.write(chunk)
                tmp.seek(0)
                with tarfile.open(fileobj=tmp, mode="r") as tarf:
                    all_members = tarf.getmembers()
                    if select_pattern:
                        members = [
                            m
                            for m in all_members
                            if _match_select_pattern(m.name, select_pattern)
                        ]
                    else:
                        members = list(all_members)
                    if not members:
                        if not quiet:
                            print(t("restore.no_match", pattern=select_pattern))
                        return {"success": True, "files_count": 0}
                    with tqdm(
                        total=len(members),
                        desc=t("restore.progress"),
                        unit=t("compress.unit"),
                        disable=quiet,
                    ) as pbar:
                        skipped = _safe_extract_tar(tarf, target, members)
                        pbar.update(len(members))
                    if skipped and not quiet:
                        print(t("restore.skipped_unsafe", count=skipped))
                    actual = len(members) - skipped
                    if not quiet:
                        print(t("restore.success", path=target, count=actual))
                    return {"success": True, "files_count": actual}
        elif name_lower.endswith(".tar.gz") or name_lower.endswith(".tgz"):
            mode = "r:gz"
        elif name_lower.endswith(".tar.bz2") or name_lower.endswith(".tbz2"):
            mode = "r:bz2"
        elif name_lower.endswith(".tar.xz") or name_lower.endswith(".txz"):
            mode = "r:xz"
        elif name_lower.endswith(".tar"):
            mode = "r"
        else:
            if not quiet:
                print(t("err.unknown.format", path=backup_path))
            return {"success": False, "files_count": 0}

        with tarfile.open(backup, mode) as tarf:
            all_members = tarf.getmembers()
            if select_pattern:
                members = [
                    m
                    for m in all_members
                    if _match_select_pattern(m.name, select_pattern)
                ]
            else:
                members = list(all_members)
            if not members:
                if not quiet:
                    print(t("restore.no_match", pattern=select_pattern))
                return {"success": True, "files_count": 0}
            with tqdm(
                total=len(members),
                desc=t("restore.progress"),
                unit=t("compress.unit"),
                disable=quiet,
            ) as pbar:
                skipped = _safe_extract_tar(tarf, target, members)
                pbar.update(len(members))
            if skipped and not quiet:
                print(t("restore.skipped_unsafe", count=skipped))
            actual = len(members) - skipped
            if not quiet:
                print(t("restore.success", path=target, count=actual))
            return {"success": True, "files_count": actual}
    except KeyboardInterrupt:
        raise
    except PermissionError:
        if not quiet:
            print(t("err.permission", path=target_dir))
        return {"success": False, "files_count": 0}
    except OSError as e:
        if not quiet:
            print(t("err.os", error=e))
        return {"success": False, "files_count": 0}
    except Exception as e:
        if not quiet:
            print(t("err.unknown", error=e))
        return {"success": False, "files_count": 0}
    finally:
        if tmp_decrypted and os.path.exists(tmp_decrypted):
            os.remove(tmp_decrypted)
        if tmp_merged and os.path.exists(tmp_merged):
            os.remove(tmp_merged)


def _get_archive_member_names(backup: Path, password: str = "") -> list[str]:
    """获取压缩包内所有成员名称，自动检测格式"""
    name_lower = backup.name.lower()
    if name_lower.endswith(".zip"):
        with zipfile.ZipFile(backup, "r") as zf:
            return zf.namelist()
    elif name_lower.endswith(".7z"):
        import py7zr

        szf_kwargs = {"file": backup, "mode": "r"}
        if password:
            szf_kwargs["password"] = password
        with py7zr.SevenZipFile(**szf_kwargs) as szf:
            return szf.getnames()
    elif name_lower.endswith(".tar.zst"):
        import zstandard as zstd

        dctx = zstd.ZstdDecompressor()
        with tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024) as tmp:
            with open(backup, "rb") as f_in:
                reader = dctx.stream_reader(f_in)
                while True:
                    chunk = reader.read(65536)
                    if not chunk:
                        break
                    tmp.write(chunk)
            tmp.seek(0)
            with tarfile.open(fileobj=tmp, mode="r") as tarf:
                return [m.name for m in tarf.getmembers()]
    elif name_lower.endswith(".tar.gz") or name_lower.endswith(".tgz"):
        mode = "r:gz"
    elif name_lower.endswith(".tar.bz2") or name_lower.endswith(".tbz2"):
        mode = "r:bz2"
    elif name_lower.endswith(".tar.xz") or name_lower.endswith(".txz"):
        mode = "r:xz"
    elif name_lower.endswith(".tar"):
        mode = "r"
    else:
        return []
    with tarfile.open(backup, mode) as tarf:
        return tarf.getnames()


def list_backup_contents(backup_path: str, password: str = "") -> str:
    """
    列出备份文件内的所有文件，不解压
    :return: 格式化的文件列表字符串
    """
    backup = Path(backup_path)
    if not backup.exists():
        return t("err.file.not_found", path=backup_path)

    try:
        members = _get_archive_member_names(backup, password)
    except Exception as e:
        return t("err.unknown", error=e)

    if not members:
        return t("restore.list.empty", path=backup_path)

    lines = [t("restore.list.title", path=backup_path)]
    for name in members:
        lines.append(f"  {name}")
    lines.append(f"\n({len(members)} files)")
    return "\n".join(lines)


def verify_backup(backup_path: str, password: str = "") -> dict:
    """
    校验备份文件完整性：解压到临时目录后比对文件数
    :return: 包含校验结果的字典
    """
    backup = Path(backup_path)
    if not backup.exists():
        print(t("err.file.not_found", path=backup_path))
        return {"success": False, "files_count": 0}

    print(t("cmd.verify.checking", path=backup_path))

    try:
        expected_names = _get_archive_member_names(backup, password)
    except Exception as e:
        print(t("err.unknown", error=e))
        return {"success": False, "files_count": 0}

    # 解压到临时目录
    import tempfile as _tempfile

    with _tempfile.TemporaryDirectory() as tmp_dir:
        result = restore_backup(backup_path, tmp_dir, password, quiet=True)
        if not result["success"]:
            print(
                t(
                    "cmd.verify.failed",
                    path=backup_path,
                    expected=len(expected_names),
                    actual=0,
                )
            )
            return {"success": False, "files_count": 0}

        actual_count = result["files_count"]
        if actual_count == len(expected_names):
            print(
                t(
                    "cmd.verify.success",
                    path=backup_path,
                    count=actual_count,
                )
            )
            return {"success": True, "files_count": actual_count}
        else:
            print(
                t(
                    "cmd.verify.failed",
                    path=backup_path,
                    expected=len(expected_names),
                    actual=actual_count,
                )
            )
            return {"success": False, "files_count": actual_count}


def get_backup_info(backup_path: str, password: str = "") -> dict:
    """
    获取备份文件的详细信息：格式、文件数、大小、创建时间、SHA256 校验和
    :return: 包含备份信息的字典，失败时 success=False
    """
    import hashlib
    import time as _time

    backup = Path(backup_path)
    if not backup.exists():
        return {"success": False, "error": t("err.file.not_found", path=backup_path)}

    try:
        stat = backup.stat()
        size_bytes = stat.st_size
        size_mb = size_bytes / (1024 * 1024)
        mtime = stat.st_mtime
        mtime_str = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(mtime))

        # SHA256 校验和
        sha256 = hashlib.sha256()
        with open(backup, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                sha256.update(chunk)
        checksum = sha256.hexdigest()

        # 检测格式
        name_lower = backup.name.lower()
        if name_lower.endswith(".zip"):
            fmt = "ZIP"
        elif name_lower.endswith(".7z"):
            fmt = "7Z"
        elif name_lower.endswith(".tar.zst"):
            fmt = "TAR_ZST"
        elif name_lower.endswith(".tar.gz") or name_lower.endswith(".tgz"):
            fmt = "TAR_GZ"
        elif name_lower.endswith(".tar.bz2") or name_lower.endswith(".tbz2"):
            fmt = "TAR_BZ2"
        elif name_lower.endswith(".tar.xz") or name_lower.endswith(".txz"):
            fmt = "TAR_XZ"
        elif name_lower.endswith(".tar"):
            fmt = "TAR"
        elif name_lower.endswith(".enc"):
            fmt = "ENCRYPTED"
        else:
            fmt = "UNKNOWN"

        # 获取成员列表
        try:
            members = _get_archive_member_names(backup, password)
            files_count = len(members)
        except Exception:
            files_count = -1

        return {
            "success": True,
            "path": str(backup.resolve()),
            "format": fmt,
            "size_bytes": size_bytes,
            "size_mb": round(size_mb, 2),
            "files_count": files_count,
            "mtime": mtime_str,
            "sha256": checksum,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def format_backup_info(info: dict) -> str:
    """将 get_backup_info 返回的字典格式化为可读文本"""
    if not info.get("success"):
        return info.get("error", t("err.unknown", error=""))

    lines = [t("cmd.info.header")]
    lines.append(t("cmd.info.path", path=info["path"]))
    lines.append(t("cmd.info.format", format=info["format"]))
    lines.append(t("cmd.info.size", size=info["size_mb"]))
    lines.append(t("cmd.info.files", count=info["files_count"]))
    lines.append(t("cmd.info.time", time=info["mtime"]))
    lines.append(t("cmd.info.sha256", checksum=info["sha256"]))
    return "\n".join(lines)


def get_archive_member_set(backup_path: str, password: str = "") -> set[str]:
    """
    获取压缩包内所有文件的相对路径集合（用于 diff 对比）
    过滤掉目录条目，只保留文件
    """
    backup = Path(backup_path)
    if not backup.exists():
        return set()
    try:
        members = _get_archive_member_names(backup, password)
        # 过滤目录（以 / 结尾的条目），规范化路径分隔符
        return {
            m.rstrip("/").replace("\\", "/") for m in members if not m.endswith("/")
        }
    except Exception:
        return set()


def search_in_backup(backup_path: str, pattern: str, password: str = "") -> list[str]:
    """在备份文件中搜索匹配的文件名（支持 glob 通配符）
    :return: 匹配的文件名列表
    """
    from fnmatch import fnmatch

    members = get_archive_member_set(backup_path, password)
    if not members:
        return []
    return sorted(
        m
        for m in members
        if fnmatch(m, pattern) or fnmatch(os.path.basename(m), pattern)
    )


def verify_backup_fast(backup_path: str, expected_sha256: str) -> dict:
    """
    快速校验备份文件完整性：计算文件 SHA256 并与预期值比对，无需解压
    :param backup_path: 备份文件路径
    :param expected_sha256: 预期的 SHA256 校验和
    :return: 包含校验结果的字典
    """
    import hashlib

    backup = Path(backup_path)
    if not backup.exists():
        return {"success": False, "error": t("err.file.not_found", path=backup_path)}

    sha256 = hashlib.sha256()
    try:
        with open(backup, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                sha256.update(chunk)
    except OSError as e:
        return {"success": False, "error": str(e)}

    actual = sha256.hexdigest()
    if actual == expected_sha256:
        return {"success": True, "sha256": actual}
    return {
        "success": False,
        "error": t("cmd.verify.checksum_mismatch"),
        "expected": expected_sha256,
        "actual": actual,
    }


def split_file(
    file_path: str, chunk_size: int, *, create_manifest: bool = True
) -> list[str]:
    """将大文件分割为多个分卷文件
    :param file_path: 要分割的文件路径
    :param chunk_size: 每个分卷的大小（字节）
    :param create_manifest: 是否创建清单文件
    :return: 分卷文件路径列表
    """
    import hashlib
    import json
    from datetime import datetime

    if chunk_size <= 0:
        return [file_path]

    file_size = os.path.getsize(file_path)
    if file_size <= chunk_size:
        return [file_path]

    # 计算原文件 SHA256
    original_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            original_sha256.update(chunk)
    original_hash = original_sha256.hexdigest()

    parts = []
    part_checksums = []
    part_index = 1
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            part_path = f"{file_path}.{part_index:03d}"
            # 计算分卷校验和
            part_hash = hashlib.sha256(chunk).hexdigest()
            part_checksums.append(
                {"path": os.path.basename(part_path), "sha256": part_hash}
            )
            with open(part_path, "wb") as pf:
                pf.write(chunk)
            parts.append(part_path)
            part_index += 1

    # 创建清单文件
    if create_manifest:
        manifest_path = f"{file_path}.manifest.json"
        manifest = {
            "original_file": os.path.basename(file_path),
            "original_size": file_size,
            "original_sha256": original_hash,
            "chunk_size": chunk_size,
            "parts_count": len(parts),
            "parts": part_checksums,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        with open(manifest_path, "w", encoding="utf-8") as mf:
            json.dump(manifest, mf, indent=2, ensure_ascii=False)

    # 删除原文件
    os.remove(file_path)
    return parts


def merge_files(
    part_paths: list[str],
    output_path: str,
    *,
    resume: bool = False,
    progress_callback=None,
) -> bool:
    """合并分卷文件为单个文件
    :param part_paths: 分卷文件路径列表（按顺序）
    :param output_path: 输出文件路径
    :param resume: 是否支持断点续传（从上次中断处继续）
    :param progress_callback: 进度回调函数 callback(current_bytes, total_bytes)
    :return: 是否成功
    """
    if not part_paths:
        return False

    # 计算总大小
    total_size = 0
    for p in part_paths:
        try:
            total_size += os.path.getsize(p)
        except OSError:
            return False

    # 断点续传：检查已写入的字节数
    written_bytes = 0
    start_part_idx = 0
    if resume and os.path.exists(output_path):
        written_bytes = os.path.getsize(output_path)
        # 计算从哪个分卷开始
        accumulated = 0
        for i, p in enumerate(part_paths):
            accumulated += os.path.getsize(p)
            if accumulated > written_bytes:
                start_part_idx = i
                # 计算该分卷内已写入的偏移
                prev_accumulated = accumulated - os.path.getsize(p)
                part_offset = written_bytes - prev_accumulated
                break
        else:
            # 所有分卷都已写入
            return True
    else:
        part_offset = 0

    try:
        mode = "ab" if resume and os.path.exists(output_path) else "wb"
        with open(output_path, mode) as out_f:
            for i in range(start_part_idx, len(part_paths)):
                part_path = part_paths[i]
                with open(part_path, "rb") as in_f:
                    if i == start_part_idx and part_offset > 0:
                        in_f.seek(part_offset)
                    while True:
                        chunk = in_f.read(65536)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        written_bytes += len(chunk)
                        if progress_callback:
                            progress_callback(written_bytes, total_size)
        return True
    except OSError:
        return False


def verify_split_integrity(file_path: str) -> dict:
    """验证分卷文件完整性
    :param file_path: 任意分卷文件路径或清单文件路径
    :return: 验证结果字典
    """
    import hashlib
    import json

    # 查找清单文件
    if file_path.endswith(".manifest.json"):
        manifest_path = file_path
    else:
        # 从分卷文件推断清单路径
        base = file_path.rsplit(".", 1)[0] if ".0" in file_path else file_path
        manifest_path = f"{base}.manifest.json"
        if not os.path.exists(manifest_path):
            # 尝试去掉 .001 后缀
            if file_path.endswith(".001"):
                manifest_path = f"{file_path[:-4]}.manifest.json"

    if not os.path.exists(manifest_path):
        return {"success": False, "error": "Manifest file not found"}

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {"success": False, "error": f"Failed to read manifest: {e}"}

    manifest_dir = os.path.dirname(manifest_path)
    results = []
    all_ok = True

    for part_info in manifest.get("parts", []):
        part_name = part_info["path"]
        expected_hash = part_info["sha256"]
        part_path = os.path.join(manifest_dir, part_name)

        if not os.path.exists(part_path):
            results.append(
                {"path": part_name, "status": "missing", "expected": expected_hash}
            )
            all_ok = False
            continue

        # 计算实际校验和
        sha256 = hashlib.sha256()
        with open(part_path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                sha256.update(chunk)
        actual_hash = sha256.hexdigest()

        if actual_hash == expected_hash:
            results.append({"path": part_name, "status": "ok"})
        else:
            results.append(
                {
                    "path": part_name,
                    "status": "corrupted",
                    "expected": expected_hash,
                    "actual": actual_hash,
                }
            )
            all_ok = False

    return {
        "success": all_ok,
        "original_file": manifest.get("original_file", ""),
        "original_size": manifest.get("original_size", 0),
        "parts_count": manifest.get("parts_count", 0),
        "results": results,
    }
