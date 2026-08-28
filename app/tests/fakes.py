"""In-memory radio for FastAPI tests. Does not speak UDP."""

from __future__ import annotations

import asyncio


class FakeRadio:
    def __init__(self):
        self.model = "BCD536HP"
        self.version = "Version 1.28.14"
        self.status = {
            "mode": "Scan Mode",
            "source": "GSI",
            "property": {"VOL": "3", "SQL": "11", "Mute": "Unmute"},
            "system": {"Name": "Test", "Index": "1", "Hold": "Off"},
            "listen": {"title": "Test", "scanning": False, "landed": True},
        }
        self.calls: list[tuple] = []
        self.fail: Exception | None = None
        self.last_error: str | None = None
        self.psi_age: float | None = 0.1
        self.glt_result = {"kind": "FL", "items": [{"Index": "0", "Name": "Reno"}]}
        self.menu = {"name": "TOP", "menuType": "TypeSelect", "items": [{"Name": "Settings"}]}
        self.fields = ["OK"]
        self.level = 3
        self._listeners: set[asyncio.Queue] = set()

    def _check(self) -> None:
        if self.fail is not None:
            raise self.fail

    def _record(self, name: str, *args) -> None:
        self.calls.append((name, *args))
        self._check()

    async def start(self) -> None:
        self.calls.append(("start",))

    async def close(self) -> None:
        self.calls.append(("close",))

    async def gsi(self) -> dict:
        self._record("gsi")
        return self.status

    async def psi_start(self, interval_ms: int | None = None) -> None:
        self.calls.append(("psi_start", interval_ms))
        self._check()

    def psi_age_s(self) -> float | None:
        return self.psi_age

    async def snapshot(self, force: bool = False) -> dict:
        self._record("snapshot", force)
        return self.status

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=8)
        self._listeners.add(queue)
        if self.status:
            queue.put_nowait(self.status)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._listeners.discard(queue)

    async def key(self, code: str, mode: str = "P") -> list[str]:
        self._record("key", code, mode)
        return ["KEY", "OK"]

    async def vol(self, level: int | None = None) -> int:
        self._record("vol", level)
        if level is not None:
            self.level = level
        return self.level

    async def sql(self, level: int | None = None) -> int:
        self._record("sql", level)
        if level is not None:
            self.level = level
        return self.level

    async def hold(self, target=None) -> list[str]:
        self._record("hold", target)
        return self.fields

    async def next(self, target=None, count: int = 1) -> list[str]:
        self._record("next", target, count)
        return self.fields

    async def prev(self, target=None, count: int = 1) -> list[str]:
        self._record("prev", target, count)
        return self.fields

    async def avoid(self, status: int, target=None) -> list[str]:
        self._record("avoid", status, target)
        return self.fields

    async def glt(self, kind: str, parent: str | None = None, timeout: float = 15.0) -> dict:
        self._record("glt", kind, parent, timeout)
        return self.glt_result

    async def quick_keys(self, kind: str, *prefix: object, values: list[int] | None = None) -> list[str]:
        self._record("quick_keys", kind, prefix, values)
        return ["FQK", "OK"]

    async def jump_number_tag(self, fl_tag: int, sys_tag: int, chan_tag: int) -> list[str]:
        self._record("jump_number_tag", fl_tag, sys_tag, chan_tag)
        return self.fields

    async def jump_mode(self, mode: str, index: str = "") -> list[str]:
        self._record("jump_mode", mode, index)
        return self.fields

    async def menu_enter(self, menu_id: str, index: str = "") -> list[str]:
        self._record("menu_enter", menu_id, index)
        return self.fields

    async def menu_status(self) -> dict:
        self._record("menu_status")
        return self.menu

    async def menu_set(self, value: str) -> list[str]:
        self._record("menu_set", value)
        return self.fields

    async def menu_back(self, level: str = "") -> list[str]:
        self._record("menu_back", level)
        return self.fields

    async def record(self, start: bool | None = None) -> list[str]:
        self._record("record", start)
        return self.fields

    async def clock(self, fields: list[str] | None = None) -> list[str]:
        self._record("clock", fields)
        return ["DTM", "0", "2026", "8", "24", "12", "0", "0"]

    async def location(self, lat: str | None = None, lon: str | None = None, rng: str | None = None) -> list[str]:
        self._record("location", lat, lon, rng)
        return ["LCR", "39.5", "-119.8", "10"]

    async def service_types(self, values: list[str] | None = None) -> list[str]:
        self._record("service_types", values)
        return ["SVC", "1"]
