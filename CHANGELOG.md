# Changelog

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
