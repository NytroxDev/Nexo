"""Transfer tests — validates buffered unordered chunks + deferred DONE."""

import hashlib
import os
import socket
import tempfile
import threading
import time
from pathlib import Path

from nexo.core.server import start_server
from nexo.core.client import send_file

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 19870


def _wait_for_port(host: str, port: int, timeout: float = 5.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.05)
    return False


def test_concurrent_transfers():
    n = 8
    file_size = 512 * 1024

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "received"
        src = Path(tmp) / "source"
        src.mkdir()

        files = []
        for i in range(n):
            p = src / f"f{i}.bin"
            p.write_bytes(os.urandom(file_size))
            files.append((p.name, hashlib.sha256(p.read_bytes()).hexdigest()))

        srv = start_server(SERVER_HOST, SERVER_PORT, out)
        assert _wait_for_port(SERVER_HOST, SERVER_PORT), \
            "server did not start in time"

        errs = []

        def _send(p):
            try:
                result = send_file(str(p), SERVER_HOST, SERVER_PORT)
                if result is None:
                    errs.append((p.name, "send_file returned None"))
            except Exception as e:
                errs.append((p.name, e))

        threads = [threading.Thread(target=_send, args=(src / f[0],)) for f in files]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        srv.close_all()
        time.sleep(0.2)

        assert not errs, f"Errors: {errs}"
        missing = [n for n, _ in files if not (out / n).exists()]
        mismatch = [
            (n, h)
            for n, h in files
            if (out / n).exists()
            and hashlib.sha256((out / n).read_bytes()).hexdigest() != h
        ]
        assert not missing, f"Missing: {missing}"
        assert not mismatch, f"Mismatch: {mismatch}"
        total = n * file_size / 1024 / 1024
        print(f"OK — {n} files ({total:.1f} MB)")


if __name__ == "__main__":
    test_concurrent_transfers()
