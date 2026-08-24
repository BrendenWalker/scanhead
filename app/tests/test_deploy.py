"""Deploy file contracts. No Docker required."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_compose_yaml_builds_locally_with_host_network():
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "network_mode: host" in text
    assert "build: ./app" in text
    assert "bluenviron/mediamtx" in text
    assert "SCANNER_IP" in text
    assert "SCANNER_RTSP_IP" in text
    assert "rtsp://${SCANNER_RTSP_IP" in text
    assert "./mediamtx.yml:/mediamtx.yml:ro" in text
    mtx = (ROOT / "mediamtx.yml").read_text(encoding="utf-8")
    assert "rtsp: true" in mtx
    assert ":8554" in mtx


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
    assert "MTX_PATHS_SCANNER_SOURCE" in text
    assert "au:scanner.au" in text
    # Uniden OPTIONS returns 400 if the RTSP URL host is a DNS name.
    assert "SCANNER_RTSP_IP" in text
    assert "rtsp://${SCANNER_RTSP_IP" in text
    assert "SCANNER_IP" in env
    assert "SCANNER_RTSP_IP" in env
    assert "derpmhichurp" in env
    assert "IMAGE_TAG=latest" in env
    assert "WEBRTC_HOST" in env
