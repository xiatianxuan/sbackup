import os
import json
import shutil
import logging
from pathlib import Path
from dataclasses import dataclass
from sbackup.config import (
    Config,
    load_config,
    get_default_data_file,
    DEFAULT_SKIP_PATTERNS,
)
from sbackup.compression import create_compressor
from sbackup.i18n import t

logger = logging.getLogger(__name__)


@dataclass
class BackupEntry:
    """备份策略条目"""

    mtime: float
    target: str
    skip_patterns: list[str]
    compression_format: str = ""  # 空字符串表示使用全局默认格式

    def to_list(self) -> list:
        """转为 JSON 兼容的列表格式"""
        return [self.mtime, self.target, self.skip_patterns, self.compression_format]

    @staticmethod
    def from_list(data: list) -> "BackupEntry":
        """从 JSON 兼容的列表格式创建（向后兼容旧格式）"""
        fmt = data[3] if len(data) > 3 else ""
        return BackupEntry(
            mtime=data[0], target=data[1], skip_patterns=data[2], compression_format=fmt
        )


class BackupManager:
    """
    管理备份策略的类，封装状态和读写操作
    """

    def __init__(self, data_file: str = ""):
        self.data_file: str = data_file or get_default_data_file()
        self.data: dict[str, list] = {}
        self.load()

    def load(self):
        """
        从 JSON 文件加载数据到内存
        """
        logger.debug(t("log.data.read"), self.data_file)
        if not os.path.exists(self.data_file):
            logger.debug(t("log.data.create"), self.data_file)
            self.save(initial=True)
        else:
            logger.debug(t("log.data.load"), self.data_file)
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except json.JSONDecodeError:
                print(t("warn.json.decode.error", path=self.data_file))
                # 备份损坏文件，避免数据丢失
                backup_path = self.data_file + ".bak"
                try:
                    shutil.copy2(self.data_file, backup_path)
                    print(t("warn.json.backup", path=backup_path))
                except OSError:
                    # 备份失败时重命名损坏文件，避免下次再次触发
                    try:
                        os.rename(self.data_file, self.data_file + ".corrupted")
                        print(
                            t("warn.json.renamed", path=self.data_file + ".corrupted")
                        )
                    except OSError:
                        pass
                self.data = {}

    def save(self, initial: bool = False):
        """
        将内存数据写入 JSON 文件
        """
        if not initial:
            logger.debug(t("log.data.write"), self.data_file)

        data_dir = os.path.dirname(self.data_file)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)

        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    def _get_entry(self, key: str) -> BackupEntry | None:
        """获取指定路径的备份策略条目"""
        raw = self.data.get(key)
        if raw is None:
            return None
        return BackupEntry.from_list(raw)

    def _set_entry(self, key: str, entry: BackupEntry):
        """设置指定路径的备份策略条目"""
        self.data[key] = entry.to_list()

    def add_folder(
        self,
        folder_path: str,
        target_folder: str,
        skip_patterns: str | None = None,
        compression_format: str = "",
    ):
        """
        添加备份策略
        :param compression_format: 条目级打包格式，空字符串使用全局默认
        """
        if skip_patterns is None:
            skip_patterns = ",".join(DEFAULT_SKIP_PATTERNS)
        skip_list = (
            [s.strip() for s in skip_patterns.split(",") if s.strip()]
            if skip_patterns
            else []
        )

        if not os.path.isdir(folder_path):
            print(t("err.folder.invalid", path=folder_path))
            return False
        if not os.path.isdir(target_folder):
            print(t("err.dest.invalid", path=target_folder))
            return False

        abs_path = os.path.abspath(folder_path)
        if abs_path in self.data:
            print(t("info.already.added", path=abs_path))
            return False

        try:
            entry = BackupEntry(
                mtime=os.stat(abs_path).st_mtime,
                target=os.path.abspath(target_folder),
                skip_patterns=skip_list,
                compression_format=compression_format,
            )
        except OSError as e:
            print(t("err.os", error=e))
            return False
        self._set_entry(abs_path, entry)
        self.save()
        return True

    def rm_folder(self, folder_path: str) -> bool:
        """
        删除备份策略
        """
        abs_path = os.path.abspath(folder_path)
        if abs_path in self.data:
            del self.data[abs_path]
            self.save()
            return True
        else:
            print(t("warn.no.strategy.found", path=abs_path))
            return False

    def execute_backups(self, keep: int = 0, password: str = ""):
        """
        执行所有备份策略
        :param keep: 保留最近 N 个备份文件，0 表示不清理
        :param password: 加密密码（仅 7z 格式支持）
        """
        config = load_config()
        backup_count = 0
        skip_count = 0
        for key, raw in list(self.data.items()):
            if key == "_history":
                continue
            if not os.path.exists(key):
                print(t("warn.source.missing", path=key))
                continue
            try:
                current_mtime = os.stat(key).st_mtime
            except OSError as e:
                print(t("err.os", error=e))
                continue
            entry = BackupEntry.from_list(raw)
            if entry.mtime != current_mtime:
                # 条目级格式优先，否则使用全局配置
                fmt = entry.compression_format or config.compression_format
                config_instance = Config(
                    folder_path=key,
                    zipfile_path=entry.target,
                    skip_patterns=entry.skip_patterns,
                    compression_format=fmt,
                    compression_algorithm=config.compression_algorithm,
                    compression_level=config.compression_level,
                    password=password,
                )
                result = create_compressor(config_instance).compress()
                if result["success"]:
                    entry.mtime = current_mtime
                    self._set_entry(key, entry)
                    self._add_history(key, result["size_mb"], result["files_count"])
                    if keep > 0:
                        self._cleanup_old_backups(entry.target, keep)
                    backup_count += 1
            else:
                skip_count += 1
        if backup_count > 0:
            self.save()
            print(t("cmd.save.completed", count=backup_count))
        elif skip_count > 0:
            print(t("cmd.save.uptodate"))

    # 向后兼容别名
    save_folder = execute_backups

    def _add_history(self, source: str, size_mb: float, files_count: int):
        """记录备份历史"""
        from datetime import datetime

        history = self.data.setdefault("_history", [])
        history.append(
            {
                "time": datetime.now().isoformat(timespec="seconds"),
                "source": source,
                "size_mb": round(size_mb, 2),
                "files_count": files_count,
            }
        )
        # 保留最近 100 条记录
        if len(history) > 100:
            self.data["_history"] = history[-100:]

    def get_history(self) -> list[dict]:
        """获取备份历史记录"""
        return self.data.get("_history", [])

    @staticmethod
    def _cleanup_old_backups(target_dir: str, keep: int):
        """清理旧备份文件，仅保留最近 keep 个（keep=0 时不清理）"""
        if keep <= 0:
            return

        target = Path(target_dir)
        if not target.is_dir():
            return
        # 收集所有备份文件（.zip / .tar.* / .7z）
        patterns = [
            "*.zip",
            "*.tar",
            "*.tar.gz",
            "*.tar.bz2",
            "*.tar.xz",
            "*.tar.zst",
            "*.7z",
        ]
        files = []
        for pat in patterns:
            files.extend(target.glob(pat))
        if len(files) <= keep:
            return
        # 按修改时间排序，删除旧的
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        for old_file in files[keep:]:
            try:
                old_file.unlink()
                logger.debug(t("log.cleanup.delete"), old_file)
            except OSError:
                pass

    def all_folder(self) -> dict[str, str]:
        """
        查看所有备份策略
        """
        return {
            key: BackupEntry.from_list(raw).target for key, raw in self.data.items()
        }

    @staticmethod
    def _display_width(s: str) -> int:
        """计算字符串的终端显示宽度（中文字符算2，英文字符算1）"""
        if not isinstance(s, str):
            return len(str(s))
        width = 0
        for ch in s:
            if ord(ch) > 0x2E80:
                width += 2
            else:
                width += 1
        return width

    def list_folder_table(self) -> str:
        """
        生成对齐的文本表格
        """
        if not self.data:
            return t("cmd.all.empty")

        headers = [
            t("table.header.source"),
            t("table.header.dest"),
            t("table.header.format"),
            t("table.header.ignore"),
        ]
        rows = []
        for path, raw in self.data.items():
            if path == "_history":
                continue
            entry = BackupEntry.from_list(raw)
            fmt_display = (
                entry.compression_format
                if entry.compression_format
                else t("table.cell.default")
            )
            skip = (
                ", ".join(entry.skip_patterns)
                if entry.skip_patterns
                else t("table.cell.none")
            )
            rows.append([path, entry.target, fmt_display, skip])

        col_widths = [self._display_width(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], self._display_width(cell))

        fmt = " | ".join(["{:<" + str(w) + "}" for w in col_widths])
        sep = "-+-".join(["-" * w for w in col_widths])

        lines = []
        lines.append(fmt.format(*headers))
        lines.append(sep)
        for row in rows:
            lines.append(fmt.format(*row))

        return "\n".join(lines)
