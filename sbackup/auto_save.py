import os
import json
import logging
from sbackup._compression import Config, ZipfileCompression, load_config
from sbackup.i18n import t

logger = logging.getLogger(__name__)


class BackupManager:
    """
    管理备份策略的类，封装状态和读写操作
    """
    def __init__(self, data_file: str = "./sbackup.json"):
        self.data_file: str = data_file
        self.data: dict = {}
        self.load()

    def load(self):
        """
        从 JSON 文件加载数据到内存
        """
        logger.debug(f"读取数据文件: {self.data_file}")
        if not os.path.exists(self.data_file):
            logger.debug(f"数据文件不存在，创建新文件: {self.data_file}")
            self.save(initial=True)
        else:
            logger.debug(f"加载现有数据文件: {self.data_file}")
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except json.JSONDecodeError:
                print(t("warn.json.decode.error", path=self.data_file))
                self.data = {}

    def save(self, initial: bool = False):
        """
        将内存数据写入 JSON 文件
        """
        if not initial:
            logger.debug(f"写入数据文件: {self.data_file}")
        
        data_dir = os.path.dirname(self.data_file)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
            
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)


    def add_folder(
        self,
        folder_path: str,
        target_folder: str,
        skip_patterns: str | None = None,
    ):
        """
        添加备份策略
        """
        if skip_patterns is None:
            skip_patterns = ".git,__pycache__"
        skip_list = skip_patterns.split(",") if skip_patterns else []
        
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
            
        self.data[abs_path] = [
            os.stat(abs_path).st_mtime,
            os.path.abspath(target_folder),
            skip_list,
        ]
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


    def save_folder(self):
        """
        备份所有文件夹
        """
        config = load_config()
        for key, value in list(self.data.items()):
            if not os.path.exists(key):
                print(t("warn.source.missing", path=key))
                continue
            if value[0] != os.stat(key).st_mtime:
                # 使用配置文件中的默认值，但允许覆盖特定项
                config_instance = Config(
                    folder_path=key,
                    zipfile_path=value[1],
                    skip_patterns=value[2],
                    compression_algorithm=config.compression_algorithm,
                    compression_level=config.compression_level
                )
                ZipfileCompression(config_instance).zip_folder()


    def all_folder(self) -> dict[str, str]:
        """
        查看所有备份策略
        """
        return {key: value[1] for key, value in self.data.items()}

    def list_folder_table(self) -> str:
        """
        生成对齐的文本表格
        """
        if not self.data:
            return t("cmd.all.empty")
        
        headers = [t("table.header.source"), t("table.header.dest"), t("table.header.ignore")]
        rows = []
        for path, info in self.data.items():
            # 格式化忽略模式
            skip = ", ".join(info[2]) if info[2] else t("table.cell.none")
            rows.append([path, info[1], skip])
        
        # 计算列宽
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(cell))
        
        # 构建表格
        fmt = " | ".join(["{:<" + str(w) + "}" for w in col_widths])
        sep = "-+-".join(["-" * w for w in col_widths])
        
        lines = []
        lines.append(fmt.format(*headers))
        lines.append(sep)
        for row in rows:
            lines.append(fmt.format(*row))
            
        return "\n".join(lines)
  
