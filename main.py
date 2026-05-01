import sys
from sbackup import run
from sbackup.i18n import t


def main() -> None:
    """主函数入口"""
    try:
        sys.exit(run())
    except KeyboardInterrupt:
        print(t("exit.message"))
        sys.exit(130)


if __name__ == "__main__":
    main()
