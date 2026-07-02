# Changelog

## 1.2.0 : 2026-07-02

### Fixed

- **"Transfer complete" spam** — no longer logged after every file in a directory transfer (only `dir_done` triggers it)
- **"Sending 100%" before ACK** — progress capped at 99% until the server confirms; status jumps to "Done" on real completion
- **Python 3.8 crash** — `collections.abc.Callable` is not subscriptable on 3.8; switched to `typing.Callable`

### Added

- **Progress bar** — restored in the Send tab (between stats and treeview), shows current file's progress

## 1.1.0 : 2026-07-02

### Added

- **Directory transfer** — `send-dir` CLI command, `send_directory()` API, `DIR_TREE`/`DIR_END` protocol messages
- **Progress callback** — `on_progress(current, total, label)` on both `send()` and `send_directory()`
- **GUI Send tab treeview** — replaced progress bar with a full table (file, size, status) + log pane, matching the Receive tab
- **GUI Cancel button** — abort an ongoing transfer cleanly
- **Transfer speed stats** — live speed (MB/s), byte count, and file progress shown in both Send and Receive tabs
- **GUI folder picker** — File/Directory radio toggle on Send tab
- **Auto-scroll** — Receive tab treeview scrolls to the latest entry

### Changed

- **Chunk size** — 64 KB → **1 MB**; Veltix buffer `LARGE` → `HUGE` for higher throughput
- **Directory progress** — now reports per-chunk byte progress (like single files) instead of per-file index
- **Log verbosity** — Receive tab no longer logs every file start/done (treeview suffices); shows only "Transfer complete" / errors
- **Veltix** — bumped dependency to `>=1.7.5` (fixes SO_REUSEPORT on Windows, async backend default)

### Fixed

- **Zero-byte file crash** — `ZeroDivisionError` in receive progress when `size == 0`
- **Python 3.8 compat** — `dict[str, str]` annotation now guarded with `from __future__ import annotations`

## 1.0.0-beta : 2026-07-01

### Added

- **Python 3.14 support** — tested and compatible with latest Python release
- **Directory transfer** — new `send-dir` CLI command and `send_directory()` API ; sends a `DIR_TREE` with the full
  structure, then each file individually via the existing chunked mechanism (`DIR_TREE`/`DIR_END` messages)
- **Progress tracking** — `on_progress` callback on both `send()` and `send_directory()` for real-time UI updates
- **GUI folder picker** — SendTab now has a File/Directory radio toggle ; Browse adapts to mode

### Changed

- **Migrated from Veltix 1.6.4 to 1.7.5** — full API compatibility pass:
  - Route handler signatures corrected from `(response, client)` to `(client, response)`
  - `ClientInfo.tags` direct access replaced with `add_tag()` / `get_tag()` / `remove_tag()` API
  - Client-side `on_ack` callback simplified (removed unused `_client` parameter)
- **Log level reduced** — default from `DEBUG` to `INFO` for quieter output
- **PyPI package name** — `nexo_transfert` (install with `pip install nexo-transfert`)

### Fixed

- **6 route handlers** had inverted `client`/`response` arguments — caused `AttributeError` on every message
- **Per-client tag writes silently lost** — `client.tags["x"] = y` wrote to a dict copy; now uses the proper lock-safe API
- **Directory transfer file path** — files in subdirectories were saved directly under output dir instead of preserving
  the parent folder structure ; fixed by resolving paths through `dir_root`
- **Linter** — 13 `F401` warnings silenced with proper ruff config for `__init__.py` re-exports
- **Test file** — removed unnecessary `sys.path.insert(0, ...)` hack

### Security

- **Veltix 1.7.2** brings thread-safe tag locking, socket cleanup on reconnect, and handshake state protection

## 0.0.3 : 2026-05-09

### Added

- `nexo/__main__.py` — allows `python -m nexo` as an alternative to the installed `nexo` command

## 0.0.2 : 2026-05-09

### Added
- `NexoServer` class: `start()`, `stop()` (alias `close_all()`), `on_event()`, `is_running`
- `NexoClient` class: `send(filepath, target, port)`
- `Transfer` class: public API for tracking incoming file transfers
- Robust concurrent transfer handling via unordered chunk buffering with sequence numbers
- Per-transfer `threading.Lock` for safe concurrent chunk ingestion
- DONE acknowledgment is deferred until all chunks are received and written in order

### Changed
- Server handler rewritten from functional `on_recv` callback to `@server.route()` decorators
- Chunks now include a 4-byte big-endian sequence number prefix
- `start_server()` / `send_file()` kept as backward-compatible wrappers
- `core/__init__.py` exports `NexoServer`, `NexoClient`, `start_server`, `send_file`

### Fixed
- Race condition when multiple files are transferred concurrently: chunks and DONE
  messages could be processed out of order by Veltix's thread pool, causing incomplete
  or corrupted files. Fixed by buffering incoming chunks by sequence number and
  deferring the DONE response until all chunks have been received and written
  sequentially.

## 0.0.1 : 2026-05-08

### Added
- Initial release
- CLI commands: `nexo serve`, `nexo send`, `nexo gui`
- Core protocol: `FILE_META`, `FILE_CHUNK`, `FILE_DONE`, `FILE_ACK`, `FILE_ERR`
- Server with per-client serialised queue processing
- Client with zlib compression (level 1, files ≥ 1 KB) and chunked sending
- Tkinter GUI with dark theme, live transfer logs, receive and send tabs
- Published on PyPI as `nexo-transfert`
