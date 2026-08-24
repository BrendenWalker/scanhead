"""Deploy file contracts. No Docker required."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_compose_yaml_builds_locally_with_host_network():
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "network_mode: host" in text
    assert "build: ./app" in text
    assert "bluenviron/mediamtx" in text
    assert "SCANNER_IP" in text
    assert "./mediamtx.yml:/mediamtx.yml:ro" in text


def test_portainer_stack_pulls_published_image():
    text = (ROOT / "portainer-stack.yml").read_text(encoding="utf-8")
    env = (ROOT / "portainer-stack.env.example").read_text(encoding="utf-8")
    assert "network_mode: host" not in text
    assert "${APP_PORT:-8080}:8080" in text
    assert '"8888:8888"' in text
    assert '"8889:8889"' in text
    assert '"8189:8189/udp"' in text
    assert '"8189:8189/tcp"' not in text
    assert "DOCKER_HUB_REGISTRY_USERNAME" in text
    assert "IMAGE_TAG" in text
    assert "scanhead" in text
    assert "bluenviron/mediamtx" in text
    assert "MTX_PATHS_SCANNER_SOURCE" in text
    assert "RTSPTRANSPORT: tcp" in text
    assert "SCANNER_IP" in env
    assert "derpmhichurp" in env
    assert "IMAGE_TAG=latest" in env
    assert "WEBRTC_HOST" in env
