import json
import math
import struct
import threading
import zlib
from pathlib import Path
from typing import Callable, Optional

from veltix import Client, ClientConfig, Request, BufferSize, Logger

from .protocol import FILE_META, FILE_CHUNK, FILE_DONE, FILE_ACK, DIR_TREE, DIR_END, MIN_COMPRESS_SIZE


CHUNK_SIZE = 1048576  # 1 MB
SEND_TIMEOUT = 120.0


class NexoClient:
    """Client that sends a file to a NexoServer.

    Usage:
        client = NexoClient()
        client.send("photo.jpg", "192.168.1.42", 9000)
    """

    def __init__(self) -> None:
        self._client: Optional[Client] = None
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()
        if self._client:
            try:
                self._client.disconnect()
            except Exception:
                pass

    def send(self, filepath: str, target: str, port: int,
             on_progress: Optional[Callable[[int, int, str], None]] = None) -> None:
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

        self._client = Client(ClientConfig(
            server_addr=target,
            port=port,
            buffer_size=BufferSize.HUGE,
        ))
        self._client.connect()
        sender = self._client.get_sender()

        @self._client.route(FILE_ACK)
        def on_ack(response):
            logger.debug(f"Server ACK: {response.content.decode()}")

        meta_req = Request(FILE_META, json.dumps({
            "filename": path.name,
            "size": file_size,
            "num_chunks": num_chunks,
            "compression": "zlib" if use_compress else None,
        }).encode())
        meta_ack = self._client.send_and_wait(meta_req, timeout=SEND_TIMEOUT)
        if not meta_ack or meta_ack.content != b"ready":
            logger.error("Server rejected or timed out on metadata")
            self._client.disconnect()
            return
        logger.debug("Server ready "
                     f"(compression: {'zlib' if use_compress else 'none'})")

        last_pct = -1
        total_sent = 0
        with open(path, "rb") as fh:
            for idx in range(num_chunks):
                if self._cancelled.is_set():
                    return
                data = fh.read(CHUNK_SIZE)
                payload = zlib.compress(data, 1) if use_compress else data
                sender.send(
                    Request(FILE_CHUNK, struct.pack(">I", idx) + payload))
                total_sent += len(data)
                if on_progress:
                    on_progress(total_sent, file_size, path.name)
                pct = (int(total_sent / file_size * 100)
                       if file_size > 0 else 100)
                saved = len(data) - len(payload) if use_compress else 0
                if pct // 10 != last_pct // 10 or pct == 100:
                    extra = f" (saved {saved}B)" if saved > 0 else ""
                    logger.info(f"Progress: {pct}% "
                                f"({total_sent}/{file_size} bytes){extra}")
                    last_pct = pct

        done = Request(FILE_DONE, b"")
        ack = self._client.send_and_wait(done, timeout=SEND_TIMEOUT)

        if ack and ack.content == b"done":
            logger.success(f"Transfer complete: {path.name}")
        else:
            logger.error("Transfer failed — no ACK from server")
        self._client.disconnect()


    def send_directory(self, dirpath: str, target: str, port: int,
                       on_progress: Optional[Callable[[int, int, str], None]] = None) -> None:
        logger = Logger.get_instance()

        root = Path(dirpath)
        if not root.is_dir():
            logger.error(f"Directory not found: {dirpath}")
            return

        all_dirs = []
        all_files = []
        total_bytes = 0
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if path.is_dir():
                all_dirs.append(str(rel))
            else:
                all_files.append(str(rel))
                total_bytes += path.stat().st_size

        base = root.name
        logger.info(f"Sending directory '{base}' "
                    f"({len(all_dirs)} dirs, {len(all_files)} files, "
                    f"{total_bytes} bytes) "
                    f"to {target}:{port}")

        self._client = Client(ClientConfig(
            server_addr=target,
            port=port,
            buffer_size=BufferSize.HUGE,
        ))
        self._client.connect()
        sender = self._client.get_sender()

        @self._client.route(FILE_ACK)
        def on_ack(response):
            logger.debug(f"Server ACK: {response.content.decode()}")

        tree_payload = json.dumps({
            "base": base,
            "dirs": all_dirs,
            "files": all_files,
            "total_bytes": total_bytes,
        }).encode()
        tree_req = Request(DIR_TREE, tree_payload)
        tree_ack = self._client.send_and_wait(tree_req, timeout=SEND_TIMEOUT)
        if not tree_ack or tree_ack.content != b"ready":
            logger.error("Server rejected or timed out on directory tree")
            self._client.disconnect()
            return

        for rel_path in all_files:
            if self._cancelled:
                return
            full_path = root / rel_path
            file_size = full_path.stat().st_size
            use_compress = file_size >= MIN_COMPRESS_SIZE
            num_chunks = max(math.ceil(file_size / CHUNK_SIZE), 1)

            logger.info(f"  {rel_path} ({file_size} bytes)"
                        f"{' [zlib]' if use_compress else ''}")

            meta_req = Request(FILE_META, json.dumps({
                "filename": rel_path,
                "size": file_size,
                "num_chunks": num_chunks,
                "compression": "zlib" if use_compress else None,
            }).encode())
            meta_ack = self._client.send_and_wait(meta_req, timeout=SEND_TIMEOUT)
            if not meta_ack or meta_ack.content != b"ready":
                logger.error(f"Server rejected {rel_path}, aborting")
                self._client.disconnect()
                return

            total_sent = 0
            with open(full_path, "rb") as fh:
                for ci in range(num_chunks):
                    if self._cancelled.is_set():
                        return
                    data = fh.read(CHUNK_SIZE)
                    payload = zlib.compress(data, 1) if use_compress else data
                    sender.send(
                        Request(FILE_CHUNK, struct.pack(">I", ci) + payload))
                    total_sent += len(data)
                    if on_progress:
                        on_progress(total_sent, file_size, rel_path)

            done = Request(FILE_DONE, b"")
            ack = self._client.send_and_wait(done, timeout=SEND_TIMEOUT)
            if not ack or ack.content != b"done":
                logger.error(f"Failed to complete {rel_path}")
                self._client.disconnect()
                return

            logger.success(f"  {rel_path} done")

        end_req = Request(DIR_END, b"")
        end_ack = self._client.send_and_wait(end_req, timeout=SEND_TIMEOUT)
        if end_ack and end_ack.content == b"done":
            logger.success(f"Directory transfer complete: {base}")
        else:
            logger.error("Directory transfer failed — no ACK from server")

        self._client.disconnect()


def send_file(filepath: str, target: str, port: int,
              on_progress: Optional[Callable[[int, int, str], None]] = None) -> Optional[NexoClient]:
    """Legacy wrapper. Returns the NexoClient for cancellation, or None on error."""
    c = NexoClient()
    try:
        c.send(filepath, target, port, on_progress=on_progress)
        return c
    except Exception as e:
        Logger.get_instance().error(f"send_file failed: {e}")
        return None


def send_directory(dirpath: str, target: str, port: int,
                   on_progress: Optional[Callable[[int, int, str], None]] = None) -> Optional[NexoClient]:
    """Send a directory and all its contents. Returns the NexoClient for cancellation, or None on error."""
    c = NexoClient()
    try:
        c.send_directory(dirpath, target, port, on_progress=on_progress)
        return c
    except Exception as e:
        Logger.get_instance().error(f"send_directory failed: {e}")
        return None
