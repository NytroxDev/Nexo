# Nexo

Fast and reliable local file transfer powered by [Veltix](https://github.com/NytroxDev/Veltix).

[![License](https://img.shields.io/github/license/NytroxDev/Nexo)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)

Nexo is a lightweight file transfer tool designed for local networks. Built on Veltix's high-performance TCP stack, it lets you send files between machines with zero setup — just run and go.

Two modes, same speed: a **CLI** for power users and a **Tkinter GUI** for everyone else.

---

## Why Nexo?

Moving files between machines on the same network shouldn't require a USB drive, cloud upload, or SSH config. Nexo is made for the LAN — instant transfers, no fuss.

No encryption overhead (yet — will follow Veltix's TLS support when it lands). Just raw speed and simplicity.

---

## Features

- **LAN-optimized** — built for local network transfers between machines
- **CLI + GUI** — use the terminal or the Tkinter interface
- **Dead simple** — no config files, no daemons, no setup
- **Fast** — leverages Veltix's 110k+ msg/s throughput
- **Integrity checks** — CRC32 verification on every chunk
- **Python 3.8+** — same compatibility as Veltix

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
2. The sender connects and pushes the file in chunks
3. Each chunk is verified with CRC32 before the next one is sent
4. The receiver reassembles and saves the file

Both push (send to a server) and pull (list and download from a server) are supported.

---

## License

[MIT](LICENSE) — Copyright (c) 2026 Nytrox
