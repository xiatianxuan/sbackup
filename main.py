from sbackup import run

def main():
    try:
        run()
    except KeyboardInterrupt:
        print("\nExit.")


if __name__ == "__main__":
    main()
