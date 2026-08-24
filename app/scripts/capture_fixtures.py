"""Capture live UDP fixtures from a scanner. Lab use only."""

from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

HOST = sys.argv[1] if len(sys.argv) > 1 else "scanner.plud.org"
PORT = 50536
ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def grab(sock: socket.socket, cmd: str, name: str, wait: float = 5.0) -> None:
    sock.sendto(f"{cmd}\r".encode("ascii"), (HOST, PORT))
    deadline = time.time() + wait
    pkts: list[bytes] = []
    while time.time() < deadline:
        sock.settimeout(max(0.2, deadline - time.time()))
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            break
        pkts.append(data)
        text = data.decode("utf-8", errors="replace")
        if "</ScannerInfo>" in text and cmd == "GSI":
            break
        if 'EOT="1"' in text:
            sock.settimeout(0.25)
            try:
                while True:
                    extra, _ = sock.recvfrom(65535)
                    pkts.append(extra)
            except socket.timeout:
                break
            break
    ROOT.mkdir(parents=True, exist_ok=True)
    for i, pkt in enumerate(pkts, 1):
        path = ROOT / f"{name}_{i:02d}.bin"
        path.write_bytes(pkt)
        print(f"{path.name} {len(pkt)}")


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        grab(sock, "GSI", "gsi", wait=3.0)
        grab(sock, "GLT,FL", "glt_fl", wait=3.0)
        grab(sock, "GLT,SYS,0", "glt_sys", wait=6.0)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
