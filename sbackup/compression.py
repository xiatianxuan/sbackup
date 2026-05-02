"""
压缩模块：ZIP / TAR / Zstd / 7z 文件压缩逻辑
"""

import os
import io
import tarfile
import zipfile
from pathlib import Path
from fnmatch import fnmatch
from tqdm import tqdm
from sbackup.i18n import t
from sbackup.config import Config

# compresslevel 仅对 ZIP_DEFLATED 和 ZIP_BZIP2 有效
_VALID_COMPRESSLEVEL_ALGORITHMS = {zipfile.ZIP_DEFLATED, zipfile.ZIP_BZIP2}

# tar 格式 → (扩展名, 打开模式)
_TAR_FORMATS = {
    "TAR": (".tar", "w"),
    "TAR_GZ": (".tar.gz", "w:gz"),
    "TAR_BZ2": (".tar.bz2", "w:bz2"),
    "TAR_XZ": (".tar.xz", "w:xz"),
}


class BaseCompressor:
    """压缩器基类，提供公共的文件收集和忽略逻辑"""

    def __init__(self, config: Config) -> None:
        self.folder_path: Path = Path(config.folder_path)
        self.zipfile_path: Path | None = (
            Path(config.zipfile_path) if config.zipfile_path else None
        )
        self.skip_patterns: list[str] = config.skip_patterns
        self.compression_level: int | None = None

    def _should_ignore(self, rel_path: str) -> bool:
        """检查相对路径是否匹配忽略模式（支持路径级匹配如 subdir/*.log）"""
        for pattern in self.skip_patterns:
            if fnmatch(rel_path, pattern) or fnmatch(
                os.path.basename(rel_path), pattern
            ):
                return True
        return False

    def _collect_files(self, folder_path: Path) -> list[tuple[str, str]]:
        """遍历文件夹收集需要压缩的文件列表，处理权限错误"""
        files = []
        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
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
                            else d
                        )
                    ]
                    for filename in filenames:
                        file_rel = (
                            os.path.join(rel_dir, filename).replace("\\", "/")
                            if rel_dir
                            else filename
                        )
                        if not self._should_ignore(file_rel):
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
        if self.zipfile_path is None:
            return folder_path.parent / f"{folder_path.name}.zip"
        zipfile_path = self.zipfile_path.resolve()
        if zipfile_path.is_dir():
            return zipfile_path / f"{folder_path.name}.zip"
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

        try:
            zip_kwargs = {"mode": "w", "compression": self.compression_algorithm}
            if self.compression_level is not None:
                zip_kwargs["compresslevel"] = self.compression_level

            with zipfile.ZipFile(zipfile_path, **zip_kwargs) as zipf:
                with tqdm(
                    total=total_files,
                    desc=t("compress.progress"),
                    unit=t("compress.unit"),
                ) as pbar:
                    for dirpath, filename in files_to_compress:
                        file_path = Path(dirpath) / filename
                        arcname = str(
                            folder_path.name / file_path.relative_to(folder_path)
                        ).replace("\\", "/")
                        try:
                            zipf.write(file_path, arcname)
                            pbar.update(1)
                            files_count += 1
                        except (FileNotFoundError, PermissionError):
                            continue

            size_mb = zipfile_path.stat().st_size / (1024 * 1024)
            print(
                t(
                    "compress.success",
                    path=zipfile_path,
                    size=size_mb,
                    count=files_count,
                )
            )
            return {
                "success": True,
                "files_count": files_count,
                "size_mb": size_mb,
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
        fmt = config.compression_format.upper()
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
        if self.zipfile_path is None:
            return folder_path.parent / f"{folder_path.name}{self._extension}"
        tarfile_path = self.zipfile_path.resolve()
        if tarfile_path.is_dir():
            return tarfile_path / f"{folder_path.name}{self._extension}"
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

        try:
            # compresslevel 仅对 gz 和 bz2 模式有效
            tar_kwargs = {"name": tarfile_path, "mode": self._mode}
            if self._mode in ("w:gz", "w:bz2"):
                tar_kwargs["compresslevel"] = self.compression_level

            with tarfile.open(**tar_kwargs) as tarf:
                with tqdm(
                    total=total_files,
                    desc=t("compress.progress"),
                    unit=t("compress.unit"),
                ) as pbar:
                    for dirpath, filename in files_to_compress:
                        file_path = Path(dirpath) / filename
                        arcname = str(
                            folder_path.name / file_path.relative_to(folder_path)
                        ).replace("\\", "/")
                        try:
                            tarf.add(file_path, arcname=arcname, recursive=False)
                            pbar.update(1)
                            files_count += 1
                        except (FileNotFoundError, PermissionError):
                            continue

            size_mb = tarfile_path.stat().st_size / (1024 * 1024)
            print(
                t(
                    "compress.success",
                    path=tarfile_path,
                    size=size_mb,
                    count=files_count,
                )
            )
            return {
                "success": True,
                "files_count": files_count,
                "size_mb": size_mb,
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
        if self.zipfile_path is None:
            return folder_path.parent / f"{folder_path.name}.tar.zst"
        path = self.zipfile_path.resolve()
        if path.is_dir():
            return path / f"{folder_path.name}.tar.zst"
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

        try:
            cctx = zstd.ZstdCompressor(level=self.compression_level)
            # 先创建 tar，再用 zstd 压缩
            tar_buffer = io.BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w") as tarf:
                with tqdm(
                    total=total_files,
                    desc=t("compress.progress"),
                    unit=t("compress.unit"),
                ) as pbar:
                    for dirpath, filename in files_to_compress:
                        file_path = Path(dirpath) / filename
                        arcname = str(
                            folder_path.name / file_path.relative_to(folder_path)
                        ).replace("\\", "/")
                        try:
                            tarf.add(file_path, arcname=arcname, recursive=False)
                            pbar.update(1)
                            files_count += 1
                        except (FileNotFoundError, PermissionError):
                            continue

            compressed = cctx.compress(tar_buffer.getvalue())
            output_path.write_bytes(compressed)

            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(
                t("compress.success", path=output_path, size=size_mb, count=files_count)
            )
            return {
                "success": True,
                "files_count": files_count,
                "size_mb": size_mb,
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
        if self.zipfile_path is None:
            return folder_path.parent / f"{folder_path.name}.7z"
        path = self.zipfile_path.resolve()
        if path.is_dir():
            return path / f"{folder_path.name}.7z"
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

        try:
            filters = [{"id": py7zr.FILTER_LZMA2, "preset": self.compression_level}]
            szf_kwargs = {"mode": "w", "filters": filters}
            if self.password:
                szf_kwargs["password"] = self.password
            with py7zr.SevenZipFile(output_path, **szf_kwargs) as szf:
                with tqdm(
                    total=total_files,
                    desc=t("compress.progress"),
                    unit=t("compress.unit"),
                ) as pbar:
                    for dirpath, filename in files_to_compress:
                        file_path = Path(dirpath) / filename
                        arcname = str(
                            folder_path.name / file_path.relative_to(folder_path)
                        ).replace("\\", "/")
                        try:
                            szf.write(file_path, arcname)
                            pbar.update(1)
                            files_count += 1
                        except (FileNotFoundError, PermissionError):
                            continue

            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(
                t("compress.success", path=output_path, size=size_mb, count=files_count)
            )
            return {
                "success": True,
                "files_count": files_count,
                "size_mb": size_mb,
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
    fmt = config.compression_format.upper()
    if fmt in _TAR_FORMATS:
        return TarfileCompression(config)
    if fmt == "TAR_ZST":
        return ZstdCompression(config)
    if fmt == "7Z":
        return SevenZipCompression(config)
    return ZipfileCompression(config)


def restore_backup(backup_path: str, target_dir: str) -> dict:
    """
    从备份文件还原到目标目录
    自动检测格式（ZIP / tar.gz / tar.bz2 / tar.xz）
    :return: 包含统计信息的字典
    """
    backup = Path(backup_path)
    if not backup.exists():
        print(t("err.folder.invalid", path=backup_path))
        return {"success": False, "files_count": 0}

    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    name_lower = backup.name.lower()
    try:
        if name_lower.endswith(".zip"):
            with zipfile.ZipFile(backup, "r") as zf:
                members = zf.namelist()
                with tqdm(
                    total=len(members),
                    desc=t("restore.progress"),
                    unit=t("compress.unit"),
                ) as pbar:
                    for member in members:
                        zf.extract(member, target)
                        pbar.update(1)
                print(t("restore.success", path=target, count=len(members)))
                return {"success": True, "files_count": len(members)}
        elif name_lower.endswith(".7z"):
            import py7zr

            with py7zr.SevenZipFile(backup, "r") as szf:
                members = szf.getnames()
                with tqdm(
                    total=len(members),
                    desc=t("restore.progress"),
                    unit=t("compress.unit"),
                ) as pbar:
                    szf.extractall(target)
                    pbar.update(len(members))
                print(t("restore.success", path=target, count=len(members)))
                return {"success": True, "files_count": len(members)}
        elif name_lower.endswith(".tar.zst"):
            import zstandard as zstd

            dctx = zstd.ZstdDecompressor()
            compressed = backup.read_bytes()
            tar_data = dctx.decompress(compressed)
            with tarfile.open(fileobj=io.BytesIO(tar_data), mode="r") as tarf:
                members = tarf.getmembers()
                with tqdm(
                    total=len(members),
                    desc=t("restore.progress"),
                    unit=t("compress.unit"),
                ) as pbar:
                    for member in members:
                        tarf.extract(member, target, filter="data")
                        pbar.update(1)
                print(t("restore.success", path=target, count=len(members)))
                return {"success": True, "files_count": len(members)}
        elif name_lower.endswith(".tar.gz") or name_lower.endswith(".tgz"):
            mode = "r:gz"
        elif name_lower.endswith(".tar.bz2") or name_lower.endswith(".tbz2"):
            mode = "r:bz2"
        elif name_lower.endswith(".tar.xz") or name_lower.endswith(".txz"):
            mode = "r:xz"
        elif name_lower.endswith(".tar"):
            mode = "r"
        else:
            print(t("err.unknown.format", path=backup_path))
            return {"success": False, "files_count": 0}

        with tarfile.open(backup, mode) as tarf:
            members = tarf.getmembers()
            with tqdm(
                total=len(members), desc=t("restore.progress"), unit=t("compress.unit")
            ) as pbar:
                for member in members:
                    tarf.extract(member, target, filter="data")
                    pbar.update(1)
            print(t("restore.success", path=target, count=len(members)))
            return {"success": True, "files_count": len(members)}
    except KeyboardInterrupt:
        raise
    except PermissionError:
        print(t("err.permission", path=target_dir))
        return {"success": False, "files_count": 0}
    except OSError as e:
        print(t("err.os", error=e))
        return {"success": False, "files_count": 0}
    except Exception as e:
        print(t("err.unknown", error=e))
        return {"success": False, "files_count": 0}
