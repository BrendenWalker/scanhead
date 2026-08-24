"""Deploy file contracts. No Docker required."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

AUDIO_FILTER = (
    "highpass=f=200,"
    "agate=threshold=0.03:ratio=10:attack=5:release=150:range=0.002,"
    "acompressor=threshold=0.1:ratio=6:attack=10:release=200:makeup=4"
)


def test_compose_yaml_builds_locally_with_host_network():
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "network_mode: host" in text
    assert "build: ./app" in text
    assert "bluenviron/mediamtx" in text
    assert "${MEDIAMTX_TAG:-1-ffmpeg}" in text
    assert "SCANNER_IP" in text
    assert "SCANNER_RTSP_IP" in text
    assert "rtsp://${SCANNER_RTSP_IP" in text
    assert "./mediamtx.yml:/mediamtx.yml:ro" in text
    assert "MTX_PATHS_RAW_SOURCE" in text
    assert "MTX_PATHS_SCANNER_SOURCE" not in text
    mtx = (ROOT / "mediamtx.yml").read_text(encoding="utf-8")
    assert "rtsp: true" in mtx
    assert ":8554" in mtx


def test_mediamtx_gates_and_compresses_before_scanner_path():
    mtx = (ROOT / "mediamtx.yml").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "\n  raw:" in mtx
    assert "runOnAvailable:" in mtx
    assert "runOnAvailableRestart: yes" in mtx
    assert AUDIO_FILTER in mtx
    assert "ffmpeg" in mtx
    assert "pcm_mulaw" in mtx
    assert "rtsp://127.0.0.1:8554/raw" in mtx
    assert "rtsp://127.0.0.1:8554/scanner" in mtx
    assert "source: publisher" in mtx
    assert "dynaudnorm" not in mtx
    assert "loudnorm" not in mtx
    assert "MTX_PATHS_RAW_SOURCE" in compose
    assert "1-ffmpeg" in env_example


def test_portainer_stack_pulls_published_image():
    text = (ROOT / "portainer-stack.yml").read_text(encoding="utf-8")
    env = (ROOT / "portainer-stack.env.example").read_text(encoding="utf-8")
    # Host networking hides mappings in Portainer/docker ps. Uniden rejects
    # interleaved TCP, so MediaMTX still pulls over UDP on the published ports.
    assert "network_mode: host" not in text
    assert "${APP_PORT:-8080}:8080" in text
    assert '"8554:8554"' in text
    assert '"8888:8888"' in text
    assert '"8889:8889"' in text
    assert '"8189:8189/udp"' in text
    assert '"8189:8189/tcp"' not in text
    assert "RTSPTRANSPORT: tcp" not in text
    assert "RTSPTRANSPORT: udp" in text
    assert 'MTX_RTSP: "yes"' in text
    assert "8554" in text
    assert "DOCKER_HUB_REGISTRY_USERNAME" in text
    assert "IMAGE_TAG" in text
    assert "scanhead" in text
    assert "bluenviron/mediamtx" in text
    assert "${MEDIAMTX_TAG:-1-ffmpeg}" in text
    assert "MTX_PATHS_RAW_SOURCE" in text
    assert "MTX_PATHS_RAW_RUNONAVAILABLE" in text
    assert "MTX_PATHS_RAW_RUNONAVAILABLERESTART" in text
    assert AUDIO_FILTER in text
    assert "pcm_mulaw" in text
    assert "MTX_PATHS_SCANNER_SOURCE: publisher" in text
    assert "au:scanner.au" in text
    # Uniden OPTIONS returns 400 if the RTSP URL host is a DNS name.
    assert "SCANNER_RTSP_IP" in text
    assert "rtsp://${SCANNER_RTSP_IP" in text
    assert "SCANNER_IP" in env
    assert "SCANNER_RTSP_IP" in env
    assert "derpmhichurp" in env
    assert "IMAGE_TAG=latest" in env
    assert "WEBRTC_HOST" in env
    assert "MEDIAMTX_TAG=1-ffmpeg" in env
