import os
import json
from sbackup.pack import zip_folder

data = {}

def read_data():
    global data
    if not os.path.exists("sbackup.json"):
        with open("sbackup.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    else:
        with open("sbackup.json", "r", encoding="utf-8") as f:
            data = json.load(f)

def write_data():
    global data
    with open("sbackup.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def add_folder(folder_path: str, target_folder: str, skip_patterns: list[str] = [".git", "__pycache__"]):
    read_data()
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
    data[folder_path] = [os.stat(folder_path).st_mtime, os.path.abspath(target_folder), skip_patterns]
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
        if value[0] != os.stat(key).st_mtime:
            zip_folder(key, value[1], value[2])

def all_folder() -> dict[str, str]:
    read_data()
    return {key: value[1] for key, value in data.items()}