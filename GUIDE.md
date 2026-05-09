# Nexo Guide

## Installation

```bash
pip install nexo-transfert
```

---

## CLI Reference

### `nexo serve`

Start a file server that listens for incoming transfers.

```
nexo serve [--host HOST] [--port PORT] [-o OUTPUT]
```

| Option | Default | Description |
|---|---|---|
| `--host` | `0.0.0.0` | Interface to bind to |
| `--port` | `9000` | Listening port |
| `-o` / `--output` | `./downloads` | Directory to save received files |

Example:
```bash
nexo serve --port 9000 --output ~/Downloads
```

### `nexo send`

Send a file to a remote server.

```
nexo send FILE --to HOST:PORT
```

| Argument | Description |
|---|---|
| `FILE` | Path to the file to send |
| `--to` | Target address in `host:port` format |

Example:
```bash
nexo send photo.jpg --to 192.168.1.42:9000
```

### `nexo gui`

Launch the Tkinter graphical interface.

```
nexo gui
```

No options. The GUI lets you start/stop a server with a configurable port and output directory (Receive tab), and send files to a target address (Send tab).

---

## Python API

### `NexoServer`

```python
from nexo.core import NexoServer

srv = NexoServer(host="0.0.0.0", port=9000, output_dir="./downloads")
srv.start()
# ... transfers happen ...
srv.stop()
```

#### Constructor

```python
NexoServer(host="0.0.0.0", port=9000, output_dir="./downloads")
```

| Parameter | Default | Description |
|---|---|---|
| `host` | `"0.0.0.0"` | Bind address |
| `port` | `9000` | Listening port |
| `output_dir` | `"./downloads"` | Output directory for received files |

#### Methods

| Method | Description |
|---|---|
| `start()` | Start the server (non-blocking) |
| `stop()` | Stop the server, close all connections |
| `on_event(callback)` | Register an event handler (see Events below) |

#### Properties

| Property | Description |
|---|---|
| `is_running` | `True` if the server is currently running |

### `NexoClient`

```python
from nexo.core import NexoClient

NexoClient().send("photo.jpg", "192.168.1.42", 9000)
```

#### Methods

| Method | Description |
|---|---|
| `send(filepath, target, port)` | Send a file to a remote server |

| Parameter | Description |
|---|---|
| `filepath` | Path to the file to send |
| `target` | Server hostname or IP |
| `port` | Server port |

### Legacy API

```python
from nexo.core import start_server, send_file

# Returns a NexoServer instance (same API: .on_event(), .stop())
server = start_server("0.0.0.0", 9000, Path("./downloads"), on_event=cb)

# Sends a file (blocking)
send_file("photo.jpg", "192.168.1.42", 9000)
```

---

## Events

The `on_event(callback)` method receives a callback with the signature:

```python
def handler(event_type: str, data: dict) -> None: ...
```

| Event | When | `data` keys |
|---|---|---|
| `server_start` | Server started | `host`, `port` |
| `file_start` | File transfer started | `filename`, `size`, `addr` |
| `file_progress` | Chunk received | `filename`, `received`, `size` |
| `file_done` | Transfer complete | `filename`, `received`, `size` |
| `file_abort` | Transfer aborted | `filename`, `received`, `size`, `reason` |

Example:
```python
def on_event(evt, data):
    if evt == "file_start":
        print(f"Receiving {data['filename']} ({data['size']} bytes)")
    elif evt == "file_progress":
        pct = int(data["received"] / data["size"] * 100)
        print(f"  {pct}%")
    elif evt == "file_done":
        print(f"Done: {data['filename']}")
    elif evt == "file_abort":
        print(f"Failed: {data['reason']}")

srv = NexoServer()
srv.on_event(on_event)
srv.start()
```

---

## Protocol

| Message | Code | Direction | Content |
|---|---|---|---|
| `FILE_META` | 201 | Client → Server | JSON: `filename`, `size`, `num_chunks`, `compression` |
| `FILE_ACK` | 204 | Server → Client | `"ready"` or `"done"` |
| `FILE_CHUNK` | 202 | Client → Server | `[4-byte BE seq][compressed/raw data]` |
| `FILE_DONE` | 203 | Client → Server | empty |
| `FILE_ERR` | 205 | Server → Client | error message string |

### Transfer Flow

1. Client sends `FILE_META` → waits for `FILE_ACK("ready")`
2. Client sends all chunks as `FILE_CHUNK` (with sequence numbers, fire-and-forget)
3. Client sends `FILE_DONE` → waits for `FILE_ACK("done")`
4. Server buffers chunks by sequence number, writes in order once all received
5. Server sends `FILE_ACK("done")` when the file is fully written

Compression: zlib level 1, applied per-chunk when file size ≥ 1 KB.

---
