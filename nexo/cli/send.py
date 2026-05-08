from nexo.core import send_file


def send(file: str, target: str) -> None:
    host, port_str = target.split(":")
    port = int(port_str)
    send_file(file, host, port)
