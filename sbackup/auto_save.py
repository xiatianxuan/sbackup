import os
import json
from sbackup._compression import Config, ZipfileCompression

data = {}


def read_data():
    global data
    data_file = os.getenv("SBACKUP_DATA_FILE", "sbackup.json")
    print(f"读取数据文件: {data_file}")  # 添加调试信息
    if not os.path.exists(data_file):
        print(f"数据文件不存在，创建新文件: {data_file}")  # 添加调试信息
        # 确保目录存在
        os.makedirs(os.path.dirname(data_file), exist_ok=True)
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
    else:
        print(f"加载现有数据文件: {data_file}")  # 添加调试信息
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)


def write_data():
    global data
    data_file = "./sbackup.json"
    print(f"写入数据文件: {data_file}")  # 添加调试信息
    # 确保目录存在
    os.makedirs(os.path.dirname(data_file), exist_ok=True)
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def add_folder(
    folder_path: str,
    target_folder: str,
    skip_patterns: str | None = None,
):
    global data  # 使用全局变量
    read_data()
    if skip_patterns is None:
        skip_patterns = ".git,__pycache__"
    skip_list = skip_patterns.split(",") if skip_patterns else []
    if not os.path.isdir(folder_path):
        print(f"{folder_path} 不是有效的文件夹名或不存在.")
        return
    if not os.path.isdir(target_folder):
        print(f"目标文件夹 {target_folder} 不是有效的文件夹或不存在.")
        return
    folder_path = os.path.abspath(folder_path)
    if folder_path in data.keys():
        print(f"{folder_path} 已经添加过了,请勿重复添加.")
        return
    data[folder_path] = [
        os.stat(folder_path).st_mtime,
        os.path.abspath(target_folder),
        skip_list,
    ]
    write_data()


def rm_folder(folder_path: str):
    read_data()
    folder_path = os.path.abspath(folder_path)
    if folder_path in data.keys():
        del data[folder_path]
        write_data()
    else:
        print(f"未找到 {folder_path} 的备份策略.")


def save_folder():
    read_data()
    for key, value in data.items():
        if not os.path.exists(key):
            print(f"源文件夹不存在: {key}")
            continue
        if value[0] != os.stat(key).st_mtime:
            config = Config(
                folder_path=key,
                zipfile_path=value[1],
                skip_patterns=value[2],
            )
            ZipfileCompression(config).zip_folder()


def all_folder() -> dict[str, str]:
    read_data()
    return {key: value[1] for key, value in data.items()}
