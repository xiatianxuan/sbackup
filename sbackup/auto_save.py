import os
import json
import shutil
import logging
import unicodedata
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from sbackup.retry import retry_call

logger = logging.getLogger(__name__)

_HISTORY_KEY = "_history"


@dataclass
class BackupEntry:
    """备份策略条目"""

    mtime: float
    target: str
    skip_patterns: list[str]
    compression_format: str = ""  # 空字符串表示使用全局默认格式
    name_template: str = ""  # 空字符串表示使用全局默认模板

    def to_list(self) -> list:
        """转为 JSON 兼容的列表格式"""
        return [
            self.mtime,
            self.target,
            self.skip_patterns,
            self.compression_format,
            self.name_template,
        ]

    @staticmethod
    def from_list(data: list) -> "BackupEntry":
        """从 JSON 兼容的列表格式创建（向后兼容旧格式）"""
        if not isinstance(data, list) or len(data) < 3:
            return BackupEntry(mtime=0.0, target="", skip_patterns=[])
        fmt = data[3] if len(data) > 3 else ""
        tpl = data[4] if len(data) > 4 else ""
        return BackupEntry(
            mtime=data[0],
            target=data[1],
            skip_patterns=data[2],
            compression_format=fmt,
            name_template=tpl,
        )


def _file_sha256_from_source(
    base_path: str, rel_path: str, password: str = ""
) -> str | None:
    """从归档或源目录中读取文件内容并返回 SHA256。

    base_path 为归档路径时从归档内提取，为目录时直接读磁盘文件。
    """
    import hashlib
    import zipfile
    import tarfile

    bp = Path(base_path)
    if bp.is_dir():
        try:
            # strip source_name prefix (e.g. "src/file.txt" -> "file.txt")
            parts = rel_path.split("/", 1)
            rel = parts[1] if len(parts) > 1 else parts[0]
            src_file = bp / rel
            sha = hashlib.sha256()
            with open(src_file, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    sha.update(chunk)
            return sha.hexdigest()
        except OSError:
            return None

    ext = bp.suffix.lower()
    if ext == ".enc":
        ext = Path(bp.stem).suffix.lower()
    member = rel_path.replace("\\", "/")

    try:
        if ext == ".zip":
            with zipfile.ZipFile(str(bp), "r") as zf:
                names = zf.namelist()
                if member not in names:
                    for name in names:
                        if name.endswith("/" + member) or name == member:
                            member = name
                            break
                    else:
                        return None
                data = zf.read(member)
        elif ext == ".7z":
            import py7zr
            with py7zr.SevenZipFile(str(bp), "r", password=password or None) as szf:
                names = szf.getnames()
                if member not in names:
                    for name in names:
                        if name.endswith("/" + member) or name == member:
                            member = name
                            break
                    else:
                        return None
                result = szf.read(targets=[member])
                data = None
                for _an, files in result.items():
                    for _fn, bio in files.items():
                        data = bio.read()
                        break
                    break
                if data is None:
                    return None
        elif ext in (".tar", ".gz", ".bz2", ".xz", ".zst", ".tgz", ".tbz2", ".txz"):
            mode = "r"
            if ".tar.gz" in str(bp) or ext in (".gz", ".tgz"):
                mode = "r:gz"
            elif ".tar.bz2" in str(bp) or ext in (".bz2", ".tbz2"):
                mode = "r:bz2"
            elif ".tar.xz" in str(bp) or ext in (".xz", ".txz"):
                mode = "r:xz"
            elif ".tar.zst" in str(bp) or ext == ".zst":
                import zstandard
                with open(str(bp), "rb") as fh:
                    dctx = zstandard.ZstdDecompressor()
                    with dctx.stream_reader(fh) as reader:
                        with tarfile.open(fileobj=reader, mode="r|") as tf:
                            info = None
                            for m in tf.getmembers():
                                mn = m.name.replace("\\", "/")
                                if mn == member or mn.endswith("/" + member):
                                    info = m
                                    break
                            if info is None:
                                return None
                            f = tf.extractfile(info)
                            data = f.read() if f else b""
                return hashlib.sha256(data).hexdigest()
            with tarfile.open(str(bp), mode) as tf:
                info = None
                for m in tf.getmembers():
                    mn = m.name.replace("\\", "/")
                    if mn == member or mn.endswith("/" + member):
                        info = m
                        break
                if info is None:
                    return None
                f = tf.extractfile(info)
                data = f.read() if f else b""
        else:
            return None
        return hashlib.sha256(data).hexdigest()
    except Exception:
        return None


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
        将内存数据写入 JSON 文件（原子写入，防止中断导致数据损坏）
        """
        if not initial:
            logger.debug(t("log.data.write"), self.data_file)

        data_dir = os.path.dirname(self.data_file)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)

        # 原子写入：先写入临时文件，再 rename 替换
        tmp_path = self.data_file + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
                f.flush()
                os.fsync(f.fileno())
            # os.replace() 在 Windows 和 Unix 上都是原子操作
            os.replace(tmp_path, self.data_file)
        except OSError:
            # 如果临时文件写入失败，尝试清理
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

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
        name_template: str = "",
    ):
        """
        添加备份策略
        :param compression_format: 条目级打包格式，空字符串使用全局默认
        :param name_template: 条目级文件名模板，空字符串使用全局默认
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
        abs_dest = os.path.abspath(target_folder)
        if abs_path == abs_dest:
            print(t("err.dest.invalid", path=target_folder))
            return False
        if abs_path in self.data:
            print(t("info.already.added", path=abs_path))
            return False

        try:
            entry = BackupEntry(
                mtime=os.stat(abs_path).st_mtime,
                target=os.path.abspath(target_folder),
                skip_patterns=skip_list,
                compression_format=compression_format,
                name_template=name_template,
            )
        except OSError as e:
            print(t("err.os", error=e))
            return False
        self._set_entry(abs_path, entry)
        self.save()
        return True

    def edit_strategy(
        self,
        source: str,
        new_target: str | None = None,
        new_ignore: str | None = None,
        new_format: str | None = None,
        new_name_template: str | None = None,
    ) -> bool:
        """
        编辑已有备份策略的字段（仅修改指定的字段）
        :param source: 源文件夹路径（用于定位策略）
        :param new_target: 新的目标路径，None 表示不修改
        :param new_ignore: 新的忽略模式（逗号分隔），None 表示不修改
        :param new_format: 新的打包格式，None 表示不修改
        :param new_name_template: 新的文件名模板，None 表示不修改
        :return: 是否编辑成功
        """
        abs_path = os.path.abspath(source)
        entry = self._get_entry(abs_path)
        if entry is None:
            print(t("warn.no.strategy.found", path=abs_path))
            return False

        changed = False
        if new_target is not None:
            abs_target = os.path.abspath(new_target)
            if not os.path.isdir(abs_target):
                print(t("err.dest.invalid", path=new_target))
                return False
            if abs_path == abs_target:
                print(t("err.dest.invalid", path=new_target))
                return False
            entry.target = abs_target
            changed = True
        if new_ignore is not None:
            entry.skip_patterns = [
                s.strip() for s in new_ignore.split(",") if s.strip()
            ]
            changed = True
        if new_format is not None:
            entry.compression_format = new_format.upper().replace(".", "_")
            changed = True
        if new_name_template is not None:
            entry.name_template = new_name_template
            changed = True

        if not changed:
            print(t("cmd.edit.nothing"))
            return False

        self._set_entry(abs_path, entry)
        self.save()
        return True

    def diff_backup(
        self,
        source: str,
        backup_file: str | None = None,
        password: str = "",
        detail: bool = False,
        backup_file2: str | None = None,
    ) -> dict:
        """
        对比差异：源目录 vs 备份，或备份 vs 备份
        :param source: 源文件夹路径（备份-vs-备份模式下为第一个备份）
        :param backup_file: 指定备份文件路径，None 则自动查找最新备份
        :param password: 解密密码
        :param detail: 是否计算行级差异
        :param backup_file2: 第二个备份文件路径（备份-vs-备份模式）
        """
        from sbackup.compression import get_archive_member_set

        abs_source = os.path.abspath(source)
        entry = self._get_entry(abs_source)

        # ---- archive-vs-archive 模式 ----
        if backup_file2:
            if not os.path.isfile(abs_source) or not os.path.isfile(backup_file2):
                print(t("err.file.not_found", path=abs_source if not os.path.isfile(abs_source) else backup_file2))
                return {"success": False}
            files_a = get_archive_member_set(abs_source, password)
            files_b = get_archive_member_set(backup_file2, password)
            if not files_a or not files_b:
                print(t("cmd.diff.empty_backup", path=abs_source if not files_a else backup_file2))
                return {"success": False}
            added = sorted(files_b - files_a)
            removed = sorted(files_a - files_b)
            common = files_a & files_b

            modified = []
            if common:
                for rel_path in sorted(common):
                    h1 = _file_sha256_from_source(abs_source, rel_path, password)
                    h2 = _file_sha256_from_source(backup_file2, rel_path, password)
                    if h1 and h2 and h1 != h2:
                        modified.append(rel_path)

            detail_map: dict[str, str] = {}
            return {
                "success": True,
                "backup_file": abs_source,
                "backup_file2": backup_file2,
                "added": added,
                "removed": removed,
                "modified": modified,
                "detail": detail_map,
            }

        # 确定备份文件
        if backup_file:
            if not os.path.isfile(backup_file):
                print(t("err.file.not_found", path=backup_file))
                return {"success": False}
            target_backup = backup_file
        elif entry:
            target_dir = Path(entry.target)
            if not target_dir.is_dir():
                print(t("err.dest.invalid", path=entry.target))
                return {"success": False}
            # 查找最新的备份文件
            patterns = [
                "*.zip",
                "*.tar",
                "*.tar.gz",
                "*.tar.bz2",
                "*.tar.xz",
                "*.tar.zst",
                "*.7z",
            ]
            all_files = []
            for pat in patterns:
                all_files.extend(target_dir.glob(pat))
            if not all_files:
                print(t("cmd.diff.no_backup", path=entry.target))
                return {"success": False}
            all_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            target_backup = str(all_files[0])
        else:
            print(t("warn.no.strategy.found", path=abs_source))
            return {"success": False}

        if not os.path.isdir(abs_source):
            print(t("err.folder.invalid", path=abs_source))
            return {"success": False}

        # 获取备份中的文件集合
        backup_files = get_archive_member_set(target_backup, password)
        if not backup_files:
            print(t("cmd.diff.empty_backup", path=target_backup))
            return {"success": False}

        # 收集当前源目录的文件集合（复用忽略逻辑）
        from sbackup.compression import create_compressor

        skip_patterns = entry.skip_patterns if entry else [".git", "__pycache__"]
        cfg = Config(
            folder_path=abs_source,
            skip_patterns=skip_patterns,
        )
        compressor = create_compressor(cfg)
        current_files_raw = compressor._collect_files(Path(abs_source))
        source_name = Path(abs_source).name
        current_files = set()
        for dirpath, filename in current_files_raw:
            file_path = Path(dirpath) / filename
            arcname = str(
                source_name / file_path.relative_to(Path(abs_source))
            ).replace("\\", "/")
            current_files.add(arcname)

        # 计算差异
        added = sorted(current_files - backup_files)
        removed = sorted(backup_files - current_files)
        common = current_files & backup_files
        # SHA256 内容级修改检测
        modified = []
        if common:
            for rel_path in sorted(common):
                h1 = _file_sha256_from_source(target_backup, rel_path, password)
                h2 = _file_sha256_from_source(abs_source, rel_path, password)
                if h1 and h2 and h1 != h2:
                    modified.append(rel_path)

        # 逐行差异详情
        detail_map: dict[str, str] = {}
        if detail and modified:
            from sbackup.compression import get_diff_detail

            for rel_path in modified:
                src_file = (
                    Path(abs_source) / rel_path.split("/", 1)[-1]
                    if "/" in rel_path
                    else Path(abs_source) / rel_path
                )
                diff_text = get_diff_detail(
                    source_path=str(src_file),
                    archive_path=target_backup,
                    archive_member=rel_path,
                    password=password,
                )
                if diff_text is not None:
                    detail_map[rel_path] = diff_text

        return {
            "success": True,
            "backup_file": target_backup,
            "added": added,
            "removed": removed,
            "modified": modified,
            "detail": detail_map,
        }

    def format_diff(self, diff_result: dict) -> str:
        """将 diff 结果格式化为可读文本"""
        if not diff_result.get("success"):
            return ""

        bk2 = diff_result.get("backup_file2", "")
        if bk2:
            lines = [
                t("cmd.diff.header", backup=diff_result["backup_file"])
                + f"\n  vs {bk2}"
            ]
        else:
            lines = [t("cmd.diff.header", backup=diff_result["backup_file"])]

        added = diff_result["added"]
        removed = diff_result["removed"]
        modified = diff_result["modified"]

        if added:
            lines.append(t("cmd.diff.added_header", count=len(added)))
            for f in added:
                lines.append(f"  + {f}")
        if removed:
            lines.append(t("cmd.diff.removed_header", count=len(removed)))
            for f in removed:
                lines.append(f"  - {f}")
        if modified:
            lines.append(t("cmd.diff.modified_header", count=len(modified)))
            for f in modified:
                lines.append(f"  ~ {f}")

        if not added and not removed and not modified:
            lines.append(t("cmd.diff.no_changes"))

        lines.append(
            t(
                "cmd.diff.summary",
                added=len(added),
                removed=len(removed),
                modified=len(modified),
            )
        )
        return "\n".join(lines)

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

    def execute_backups(
        self,
        keep: int = 0,
        keep_days: int = 0,
        password: str = "",
        sftp_upload: bool = False,
        webdav_upload: bool = False,
        cloud_upload: bool = False,
        dry_run: bool = False,
        verify: bool = False,
        name_template: str | None = None,
        webhook_url: str | None = None,
        follow_symlinks: bool = False,
        max_size: int = 0,
        min_size: int = 0,
        max_age_seconds: float = 0,
        incremental: str | None = None,
        split_size: int = 0,
        tag: str = "",
        checksum: bool = False,
        pre_hooks: list[str] | None = None,
        post_hooks: list[str] | None = None,
        dedup: bool = False,
        threads: int = 1,
    ):
        """
        执行所有备份策略
        :param keep: 保留最近 N 个备份文件，0 表示不清理
        :param keep_days: 保留最近 N 天的备份文件，0 表示不按时间清理
        :param password: 加密密码（仅 7z 格式支持）
        :param sftp_upload: 是否在备份后上传到 SFTP 服务器
        :param webdav_upload: 是否在备份后上传到 WebDAV 服务器
        :param cloud_upload: 是否在备份后上传到 S3 兼容云存储
        :param dry_run: 仅预览将备份的文件，不实际执行
        :param verify: 备份后自动校验完整性
        :param name_template: 备份文件名模板（覆盖全局和条目级设置）
        :param webhook_url: 备份完成后 POST 结果到此 URL
        :param follow_symlinks: 是否跟随符号链接
        :param max_size: 文件大小上限（字节），0 不限制
        :param min_size: 文件大小下限（字节），0 不限制
        :param max_age_seconds: 文件年龄上限（秒），0 不限制
        :param incremental: 增量备份模式: None/""=全量, "file"=文件级, "block"=块级
        :param pre_hooks: 备份前执行的命令列表
        :param post_hooks: 备份后执行的命令列表
        :param dedup: 启用跨策略 SHA256 内容哈希去重
        :param threads: 并行压缩线程数（仅 ZIP 格式支持并行写入，默认 1=串行）
        """
        config = load_config()
        start_time = time.monotonic()

        # 执行前置钩子
        self._run_hooks(pre_hooks or [], "pre")

        # 加载文件级/块级元数据（增量备份用）
        file_meta_all = self.data.get("_file_meta", {}) if incremental else {}
        chunk_meta_all = (
            self.data.get("_chunk_meta", {}) if incremental == "block" else {}
        )

        # 收集需要备份的条目
        tasks = []
        skip_count = 0
        for key, raw in list(self.data.items()):
            if key in (_HISTORY_KEY, "_file_meta", "_chunk_meta"):
                continue
            if not os.path.exists(key):
                print(t("warn.source.missing", path=key))
                continue
            try:
                dir_mtime = os.stat(key).st_mtime
            except OSError as e:
                print(t("err.os", error=e))
                continue
            entry = BackupEntry.from_list(raw)
            file_meta = file_meta_all.get(key, {}) if incremental else {}
            chunk_meta = chunk_meta_all.get(key, {}) if incremental == "block" else {}
            # 无本地元数据 + 远端已启用 → 尝试从远端下载（换机器后继续增量）
            if (
                incremental == "block"
                and not chunk_meta
                and (sftp_upload or webdav_upload or cloud_upload)
            ):
                downloaded = self._download_chunk_meta_from_remote(config, key)
                if downloaded:
                    chunk_meta = downloaded
                    self.data.setdefault("_chunk_meta", {})[key] = downloaded
            # 检测策略是否需要备份：优先用文件级元数据判断，因为目录
            # mtime 在某些文件系统/Git checkout 后不会随内容变化而更新
            if file_meta:
                max_file_mtime = self._get_max_file_mtime(key)
                strategy_changed = entry.mtime != max_file_mtime
            else:
                strategy_changed = entry.mtime != dir_mtime
            if strategy_changed:
                effective_mtime = max(dir_mtime, max_file_mtime) if file_meta else dir_mtime
                tasks.append(
                    (
                        key,
                        entry,
                        effective_mtime,
                        config,
                        password,
                        name_template,
                        follow_symlinks,
                        max_size,
                        min_size,
                        max_age_seconds,
                        file_meta,
                        split_size,
                        incremental,
                        chunk_meta,
                        threads,
                    )
                )
            else:
                skip_count += 1

        # dry-run 模式：仅预览，不执行备份
        if dry_run:
            self._dry_run_preview(tasks, config)
            return

        # 初始化去重存储
        dedup_store = None
        dedup_dup_count = 0
        dedup_saved_size = 0
        if dedup:
            from sbackup.dedup import DedupStore

            dedup_store = DedupStore(os.path.dirname(self.data_file))

        # 初始化审计日志
        from sbackup.audit import AuditLogger

        audit = AuditLogger()

        backup_count = 0
        verify_failures = 0
        uploaded_files = []

        if len(tasks) > 1:
            # 并行备份多个策略
            logger.debug(t("log.parallel.backup"), len(tasks))
            # 记录每个任务的开始时间和审计条目
            task_starts: dict[str, float] = {}
            task_audits: dict[str, object] = {}
            for task in tasks:
                t_key = task[0]
                t_entry = task[1]
                t_fmt = t_entry.compression_format or config.compression_format
                task_starts[t_key] = time.monotonic()
                task_audits[t_key] = audit.log(
                    "backup_start",
                    source_path=t_key,
                    target_path=t_entry.target,
                    format=t_fmt,
                )
            with ThreadPoolExecutor() as executor:
                futures = {
                    executor.submit(self._do_backup, *task): task for task in tasks
                }
                for future in as_completed(futures):
                    (
                        key,
                        entry,
                        current_mtime,
                        _,
                        _,
                        _,
                        _,
                        _,
                        _,
                        _,
                        _,
                        _,
                        incr_mode,
                        _,
                        _,
                    ) = futures[future]
                    task_duration = time.monotonic() - task_starts.get(
                        key, time.monotonic()
                    )
                    try:
                        result = future.result()
                    except Exception as e:
                        logger.error("Backup failed for %s: %s", key, e)
                        result = {"success": False}
                    if result and result.get("success"):
                        entry.mtime = current_mtime
                        self._set_entry(key, entry)
                        self._add_history(
                            key,
                            result["size_mb"],
                            result["files_count"],
                            result.get("original_size_mb", 0.0),
                            result.get("path", ""),
                            tag=tag,
                        )
                        if incr_mode:
                            self.data.setdefault("_file_meta", {})[key] = (
                                self._collect_file_meta(key, checksum=checksum)
                            )
                        if incr_mode == "block":
                            self._update_chunk_meta(key)
                            if sftp_upload or webdav_upload or cloud_upload:
                                self._sync_chunk_meta_to_remote(
                                    config, key,
                                    self.data.get("_chunk_meta", {}).get(key, {}),
                                )
                        # 文件级去重：扫描源目录并注册文件哈希
                        if dedup_store is not None:
                            try:
                                hash_counts = dedup_store.scan_directory(key)
                                d_count, d_size = dedup_store.count_duplicates(
                                    hash_counts
                                )
                                dedup_dup_count += d_count
                                dedup_saved_size += d_size
                            except OSError:
                                pass
                        if keep > 0 or keep_days > 0:
                            self._cleanup_old_backups(entry.target, keep, keep_days)
                        backup_count += 1
                        if (sftp_upload or webdav_upload or cloud_upload) and result.get("path"):
                            uploaded_files.append(result["path"])
                        if verify and result.get("path"):
                            if not self._verify_single(result["path"], password):
                                verify_failures += 1
                        # 审计：备份完成
                        audit.log(
                            "backup_complete",
                            source_path=key,
                            target_path=entry.target,
                            format=entry.compression_format
                            or config.compression_format,
                            files_count=result.get("files_count", 0),
                            backup_size=result.get("size_bytes", 0),
                            duration=task_duration,
                        )
                    else:
                        # 审计：备份失败
                        error_msg = ""
                        if result and result.get("error"):
                            error_msg = str(result["error"])
                        elif result and result.get("message"):
                            error_msg = str(result["message"])
                        audit.log(
                            "backup_failed",
                            source_path=key,
                            target_path=entry.target,
                            format=entry.compression_format
                            or config.compression_format,
                            status="failed",
                            error_message=error_msg,
                            duration=task_duration,
                        )
        else:
            # 单策略串行执行
            for (
                key,
                entry,
                current_mtime,
                cfg,
                pwd,
                tpl,
                sym,
                mx,
                mn,
                age,
                fmeta,
                split,
                incr_mode,
                chmeta,
                threads_val,
            ) in tasks:
                # 审计：备份开始
                task_start = time.monotonic()
                fmt = entry.compression_format or config.compression_format
                audit.log(
                    "backup_start",
                    source_path=key,
                    target_path=entry.target,
                    format=fmt,
                )
                result = self._do_backup(
                    key,
                    entry,
                    current_mtime,
                    cfg,
                    pwd,
                    tpl,
                    sym,
                    mx,
                    mn,
                    age,
                    fmeta,
                    split,
                    incr_mode,
                    chmeta,
                    threads_val,
                )
                task_duration = time.monotonic() - task_start
                if result and result.get("success"):
                    entry.mtime = current_mtime
                    self._set_entry(key, entry)
                    self._add_history(
                        key,
                        result["size_mb"],
                        result["files_count"],
                        result.get("original_size_mb", 0.0),
                        result.get("path", ""),
                        tag=tag,
                    )
                    if incr_mode:
                        self.data.setdefault("_file_meta", {})[key] = (
                            self._collect_file_meta(key, checksum=checksum)
                        )
                    if incr_mode == "block":
                        self._update_chunk_meta(key)
                        if sftp_upload or webdav_upload or cloud_upload:
                            self._sync_chunk_meta_to_remote(
                                config, key,
                                self.data.get("_chunk_meta", {}).get(key, {}),
                            )
                    # 文件级去重：扫描源目录并注册文件哈希
                    if dedup_store is not None:
                        try:
                            hash_counts = dedup_store.scan_directory(key)
                            d_count, d_size = dedup_store.count_duplicates(hash_counts)
                            dedup_dup_count += d_count
                            dedup_saved_size += d_size
                        except OSError:
                            pass
                    if keep > 0 or keep_days > 0:
                        self._cleanup_old_backups(entry.target, keep, keep_days)
                    backup_count += 1
                    if (sftp_upload or webdav_upload or cloud_upload) and result.get("path"):
                        uploaded_files.append(result["path"])
                    if verify and result.get("path"):
                        if not self._verify_single(result["path"], password):
                            verify_failures += 1
                    # 审计：备份完成
                    audit.log(
                        "backup_complete",
                        source_path=key,
                        target_path=entry.target,
                        format=fmt,
                        files_count=result.get("files_count", 0),
                        backup_size=result.get("size_bytes", 0),
                        duration=task_duration,
                    )
                else:
                    # 审计：备份失败
                    error_msg = ""
                    if result and result.get("error"):
                        error_msg = str(result["error"])
                    elif result and result.get("message"):
                        error_msg = str(result["message"])
                    audit.log(
                        "backup_failed",
                        source_path=key,
                        target_path=entry.target,
                        format=fmt,
                        status="failed",
                        error_message=error_msg,
                        duration=task_duration,
                    )

        elapsed = time.monotonic() - start_time
        total = backup_count + skip_count

        if backup_count > 0:
            self.save()
            print(t("cmd.save.completed", count=backup_count))
        elif skip_count > 0:
            print(t("cmd.save.uptodate"))

        # 统计摘要
        if total > 0:
            print(
                t(
                    "cmd.save.summary",
                    total=total,
                    backed=backup_count,
                    skipped=skip_count,
                    elapsed=elapsed,
                )
            )

        # 校验失败提示
        if verify_failures > 0:
            print(t("cmd.verify.partial_fail", count=verify_failures))

        # 去重统计
        if dedup_store is not None and dedup_dup_count > 0:
            print(
                t(
                    "cmd.dedup.saved",
                    count=dedup_dup_count,
                    saved=dedup_saved_size / (1024 * 1024),
                )
            )

        # 并行上传到 SFTP、WebDAV 和云存储（使用 ThreadPoolExecutor）
        sftp_needed = sftp_upload and bool(uploaded_files)
        webdav_needed = webdav_upload and bool(uploaded_files)
        cloud_needed = cloud_upload and bool(uploaded_files)

        upload_services = sum([sftp_needed, webdav_needed, cloud_needed])
        if upload_services > 1:
            print(t("cmd.upload.parallel"))
            with ThreadPoolExecutor(max_workers=upload_services) as upload_executor:
                futures = []
                if sftp_needed:
                    futures.append(
                        upload_executor.submit(
                            self._upload_to_sftp, uploaded_files, config
                        )
                    )
                if webdav_needed:
                    futures.append(
                        upload_executor.submit(
                            self._upload_to_webdav, uploaded_files, config
                        )
                    )
                if cloud_needed:
                    futures.append(
                        upload_executor.submit(
                            self._upload_to_cloud, uploaded_files, config
                        )
                    )
                for f in as_completed(futures):
                    exc = f.exception()
                    if exc:
                        logger.error("Parallel upload error: %s", exc)
        else:
            if sftp_needed:
                self._upload_to_sftp(uploaded_files, config)
            if webdav_needed:
                self._upload_to_webdav(uploaded_files, config)
            if cloud_needed:
                self._upload_to_cloud(uploaded_files, config)

        # Webhook 通知（支持多个 URL、自定义模板、重试）
        all_webhook_urls = list(getattr(config, "webhook_urls", []))
        # CLI --webhook 参数追加到列表（支持字符串或列表）
        if webhook_url:
            urls_from_cli = (
                webhook_url if isinstance(webhook_url, list) else [webhook_url]
            )
            for u in urls_from_cli:
                if u and u not in all_webhook_urls:
                    all_webhook_urls.append(u)
        # 向后兼容：单个 webhook_url 配置
        legacy_url = getattr(config, "webhook_url", "")
        if legacy_url and legacy_url not in all_webhook_urls:
            all_webhook_urls.append(legacy_url)

        if all_webhook_urls:
            status = "success" if verify_failures == 0 else "partial"
            if backup_count == 0:
                status = "skipped"
            self._send_webhooks(
                all_webhook_urls,
                status=status,
                backed=backup_count,
                skipped=skip_count,
                elapsed=elapsed,
                verify_failures=verify_failures,
                template=getattr(config, "webhook_template", ""),
                retries=getattr(config, "webhook_retries", 2),
            )

        # SMTP 邮件通知
        if getattr(config, "smtp_enabled", False):
            status = "成功" if verify_failures == 0 else "部分成功"
            if backup_count == 0:
                status = "跳过"
            self._send_email(
                config,
                status=status,
                backed=backup_count,
                skipped=skip_count,
                elapsed=elapsed,
                verify_failures=verify_failures,
            )

        # 执行后置钩子
        self._run_hooks(post_hooks or [], "post")

        # 备份完成后自动轮转（如果有 rotation 配置）
        rotation_count = getattr(config, "rotation_keep_count", 0)
        rotation_days = getattr(config, "rotation_keep_days", 0)
        rotation_daily = getattr(config, "rotation_keep_daily", 0)
        if rotation_count > 0 or rotation_days > 0 or rotation_daily > 0:
            self._auto_rotate(
                config,
                keep_count=rotation_count,
                keep_days=rotation_days,
                keep_daily=rotation_daily,
            )

    def _auto_rotate(
        self,
        config: Config,
        keep_count: int = 0,
        keep_days: int = 0,
        keep_daily: int = 0,
    ) -> None:
        """备份完成后自动轮转所有策略的目标目录"""
        from sbackup.rotation import BackupRotator, RotationPolicy

        # 收集所有策略的目标目录
        target_dirs: set[str] = set()
        for key, raw in self.data.items():
            if key in (_HISTORY_KEY, "_file_meta", "_chunk_meta"):
                continue
            entry = BackupEntry.from_list(raw)
            if entry.target:
                target_dirs.add(entry.target)

        policy = RotationPolicy(
            keep_count=keep_count,
            keep_days=keep_days,
            keep_daily=keep_daily,
            dry_run=False,
        )

        total_deleted = 0
        for target_dir in target_dirs:
            if not os.path.isdir(target_dir):
                continue
            try:
                rotator = BackupRotator(target_dir, policy)
                deleted_count, _ = rotator.execute()
                if deleted_count > 0:
                    print(
                        t(
                            "cmd.rotate.auto_done",
                            deleted=deleted_count,
                        )
                    )
                    total_deleted += deleted_count
            except Exception as e:
                logger.warning("Auto-rotation failed for %s: %s", target_dir, e)

    @staticmethod
    def _run_hooks(hooks: list[str], hook_type: str) -> None:
        """执行钩子命令列表（委托给 HookRunner）

        :param hooks: 命令列表
        :param hook_type: "pre" 或 "post"，用于日志标识
        """
        from sbackup.hooks import HookRunner
        from sbackup.config import load_config

        config = load_config()
        runner = HookRunner(
            pre_hooks=hooks if hook_type == "pre" else [],
            post_hooks=hooks if hook_type == "post" else [],
            timeout=config.hook_timeout,
        )
        results = runner.run_hooks(hook_type)
        # 记录结果摘要
        for r in results:
            if not r.success:
                logger.warning("Hook failed: %s (rc=%s)", r.command, r.return_code)

    @staticmethod
    def _do_backup(
        key: str,
        entry: BackupEntry,
        current_mtime: float,
        config: Config,
        password: str,
        name_template: str | None = None,
        follow_symlinks: bool = False,
        max_size: int = 0,
        min_size: int = 0,
        max_age_seconds: float = 0,
        file_metadata: dict | None = None,
        split_size: int = 0,
        incremental: str | None = None,
        chunk_meta: dict | None = None,
        threads: int = 1,
    ) -> dict:
        """执行单个备份策略（线程安全）"""
        fmt = entry.compression_format or config.compression_format
        # 模板优先级：CLI 参数 > 条目级 > 全局配置
        effective_template = (
            name_template or entry.name_template or config.name_template
        )
        # 磁盘空间检查
        BackupManager._check_disk_space(entry.target)

        # 块级增量：已有元数据时构建增量归档，仅打包变化块
        if incremental == "block" and chunk_meta:
            result = BackupManager._build_block_incremental(
                source_path=key,
                target_dir=entry.target,
                chunk_meta=chunk_meta,
                skip_patterns=entry.skip_patterns,
                compression_format=fmt,
                compression_algorithm=config.compression_algorithm,
                compression_level=config.compression_level,
                password=password,
                name_template=effective_template,
                threads=threads,
            )
            # 分卷
            if split_size > 0 and result.get("success") and result.get("path"):
                from sbackup.compression import split_file

                parts = split_file(result["path"], split_size)
                if len(parts) > 1:
                    result["parts"] = parts
                    result["split_count"] = len(parts)
                    logger.debug("分卷完成: %d 个分卷", len(parts))
            return result

        config_instance = Config(
            folder_path=key,
            zipfile_path=entry.target,
            skip_patterns=entry.skip_patterns,
            compression_format=fmt,
            compression_algorithm=config.compression_algorithm,
            compression_level=config.compression_level,
            password=password,
            name_template=effective_template,
            follow_symlinks=follow_symlinks,
            max_size=max_size,
            min_size=min_size,
            max_age_seconds=max_age_seconds,
            file_metadata=file_metadata or {},
            threads=threads,
        )
        result = create_compressor(config_instance).compress()
        # 非 7z 格式 + 有密码 → 全格式加密
        if result.get("success") and password and fmt != "7Z" and result.get("path"):
            from sbackup.compression import _encrypt_file

            encrypted_path = _encrypt_file(result["path"], password)
            result["path"] = encrypted_path
        # 分卷：压缩完成后按大小分割
        if split_size > 0 and result.get("success") and result.get("path"):
            from sbackup.compression import split_file

            parts = split_file(result["path"], split_size)
            if len(parts) > 1:
                result["parts"] = parts
                result["split_count"] = len(parts)
                logger.debug("分卷完成: %d 个分卷", len(parts))
        return result

    @staticmethod
    def _get_max_file_mtime(source_path: str) -> float:
        """获取源目录中所有文件的最大 mtime（比目录 mtime 更可靠）。

        目录 mtime 在部分文件系统上不会随内部文件变更而更新，
        导致策略级检测误判为"未变化"而跳过备份。
        """
        max_mtime = 0.0
        try:
            for dirpath, _, filenames in os.walk(source_path):
                for fn in filenames:
                    try:
                        mtime = os.stat(os.path.join(dirpath, fn)).st_mtime
                        if mtime > max_mtime:
                            max_mtime = mtime
                    except OSError:
                        pass
        except OSError:
            pass
        return max_mtime

    @staticmethod
    def _collect_file_meta(
        source_path: str, checksum: bool = False
    ) -> dict[str, list | str]:
        """收集源目录下所有文件的元数据
        :param checksum: True 时存储 SHA256，False 时存储 [mtime, size]
        """
        import hashlib

        meta = {}
        source = Path(source_path)
        if not source.is_dir():
            return meta
        try:
            for dirpath, dirnames, filenames in os.walk(source):
                rel_dir = os.path.relpath(dirpath, source)
                if rel_dir == ".":
                    rel_dir = ""
                for filename in filenames:
                    file_rel = (
                        os.path.join(rel_dir, filename).replace("\\", "/")
                        if rel_dir
                        else filename
                    )
                    try:
                        file_path = Path(dirpath) / filename
                        if checksum:
                            sha = hashlib.sha256()
                            with open(file_path, "rb") as f:
                                while True:
                                    chunk = f.read(65536)
                                    if not chunk:
                                        break
                                    sha.update(chunk)
                            meta[file_rel] = sha.hexdigest()
                        else:
                            stat = file_path.stat()
                            meta[file_rel] = [stat.st_mtime, stat.st_size]
                    except OSError:
                        pass
        except OSError:
            pass
        return meta

    def _update_chunk_meta(self, key: str) -> None:
        """为指定策略更新块级哈希元数据"""
        from sbackup.chunked_backup import compute_chunk_hashes

        if not os.path.isdir(key):
            return
        try:
            for dirpath, _, filenames in os.walk(key):
                for fn in filenames:
                    fp = os.path.join(dirpath, fn)
                    try:
                        if os.path.isfile(fp):
                            rel = os.path.relpath(fp, key).replace("\\", "/")
                            self.data.setdefault("_chunk_meta", {}).setdefault(key, {})[
                                rel
                            ] = compute_chunk_hashes(fp)
                    except OSError:
                        pass
        except OSError:
            pass

    @staticmethod
    def _sync_chunk_meta_to_remote(config, key: str, chunk_meta: dict) -> None:
        """上传 chunk_meta 到远端，使得其他机器也能基于它做增量备份。"""
        import json as _json

        if not chunk_meta:
            return
        meta_bytes = _json.dumps(
            {"source": key, "chunk_meta": chunk_meta},
            ensure_ascii=False,
        ).encode("utf-8")
        remote_name = "_sbackup_chunk_meta.json"

        errors = []
        if config.sftp_enabled and config.sftp_host:
            try:
                BackupManager._upload_bytes_to_sftp(meta_bytes, remote_name, config)
            except Exception as e:
                errors.append(f"sftp: {e}")
        if config.webdav_enabled and config.webdav_url:
            try:
                BackupManager._upload_bytes_to_webdav(meta_bytes, remote_name, config)
            except Exception as e:
                errors.append(f"webdav: {e}")
        if config.cloud_enabled and config.cloud_endpoint:
            try:
                BackupManager._upload_bytes_to_cloud(meta_bytes, remote_name, config)
            except Exception as e:
                errors.append(f"cloud: {e}")
        if errors:
            logger.debug("Remote chunk_meta sync errors: %s", "; ".join(errors))

    @staticmethod
    def _download_chunk_meta_from_remote(config, key: str) -> dict[str, dict[str, str]] | None:
        """尝试从远端下载 chunk_meta（换机器后继续增量备份）。"""
        import json as _json

        remote_name = "_sbackup_chunk_meta.json"

        for try_backend in [
            (config.sftp_enabled and config.sftp_host, "sftp"),
            (config.webdav_enabled and config.webdav_url, "webdav"),
            (config.cloud_enabled and config.cloud_endpoint, "cloud"),
        ]:
            enabled, backend = try_backend
            if not enabled:
                continue
            try:
                if backend == "sftp":
                    data = BackupManager._download_bytes_from_sftp(remote_name, config)
                elif backend == "webdav":
                    data = BackupManager._download_bytes_from_webdav(
                        remote_name, config
                    )
                else:
                    data = BackupManager._download_bytes_from_cloud(
                        remote_name, config
                    )
                if data:
                    loaded = _json.loads(data.decode("utf-8"))
                    if loaded.get("source") == key:
                        return loaded.get("chunk_meta", {})
            except Exception:
                continue
        return None

    @staticmethod
    def _build_block_incremental(
        source_path: str,
        target_dir: str,
        chunk_meta: dict[str, dict[str, str]],
        skip_patterns: list[str],
        compression_format: str,
        compression_algorithm: str,
        compression_level: int,
        password: str,
        name_template: str,
        threads: int,
    ) -> dict:
        """构建块级增量备份归档。

        对每个文件计算当前块哈希，与存储的 chunk_meta 对比：
        - 新文件/变化超过阈值 → 完整文件
        - 部分变化 → 仅写入变化块补丁（.sbackup_patch）
        - 无变化 → 跳过
        归档内含 _sbackup_manifest.json 供还原时合并。

        :returns: 与 compress() 兼容的 result dict
        """
        from sbackup.chunked_backup import (
            compute_chunk_hashes,
            find_changed_chunks,
            create_patch,
            should_do_full_backup,
        )
        from sbackup.compression import (
            create_compressor as _create_compressor,
        )
        import json as _json

        source = Path(source_path).resolve()
        source_name = source.name
        target = Path(target_dir)

        if not source.is_dir():
            return {"success": False, "files_count": 0, "size_mb": 0.0}

        # 收集文件列表（复用忽略规则）
        extra_ignore = []
        ignore_file = source / ".sbackupignore"
        if ignore_file.is_file():
            try:
                extra_ignore = [
                    l.strip()
                    for l in ignore_file.read_text("utf-8").splitlines()
                    if l.strip() and not l.strip().startswith("#")
                ]
            except OSError:
                pass

        all_patterns = skip_patterns + extra_ignore

        def _should_ignore(rel: str) -> bool:
            from fnmatch import fnmatch as _fnmatch

            basename = os.path.basename(rel)
            for pat in all_patterns:
                if pat.startswith("!"):
                    continue
                if _fnmatch(rel, pat) or _fnmatch(basename, pat):
                    return True
            return False

        # 构建临时目录
        import tempfile as _tmp

        tmp_dir = _tmp.mkdtemp(prefix="sbackup_incr_")
        try:
            tmp_source = Path(tmp_dir) / source_name
            tmp_source.mkdir()

            manifest: dict = {
                "version": 1,
                "type": "incremental",
                "chunk_size": 65536,
                "full_files": [],
                "patches": {},
                "deleted_files": [],
                "base_archive": "",
            }

            total_full = 0
            total_patch = 0
            total_skipped = 0

            for dirpath, dirnames, filenames in os.walk(source):
                rel_dir = os.path.relpath(dirpath, source)
                if rel_dir == ".":
                    rel_dir = ""

                # 过滤目录
                dirnames[:] = [
                    d
                    for d in dirnames
                    if not _should_ignore(
                        os.path.join(rel_dir, d).replace("\\", "/") if rel_dir else d
                    )
                ]

                for fn in filenames:
                    file_rel = (
                        os.path.join(rel_dir, fn).replace("\\", "/")
                        if rel_dir
                        else fn
                    )
                    if _should_ignore(file_rel):
                        continue

                    fp = os.path.join(dirpath, fn)
                    try:
                        if not os.path.isfile(fp):
                            continue
                    except OSError:
                        continue

                    stored = chunk_meta.get(file_rel, {})
                    if not stored:
                        # 新文件 → 完整备份
                        total_full += 1
                        dest = tmp_source / file_rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(fp, str(dest))
                        manifest["full_files"].append(file_rel)
                        continue

                    try:
                        changed_indices, total_chunks = find_changed_chunks(fp, stored)
                    except OSError:
                        continue

                    if not changed_indices:
                        total_skipped += 1
                        continue

                    if should_do_full_backup(fp, changed_indices):
                        total_full += 1
                        dest = tmp_source / file_rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(fp, str(dest))
                        manifest["full_files"].append(file_rel)
                    else:
                        # 部分变化 → 补丁
                        total_patch += 1
                        patch_rel = file_rel + ".sbackup_patch"
                        patch_path = tmp_source / patch_rel
                        patch_path.parent.mkdir(parents=True, exist_ok=True)
                        create_patch(fp, changed_indices, str(patch_path))
                        manifest["patches"][file_rel] = {
                            "original_blocks": total_chunks,
                            "changed_blocks": sorted(changed_indices),
                        }

            # 检查删除的文件（在 chunk_meta 中存在但源目录中不存在）
            for file_rel in chunk_meta:
                fp = source / file_rel
                try:
                    if not fp.exists():
                        manifest["deleted_files"].append(file_rel)
                except OSError:
                    pass

            # 写入 manifest
            manifest_path = tmp_source / "_sbackup_manifest.json"
            manifest_path.write_text(
                _json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            if total_full == 0 and total_patch == 0 and not manifest["deleted_files"]:
                return {"success": True, "files_count": 0, "size_mb": 0.0}

            # 使用标准压缩器打包（以 tmp_source 为根，确保归档内路径为 source_name/...）
            cfg = Config(
                folder_path=str(tmp_source),
                zipfile_path=str(target),
                skip_patterns=[],
                compression_format=compression_format,
                compression_algorithm=compression_algorithm,
                compression_level=compression_level,
                password=password,
                name_template=name_template,
                threads=threads,
            )
            result = _create_compressor(cfg).compress()

            # 非 7z 格式 + 有密码 → 加密
            if result.get("success") and password and compression_format != "7Z":
                from sbackup.compression import _encrypt_file as _enc

                encrypted_path = _enc(result["path"], password)
                result["path"] = encrypted_path

            return result
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @staticmethod
    def _check_disk_space(target_dir: str, min_ratio: float = 0.05) -> None:
        """检查目标目录剩余空间，不足时打印警告"""
        try:
            target = Path(target_dir)
            if not target.is_dir():
                return
            usage = shutil.disk_usage(target)
            # 如果剩余空间不足总量的 min_ratio，发出警告
            if usage.free < usage.total * min_ratio:
                need_mb = (usage.total * min_ratio) / (1024 * 1024)
                free_mb = usage.free / (1024 * 1024)
                print(
                    t(
                        "warn.disk.space",
                        path=target_dir,
                        need=need_mb,
                        free=free_mb,
                    )
                )
        except OSError:
            pass

    @staticmethod
    def _dry_run_preview(tasks: list[tuple], config: Config) -> None:
        """预览将要备份的文件（dry-run 模式）"""
        from sbackup.compression import create_compressor as _create

        if not tasks:
            print(t("cmd.dry_run.nothing"))
            return

        print(t("cmd.dry_run.header"))
        total_files = 0
        total_size = 0.0
        for key, entry, *_rest in tasks:
            fmt = entry.compression_format or config.compression_format
            cfg = Config(
                folder_path=key,
                zipfile_path=entry.target,
                skip_patterns=entry.skip_patterns,
                compression_format=fmt,
            )
            compressor = _create(cfg)
            files = compressor._collect_files(Path(key))
            file_count = len(files)
            size_bytes = sum(
                (Path(dp) / fn).stat().st_size
                for dp, fn in files
                if (Path(dp) / fn).exists()
            )
            size_mb = size_bytes / (1024 * 1024)
            total_files += file_count
            total_size += size_mb
            print(
                t(
                    "cmd.dry_run.item",
                    source=key,
                    target=entry.target,
                    format=fmt,
                    count=file_count,
                    size=f"{size_mb:.2f}",
                )
            )
        print(
            t(
                "cmd.dry_run.total",
                count=len(tasks),
                files=total_files,
                size=f"{total_size:.2f}",
            )
        )

    @staticmethod
    def _verify_single(backup_path: str, password: str = "") -> bool:
        """校验单个备份文件完整性"""
        from sbackup.compression import verify_backup

        result = verify_backup(backup_path, password)
        return result.get("success", False)

    @staticmethod
    def _send_webhook(
        url: str,
        *,
        status: str,
        backed: int,
        skipped: int,
        elapsed: float,
        verify_failures: int = 0,
        template: str = "",
        retries: int = 2,
    ) -> None:
        """POST 备份结果到单个 webhook URL，支持自定义模板和重试"""
        import urllib.request
        import urllib.error
        import random
        import time as _time
        from datetime import datetime

        variables = {
            "status": status,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "backed": str(backed),
            "skipped": str(skipped),
            "elapsed": f"{elapsed:.2f}",
            "verify_failures": str(verify_failures),
        }

        if template:
            try:
                payload = template.format(**variables).encode("utf-8")
            except (KeyError, ValueError):
                payload = json.dumps(variables, ensure_ascii=False).encode("utf-8")
        else:
            payload = json.dumps(
                {
                    "status": status,
                    "timestamp": variables["timestamp"],
                    "backed": backed,
                    "skipped": skipped,
                    "elapsed_seconds": round(elapsed, 2),
                    "verify_failures": verify_failures,
                },
                ensure_ascii=False,
            ).encode("utf-8")

        max_attempts = min(max(retries, 1), 5)

        # SSRF 防护：只允许 http/https 协议，阻止内网地址
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            logger.warning("Webhook URL 协议不允许: %s (仅支持 http/https)", url)
            return

        # 解析主机名并阻止内部/保留 IP
        if parsed.hostname:
            try:
                import ipaddress
                import socket as _socket

                host_ip = _socket.getaddrinfo(
                    parsed.hostname, None, type=_socket.SOCK_STREAM
                )[0][4][0]
                ip = ipaddress.ip_address(host_ip)
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_multicast
                ):
                    logger.warning(
                        "Webhook URL 指向内部地址，已阻止: %s", parsed.hostname
                    )
                    return
            except (OSError, ValueError):
                pass

        # 禁用自动重定向（防止重定向链绕过协议/地址检查）
        class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        no_redirect_opener = urllib.request.build_opener(_NoRedirectHandler)

        for attempt in range(max_attempts):
            try:
                req = urllib.request.Request(
                    url,
                    data=payload,
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                no_redirect_opener.open(req, timeout=10)
                logger.debug("Webhook 通知成功: %s", parsed.hostname)
                return
            except (urllib.error.URLError, OSError) as e:
                if attempt < max_attempts - 1:
                    wait = min(2**attempt, 30.0)
                    wait += random.uniform(0, wait * 0.3)
                    logger.debug(
                        "Webhook 重试 %d/%d (%.1fs后): %s",
                        attempt + 1,
                        max_attempts,
                        wait,
                        parsed.hostname,
                    )
                    _time.sleep(wait)
                else:
                    logger.warning("Webhook 通知失败: %s — %s", parsed.hostname, e)

    @staticmethod
    def _send_webhooks(
        urls: list[str],
        *,
        status: str,
        backed: int,
        skipped: int,
        elapsed: float,
        verify_failures: int = 0,
        template: str = "",
        retries: int = 2,
    ) -> None:
        """POST 备份结果到多个 webhook URL"""
        for url in urls:
            if url:
                BackupManager._send_webhook(
                    url,
                    status=status,
                    backed=backed,
                    skipped=skipped,
                    elapsed=elapsed,
                    verify_failures=verify_failures,
                    template=template,
                    retries=retries,
                )

    # 向后兼容别名
    save_folder = execute_backups

    @staticmethod
    def _safe_smtp_header(value: str) -> str:
        """净化 SMTP 头值，防止头注入"""
        return value.replace("\r", "").replace("\n", "")

    @staticmethod
    def _send_email(
        config: Config,
        *,
        status: str,
        backed: int,
        skipped: int,
        elapsed: float,
        verify_failures: int = 0,
    ) -> None:
        """通过 SMTP 发送备份结果邮件通知"""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from datetime import datetime

        if not config.smtp_enabled or not config.smtp_host:
            return

        subject = (
            f"[sbackup] 备份{status} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

        body = f"""sbackup 备份通知

状态: {status}
备份策略数: {backed}
跳过数: {skipped}
耗时: {elapsed:.2f} 秒
验证失败: {verify_failures}
时间: {datetime.now().isoformat(timespec="seconds")}
"""

        msg = MIMEMultipart()
        msg["From"] = BackupManager._safe_smtp_header(
            config.smtp_from or config.smtp_user
        )
        msg["To"] = BackupManager._safe_smtp_header(config.smtp_to)
        msg["Subject"] = BackupManager._safe_smtp_header(subject)
        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            if config.smtp_tls:
                server = smtplib.SMTP(config.smtp_host, config.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(config.smtp_host, config.smtp_port)

            if config.smtp_user and config.smtp_password:
                server.login(config.smtp_user, config.smtp_password)

            server.send_message(msg)
            server.quit()
            logger.debug("邮件通知成功: %s", config.smtp_to)
        except (smtplib.SMTPException, OSError) as e:
            logger.warning("邮件通知失败: %s", e)

    @staticmethod
    def _upload_to_sftp(file_paths: list[str], config: Config) -> None:
        """将备份文件上传到 SFTP 服务器（多文件并行）"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from sbackup.sftp import SFTPClient, SFTPError

        if not config.sftp_enabled or not config.sftp_host:
            print(t("err.sftp.not_configured"))
            return

        # 获取认证凭据
        key_file = config.sftp_key_file
        key_passphrase = config.sftp_key_passphrase
        password = config.sftp_password

        if not key_file and not password:
            default_key = SFTPClient.try_default_key()
            if default_key:
                print(t("cmd.sftp.using_default_key", path=default_key))
                key_file = default_key
                key_passphrase = SFTPClient.resolve_key_passphrase(default_key)
                if key_passphrase is None:
                    key_file = ""
                    password = config.sftp_password
                    key_passphrase = ""
            else:
                print(t("cmd.sftp.no_default_key"))
                return
        elif key_file and not key_passphrase and not password:
            key_passphrase = SFTPClient.resolve_key_passphrase(key_file)
            if key_passphrase is None:
                key_file = ""
                password = config.sftp_password
                key_passphrase = ""

        def _upload_single(local_path: str) -> tuple[str, bool, str]:
            """单文件上传（线程安全，每个线程独立连接，带重试）"""
            filename = os.path.basename(local_path)
            try:
                retry_call(
                    lambda: _do_upload(local_path, filename),
                )
                return filename, True, ""
            except SFTPError as e:
                return filename, False, str(e)

        def _do_upload(local_path: str, filename: str) -> None:
            """实际执行 SFTP 上传（可被 retry_call 包裹）"""
            with SFTPClient(
                config.sftp_host,
                config.sftp_port,
                config.sftp_user,
                password,
                key_file,
                key_passphrase,
            ) as client:
                client.upload_file(local_path, config.sftp_remote_path)

        if len(file_paths) == 1:
            # 单文件直接上传（带进度条）
            local_path = file_paths[0]
            filename = os.path.basename(local_path)
            file_size = os.path.getsize(local_path)
            print(t("cmd.sftp.uploading", file=filename))
            try:
                from tqdm import tqdm as tqdm_cls

                def _do_sftp_upload():
                    with SFTPClient(
                        config.sftp_host,
                        config.sftp_port,
                        config.sftp_user,
                        password,
                        key_file,
                        key_passphrase,
                    ) as client:
                        with tqdm_cls(
                            total=file_size,
                            unit="B",
                            unit_scale=True,
                            desc=t("cmd.sftp.progress"),
                        ) as pbar:
                            client.upload_file(
                                local_path,
                                config.sftp_remote_path,
                                progress_callback=lambda sent, total: pbar.update(
                                    sent - pbar.n
                                ),
                            )

                retry_call(_do_sftp_upload)
                print(t("cmd.sftp.success", file=filename))
            except SFTPError as e:
                print(str(e))
        else:
            # 多文件并行上传
            print(t("cmd.sftp.parallel_upload", count=len(file_paths)))
            with ThreadPoolExecutor(max_workers=min(len(file_paths), 4)) as executor:
                futures = {executor.submit(_upload_single, fp): fp for fp in file_paths}
                for future in as_completed(futures):
                    filename, success, error = future.result()
                    if success:
                        print(t("cmd.sftp.success", file=filename))
                    else:
                        print(error)

    @staticmethod
    def _upload_to_webdav(file_paths: list[str], config: Config) -> None:
        """将备份文件上传到 WebDAV 服务器（多文件并行）"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from sbackup.webdav import WebDAVClient, WebDAVError

        if not config.webdav_enabled or not config.webdav_url:
            print(t("err.webdav.not_configured"))
            return

        def _upload_single(local_path: str) -> tuple[str, bool, str]:
            filename = os.path.basename(local_path)
            try:
                retry_call(_do_webdav_upload, local_path)
                return filename, True, ""
            except WebDAVError as e:
                return filename, False, str(e)

        def _do_webdav_upload(local_path: str) -> None:
            """实际执行 WebDAV 上传（可被 retry_call 包裹）"""
            filename = os.path.basename(local_path)
            client = WebDAVClient(
                config.webdav_url,
                config.webdav_user,
                config.webdav_password,
            )
            client.connect()
            remote_path = config.webdav_remote_path.rstrip("/") + "/" + filename
            client.upload_file(local_path, remote_path)

        if len(file_paths) <= 1:
            # 单文件直接上传
            for local_path in file_paths:
                filename = os.path.basename(local_path)
                print(t("cmd.webdav.uploading", file=filename))
                _, success, error = _upload_single(local_path)
                if success:
                    print(t("cmd.webdav.success", file=filename))
                else:
                    print(error)
        else:
            # 多文件并行上传
            print(t("cmd.webdav.parallel_upload", count=len(file_paths)))
            with ThreadPoolExecutor(max_workers=min(len(file_paths), 4)) as executor:
                futures = {executor.submit(_upload_single, fp): fp for fp in file_paths}
                for future in as_completed(futures):
                    filename, success, error = future.result()
                    if success:
                        print(t("cmd.webdav.success", file=filename))
                    else:
                        print(error)

    @staticmethod
    def _upload_to_cloud(file_paths: list[str], config: Config) -> None:
        """将备份文件上传到 S3 兼容云存储"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from sbackup.cloud_storage import CloudStorageClient, CloudStorageError
        from sbackup.retry import retry_call

        if not config.cloud_enabled or not config.cloud_endpoint or not config.cloud_bucket:
            print(t("err.cloud.not_configured"))
            return

        endpoint = config.cloud_endpoint
        access_key = config.cloud_access_key
        secret_key = config.cloud_secret_key
        bucket = config.cloud_bucket
        region = config.cloud_region or None
        secure = config.cloud_secure
        remote_path_prefix = config.cloud_remote_path or "/"

        def _do_cloud_upload(local_path: str) -> None:
            """实际执行云上传（可被 retry_call 包裹）"""
            filename = os.path.basename(local_path)
            with CloudStorageClient(
                endpoint, access_key, secret_key, bucket,
                region=region, secure=secure,
            ) as client:
                remote_path = remote_path_prefix.rstrip("/") + "/" + filename
                client.upload_file(local_path, remote_path.lstrip("/"))

        def _upload_single(local_path: str) -> tuple[str, bool, str]:
            filename = os.path.basename(local_path)
            try:
                retry_call(_do_cloud_upload, local_path)
                return filename, True, ""
            except (CloudStorageError, Exception) as e:
                return filename, False, str(e)

        if len(file_paths) <= 1:
            for local_path in file_paths:
                filename = os.path.basename(local_path)
                print(t("cmd.cloud.uploading", file=filename))
                _, success, error = _upload_single(local_path)
                if success:
                    print(t("cmd.cloud.success", file=filename))
                else:
                    print(error)
        else:
            print(t("cmd.cloud.parallel_upload", count=len(file_paths)))
            with ThreadPoolExecutor(max_workers=min(len(file_paths), 4)) as executor:
                futures = {executor.submit(_upload_single, fp): fp for fp in file_paths}
                for future in as_completed(futures):
                    filename, success, error = future.result()
                    if success:
                        print(t("cmd.cloud.success", file=filename))
                    else:
                        print(error)

    # ---- 远端 chunk_meta 字节级传输辅助方法 ----

    @staticmethod
    def _upload_bytes_to_sftp(data: bytes, filename: str, config: Config) -> None:
        from io import BytesIO
        from sbackup.sftp import SFTPClient

        key_file = config.sftp_key_file
        key_passphrase = config.sftp_key_passphrase
        password = config.sftp_password
        if not key_file and not password:
            default_key = SFTPClient.try_default_key()
            if default_key:
                key_file = default_key
                key_passphrase = SFTPClient.resolve_key_passphrase(default_key) or ""

        with SFTPClient(
            config.sftp_host, config.sftp_port, config.sftp_user,
            password, key_file, key_passphrase,
        ) as client:
            remote_path = config.sftp_remote_path.rstrip("/") + "/" + filename
            client.connect()
            client.sftp.putfo(BytesIO(data), remote_path)

    @staticmethod
    def _download_bytes_from_sftp(filename: str, config: Config) -> bytes | None:
        from io import BytesIO
        from sbackup.sftp import SFTPClient

        key_file = config.sftp_key_file
        key_passphrase = config.sftp_key_passphrase
        password = config.sftp_password
        if not key_file and not password:
            default_key = SFTPClient.try_default_key()
            if default_key:
                key_file = default_key
                key_passphrase = SFTPClient.resolve_key_passphrase(default_key) or ""

        with SFTPClient(
            config.sftp_host, config.sftp_port, config.sftp_user,
            password, key_file, key_passphrase,
        ) as client:
            remote_path = config.sftp_remote_path.rstrip("/") + "/" + filename
            client.connect()
            buf = BytesIO()
            client.sftp.getfo(remote_path, buf)
            return buf.getvalue()

    @staticmethod
    def _upload_bytes_to_webdav(data: bytes, filename: str, config: Config) -> None:
        from sbackup.webdav import WebDAVClient
        from urllib.request import Request
        from urllib.request import urlopen

        remote_path = config.webdav_remote_path.rstrip("/") + "/" + filename
        client = WebDAVClient(config.webdav_url, config.webdav_user, config.webdav_password)
        client.connect()
        req = Request(remote_path, data=data, method="PUT")
        req.add_header("Content-Type", "application/octet-stream")
        auth = client._auth_header
        if auth:
            req.add_header("Authorization", auth)
        urlopen(req, timeout=30)

    @staticmethod
    def _download_bytes_from_webdav(filename: str, config: Config) -> bytes | None:
        from urllib.request import Request, urlopen

        remote_path = config.webdav_remote_path.rstrip("/") + "/" + filename
        from sbackup.webdav import WebDAVClient
        client = WebDAVClient(config.webdav_url, config.webdav_user, config.webdav_password)
        req = Request(remote_path, method="GET")
        auth = client._auth_header
        if auth:
            req.add_header("Authorization", auth)
        resp = urlopen(req, timeout=30)
        return resp.read()

    @staticmethod
    def _upload_bytes_to_cloud(data: bytes, filename: str, config: Config) -> None:
        from io import BytesIO
        from sbackup.cloud_storage import CloudStorageClient

        remote_path = (config.cloud_remote_path or "/").rstrip("/") + "/" + filename
        with CloudStorageClient(
            config.cloud_endpoint, config.cloud_access_key,
            config.cloud_secret_key, config.cloud_bucket,
            region=config.cloud_region or None, secure=config.cloud_secure,
        ) as client:
            client.client.put_object(
                config.cloud_bucket,
                remote_path.lstrip("/"),
                BytesIO(data),
                len(data),
            )

    @staticmethod
    def _download_bytes_from_cloud(filename: str, config: Config) -> bytes | None:
        from sbackup.cloud_storage import CloudStorageClient

        remote_path = (config.cloud_remote_path or "/").rstrip("/") + "/" + filename
        with CloudStorageClient(
            config.cloud_endpoint, config.cloud_access_key,
            config.cloud_secret_key, config.cloud_bucket,
            region=config.cloud_region or None, secure=config.cloud_secure,
        ) as client:
            return client.client.get_object(
                config.cloud_bucket, remote_path.lstrip("/")
            ).read()

    def _add_history(
        self,
        source: str,
        size_mb: float,
        files_count: int,
        original_size_mb: float = 0.0,
        backup_path: str = "",
        tag: str = "",
    ):
        """记录备份历史（可选存储 SHA256 校验和、标签和备份文件路径）"""
        import hashlib
        from datetime import datetime

        history = self.data.setdefault(_HISTORY_KEY, [])
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "source": source,
            "size_mb": round(size_mb, 2),
            "files_count": files_count,
        }
        if tag:
            entry["tag"] = tag
        if backup_path:
            entry["path"] = backup_path
        if original_size_mb > 0:
            entry["original_size_mb"] = round(original_size_mb, 2)
            entry["ratio"] = (
                round((1 - size_mb / original_size_mb) * 100, 1)
                if original_size_mb > 0
                else 0
            )
        # 计算并存储 SHA256 校验和
        if backup_path and os.path.isfile(backup_path):
            try:
                sha256 = hashlib.sha256()
                with open(backup_path, "rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        sha256.update(chunk)
                entry["sha256"] = sha256.hexdigest()
            except OSError:
                pass
        history.append(entry)
        # 保留最近 100 条记录
        if len(history) > 100:
            self.data[_HISTORY_KEY] = history[-100:]

    def get_history(self) -> list[dict]:
        """获取备份历史记录"""
        return self.data.get(_HISTORY_KEY, [])

    def get_history_by_tag(self, tag: str) -> list[dict]:
        """根据标签筛选备份历史记录"""
        history = self.get_history()
        return [entry for entry in history if entry.get("tag", "") == tag]

    def get_tags(self) -> set[str]:
        """获取所有已使用的标签"""
        history = self.get_history()
        return {entry["tag"] for entry in history if entry.get("tag")}

    def find_checksum(self, backup_path: str) -> str:
        """从历史记录中查找备份文件的 SHA256 校验和
        :param backup_path: 备份文件路径
        :return: SHA256 校验和，未找到返回空字符串
        """
        abs_path = os.path.abspath(backup_path)
        for entry in reversed(self.data.get(_HISTORY_KEY, [])):
            sha = entry.get("sha256", "")
            if not sha:
                continue
            # 匹配路径或文件名
            if entry.get("source") == abs_path:
                return sha
        # 回退：查找最近一条有 sha256 的记录
        for entry in reversed(self.data.get(_HISTORY_KEY, [])):
            sha = entry.get("sha256", "")
            if sha:
                return sha
        return ""

    def get_versions(self, source: str = "", tag: str = "") -> dict[str, list[dict]]:
        """获取备份版本列表，按源目录分组
        :param source: 指定源目录路径，空字符串表示全部
        :param tag: 按标签筛选，空字符串表示不筛选
        :return: {source_path: [version_entries]}
        """
        history = self.get_history()
        versions: dict[str, list[dict]] = {}
        for entry in history:
            src = entry.get("source", "")
            if source and src != os.path.abspath(source):
                continue
            if tag and entry.get("tag", "") != tag:
                continue
            versions.setdefault(src, []).append(entry)
        # 每个源的版本按时间倒序
        for src in versions:
            versions[src].sort(key=lambda e: e.get("time", ""), reverse=True)
        return versions

    def format_versions(self, source: str = "", tag: str = "") -> str:
        """格式化版本列表为可读文本"""
        versions = self.get_versions(source, tag)
        if not versions:
            return t("cmd.versions.empty")

        lines = [t("cmd.versions.header")]
        for src, entries in versions.items():
            lines.append("")
            lines.append(t("cmd.versions.source", source=src))
            for i, entry in enumerate(entries, 1):
                time_str = entry.get("time", "N/A")
                size = entry.get("size_mb", 0)
                files = entry.get("files_count", 0)
                ratio = entry.get("ratio")
                sha = entry.get("sha256", "")
                ratio_str = f"{ratio:.0f}%" if isinstance(ratio, (int, float)) else "-"
                sha_short = sha[:12] + "..." if sha else "-"
                tag_str = f"  [{entry['tag']}]" if entry.get("tag") else ""
                lines.append(
                    f"  #{i}  {time_str}  {size:>8.2f} MB  {files:>5} files  "
                    f"{ratio_str:>5}  {sha_short}{tag_str}"
                )
        lines.append("")
        total = sum(len(e) for e in versions.values())
        lines.append(t("cmd.versions.total", count=total, sources=len(versions)))
        return "\n".join(lines)

    def format_history_table(self) -> str:
        """生成备份历史的对齐文本表格"""
        history = self.get_history()
        if not history:
            return t("cmd.list.empty")

        headers = [
            t("table.header.time"),
            t("table.header.source"),
            t("table.header.size"),
            t("table.header.ratio"),
            t("table.header.files"),
        ]
        rows = []
        for entry in reversed(history):
            ratio = entry.get("ratio")
            ratio_str = f"{ratio:.0f}%" if ratio is not None else "-"
            rows.append(
                [
                    entry.get("time", ""),
                    entry.get("source", ""),
                    str(entry.get("size_mb", 0)),
                    ratio_str,
                    str(entry.get("files_count", 0)),
                ]
            )

        return self._render_table(headers, rows)

    @staticmethod
    def _cleanup_old_backups(
        target_dir: str, keep: int = 0, keep_days: int = 0
    ) -> None:
        """清理旧备份文件
        :param keep: 保留最近 N 个备份文件，0 表示不按数量清理
        :param keep_days: 保留最近 N 天的备份文件，0 表示不按时间清理
        """
        import time as _time

        if keep <= 0 and keep_days <= 0:
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

        to_delete: set[Path] = set()

        # 按数量清理
        if keep > 0 and len(files) > keep:
            sorted_by_time = sorted(
                files, key=lambda f: f.stat().st_mtime, reverse=True
            )
            to_delete.update(sorted_by_time[keep:])

        # 按时间清理
        if keep_days > 0:
            cutoff = _time.time() - keep_days * 86400
            for f in files:
                try:
                    if f.stat().st_mtime < cutoff:
                        to_delete.add(f)
                except OSError:
                    pass

        for old_file in to_delete:
            try:
                old_file.unlink()
                logger.debug(t("log.cleanup.delete"), old_file)
            except OSError:
                pass

    def clean_all_backups(
        self, keep: int = 0, keep_days: int = 0, dry_run: bool = False
    ) -> dict:
        """清理所有策略的备份文件
        :param keep: 每个策略保留最近 N 个，0 不按数量清理
        :param keep_days: 删除 N 天前的文件，0 不按时间清理
        :param dry_run: 仅预览不删除
        :return: {deleted: [...], kept: [...]}
        """
        import time as _time

        if keep <= 0 and keep_days <= 0:
            return {"deleted": [], "kept": []}

        patterns = [
            "*.zip",
            "*.tar",
            "*.tar.gz",
            "*.tar.bz2",
            "*.tar.xz",
            "*.tar.zst",
            "*.7z",
        ]

        # 收集所有策略的目标目录
        target_dirs: set[str] = set()
        for key, raw in self.data.items():
            if key in (_HISTORY_KEY, "_file_meta", "_chunk_meta"):
                continue
            entry = BackupEntry.from_list(raw)
            if entry.target:
                target_dirs.add(entry.target)

        deleted = []
        kept = []
        for target_dir in target_dirs:
            target = Path(target_dir)
            if not target.is_dir():
                continue
            files = []
            for pat in patterns:
                files.extend(target.glob(pat))

            to_delete: set[Path] = set()
            if keep > 0 and len(files) > keep:
                sorted_by_time = sorted(
                    files, key=lambda f: f.stat().st_mtime, reverse=True
                )
                to_delete.update(sorted_by_time[keep:])
            if keep_days > 0:
                cutoff = _time.time() - keep_days * 86400
                for f in files:
                    try:
                        if f.stat().st_mtime < cutoff:
                            to_delete.add(f)
                    except OSError:
                        pass

            for f in files:
                if f in to_delete:
                    size_mb = f.stat().st_size / (1024 * 1024)
                    if dry_run:
                        deleted.append(f"[dry-run] {f} ({size_mb:.2f} MB)")
                    else:
                        try:
                            f.unlink()
                            deleted.append(f"{f} ({size_mb:.2f} MB)")
                        except OSError:
                            kept.append(str(f))
                else:
                    kept.append(str(f))

        return {"deleted": deleted, "kept": kept}

    def export_strategies(self, output_file: str) -> int:
        """导出所有备份策略到 JSON 文件，返回导出的策略数"""
        export_data = {}
        for key, raw in self.data.items():
            if key in (_HISTORY_KEY, "_file_meta", "_chunk_meta"):
                continue
            export_data[key] = raw
        data_dir = os.path.dirname(output_file)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=4)
        return len(export_data)

    def import_strategies(self, input_file: str) -> tuple[int, int] | None:
        """从 JSON 文件导入备份策略，返回 (导入数, 跳过数) 或 None"""
        if not os.path.exists(input_file):
            return None
        # 文件大小限制：最多 10 MB
        try:
            if os.path.getsize(input_file) > 10 * 1024 * 1024:
                logger.warning("Import file too large: %s", input_file)
                return None
        except OSError:
            return None
        try:
            with open(input_file, "r", encoding="utf-8") as f:
                import_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(import_data, dict):
            return None
        imported = 0
        skipped = 0
        _RESERVED_KEYS = {_HISTORY_KEY, "_file_meta", "_chunk_meta"}
        _VALID_FORMATS = {
            "",
            "ZIP",
            "TAR",
            "TAR_GZ",
            "TAR_BZ2",
            "TAR_XZ",
            "TAR_ZST",
            "7Z",
            "zip",
            "tar",
            "tar.gz",
            "tar.bz2",
            "tar.xz",
            "tar.zst",
            "7z",
        }
        for key, raw in import_data.items():
            # 安全检查：拒绝内部保留键
            if key in _RESERVED_KEYS:
                skipped += 1
                continue
            if not isinstance(raw, list) or len(raw) < 3:
                continue
            # 安全检查：验证数据结构
            if not isinstance(raw[0], (int, float)):
                continue
            if not isinstance(raw[1], str):
                continue
            if not isinstance(raw[2], list):
                continue
            # 拒绝包含路径遍历的源/目标路径
            if ".." in key or not key.strip():
                skipped += 1
                continue
            if ".." in raw[1] or not raw[1].strip():
                skipped += 1
                continue
            # 验证条目级格式（如有）
            if len(raw) > 3 and raw[3]:
                if not isinstance(raw[3], str) or raw[3] not in _VALID_FORMATS:
                    skipped += 1
                    continue
            if key in self.data:
                skipped += 1
                continue
            self.data[key] = raw
            imported += 1
        if imported > 0:
            self.save()
        return imported, skipped

    def format_status(self) -> str:
        """生成备份状态仪表盘"""
        lines = [t("cmd.status.header")]

        # 统计策略数
        strategies = {
            k: v
            for k, v in self.data.items()
            if k not in (_HISTORY_KEY, "_file_meta", "_chunk_meta")
        }
        lines.append(t("cmd.status.strategies", count=len(strategies)))

        # 统计历史记录
        history = self.get_history()
        lines.append(t("cmd.status.history", count=len(history)))

        # 计算备份总大小和平均压缩率
        total_size = 0.0
        ratios = []
        for entry in history:
            total_size += entry.get("size_mb", 0)
            if "ratio" in entry:
                ratios.append(entry["ratio"])
        lines.append(t("cmd.status.total_size", size=total_size))
        if ratios:
            avg_ratio = sum(ratios) / len(ratios)
            lines.append(t("cmd.status.avg_ratio", ratio=avg_ratio))

        # 策略详情
        lines.append("")
        lines.append(t("cmd.status.strategy.header"))
        for source, raw in strategies.items():
            entry = BackupEntry.from_list(raw)
            lines.append(
                t("cmd.status.strategy.item", source=source, target=entry.target)
            )
            # 查找该策略的最后一次备份时间
            last_backup = None
            for h in reversed(history):
                if h.get("source") == source:
                    last_backup = h.get("time")
                    break
            if last_backup:
                lines.append(t("cmd.status.strategy.last_backup", time=last_backup))
            else:
                lines.append(t("cmd.status.strategy.never"))

            fmt = entry.compression_format or t("table.cell.default")
            lines.append(t("cmd.status.strategy.format", format=fmt))

            # 计算目标目录大小
            target_path = Path(entry.target)
            if target_path.is_dir():
                dir_size = 0
                try:
                    for f in target_path.rglob("*"):
                        try:
                            if f.is_file():
                                dir_size += f.stat().st_size
                        except OSError:
                            pass
                except OSError:
                    pass
                lines.append(
                    t("cmd.status.strategy.size", size=dir_size / (1024 * 1024))
                )

        return "\n".join(lines)

    def all_folder(self) -> dict[str, str]:
        """
        查看所有备份策略（已废弃，请使用 list_folder_table）

        .. deprecated::
            CLI 的 all 命令已改用 list_folder_table()，此方法保留仅为外部 API 兼容。
        """
        return {
            key: BackupEntry.from_list(raw).target
            for key, raw in self.data.items()
            if key not in (_HISTORY_KEY, "_file_meta", "_chunk_meta")
        }

    @staticmethod
    def _display_width(s: str) -> int:
        """计算字符串的终端显示宽度（东亚宽字符算2，其余算1）"""
        if not isinstance(s, str):
            return len(str(s))
        width = 0
        for ch in s:
            eaw = unicodedata.east_asian_width(ch)
            if eaw in ("W", "F"):
                width += 2
            else:
                width += 1
        return width

    @staticmethod
    def _render_table(headers: list[str], rows: list[list[str]]) -> str:
        """生成对齐的文本表格"""
        col_widths = [BackupManager._display_width(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], BackupManager._display_width(cell))

        fmt = " | ".join(["{:<" + str(w) + "}" for w in col_widths])
        sep = "-+-".join(["-" * w for w in col_widths])

        lines = [fmt.format(*headers), sep]
        for row in rows:
            lines.append(fmt.format(*row))
        return "\n".join(lines)

    def list_folder_table(self) -> str:
        """
        生成对齐的文本表格
        """
        non_history_keys = [
            k for k in self.data if k not in (_HISTORY_KEY, "_file_meta", "_chunk_meta")
        ]
        if not non_history_keys:
            return t("cmd.all.empty")

        headers = [
            t("table.header.source"),
            t("table.header.dest"),
            t("table.header.format"),
            t("table.header.ignore"),
        ]
        rows = []
        for path, raw in self.data.items():
            if path in (_HISTORY_KEY, "_file_meta", "_chunk_meta"):
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

        return self._render_table(headers, rows)

    def export_report(self, output_file: str = "") -> str:
        """生成 Markdown 格式的备份报告
        :param output_file: 输出文件路径，空字符串则返回文本
        :return: 报告文本
        """
        from datetime import datetime

        lines = ["# Sbackup 备份报告", ""]
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 策略统计
        strategies = {
            k: v
            for k, v in self.data.items()
            if k not in (_HISTORY_KEY, "_file_meta", "_chunk_meta")
        }
        lines.append("## 策略概览")
        lines.append(f"- 策略总数: {len(strategies)}")
        lines.append("")

        if strategies:
            lines.append("### 策略列表")
            lines.append("")
            lines.append("| 源目录 | 目标目录 | 格式 |")
            lines.append("|--------|----------|------|")
            for source, raw in strategies.items():
                entry = BackupEntry.from_list(raw)
                fmt = entry.compression_format or t("table.cell.default")
                lines.append(f"| `{source}` | `{entry.target}` | {fmt} |")
            lines.append("")

        # 历史统计
        history = self.get_history()
        lines.append("## 备份历史")
        lines.append(f"- 历史记录数: {len(history)}")

        if history:
            total_size = sum(e.get("size_mb", 0) for e in history)
            total_files = sum(e.get("files_count", 0) for e in history)
            ratios = [e["ratio"] for e in history if "ratio" in e]
            lines.append(f"- 累计备份大小: {total_size:.2f} MB")
            lines.append(f"- 累计文件数: {total_files}")
            if ratios:
                lines.append(f"- 平均压缩率: {sum(ratios) / len(ratios):.1f}%")

            # 最近 10 条记录
            lines.append("")
            lines.append("### 最近备份记录")
            lines.append("")
            lines.append("| 时间 | 源目录 | 大小(MB) | 文件数 | 压缩率 |")
            lines.append("|------|--------|----------|--------|--------|")
            for entry in reversed(history[-10:]):
                ratio = entry.get("ratio", "")
                ratio_str = f"{ratio:.0f}%" if isinstance(ratio, (int, float)) else "-"
                lines.append(
                    f"| {entry.get('time', '')} | `{entry.get('source', '')}` "
                    f"| {entry.get('size_mb', 0)} | {entry.get('files_count', 0)} "
                    f"| {ratio_str} |"
                )

        report = "\n".join(lines) + "\n"

        if output_file:
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report)
            print(t("cmd.report.saved", path=output_file))

        return report

    def export_html_report(self, output_file: str = "") -> str:
        """生成 HTML 格式备份报告
        :param output_file: 输出文件路径，空字符串则返回 HTML 文本
        :return: HTML 报告文本
        """
        from datetime import datetime

        history = self.get_history()
        strategies = {
            k: v
            for k, v in self.data.items()
            if k not in (_HISTORY_KEY, "_file_meta", "_chunk_meta")
        }

        # 计算统计
        total_size = sum(h.get("size_mb", 0) for h in history)
        total_files = sum(h.get("files_count", 0) for h in history)

        # 策略行
        strategy_rows = ""
        for source, raw in strategies.items():
            entry = BackupEntry.from_list(raw)
            fmt = entry.compression_format or t("table.cell.default")
            skip_patterns = (
                ", ".join(entry.skip_patterns) if entry.skip_patterns else "-"
            )
            strategy_rows += f"""<tr>
            <td>{source}</td>
            <td>{entry.target}</td>
            <td>{fmt}</td>
            <td>{skip_patterns}</td>
        </tr>\n"""

        # 历史行（最近 50 条）
        rows_html = ""
        for h in reversed(history[-50:]):
            tag = h.get("tag", "")
            tag_html = f'<span class="tag">{tag}</span>' if tag else ""
            ratio = h.get("ratio", 0)
            ratio_str = f"{ratio:.1f}%" if isinstance(ratio, (int, float)) else "-"
            rows_html += f"""<tr>
            <td>{h.get("time", "")}</td>
            <td>{h.get("source", "")}</td>
            <td class="num">{h.get("size_mb", 0):.2f}</td>
            <td class="num">{h.get("files_count", 0)}</td>
            <td class="num">{ratio_str}</td>
            <td>{tag_html}</td>
        </tr>\n"""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>sbackup {t("cmd.report.title", default="备份报告")}</title>
<style>
body {{ font-family: -apple-system, 'Segoe UI', sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; color: #333; }}
h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
h2 {{ color: #2c3e50; margin-top: 30px; }}
.stats {{ display: flex; gap: 20px; flex-wrap: wrap; margin: 20px 0; }}
.stat-box {{ background: #fff; border-radius: 8px; padding: 20px; flex: 1; min-width: 150px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }}
.stat-box .num {{ font-size: 28px; font-weight: bold; color: #3498db; }}
.stat-box .label {{ font-size: 13px; color: #7f8c8d; margin-top: 5px; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
th {{ background: #2c3e50; color: #fff; padding: 12px; text-align: left; }}
td {{ padding: 10px 12px; border-bottom: 1px solid #ecf0f1; }}
tr:nth-child(even) {{ background: #f8f9fa; }}
tr:hover {{ background: #e8f4fd; }}
.num {{ text-align: right; font-family: 'Consolas', monospace; }}
.tag {{ display: inline-block; background: #3498db; color: #fff; padding: 2px 8px; border-radius: 12px; font-size: 12px; }}
.footer {{ text-align: center; color: #95a5a6; margin-top: 30px; font-size: 13px; }}
</style>
</head>
<body>
<h1>sbackup {t("cmd.report.title", default="备份报告")}</h1>
<p>{t("cmd.report.generated", default="生成时间")}: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
<div class="stats">
  <div class="stat-box"><div class="num">{len(strategies)}</div><div class="label">{t("cmd.report.strategies", default="备份策略")}</div></div>
  <div class="stat-box"><div class="num">{len(history)}</div><div class="label">{t("cmd.report.history", default="历史记录")}</div></div>
  <div class="stat-box"><div class="num">{total_size:.1f}</div><div class="label">{t("cmd.report.total_size", default="总大小 (MB)")}</div></div>
  <div class="stat-box"><div class="num">{total_files}</div><div class="label">{t("cmd.report.total_files", default="总文件数")}</div></div>
</div>
<h2>{t("cmd.report.strategy_overview", default="策略概览")}</h2>
<table>
<tr><th>{t("cmd.report.source", default="源目录")}</th><th>{t("cmd.report.target", default="目标目录")}</th><th>{t("cmd.report.format", default="格式")}</th><th>{t("cmd.report.skip_patterns", default="忽略模式")}</th></tr>
{strategy_rows}
</table>
<h2>{t("cmd.report.history_header", default="备份历史 (最近50条)")}</h2>
<table>
<tr><th>{t("cmd.report.time", default="时间")}</th><th>{t("cmd.report.source", default="源目录")}</th><th>{t("cmd.report.size", default="大小(MB)")}</th><th>{t("cmd.report.files", default="文件数")}</th><th>{t("cmd.report.ratio", default="压缩率")}</th><th>{t("cmd.report.tag", default="标签")}</th></tr>
{rows_html}
</table>
<div class="footer">{t("cmd.report.generated_by", default="Generated by sbackup")}</div>
</body>
</html>"""

        if output_file:
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(html)
            print(t("cmd.report.saved", path=output_file))

        return html
