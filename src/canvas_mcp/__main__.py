from dotenv import load_dotenv

from canvas_mcp.server import mcp


def main() -> None:
    load_dotenv()
    mcp.run()


if __name__ == "__main__":
    main()
