import sys

from nexo.core import send_file, send_directory


def _parse_target(target: str) -> tuple:
    try:
        host, port_str = target.split(":", 1)
        port = int(port_str)
        if not (1 <= port <= 65535):
            raise ValueError
        return host, port
    except (ValueError, IndexError):
        print(f"error: invalid target '{target}' — expected host:port", file=sys.stderr)
        sys.exit(1)


def send(file: str, target: str) -> None:
    host, port = _parse_target(target)
    try:
        send_file(file, host, port)
    except Exception as e:
        print(f"error: send failed — {e}", file=sys.stderr)
        sys.exit(1)


def send_dir(directory: str, target: str) -> None:
    host, port = _parse_target(target)
    try:
        send_directory(directory, host, port)
    except Exception as e:
        print(f"error: send directory failed — {e}", file=sys.stderr)
        sys.exit(1)
