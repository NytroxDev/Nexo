import argparse
import sys
from pathlib import Path
from typing import List, Optional

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from veltix import Logger, LoggerConfig, LogLevel
from nexo import cli


def main(argv: Optional[List[str]] = None) -> None:
    Logger.get_instance(LoggerConfig(
        level=LogLevel.INFO,
        show_caller=False,
    ))

    parser = argparse.ArgumentParser(prog="nexo")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Start a file server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=9000)
    serve.add_argument("-o", "--output", default="./downloads",
                       help="Output directory for received files")
    serve.set_defaults(func=lambda a: cli.serve(a.host, a.port, a.output))

    send = sub.add_parser("send", help="Send a file")
    send.add_argument("file", help="Path to the file to send")
    send.add_argument("--to", dest="target", required=True,
                      help="Target address (host:port)")
    send.set_defaults(func=lambda a: cli.send(a.file, a.target))

    send_dir = sub.add_parser("send-dir", help="Send a directory")
    send_dir.add_argument("directory", help="Path to the directory to send")
    send_dir.add_argument("--to", dest="target", required=True,
                          help="Target address (host:port)")
    send_dir.set_defaults(func=lambda a: cli.send_dir(a.directory, a.target))

    gui = sub.add_parser("gui", help="Launch the graphical interface")
    gui.set_defaults(func=lambda a: cli.gui())

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
