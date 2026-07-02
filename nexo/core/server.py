import json
import struct
import threading
import zlib
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from veltix import Server, ServerConfig, Request, Response, Events, BufferSize, Logger
from veltix.server.client_info import ClientInfo

from .protocol import FILE_META, FILE_CHUNK, FILE_DONE, FILE_ACK, FILE_ERR, DIR_TREE, DIR_END


EventCallback = Callable[[str, dict], None]


class Transfer:
    """Tracks a single incoming file with unordered chunk buffering."""

    def __init__(
        self, filename: str, size: int, num_chunks: int, dst: Path,
        compression: Optional[str],
    ):
        self.filename = filename
        self.size = size
        self.num_chunks = num_chunks
        self.dst = dst
        self.received = 0
        self.compression = compression
        self._buffer: Dict[int, bytes] = {}
        self._lock = threading.Lock()
        self._done_response: Optional[Response] = None
        self._closed = False
        dst.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(dst, "wb")

    def add_chunk(self, seq: int, data: bytes) -> bool:
        raw = zlib.decompress(data) if self.compression == "zlib" else data
        with self._lock:
            if self._closed or seq in self._buffer:
                return False
            self._buffer[seq] = raw
            self.received += len(raw)
            return self._flush()

    def signal_done(self, response: Response) -> bool:
        with self._lock:
            self._done_response = response
            return self._flush()

    def _flush(self) -> bool:
        if not self._done_response or self._closed:
            return False
        if len(self._buffer) < self.num_chunks:
            return False
        for seq in range(self.num_chunks):
            self._fh.write(self._buffer[seq])
        self._fh.close()
        self._closed = True
        return True

    def cleanup(self) -> None:
        if not self._closed:
            self._fh.close()
        self.dst.unlink(missing_ok=True)


