"""
@Time: 2025.12.20
@Author: codeseed
"""

import os
import zipfile
from pathlib import Path
from fnmatch import fnmatch
from dataclasses import dataclass, field

DEFAULT_SKIP_PATTERNS = [".git", "__pycache__"]

@dataclass
class Config:
    folder_path: str
    zipfile_path: str | None = None
    skip_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_SKIP_PATTERNS))
    compression_format: str = "ZIP"
    compression_algorithm: str = "ZIP_DEFLATED"
    compression_level: int = 6

class ZipfileCompression:
    def __init__(self, config: Config) -> None:
        self.folder_path: Path = Path(config.folder_path)
        self.zipfile_path: Path | None = Path(config.zipfile_path) if config.zipfile_path else None
        self.skip_patterns: list[str] = config.skip_patterns
        self.compression_algorithm: int = self._choose_compression_algorithm(config.compression_algorithm)
        self.compression_level: int = config.compression_level

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

    def _should_ignore(self, name: str) -> bool:
        for pattern in self.skip_patterns:
            if fnmatch(name, pattern):
                return True
        return False

    def zip_folder(self) -> None:
        folder_path = self.folder_path.resolve()
        if not folder_path.is_dir():
            print(f"{folder_path} 不是一个有效的文件夹或不存在.")
            return

        if self.zipfile_path is None:
            zipfile_path = folder_path.parent / f"{folder_path.name}.zip"
        else:
            zipfile_path = self.zipfile_path.resolve()
            if zipfile_path.is_dir():
                zipfile_path = zipfile_path / f"{folder_path.name}.zip"
            elif zipfile_path.suffix.lower() != ".zip":
                zipfile_path = zipfile_path.with_name(zipfile_path.name + ".zip")

        try:
            with zipfile.ZipFile(zipfile_path, "w", self.compression_algorithm, compresslevel=self.compression_level) as zipf:
                for dirpath, dirnames, filenames in os.walk(folder_path):
                    dirnames[:] = [d for d in dirnames if not self._should_ignore(d)]
                    for filename in filenames:
                        if self._should_ignore(filename):
                            continue
                        file_path = Path(dirpath) / filename
                        arcname = folder_path.parent / file_path.relative_to(folder_path)
                        zipf.write(file_path, arcname)
            print(f"成功备份: {zipfile_path}")
        except PermissionError:
            print(f"权限不足：无法写入 '{zipfile_path}'")
        except OSError as e:
            print(f"系统错误：{e}")
        except Exception as e:
            print(f"未知错误：{e}")