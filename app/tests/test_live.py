"""Optional live checks against a reachable scanner. Enable with SCANHEAD_LIVE=1."""

from __future__ import annotations

import os
import socket

import pytest

HOST = os.environ.get("SCANHEAD_LIVE_HOST", "scanner.plud.org")
PORT = int(os.environ.get("SCANHEAD_LIVE_PORT", "50536"))

pytestmark = pytest.mark.skipif(os.environ.get("SCANHEAD_LIVE") != "1", reason="set SCANHEAD_LIVE=1")


def _cmd(cmd: str, timeout: float = 3.0) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(f"{cmd}\r".encode("ascii"), (HOST, PORT))
        data, _ = sock.recvfrom(65535)
        return data.decode("utf-8", errors="replace")
    finally:
        sock.close()


def test_live_mdl_ver():
    assert "BCD536HP" in _cmd("MDL") or "SDS" in _cmd("MDL")
    assert _cmd("VER").startswith("VER,")


def test_live_gsi_xml():
    text = _cmd("GSI")
    assert "ScannerInfo" in text
    assert "Property" in text
