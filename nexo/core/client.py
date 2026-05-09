import json
import math
import struct
import zlib
from pathlib import Path

from veltix import Client, ClientConfig, Request, BufferSize, Logger

from .protocol import FILE_META, FILE_CHUNK, FILE_DONE, FILE_ACK, MIN_COMPRESS_SIZE


CHUNK_SIZE = 65536
SEND_TIMEOUT = 30.0


class NexoClient:
    """Client that sends a file to a NexoServer.

    Usage:
        client = NexoClient()
        client.send("photo.jpg", "192.168.1.42", 9000)
    """

    def send(self, filepath: str, target: str, port: int) -> None:
        logger = Logger.get_instance()

        path = Path(filepath)
        if not path.exists():
            logger.error(f"File not found: {filepath}")
            return

        file_size = path.stat().st_size
        use_compress = file_size >= MIN_COMPRESS_SIZE
        num_chunks = max(math.ceil(file_size / CHUNK_SIZE), 1)
        logger.info(f"Sending {path.name} ({file_size} bytes) to "
                    f"{target}:{port}{' [zlib]' if use_compress else ''}")

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

        meta_req = Request(FILE_META, json.dumps({
            "filename": path.name,
            "size": file_size,
            "num_chunks": num_chunks,
            "compression": "zlib" if use_compress else None,
        }).encode())
        meta_ack = client.send_and_wait(meta_req, timeout=SEND_TIMEOUT)
        if not meta_ack or meta_ack.content != b"ready":
            logger.error("Server rejected or timed out on metadata")
            client.disconnect()
            return
        logger.debug("Server ready "
                     f"(compression: {'zlib' if use_compress else 'none'})")

        last_pct = -1
        total_sent = 0
        with open(path, "rb") as fh:
            for idx in range(num_chunks):
                data = fh.read(CHUNK_SIZE)
                payload = zlib.compress(data, 1) if use_compress else data
                sender.send(
                    Request(FILE_CHUNK, struct.pack(">I", idx) + payload))
                total_sent += len(data)
                pct = (int(total_sent / file_size * 100)
                       if file_size > 0 else 100)
                saved = len(data) - len(payload) if use_compress else 0
                if pct // 10 != last_pct // 10 or pct == 100:
                    extra = f" (saved {saved}B)" if saved > 0 else ""
                    logger.info(f"Progress: {pct}% "
                                f"({total_sent}/{file_size} bytes){extra}")
                    last_pct = pct

        done = Request(FILE_DONE, b"")
        ack = client.send_and_wait(done, timeout=SEND_TIMEOUT)

        if ack and ack.content == b"done":
            logger.success(f"Transfer complete: {path.name}")
        else:
            logger.error("Transfer failed — no ACK from server")
        client.disconnect()


def send_file(filepath: str, target: str, port: int) -> None:
    """Legacy wrapper."""
    NexoClient().send(filepath, target, port)
