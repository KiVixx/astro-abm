from __future__ import annotations

import argparse
import socket
from collections.abc import Sequence


def port_is_available(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as candidate:
        # Match development servers that can safely reclaim a recently closed port.
        candidate.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            candidate.bind((host, port))
        except OSError:
            return False
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check whether a local development port is available.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--service", required=True)
    parser.add_argument("--retry-command", required=True)
    args = parser.parse_args(argv)

    if port_is_available(args.host, args.port):
        return 0

    print(
        f"Cannot start {args.service}: {args.host}:{args.port} is already in use.\n"
        f"Use another port, for example:\n  {args.retry_command}"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
