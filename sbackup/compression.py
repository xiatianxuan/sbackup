"""
压缩模块：ZIP 文件压缩逻辑
"""

import os
import zipfile
from pathlib import Path
from fnmatch import fnmatch
from tqdm import tqdm
from sbackup.i18n import t
from sbackup.config import Config

# compresslevel 仅对 ZIP_DEFLATED 和 ZIP_BZIP2 有效
_VALID_COMPRESSLEVEL_ALGORITHMS = {zipfile.ZIP_DEFLATED, zipfile.ZIP_BZIP2}


class ZipfileCompression:
    def __init__(self, config: Config) -> None:
        self.folder_path: Path = Path(config.folder_path)
        self.zipfile_path: Path | None = Path(config.zipfile_path) if config.zipfile_path else None
        self.skip_patterns: list[str] = config.skip_patterns
        self.compression_algorithm: int = self._choose_compression_algorithm(config.compression_algorithm)
        self.compression_level: int | None = self._validate_compresslevel(
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
        """校验 compresslevel：仅对 ZIP_DEFLATED 和 ZIP_BZIP2 有效，其他算法不传递该参数"""
        if algorithm not in _VALID_COMPRESSLEVEL_ALGORITHMS:
            return None  # zipfile 不接受 compresslevel 时传 None
        if not (0 <= level <= 9):
            print(t("warn.invalid.compresslevel", level=level))
            return 6
        return level

    def _should_ignore(self, name: str) -> bool:
        for pattern in self.skip_patterns:
            if fnmatch(name, pattern):
                return True
        return False

    def _collect_files(self, folder_path: Path) -> list[tuple[str, str]]:
        """遍历文件夹收集需要压缩的文件列表，处理权限错误"""
        files = []
        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                try:
                    dirnames[:] = [d for d in dirnames if not self._should_ignore(d)]
                    for filename in filenames:
                        if not self._should_ignore(filename):
                            files.append((dirpath, filename))
                except PermissionError as e:
                    print(t("err.permission", path=dirpath))
                    continue
        except PermissionError as e:
            print(t("err.permission", path=folder_path))
        except OSError as e:
            print(t("err.os", error=e))
        return files

    def zip_folder(self) -> dict:
        """
        压缩指定文件夹到 ZIP 文件
        :return: 包含统计信息的字典
        """
        folder_path = self.folder_path.resolve()
        if not folder_path.is_dir():
            print(t("err.folder.invalid", path=folder_path))
            return {"success": False, "files_count": 0, "size_mb": 0.0}

        if self.zipfile_path is None:
            zipfile_path = folder_path.parent / f"{folder_path.name}.zip"
        else:
            zipfile_path = self.zipfile_path.resolve()
            if zipfile_path.is_dir():
                zipfile_path = zipfile_path / f"{folder_path.name}.zip"
            elif zipfile_path.suffix.lower() != ".zip":
                zipfile_path = zipfile_path.with_name(zipfile_path.name + ".zip")

        # ZIP 文件已存在时提示覆盖
        if zipfile_path.exists():
            print(t("warn.zip.overwrite", path=zipfile_path))

        # 1. 收集需要压缩的文件（带异常保护）
        files_to_compress = self._collect_files(folder_path)
        total_files = len(files_to_compress)
        files_count = 0

        try:
            zip_kwargs = {"mode": "w", "compression": self.compression_algorithm}
            if self.compression_level is not None:
                zip_kwargs["compresslevel"] = self.compression_level

            with zipfile.ZipFile(zipfile_path, **zip_kwargs) as zipf:
                # 2. 使用 tqdm 显示进度条
                with tqdm(total=total_files, desc=t("compress.progress"), unit=t("compress.unit")) as pbar:
                    for dirpath, filename in files_to_compress:
                        file_path = Path(dirpath) / filename
                        arcname = str(folder_path.name / file_path.relative_to(folder_path)).replace("\\", "/")
                        try:
                            zipf.write(file_path, arcname)
                            pbar.update(1)
                            files_count += 1
                        except (FileNotFoundError, PermissionError):
                            # 文件在遍历后被删除或权限变更，跳过单个文件
                            continue

            size_mb = zipfile_path.stat().st_size / (1024 * 1024)
            # tqdm 清理输出后打印最终结果
            print(t("compress.success", path=zipfile_path, size=size_mb, count=files_count))
            return {"success": True, "files_count": files_count, "size_mb": size_mb}
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