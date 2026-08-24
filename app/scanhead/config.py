from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    scanner_ip: str
    scanner_port: int = 50536
    app_port: int = 8080
    psi_interval_ms: int = 500
    mediamtx_whep_port: int = 8889
    mediamtx_hls_port: int = 8888
    mediamtx_rtsp_port: int = 8554
    command_timeout_s: float = 8.0
    glt_timeout_s: float = 15.0


def load_settings() -> Settings:
    ip = os.environ.get("SCANNER_IP", "").strip()
    if not ip:
        raise RuntimeError("SCANNER_IP is required")
    return Settings(
        scanner_ip=ip,
        scanner_port=int(os.environ.get("SCANNER_PORT", "50536")),
        app_port=int(os.environ.get("APP_PORT", "8080")),
        psi_interval_ms=int(os.environ.get("PSI_INTERVAL_MS", "500")),
        mediamtx_whep_port=int(os.environ.get("MEDIAMTX_WHEP_PORT", "8889")),
        mediamtx_hls_port=int(os.environ.get("MEDIAMTX_HLS_PORT", "8888")),
        mediamtx_rtsp_port=int(os.environ.get("MEDIAMTX_RTSP_PORT", "8554")),
        command_timeout_s=float(os.environ.get("COMMAND_TIMEOUT_S", "8")),
        glt_timeout_s=float(os.environ.get("GLT_TIMEOUT_S", "15")),
    )
