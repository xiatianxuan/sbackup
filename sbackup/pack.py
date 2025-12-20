"""
@Time: 2025.12.20
@Author: codeseed
"""

import os
import zipfile
from fnmatch import fnmatch


def _should_ignore(name: str, patterns: list) -> bool:
    """检查文件/目录名是否匹配任意忽略模式"""
    for pattern in patterns:
        if fnmatch(name, pattern):
            return True
    return False


def zip_folder(
    folder_path: str,
    zipfile_path: str = None,
    skip_patterns: list[str] = [".git", "__pycache__"],
):
    """
    压缩文件夹为.zip文件

    :param folder_path: 被压缩文件夹路径
    :type folder_path: str
    :param zipfile_path: 目标.zip文件名,默认为被压缩文件夹名+.zip
    :type zipfile_path: str
    :param skip_patterns: 跳过压缩的文件或文件夹
    :type skip_patterns: list
    """
    #print(folder_path)
    #print(zipfile_path)
    folder_path = os.path.abspath(folder_path)
    if zipfile_path is None:

        zipfile_path = os.path.join(
            os.path.dirname(folder_path), os.path.basename(folder_path) + ".zip"
        )
    if not zipfile_path.lower().endswith(".zip"):
        #print(os.path.splitext(zipfile_path)[0])
        if not os.path.splitext(zipfile_path)[0]:
            zipfile_path = os.path.join(
            os.path.dirname(folder_path), os.path.basename(folder_path) + ".zip"
            )
        else:
            zipfile_path = os.path.splitext(zipfile_path)[0] + ".zip"
    if not os.path.isdir(folder_path):
        #print(f"{folder_path} 不是一个有效的文件夹或不存在.")
        return
    #print(folder_path)
    #print(zipfile_path)
    try:
        with zipfile.ZipFile(zipfile_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder_path):
                dirs[:] = [d for d in dirs if not _should_ignore(d, skip_patterns)]
                for file in files:
                    if _should_ignore(file, skip_patterns):
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.dirname(folder_path))
                    zipf.write(file_path, arcname)
    except PermissionError:
        print(f"权限不足：无法写入 '{zipfile_path}'")
    except OSError as e:
        print(f"系统错误：{e}")
    except Exception as e:
        print(f"未知错误：{e}")
