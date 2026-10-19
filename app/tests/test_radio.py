import asyncio

import pytest

from scanhead.protocol import Target
from scanhead.radio import Radio, RadioError
from scanhead.xmlutil import XmlAssembler, flatten_glt, parse_xml, split_frame


class FakeScannerProtocol(asyncio.DatagramProtocol):
    def __init__(self, replies: dict[str, list[bytes]]):
        self.replies = replies
        self.transport = None
        self.received: list[str] = []

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        cmd = data.decode("ascii").strip().rstrip("\r")
        self.received.append(cmd)
        name = cmd.split(",", 1)[0]
        if cmd in self.replies:
            packets = self.replies[cmd]
        elif name in self.replies:
            packets = self.replies[name]
        else:
            self.transport.sendto(f"{name},NG\r".encode(), addr)
            return
        if packets is None:
            return
        for packet in packets:
            self.transport.sendto(packet, addr)


async def _serve(replies: dict[str, list[bytes]]):
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: FakeScannerProtocol(replies),
        local_addr=("127.0.0.1", 0),
    )
    port = transport.get_extra_info("sockname")[1]
    return transport, port, protocol


def _identify():
    return {
        "MDL": [b"MDL,BCD536HP\r"],
        "VER": [b"VER,Version 1.28.14\r"],
        "PSI,0": [b"PSI,OK\r"],
        "PSI,500": [b"PSI,OK\r"],
    }


async def _mdl_and_gsi():
    gsi = (
        b'GSI,<XML>,\r<?xml version="1.0" encoding="utf-8"?>\r'
        b'<ScannerInfo Mode="Scan Mode" V_Screen="conventional_scan">'
        b'<Property VOL="3" SQL="11" Mute="Unmute" Sig="2" Rssi="1.2" />'
        b'<System Name="Test" Index="1" Hold="Off" />'
        b"</ScannerInfo>\r"
    )
    replies = {**_identify(), "GSI": [gsi]}
    server, port, _ = await _serve(replies)
    radio = Radio("127.0.0.1", port, timeout_s=2)
    try:
        await radio.start()
        assert radio.model == "BCD536HP"
        status = await radio.gsi()
        assert status["property"]["VOL"] == "3"
        assert status["system"]["Name"] == "Test"
        assert status["target"] == {"tkw": "SYS", "xxx1": "1", "xxx2": ""}
    finally:
        await radio.close()
        server.close()


async def _glt_multipart():
    pkt1 = (
        b'GLT,<XML>,\r<?xml version="1.0" encoding="utf-8"?>\r<GLT>'
        b'<FL Index="0" Name="Reno" />'
        b'<Footer No="1" EOT="0"/></GLT>\r'
    )
    pkt2 = (
        b'GLT,<XML>,\r<?xml version="1.0" encoding="utf-8"?>\r<GLT>'
        b'<FL Index="1" Name="Other" />'
        b'<Footer No="2" EOT="1"/></GLT>\r'
    )
    replies = {**_identify(), "GLT,FL": [pkt1, pkt2]}
    server, port, _ = await _serve(replies)
    radio = Radio("127.0.0.1", port, timeout_s=2)
    try:
        await radio.start()
        glt = await radio.glt("FL")
        assert [item["Name"] for item in glt["items"]] == ["Reno", "Other"]
    finally:
        await radio.close()
        server.close()


async def _key_vol_hold_and_ng():
    replies = {
        **_identify(),
        "KEY,E,P": [b"KEY,OK\r"],
        "VOL": [b"VOL,4\r"],
        "VOL,12": [b"VOL,OK\r"],
        "HLD,SYS,1,": [b"HLD,OK\r"],
    }
    server, port, proto = await _serve(replies)
    radio = Radio("127.0.0.1", port, timeout_s=2)
    try:
        await radio.start()
        assert await radio.key("E", "P") == ["KEY", "OK"]
        assert await radio.vol() == 4
        replies["VOL"] = [b"VOL,12\r"]
        assert await radio.vol(12) == 12
        assert await radio.hold(Target("SYS", "1", "")) == ["HLD", "OK"]
        with pytest.raises(RadioError, match="NG"):
            await radio.command("NADA", expect_xml=False)
        assert "KEY,E,P" in proto.received
        assert "HLD,SYS,1," in proto.received
    finally:
        await radio.close()
        server.close()


async def _psi_broadcast():
    psi = (
        b'PSI,<XML>,\r<?xml version="1.0" encoding="utf-8"?>\r'
        b'<ScannerInfo Mode="Scan Mode">'
        b'<Property VOL="9" />'
        b'<System Name="PSI Sys" Index="2" />'
        b"</ScannerInfo>\r"
    )
    replies = {**_identify(), "PSI,500": [b"PSI,OK\r", psi]}
    server, port, _ = await _serve(replies)
    radio = Radio("127.0.0.1", port, timeout_s=2, psi_interval_ms=500)
    try:
        await radio.start()
        queue = radio.subscribe()
        await radio.psi_start(500)
        payload = await asyncio.wait_for(queue.get(), 2)
        assert payload["source"] == "PSI"
        assert payload["property"]["VOL"] == "9"
        assert payload["target"]["tkw"] == "SYS"
        assert radio.psi_age_s() is not None
        snap = await radio.snapshot()
        assert snap["property"]["VOL"] == "9"
    finally:
        await radio.close()
        server.close()


