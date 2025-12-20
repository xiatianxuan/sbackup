from .auto_save import add_folder, rm_folder, save_folder, all_folder
import sys

VERSION = "0.0.1"
help_string = f"""
version: {VERSION}
为你的文件保驾护航.
        
add   添加备份策略.
rm, remove   删除备份策略.
all   查看所有备份策略.
save   备份所有文件夹.
"""

def run():
    command: str = sys.argv[1]
    if command == "add":
        add_folder(input("备份文件夹:"), input("目标文件夹:"), input("需要忽略的文件夹或文件(用" "隔开):"))
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
        print(f"version: {VERSION}.")
    elif command == "help":
        print(help_string)
    else:
        print(f"没有名为 {command} 的命令.")