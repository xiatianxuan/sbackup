"""
压缩模块：ZIP / TAR / Zstd / 7z 文件压缩逻辑
"""

import logging
import os
import tarfile
import tempfile
import zipfile
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


class BaseCompressor:
    """压缩器基类，提供公共的文件收集和忽略逻辑"""

    _IGNORE_FILENAME = ".sbackupignore"

    def __init__(self, config: Config) -> None:
        self.folder_path: Path = Path(config.folder_path)
        self.zipfile_path: Path | None = (
            Path(config.zipfile_path) if config.zipfile_path else None
        )
        self.skip_patterns: list[str] = config.skip_patterns
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
        """检查相对路径是否匹配忽略模式（支持 ** 递归匹配和 ! 取反）"""
        all_patterns = self.skip_patterns + (extra_patterns or [])
        negated = []
        matched = False
        for pattern in all_patterns:
            if pattern.startswith("!"):
                negated.append(pattern[1:])
                continue
            if fnmatch(rel_path, pattern) or fnmatch(
                os.path.basename(rel_path), pattern
            ):
                matched = True
        # 取反模式可以恢复被忽略的文件
        for pattern in negated:
            if fnmatch(rel_path, pattern) or fnmatch(
                os.path.basename(rel_path), pattern
            ):
                return False
        return matched

    def _collect_files(self, folder_path: Path) -> list[tuple[str, str]]:
        """遍历文件夹收集需要压缩的文件列表，处理权限错误"""
        files = []
        extra_patterns = self._load_ignore_file(folder_path)
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
                        if not self._should_ignore(file_rel, extra_patterns):
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
            with open(output_path, "wb") as f_out:
                compressor = cctx.stream_writer(f_out)
                with tarfile.open(fileobj=compressor, mode="w") as tarf:
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
                compressor.close()

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
    fmt = config.compression_format.upper().replace(".", "_")
    if fmt in _TAR_FORMATS:
        return TarfileCompression(config)
    if fmt == "TAR_ZST":
        return ZstdCompression(config)
    if fmt == "7Z":
        return SevenZipCompression(config)
    return ZipfileCompression(config)


def restore_backup(backup_path: str, target_dir: str, password: str = "") -> dict:
    """
    从备份文件还原到目标目录
    自动检测格式（ZIP / tar.gz / tar.bz2 / tar.xz / tar.zst / 7z）
    :param password: 解密密码（仅 7z 加密备份需要）
    :return: 包含统计信息的字典
    """
    backup = Path(backup_path)
    if not backup.exists():
        print(t("err.file.not_found", path=backup_path))
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

            szf_kwargs = {"file": backup, "mode": "r"}
            if password:
                szf_kwargs["password"] = password
            with py7zr.SevenZipFile(**szf_kwargs) as szf:
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
        result = restore_backup(backup_path, tmp_dir, password)
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
