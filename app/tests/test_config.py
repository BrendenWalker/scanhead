import pytest

from scanhead import __version__
from scanhead.config import load_settings


def test_load_settings_requires_scanner_ip(monkeypatch):
    monkeypatch.delenv("SCANNER_IP", raising=False)
    with pytest.raises(RuntimeError, match="SCANNER_IP"):
        load_settings()


def test_load_settings_defaults(monkeypatch):
    monkeypatch.setenv("SCANNER_IP", "scanner.plud.org")
    monkeypatch.delenv("SCANNER_PORT", raising=False)
    monkeypatch.delenv("APP_PORT", raising=False)
    monkeypatch.delenv("PSI_INTERVAL_MS", raising=False)
    monkeypatch.delenv("SCANHEAD_VERSION", raising=False)
    settings = load_settings()
    assert settings.scanner_ip == "scanner.plud.org"
    assert settings.scanner_port == 50536
    assert settings.app_port == 8080
    assert settings.psi_interval_ms == 500
    assert settings.mediamtx_whep_port == 8889
    assert settings.mediamtx_hls_port == 8888
    assert settings.mediamtx_rtsp_port == 8554
    assert settings.app_version == __version__


def test_load_settings_overrides(monkeypatch):
    monkeypatch.setenv("SCANNER_IP", "192.168.42.10")
    monkeypatch.setenv("SCANNER_PORT", "50537")
    monkeypatch.setenv("APP_PORT", "9090")
    monkeypatch.setenv("PSI_INTERVAL_MS", "250")
    monkeypatch.setenv("COMMAND_TIMEOUT_S", "3.5")
    settings = load_settings()
    assert settings.scanner_ip == "192.168.42.10"
    assert settings.scanner_port == 50537
    assert settings.app_port == 9090
    assert settings.psi_interval_ms == 250
    assert settings.command_timeout_s == 3.5


def test_load_settings_app_version_from_env(monkeypatch):
    monkeypatch.setenv("SCANNER_IP", "127.0.0.1")
    monkeypatch.setenv("SCANHEAD_VERSION", "1.2.3")
    settings = load_settings()
    assert settings.app_version == "1.2.3"
