from .auto_save import add_folder, rm_folder, save_folder, all_folder
import sys

VERSION = "1.0.0"
version_string = f"""
Sbackup v{VERSION} — Copyright © 2026 xiatianxuan
Licensed under GNU GPL v3.0 — https://www.gnu.org/licenses/gpl-3.0.html
"""
help_string = f"""
Sbackup v{VERSION} — Copyright © 2026 xiatianxuan
Licensed under GNU GPL v3.0 — https://www.gnu.org/licenses/gpl-3.0.html

为你的文件夹保驾护航.
add   添加备份策略.
rm, remove   删除备份策略.
all   查看所有备份策略.
save   备份所有文件夹.
version  查看版本信息.
"""


def run():
    command: str = "help"
    if len(sys.argv) > 1:
        command = sys.argv[1]
    if command == "add":
        add_folder(
            input("备份文件夹:"),
            input("目标文件夹:"),
            input("需要忽略的文件夹或文件(用隔开):"),
        )
    elif command == "rm" or command == "remove":
        rm_folder(input("目标文件夹:"))
    elif command == "all":
        folders: dict[str, str] = all_folder()
        if folders:
            for key, value in folders.items():
                print(f"{key} to {value}.")
        else:
            print("没有配置任何备份策略.")
    elif command == "save":
        save_folder()
    elif command == "version":
        print(version_string)
    elif command == "help":
        print(help_string)
    else:
        print(f"没有名为 {command} 的命令.")