class NexoServer:
    """TCP server that receives files via Veltix.

    Usage:
        srv = NexoServer(host="0.0.0.0", port=9000, output_dir="./downloads")
        srv.on_event(lambda evt, data: print(evt, data))
        srv.start()
        ...
        srv.stop()
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9000,
        output_dir: str = "./downloads",
    ):
        self.host = host
        self.port = port
        self.output_dir = Path(output_dir)
        self._server: Optional[Server] = None
        self._sender: Any = None
        self._on_event: Optional[EventCallback] = None

    @property
    def is_running(self) -> bool:
        return self._server is not None

    def on_event(self, callback: EventCallback) -> None:
        self._on_event = callback

    def start(self) -> None:
        logger = Logger.get_instance()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        config = ServerConfig(
            host=self.host,
            port=self.port,
            buffer_size=BufferSize.LARGE,
        )
        self._server = Server(config)
        self._sender = self._server.get_sender()

        @self._server.route(FILE_META)
        def on_meta(client: ClientInfo, response: Response) -> None:
            meta = json.loads(response.content)
            filename = meta["filename"]
            size = meta["size"]
            num_chunks = meta["num_chunks"]
            compression = meta.get("compression")
            dir_root = client.get_tag("dir_root")
            dst = dir_root / filename if dir_root else self.output_dir / filename
            t = Transfer(filename, size, num_chunks, dst, compression)
            client.add_tag("transfer", t)

            extra = f" [{compression}]" if compression else ""
            logger.info(f"Receiving {filename} ({size} bytes) "
                        f"from {client.addr[0]}:{client.addr[1]}{extra}")
            if self._on_event:
                self._on_event("file_start", {
                    "filename": filename, "size": size, "addr": client.addr,
                })
            self._sender.send(
                Request(FILE_ACK, b"ready", request_id=response.request_id),
                client=client.conn,
            )

        @self._server.route(FILE_CHUNK)
        def on_chunk(client: ClientInfo, response: Response) -> None:
            t = client.get_tag("transfer")
            if not t:
                return
            seq = struct.unpack(">I", response.content[:4])[0]
            done = t.add_chunk(seq, response.content[4:])
            logger.debug(f"Chunk {seq}/{t.num_chunks - 1} for "
                         f"{t.filename} — {t.received}/{t.size} bytes")
            if self._on_event:
                self._on_event("file_progress", {
                    "filename": t.filename,
                    "received": t.received,
                    "size": t.size,
                })
            if done:
                self._finish(t, client, logger)

        @self._server.route(FILE_DONE)
        def on_done(client: ClientInfo, response: Response) -> None:
            t = client.get_tag("transfer")
            if not t:
                self._sender.send(
                    Request(FILE_ERR, b"no active transfer",
                            request_id=response.request_id),
                    client=client.conn,
                )
                return
            done = t.signal_done(response)
            if done:
                self._finish(t, client, logger)

        @self._server.route(DIR_TREE)
        def on_dir_tree(client: ClientInfo, response: Response) -> None:
            tree = json.loads(response.content)
            base = tree.get("base", "")
            dirs = tree.get("dirs", [])
            root = self.output_dir / base
            root.mkdir(parents=True, exist_ok=True)
            for d in dirs:
                (root / d).mkdir(parents=True, exist_ok=True)
            client.add_tag("dir_root", root)
            logger.info(f"Receiving directory '{base}' "
                        f"({len(dirs)} dirs, {len(tree.get('files', []))} files) "
                        f"from {client.addr[0]}:{client.addr[1]}")
            if self._on_event:
                self._on_event("dir_start", {
                    "base": base, "dirs": len(dirs),
                    "files": len(tree.get("files", [])),
                    "total_bytes": tree.get("total_bytes", 0),
                    "addr": client.addr,
                })
            self._sender.send(
                Request(FILE_ACK, b"ready", request_id=response.request_id),
                client=client.conn,
            )

        @self._server.route(DIR_END)
        def on_dir_end(client: ClientInfo, response: Response) -> None:
            root = client.get_tag("dir_root")
            if self._on_event and root:
                self._on_event("dir_done", {"base": root.name})
            logger.info(f"Directory transfer complete from "
                        f"{client.addr[0]}:{client.addr[1]}")
            self._sender.send(
                Request(FILE_ACK, b"done", request_id=response.request_id),
                client=client.conn,
            )
            client.remove_tag("dir_root")

        def on_disconnect(client: ClientInfo) -> None:
            t = client.get_tag("transfer")
            if t:
                logger.warning(f"Client {client.addr[0]}:{client.addr[1]} "
                               f"disconnected mid-transfer, "
                               f"cleaning up {t.filename}")
                if self._on_event:
                    self._on_event("file_abort", {
                        "filename": t.filename,
                        "received": t.received,
                        "size": t.size,
                        "reason": "client disconnected",
                    })
                t.cleanup()
                client.remove_tag("transfer")

        self._server.set_callback(Events.ON_DISCONNECT, on_disconnect)
        self._server.start()

        logger.debug(f"Server started on {self.host}:{self.port}")
        if self._on_event:
            self._on_event("server_start", {
                "host": self.host, "port": self.port,
            })

    def stop(self) -> None:
        if self._server:
            self._server.close_all()
            self._server = None

    close_all = stop

    def _finish(
        self, t: Transfer, client: ClientInfo, logger: Any,
    ) -> None:
        logger.success(f"Transfer complete: {t.filename} "
                       f"({t.received}/{t.size} bytes)")
        if self._on_event:
            self._on_event("file_done", {
                "filename": t.filename,
                "received": t.received,
                "size": t.size,
            })
        self._sender.send(
            Request(FILE_ACK, b"done",
                    request_id=t._done_response.request_id),
            client=client.conn,
        )
        client.remove_tag("transfer")


def start_server(
    host: str,
    port: int,
    output_dir: Path,
    on_event: Optional[EventCallback] = None,
) -> "NexoServer":
    """Legacy wrapper — returns NexoServer (has close_all() for compat)."""
    srv = NexoServer(host, port, str(output_dir))
    if on_event:
        srv.on_event(on_event)
    srv.start()
    return srv
