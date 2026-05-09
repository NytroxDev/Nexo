# Nexo

Fast and reliable local file transfer powered by [Veltix](https://github.com/NytroxDev/Veltix).

[![License](https://img.shields.io/github/license/NytroxDev/Nexo)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/nexo-transfert)](https://pypi.org/project/nexo-transfert/)

Nexo is a lightweight file transfer tool designed for local networks. Built on Veltix's high-performance TCP stack, it lets you send files between machines with zero setup — just run and go.

Two modes, same speed: a **CLI** for power users and a **Tkinter GUI** for everyone else.

---

## Why Nexo?

Moving files between machines on the same network shouldn't require a USB drive, cloud upload, or SSH config. Nexo is made for the LAN — instant transfers, no fuss.

---

## Features

- **LAN-optimized** : built for local network transfers between machines
- **CLI + GUI** : use the terminal or the Tkinter interface
- **Dead simple** : no config files, no daemons, no setup
- **Concurrent transfers** : send multiple files simultaneously without corruption
- **Zlib compression** : automatic compression for files ≥ 1 KB
- **Dark-themed GUI** : clean Tkinter interface with live transfer logs
- **Python 3.8+** : same compatibility as Veltix

---

## Quick Start

```bash
pip install nexo-transfert
```

### Receive files (on machine B)

```bash
# CLI
nexo serve --port 9000

# Or with the GUI
nexo gui
```

### Send a file (from machine A)

```bash
nexo send myfile.txt --to 192.168.1.42:9000
```

---

 ## How It Works

1. The receiver starts a Nexo server (CLI or GUI)
2. The sender connects and pushes the file in chunks (with zlib compression)
3. Chunks include sequence numbers: the server buffers and orders them regardless of arrival order
4. Once all chunks are received, the server writes them sequentially and acknowledges the transfer
5. This allows multiple concurrent transfers without locks or serialisation

---

## API

```python
from nexo.core import NexoServer, NexoClient

# Server
srv = NexoServer(host="0.0.0.0", port=9000, output_dir="./downloads")
srv.on_event(lambda evt, data: print(evt, data))
srv.start()
srv.stop()  # or srv.close_all()

# Client
NexoClient().send("photo.jpg", "192.168.1.42", 9000)
```

Full CLI and API reference: **[GUIDE.md](GUIDE.md)**

Changelog: **[CHANGELOG.md](CHANGELOG.md)**

---

## License

[MIT](LICENSE) — Copyright (c) 2026 Nytrox
