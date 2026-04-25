"""
@Time: 2025.12.20
@Author: codeseed
"""

import os
import json
import zipfile
from pathlib import Path
from fnmatch import fnmatch
from dataclasses import dataclass, field
from tqdm import tqdm
from sbackup.i18n import t

DEFAULT_SKIP_PATTERNS = [".git", "__pycache__"]


@dataclass
class Config:
    folder_path: str = "."
    zipfile_path: str | None = None
    skip_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_SKIP_PATTERNS))
    compression_format: str = "ZIP"
    compression_algorithm: str = "ZIP_DEFLATED"
    compression_level: int = 6
    lang: str = "en_US"

def load_config(config_file: str = "config.json") -> Config:
    """
    从配置文件中加载配置
    """
    if not os.path.exists(config_file):
        return Config()

    with open(config_file, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    compression_config = config_data.get("compression", {})
    skip_patterns = config_data.get("skip_patterns", DEFAULT_SKIP_PATTERNS)
    data_file = config_data.get("data_file", "sbackup.json")
    lang = config_data.get("lang", "en_US")

    return Config(
        folder_path="",
        zipfile_path=None,
        skip_patterns=skip_patterns,
        compression_format="ZIP",
        compression_algorithm=compression_config.get("algorithm", "ZIP_DEFLATED"),
        compression_level=compression_config.get("level", 6),
        lang=lang
    )

def save_lang(lang: str, config_file: str = "config.json") -> None:
    """
    将语言偏好保存到配置文件
    """
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    
    data["lang"] = lang
    
    data_dir = os.path.dirname(config_file)
    if data_dir:
        os.makedirs(data_dir, exist_ok=True)
        
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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

        # 1. 预先遍历，收集所有需要压缩的文件
        files_to_compress = []
        for dirpath, dirnames, filenames in os.walk(folder_path):
            dirnames[:] = [d for d in dirnames if not self._should_ignore(d)]
            for filename in filenames:
                if not self._should_ignore(filename):
                    files_to_compress.append((dirpath, filename))
        
        total_files = len(files_to_compress)
        files_count = 0

        try:
            with zipfile.ZipFile(zipfile_path, "w", self.compression_algorithm, compresslevel=self.compression_level) as zipf:
                # 2. 使用 tqdm 显示进度条
                with tqdm(total=total_files, desc=t("compress.progress"), unit=t("compress.unit")) as pbar:
                    for dirpath, filename in files_to_compress:
                        file_path = Path(dirpath) / filename
                        arcname = folder_path.parent / file_path.relative_to(folder_path)
                        zipf.write(file_path, arcname)
                        pbar.update(1)
                        files_count += 1

            size_mb = zipfile_path.stat().st_size / (1024 * 1024)
            # tqdm 清理输出后打印最终结果
            print(t("compress.success", path=zipfile_path, size=size_mb, count=files_count))
            return {"success": True, "files_count": files_count, "size_mb": size_mb}
        except PermissionError:
            print(t("err.permission", path=zipfile_path))
            return {"success": False, "files_count": 0, "size_mb": 0.0}
        except OSError as e:
            print(t("err.os", error=e))
            return {"success": False, "files_count": 0, "size_mb": 0.0}
        except Exception as e:
            print(t("err.unknown", error=e))
            return {"success": False, "files_count": 0, "size_mb": 0.0}