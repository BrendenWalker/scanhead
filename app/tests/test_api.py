from fastapi.testclient import TestClient

from scanhead import __version__
from scanhead.config import Settings
from scanhead.main import create_app
from scanhead.protocol import Target
from scanhead.radio import RadioError

from tests.fakes import FakeRadio


def _client(radio: FakeRadio | None = None) -> tuple[TestClient, FakeRadio]:
    radio = radio or FakeRadio()
    app = create_app(Settings(scanner_ip="127.0.0.1"), radio=radio)
    return TestClient(app), radio


def test_health_and_config():
    with _client()[0] as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        body = health.json()
        assert body["ok"] is True
        assert body["model"] == "BCD536HP"
        assert body["scanner"] == "127.0.0.1:50536"

        config = client.get("/api/config")
        assert config.status_code == 200
        data = config.json()
        assert data["volMax"] == 29
        assert data["sqlMax"] == 19
        assert data["keys"]["E"] == "Yes / Enter"
        assert data["whepUrl"].endswith(":8889/scanner/whep")
        assert data["hlsUrl"].endswith(":8888/player/index.m3u8")
        assert data["rtspUrl"].endswith(":8554/player")
        assert data["appVersion"] == __version__
        assert "SCN_MODE" in data["jumpModes"]
        assert "TOP" in data["menuIds"]


def test_favicon_served():
    with _client()[0] as client:
        svg = client.get("/static/favicon.svg")
        assert svg.status_code == 200
        assert "svg" in svg.headers.get("content-type", "")
        ico = client.get("/favicon.ico")
        assert ico.status_code == 200


def test_index_served():
    with _client()[0] as client:
        res = client.get("/")
        assert res.status_code == 200
        assert "ScanHead" in res.text


def test_status_and_key():
    radio = FakeRadio()
    with _client(radio)[0] as client:
        status = client.get("/api/status")
        assert status.status_code == 200
        assert status.json()["mode"] == "Scan Mode"
        assert ("snapshot", False) in radio.calls

        key = client.post("/api/key", json={"code": "E", "mode": "P"})
        assert key.status_code == 200
        assert ("key", "E", "P") in radio.calls


def test_vol_sql_roundtrip():
    radio = FakeRadio()
    with _client(radio)[0] as client:
        assert client.get("/api/vol").json()["level"] == 3
        assert client.post("/api/vol", json={"level": 12}).json()["level"] == 12
        assert ("vol", 12) in radio.calls
        assert client.post("/api/sql", json={"level": 8}).json()["level"] == 8


def test_hold_next_prev_avoid():
    radio = FakeRadio()
    with _client(radio)[0] as client:
        assert client.post("/api/hold", json={"tkw": "SYS", "xxx1": "1", "xxx2": ""}).status_code == 200
        hold = [call for call in radio.calls if call[0] == "hold"][-1]
        assert hold[1] == Target("SYS", "1", "")

        assert client.post("/api/next", json={"tkw": "SYS", "xxx1": "1", "count": 2}).status_code == 200
        nxt = [call for call in radio.calls if call[0] == "next"][-1]
        assert nxt[2] == 2

        assert client.post("/api/prev", json={"tkw": "SYS", "xxx1": "1"}).status_code == 200

        missing = client.post("/api/avoid", json={"tkw": "SYS", "xxx1": "1"})
        assert missing.status_code == 400

        no_target = client.post("/api/hold", json={})
        assert no_target.status_code == 400
        assert "target" in no_target.json()["detail"].lower()

        ok = client.post("/api/avoid", json={"tkw": "SYS", "xxx1": "1", "status": 2})
        assert ok.status_code == 200
        avoid = [call for call in radio.calls if call[0] == "avoid"][-1]
        assert avoid[1] == 2


def test_channel_actions_use_posted_target_not_radio_status():
    radio = FakeRadio()
    radio.status = {
        "channelTag": "TGID",
        "channel": {"Index": "91712"},
        "department": {"Index": "91602"},
        "target": {"tkw": "TGID", "xxx1": "91712", "xxx2": "91602"},
    }
    displayed = {"tkw": "CFREQ", "xxx1": "25535", "xxx2": ""}
    with _client(radio)[0] as client:
        assert client.post("/api/hold", json=displayed).status_code == 200
        assert client.post("/api/next", json=displayed).status_code == 200
        assert client.post("/api/prev", json=displayed).status_code == 200
        assert client.post("/api/avoid", json={**displayed, "status": 2}).status_code == 200
        assert [call for call in radio.calls if call[0] == "hold"][-1][1] == Target("CFREQ", "25535", "")
        assert [call for call in radio.calls if call[0] == "next"][-1][1] == Target("CFREQ", "25535", "")
        assert [call for call in radio.calls if call[0] == "prev"][-1][1] == Target("CFREQ", "25535", "")
        assert [call for call in radio.calls if call[0] == "avoid"][-1][2] == Target("CFREQ", "25535", "")
        for act in ("hold", "next", "prev"):
            assert client.post(f"/api/{act}", json={}).status_code == 400
        assert client.post("/api/avoid", json={"status": 2}).status_code == 400


def test_lists_quick_keys_and_jumps():
    radio = FakeRadio()
    with _client(radio)[0] as client:
        lists = client.get("/api/lists/FL")
        assert lists.status_code == 200
        assert lists.json()["items"][0]["Name"] == "Reno"
        assert ("glt", "FL", None, 15.0) in radio.calls

        child = client.get("/api/lists/SYS", params={"parent": "0"})
        assert child.status_code == 200
        assert ("glt", "SYS", "0", 15.0) in radio.calls

        fqk = client.get("/api/qk/fqk")
        assert fqk.status_code == 200
        values = [0] * 100
        values[0] = 2
        assert client.post("/api/qk/fqk", json={"values": values}).status_code == 200

        assert client.post("/api/jnt", json={"fl": 0, "sys": 1, "chan": 2}).status_code == 200
        assert client.post("/api/jpm", json={"mode": "SCN_MODE"}).status_code == 200
        assert ("jump_mode", "SCN_MODE", "") in radio.calls


def test_menu_replay_clock_location():
    radio = FakeRadio()
    with _client(radio)[0] as client:
        entered = client.post("/api/menu", json={"menu_id": "TOP"})
        assert entered.status_code == 200
        assert entered.json()["name"] == "TOP"
        assert ("menu_enter", "TOP", "") in radio.calls

        assert client.get("/api/menu").json()["name"] == "TOP"
        assert client.post("/api/menu/value", json={"value": "a,b"}).status_code == 200
        assert ("menu_set", "a,b") in radio.calls

        back = client.post("/api/menu/back", json={"level": "RETURN_PREVOUS_MODE"})
        assert back.status_code == 200
        assert back.json() == {"exited": True}

        assert client.post("/api/replay", json={"start": True}).status_code == 200
        assert ("record", True) in radio.calls
        assert client.get("/api/clock").status_code == 200
        assert client.get("/api/location").status_code == 200
        assert client.get("/api/svc").status_code == 200


def test_radio_error_is_502():
    radio = FakeRadio()
    radio.fail = RadioError("timeout waiting for GSI")
    with _client(radio)[0] as client:
        res = client.get("/api/status")
        assert res.status_code == 502
        assert "timeout" in res.json()["detail"]


def test_websocket_pushes_status():
    with _client()[0] as client:
        with client.websocket_connect("/api/ws") as ws:
            payload = ws.receive_json()
            assert payload["mode"] == "Scan Mode"
