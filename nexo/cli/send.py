from nexo.core import send_file, send_directory


def send(file: str, target: str) -> None:
    host, port_str = target.split(":")
    port = int(port_str)
    send_file(file, host, port)


def send_dir(directory: str, target: str) -> None:
    host, port_str = target.split(":")
    port = int(port_str)
    send_directory(directory, host, port)