def test_radio_mdl_and_gsi():
    asyncio.run(_mdl_and_gsi())


def test_radio_glt_multipart():
    asyncio.run(_glt_multipart())


def test_radio_key_vol_hold_and_ng():
    asyncio.run(_key_vol_hold_and_ng())


def test_radio_psi_broadcast():
    asyncio.run(_psi_broadcast())


def test_radio_rejects_bad_args():
    radio = Radio("127.0.0.1", 9)

    async def _run():
        with pytest.raises(RadioError, match="unknown GLT"):
            await radio.glt("NOPE")
        with pytest.raises(RadioError, match="parent"):
            await radio.glt("SYS")
        with pytest.raises(RadioError, match="key mode"):
            await radio.key("E", "X")
        with pytest.raises(RadioError, match="avoid status"):
            await radio.avoid(9)
        with pytest.raises(RadioError, match="jump mode"):
            await radio.jump_mode("NOT_A_MODE")
        with pytest.raises(RadioError, match="100 entries"):
            await radio.quick_keys("FQK", values=[1, 2])

    asyncio.run(_run())


def test_unreachable_radio_records_last_error():
    async def _run():
        radio = Radio("127.0.0.1", 1, timeout_s=0.2)
        await radio.start()
        assert radio.model == ""
        assert radio.last_error == "timeout waiting for MDL"
        await radio.close()

    asyncio.run(_run())


def test_snapshot_fails_fast_after_recent_timeout():
    async def _run():
        radio = Radio("127.0.0.1", 1, timeout_s=5)
        radio.last_error = "timeout waiting for MDL"
        radio._error_at = __import__("time").monotonic()
        with pytest.raises(RadioError, match="timeout waiting for MDL"):
            await radio.snapshot(force=True)

    asyncio.run(_run())


def test_successful_command_clears_last_error():
    async def _run():
        replies = {**_identify()}
        server, port, _ = await _serve(replies)
        radio = Radio("127.0.0.1", port, timeout_s=2)
        try:
            radio.last_error = "timeout waiting for MDL"
            await radio.start()
            assert radio.model == "BCD536HP"
            assert radio.last_error is None
        finally:
            await radio.close()
            server.close()

    asyncio.run(_run())


async def _close_goodbye_logs_reply(caplog):
    replies = _identify()
    server, port, proto = await _serve(replies)
    radio = Radio("127.0.0.1", port, timeout_s=2)
    try:
        await radio.start()
        with caplog.at_level("INFO", logger="scanhead.radio"):
            await radio.close()
        assert "PSI,0" in proto.received
        assert any("control goodbye: PSI,0 sent, reply=" in r.message for r in caplog.records)
        assert radio._transport is None
        await radio.close()  # idempotent
    finally:
        server.close()


async def _close_goodbye_logs_no_reply(caplog):
    replies = {**_identify(), "PSI,0": None}
    server, port, proto = await _serve(replies)
    radio = Radio("127.0.0.1", port, timeout_s=2)
    try:
        await radio.start()
        with caplog.at_level("INFO", logger="scanhead.radio"):
            await radio.close()
        assert "PSI,0" in proto.received
        assert any("control goodbye: PSI,0 sent, no reply" in r.message for r in caplog.records)
        assert radio._transport is None
    finally:
        server.close()


async def _close_preempts_in_flight_command(caplog):
    replies = {**_identify(), "GSI": None}
    server, port, proto = await _serve(replies)
    radio = Radio("127.0.0.1", port, timeout_s=8)
    try:
        await radio.start()
        hung = asyncio.create_task(radio.command("GSI", expect_xml=True, timeout=8.0))
        for _ in range(50):
            if radio._pending is not None:
                break
            await asyncio.sleep(0.01)
        assert radio._pending is not None
        with caplog.at_level("INFO", logger="scanhead.radio"):
            await asyncio.wait_for(radio.close(), timeout=3.0)
        assert "PSI,0" in proto.received
        assert any("control goodbye:" in r.message for r in caplog.records)
        with pytest.raises(RadioError):
            await hung
    finally:
        server.close()


def test_radio_close_goodbye_logs_reply(caplog):
    asyncio.run(_close_goodbye_logs_reply(caplog))


def test_radio_close_goodbye_logs_no_reply(caplog):
    asyncio.run(_close_goodbye_logs_no_reply(caplog))


def test_radio_close_preempts_in_flight_command(caplog):
    asyncio.run(_close_preempts_in_flight_command(caplog))


def test_assembler_exported():
    assembler = XmlAssembler()
    frame = split_frame(
        b'GLT,<XML>,\r<?xml version="1.0"?><GLT><FL Name="A"/><Footer No="1" EOT="1"/></GLT>\r'
    )
    merged = assembler.add(frame.xml)
    assert flatten_glt(parse_xml(merged))["items"][0]["Name"] == "A"
