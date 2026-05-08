import json
import math
from pathlib import Path

from veltix import Client, ClientConfig, Request, BufferSize, Logger

from .protocol import FILE_META, FILE_CHUNK, FILE_DONE, FILE_ACK


CHUNK_SIZE = 65536
SEND_TIMEOUT = 30.0


def send_file(filepath: str, target: str, port: int) -> None:
    logger = Logger.get_instance()

    path = Path(filepath)
    if not path.exists():
        logger.error(f"File not found: {filepath}")
        return

    file_size = path.stat().st_size
    num_chunks = max(math.ceil(file_size / CHUNK_SIZE), 1)
    logger.info(f"Sending {path.name} ({file_size} bytes) to {target}:{port}")

    client = Client(ClientConfig(
        server_addr=target,
        port=port,
        buffer_size=BufferSize.LARGE,
    ))
    client.connect()
    sender = client.get_sender()

    @client.route(FILE_ACK)
    def on_ack(response, _client=None):
        logger.debug(f"Server ACK: {response.content.decode()}")

    meta = json.dumps({"filename": path.name, "size": file_size}).encode()
    sender.send(Request(FILE_META, meta))
    logger.debug("Sent FILE_META")

    last_pct = -1
    with open(path, "rb") as fh:
        for idx in range(num_chunks):
            data = fh.read(CHUNK_SIZE)
            sender.send(Request(FILE_CHUNK, data))
            sent = min((idx + 1) * CHUNK_SIZE, file_size)
            pct = int(sent / file_size * 100) if file_size > 0 else 100
            if pct // 10 != last_pct // 10 or pct == 100:
                logger.info(f"Progress: {pct}% ({sent}/{file_size} bytes)")
                last_pct = pct

    done = Request(FILE_DONE, b"")
    ack = client.send_and_wait(done, timeout=SEND_TIMEOUT)

    if ack and ack.content == b"done":
        logger.success(f"Transfer complete: {path.name}")
    else:
        logger.error("Transfer failed — no ACK from server")
    client.disconnect()
