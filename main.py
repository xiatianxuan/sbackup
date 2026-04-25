from sbackup import run
from sbackup.i18n import t


def main() -> None:
    """主函数入口"""
    try:
        run()
    except KeyboardInterrupt:
        print(t("exit.message"))


if __name__ == "__main__":
    main()
  
