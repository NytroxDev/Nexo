import signal
import time
from pathlib import Path

from veltix import Logger

from nexo.core import start_server


def serve(host: str, port: int, output: str) -> None:
    logger = Logger.get_instance()

    output_dir = Path(output)
    server = start_server(host, port, output_dir)
    logger.info(f"Server listening on {host}:{port}, saving to {output_dir.resolve()}")
    logger.info("Press Ctrl+C to stop")

    shutdown = False

    def _signal(sig, frame):
        nonlocal shutdown
        if shutdown:
            return
        shutdown = True
        logger.info("Shutting down...")
        server.close_all()

    signal.signal(signal.SIGINT, _signal)
    signal.signal(signal.SIGTERM, _signal)

    try:
        signal.pause()
    except AttributeError:
        while not shutdown:
            time.sleep(0.5)
