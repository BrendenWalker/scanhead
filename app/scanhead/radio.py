"""Async UDP client for one Uniden scanner (port 50536)."""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from scanhead import protocol
from scanhead.xmlutil import Frame, XmlAssembler, flatten_glt, flatten_menu, flatten_scanner_info, parse_xml, split_frame

log = logging.getLogger("scanhead.radio")

StatusHandler = Callable[[dict], None]


class RadioError(Exception):
    def __init__(self, message: str, fields: list[str] | None = None):
        super().__init__(message)
        self.fields = fields or []


@dataclass
class _Pending:
    cmd: str
    expect_xml: bool
    future: asyncio.Future
    assembler: XmlAssembler = field(default_factory=XmlAssembler)


class _Protocol(asyncio.DatagramProtocol):
    def __init__(self, radio: Radio):
        self.radio = radio

    def datagram_received(self, data: bytes, addr) -> None:  # noqa: ANN001
        self.radio._on_datagram(data, addr)


class Radio:
    def __init__(
        self,
        host: str,
        port: int = protocol.CONTROL_PORT,
        timeout_s: float = 8.0,
        psi_interval_ms: int = 500,
    ):
        self.host = host
        self.port = port
        self.timeout_s = timeout_s
        self.psi_interval_ms = psi_interval_ms
        self.model = ""
        self.version = ""
        self.status: dict = {}
        self._remote = (host, port)
        self._transport: asyncio.DatagramTransport | None = None
        self._lock = asyncio.Lock()
        self._pending: _Pending | None = None
        self._listeners: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._last_psi = 0.0
        self._psi_retry_at = 0.0
        self._watchdog: asyncio.Task | None = None

    def _send(self, payload: bytes) -> None:
        if self._transport is None:
            raise RadioError("radio is not connected")
        self._transport.sendto(payload)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        infos = await self._loop.getaddrinfo(
            self.host,
            self.port,
            family=socket.AF_INET,
            type=socket.SOCK_DGRAM,
        )
        self._remote = infos[0][4]
        transport, _ = await self._loop.create_datagram_endpoint(
            lambda: _Protocol(self),
            remote_addr=self._remote,
        )
        self._transport = transport
        try:
            mdl = await self.command("MDL")
            self.model = mdl.fields[1] if len(mdl.fields) > 1 else ""
            ver = await self.command("VER")
            self.version = ",".join(ver.fields[1:]) if len(ver.fields) > 1 else ""
            log.info("connected to %s (%s) at %s:%s", self.model, self.version, self.host, self.port)
        except Exception:
            log.exception("identify failed")

    async def close(self) -> None:
        if self._watchdog is not None:
            self._watchdog.cancel()
            self._watchdog = None
        try:
            await self.command("PSI,0", timeout=2.0)
        except Exception:
            pass
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=8)
        self._listeners.add(queue)
        if self.status:
            self._put(queue, self.status)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._listeners.discard(queue)

    def _put(self, queue: asyncio.Queue, item: dict) -> None:
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            pass

    def _broadcast(self, status: dict) -> None:
        self.status = status
        for queue in list(self._listeners):
            self._put(queue, status)

    def _on_datagram(self, data: bytes, addr) -> None:  # noqa: ANN001
        try:
            frame = split_frame(data)
        except Exception:
            log.exception("bad datagram from %s", addr)
            return
        pending = self._pending
        if frame.cmd == "PSI" and frame.is_xml:
            self._accept_psi(frame)
            return
        if pending is None or frame.cmd != pending.cmd:
            if frame.cmd != "PSI":
                log.debug("unsolicited %s from %s: %s", frame.cmd, addr, frame.fields[:4])
            return
        if pending.expect_xml and frame.is_xml:
            try:
                merged = pending.assembler.add(frame.xml)
            except ValueError as exc:
                if not pending.future.done():
                    pending.future.set_exception(RadioError(str(exc), frame.fields))
                return
            if merged is not None and not pending.future.done():
                pending.future.set_result(split_frame(f"{frame.cmd},<XML>,\n{merged}"))
            return
        if not frame.is_xml:
            self._finish(pending, frame)

    def _finish(self, pending: _Pending, frame: Frame) -> None:
        if pending.future.done():
            return
        if frame.err:
            pending.future.set_exception(RadioError(",".join(frame.fields), frame.fields))
            return
        pending.future.set_result(frame)

    def _accept_psi(self, frame: Frame) -> None:
        try:
            root = parse_xml(frame.xml)
            status = flatten_scanner_info(root)
            status["source"] = "PSI"
            self._last_psi = time.monotonic()
            self._broadcast(status)
        except Exception:
            log.exception("PSI parse failed")

    async def command(self, cmd: str, timeout: float | None = None, expect_xml: bool | None = None) -> Frame:
        name = cmd.split(",", 1)[0]
        if expect_xml is None:
            expect_xml = name in {"GSI", "GLT", "MSI", "AST"}
        wait = timeout if timeout is not None else self.timeout_s
        async with self._lock:
            if self._transport is None:
                raise RadioError("radio is not connected")
            loop = self._loop or asyncio.get_running_loop()
            future: asyncio.Future = loop.create_future()
            pending = _Pending(cmd=name, expect_xml=expect_xml, future=future)
            self._pending = pending
            try:
                payload = cmd if cmd.endswith("\r") else f"{cmd}\r"
                self._send(payload.encode("ascii", errors="strict"))
                return await asyncio.wait_for(future, wait)
            except TimeoutError as exc:
                raise RadioError(f"timeout waiting for {name}") from exc
            finally:
                self._pending = None

    async def identify(self) -> dict:
        mdl = await self.command("MDL")
        ver = await self.command("VER")
        self.model = mdl.fields[1] if len(mdl.fields) > 1 else self.model
        self.version = ",".join(ver.fields[1:]) if len(ver.fields) > 1 else self.version
        return {"model": self.model, "version": self.version}

    async def psi_start(self, interval_ms: int | None = None) -> None:
        if interval_ms is not None:
            self.psi_interval_ms = interval_ms
        await self.command(f"PSI,{self.psi_interval_ms}", expect_xml=False)
        self._ensure_watchdog()

    async def psi_stop(self) -> None:
        if self._watchdog is not None:
            self._watchdog.cancel()
            self._watchdog = None
        await self.command("PSI,0", expect_xml=False, timeout=2.0)

    def psi_age_s(self) -> float | None:
        if not self._last_psi:
            return None
        return time.monotonic() - self._last_psi

    def _ensure_watchdog(self) -> None:
        loop = self._loop or asyncio.get_running_loop()
        if self._watchdog is None or self._watchdog.done():
            self._watchdog = loop.create_task(self._psi_watchdog(), name="psi-watchdog")

    async def _psi_watchdog(self) -> None:
        """Uniden sends PSI only to the last UDP client. Reclaim if it goes quiet."""
        while True:
            await asyncio.sleep(1.0)
            if self._transport is None:
                return
            age = self.psi_age_s()
            now = time.monotonic()
            if age is not None and age < 2.0:
                continue
            if now < self._psi_retry_at:
                continue
            self._psi_retry_at = now + 3.0
            log.info("PSI stale (%s), re-subscribing", "never" if age is None else f"{age:.1f}s")
            try:
                await self.command(f"PSI,{self.psi_interval_ms}", expect_xml=False, timeout=2.0)
            except Exception:
                log.warning("PSI re-subscribe failed", exc_info=True)

    async def snapshot(self, force: bool = False) -> dict:
        age = self.psi_age_s()
        stale = force or not self.status or age is None or age > 1.5
        if not stale:
            return self.status
        try:
            return await self.gsi()
        except RadioError:
            if self.status:
                return self.status
            raise

    async def gsi(self) -> dict:
        frame = await self.command("GSI")
        root = parse_xml(frame.xml) if frame.is_xml else parse_xml(frame.raw)
        status = flatten_scanner_info(root)
        status["source"] = "GSI"
        self._broadcast(status)
        return status

    async def glt(self, kind: str, parent: str | None = None, timeout: float = 15.0) -> dict:
        kind = kind.upper()
        if kind not in protocol.GLT_KINDS:
            raise RadioError(f"unknown GLT kind {kind}")
        if kind in protocol.GLT_NEEDS_PARENT:
            if parent is None or parent == "":
                raise RadioError(f"GLT,{kind} needs a parent index")
            cmd = protocol.csv_cmd("GLT", kind, parent)
        else:
            cmd = protocol.csv_cmd("GLT", kind)
        frame = await self.command(cmd, timeout=timeout, expect_xml=True)
        return flatten_glt(parse_xml(frame.xml))

    async def key(self, code: str, mode: str = "P") -> list[str]:
        mode = mode.upper()
        if mode not in protocol.KEY_MODES:
            raise RadioError(f"bad key mode {mode}")
        if not code:
            raise RadioError("missing key code")
        frame = await self.command(protocol.csv_cmd("KEY", code, mode), expect_xml=False)
        return frame.fields

    async def vol(self, level: int | None = None) -> int:
        return await self._level("VOL", level)

    async def sql(self, level: int | None = None) -> int:
        return await self._level("SQL", level)

    async def _level(self, cmd: str, level: int | None) -> int:
        if level is None:
            frame = await self.command(cmd, expect_xml=False)
        else:
            frame = await self.command(protocol.csv_cmd(cmd, level), expect_xml=False)
        if len(frame.fields) < 2 or frame.fields[1] in {"OK", "ERR", "NG"}:
            frame = await self.command(cmd, expect_xml=False)
        return int(frame.fields[1])

    async def hold(self, target: protocol.Target | None = None) -> list[str]:
        target = target or protocol.target_from_status(self.status)
        if target is None:
            raise RadioError("no hold target in current status")
        frame = await self.command(protocol.csv_cmd("HLD", target.tkw, target.xxx1, target.xxx2), expect_xml=False)
        return frame.fields

    async def next(self, target: protocol.Target | None = None, count: int = 1) -> list[str]:
        target = target or protocol.target_from_status(self.status)
        if target is None:
            raise RadioError("no next target in current status")
        frame = await self.command(
            protocol.csv_cmd("NXT", target.tkw, target.xxx1, target.xxx2, count),
            expect_xml=False,
        )
        return frame.fields

    async def prev(self, target: protocol.Target | None = None, count: int = 1) -> list[str]:
        target = target or protocol.target_from_status(self.status)
        if target is None:
            raise RadioError("no prev target in current status")
        frame = await self.command(
            protocol.csv_cmd("PRV", target.tkw, target.xxx1, target.xxx2, count),
            expect_xml=False,
        )
        return frame.fields

    async def avoid(self, status: int, target: protocol.Target | None = None) -> list[str]:
        if status not in (
            protocol.AVOID_PERMANENT,
            protocol.AVOID_TEMPORARY,
            protocol.AVOID_STOP,
        ):
            raise RadioError("avoid status must be 1, 2, or 3")
        target = target or protocol.target_from_status(self.status)
        if target is None:
            raise RadioError("no avoid target in current status")
        frame = await self.command(
            protocol.csv_cmd("AVD", target.tkw, target.xxx1, target.xxx2, status),
            expect_xml=False,
        )
        return frame.fields

    async def quick_keys(self, kind: str, *prefix: object, values: list[int] | None = None) -> list[str]:
        kind = kind.upper()
        if kind not in {"FQK", "SQK", "DQK"}:
            raise RadioError("quick keys kind must be FQK, SQK, or DQK")
        parts: list[object] = [kind, *prefix]
        if values is not None:
            if len(values) != 100:
                raise RadioError("quick key arrays must have 100 entries")
            parts.extend(values)
        frame = await self.command(protocol.csv_cmd(*parts), expect_xml=False)
        return frame.fields

    async def jump_number_tag(self, fl_tag: int, sys_tag: int, chan_tag: int) -> list[str]:
        frame = await self.command(protocol.csv_cmd("JNT", fl_tag, sys_tag, chan_tag), expect_xml=False)
        return frame.fields

    async def jump_mode(self, mode: str, index: str = "") -> list[str]:
        mode = mode.upper()
        if mode not in protocol.JUMP_MODES:
            raise RadioError(f"unknown jump mode {mode}")
        frame = await self.command(protocol.csv_cmd("JPM", mode, index), expect_xml=False)
        return frame.fields

    async def menu_enter(self, menu_id: str, index: str = "") -> list[str]:
        menu_id = menu_id.upper()
        frame = await self.command(protocol.csv_cmd("MNU", menu_id, index), expect_xml=False)
        return frame.fields

    async def menu_status(self) -> dict:
        frame = await self.command("MSI", expect_xml=True)
        return flatten_menu(parse_xml(frame.xml))

    async def menu_set(self, value: str) -> list[str]:
        frame = await self.command(protocol.csv_cmd("MSV", "", protocol.msv_value(value)), expect_xml=False)
        return frame.fields

    async def menu_back(self, level: str = "") -> list[str]:
        frame = await self.command(protocol.csv_cmd("MSB", "", level), expect_xml=False)
        return frame.fields

    async def record(self, start: bool | None = None) -> list[str]:
        if start is None:
            frame = await self.command("URC", expect_xml=False)
        else:
            frame = await self.command(protocol.csv_cmd("URC", 1 if start else 0), expect_xml=False)
        return frame.fields

    async def clock(self, fields: list[str] | None = None) -> list[str]:
        if fields is None:
            frame = await self.command("DTM", expect_xml=False)
        else:
            frame = await self.command(protocol.csv_cmd("DTM", *fields), expect_xml=False)
        return frame.fields

    async def location(self, lat: str | None = None, lon: str | None = None, rng: str | None = None) -> list[str]:
        if lat is None:
            frame = await self.command("LCR", expect_xml=False)
        else:
            frame = await self.command(protocol.csv_cmd("LCR", lat, lon, rng), expect_xml=False)
        return frame.fields

    async def service_types(self, values: list[str] | None = None) -> list[str]:
        if values is None:
            frame = await self.command("SVC", expect_xml=False)
        else:
            frame = await self.command(protocol.csv_cmd("SVC", *values), expect_xml=False)
        return frame.fields
