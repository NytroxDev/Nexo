import json
from pathlib import Path
from collections.abc import Callable

from veltix import (
    Server, ServerConfig, Request, Response, Events, BufferSize, Logger,
)
from veltix.server.client_info import ClientInfo

from .protocol import FILE_META, FILE_CHUNK, FILE_DONE, FILE_ACK, FILE_ERR


EventCallback = Callable[[str, dict], None]


class _Transfer:
    def __init__(self, filename: str, size: int, dst: Path):
        self.filename = filename
        self.size = size
        self.dst = dst
        self.received = 0
        self._fh = open(dst, "wb")

    def write(self, data: bytes) -> None:
        self._fh.write(data)
        self.received += len(data)

    def close(self) -> None:
        self._fh.close()

    def cleanup(self) -> None:
        self._fh.close()
        self.dst.unlink(missing_ok=True)


def start_server(
    host: str,
    port: int,
    output_dir: Path,
    on_event: EventCallback | None = None,
) -> Server:
    logger = Logger.get_instance()

    output_dir.mkdir(parents=True, exist_ok=True)

    config = ServerConfig(
        host=host,
        port=port,
        buffer_size=BufferSize.LARGE,
    )
    server = Server(config)
    sender = server.get_sender()
    transfers: dict[tuple, _Transfer] = {}

    @server.route(FILE_META)
    def on_meta(response: Response, client: ClientInfo) -> None:
        meta = json.loads(response.content)
        filename = meta["filename"]
        size = meta["size"]
        dst = output_dir / filename
        state = _Transfer(filename, size, dst)
        transfers[client.addr] = state

        logger.info(
            f"Receiving {filename} ({size} bytes) "
            f"from {client.addr[0]}:{client.addr[1]}"
        )
        if on_event:
            on_event("file_start", {
                "filename": filename,
                "size": size,
                "addr": client.addr,
            })
        sender.send(Request(FILE_ACK, b"ready"), client=client.conn)

    @server.route(FILE_CHUNK)
    def on_chunk(response: Response, client: ClientInfo) -> None:
        state = transfers.get(client.addr)
        if state:
            state.write(response.content)
            if on_event:
                on_event("file_progress", {
                    "filename": state.filename,
                    "received": state.received,
                    "size": state.size,
                })
            logger.debug(
                f"Received chunk ({len(response.content)} bytes) "
                f"for {state.filename} — total {state.received}/{state.size}"
            )
        else:
            logger.warning(
                f"Chunk from {client.addr} but no active transfer"
            )

    @server.route(FILE_DONE)
    def on_done(response: Response, client: ClientInfo) -> None:
        state = transfers.pop(client.addr, None)
        if state:
            state.close()
            logger.success(
                f"Transfer complete: {state.filename} "
                f"({state.received}/{state.size} bytes)"
            )
            if on_event:
                on_event("file_done", {
                    "filename": state.filename,
                    "received": state.received,
                    "size": state.size,
                })
            reply = Request(FILE_ACK, b"done", request_id=response.request_id)
            sender.send(reply, client=client.conn)
        else:
            logger.warning(f"FILE_DONE from {client.addr} but no active transfer")
            reply = Request(FILE_ERR, b"no active transfer",
                            request_id=response.request_id)
            sender.send(reply, client=client.conn)

    def on_disconnect(client: ClientInfo) -> None:
        state = transfers.pop(client.addr, None)
        if state:
            logger.warning(
                f"Client {client.addr[0]}:{client.addr[1]} disconnected "
                f"mid-transfer, cleaning up {state.filename}"
            )
            if on_event:
                on_event("file_abort", {
                    "filename": state.filename,
                    "received": state.received,
                    "size": state.size,
                    "reason": "client disconnected",
                })
            state.cleanup()

    server.set_callback(Events.ON_DISCONNECT, on_disconnect)
    server.start()

    logger.debug(f"Server started on {host}:{port}")
    if on_event:
        on_event("server_start", {"host": host, "port": port})
    return server
