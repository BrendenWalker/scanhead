from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from scanhead import protocol
from scanhead.config import Settings, load_settings
from scanhead.models import (
    ClockBody,
    JumpModeBody,
    JumpTagBody,
    KeyBody,
    LevelBody,
    LocationBody,
    MenuBackBody,
    MenuEnterBody,
    MenuValueBody,
    QuickKeysBody,
    RecordBody,
    TargetBody,
)
from scanhead.radio import Radio, RadioError

log = logging.getLogger("scanhead")
STATIC = Path(__file__).resolve().parent.parent / "static"


def _http_error(exc: RadioError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


def _target(body: TargetBody | None) -> protocol.Target | None:
    if body is None or not body.tkw:
        return None
    return protocol.Target(body.tkw, body.xxx1, body.xxx2)


def _require_target(body: TargetBody | None) -> protocol.Target:
    target = _target(body)
    if target is None:
        raise HTTPException(status_code=400, detail="target required from displayed channel")
    return target


def create_app(settings: Settings | None = None, radio: Radio | None = None) -> FastAPI:
    settings = settings or load_settings()
    radio = radio or Radio(
        settings.scanner_ip,
        settings.scanner_port,
        timeout_s=settings.command_timeout_s,
        psi_interval_ms=settings.psi_interval_ms,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        await radio.start()
        try:
            await radio.gsi()
        except RadioError:
            log.warning("initial GSI failed")
        try:
            await radio.psi_start(settings.psi_interval_ms)
        except RadioError:
            log.warning("PSI start failed")
        app.state.radio = radio
        app.state.settings = settings
        yield
        await radio.close()

    app = FastAPI(title="ScanHead", lifespan=lifespan)

    @app.get("/api/health")
    async def health():
        return {
            "ok": True,
            "model": radio.model,
            "version": radio.version,
            "scanner": f"{settings.scanner_ip}:{settings.scanner_port}",
            "psiAgeS": radio.psi_age_s(),
        }

    @app.get("/api/config")
    async def config(request: Request):
        host = request.url.hostname or settings.scanner_ip
        scheme = request.url.scheme or "http"
        return {
            "model": radio.model,
            "version": radio.version,
            "keys": protocol.key_labels_for_model(radio.model),
            "volMax": protocol.vol_max_for_model(radio.model),
            "sqlMax": protocol.sql_max_for_model(radio.model),
            "jumpModes": protocol.JUMP_MODES,
            "menuIds": protocol.MENU_IDS,
            "wxIndexes": protocol.WX_INDEXES,
            "whepUrl": f"{scheme}://{host}:{settings.mediamtx_whep_port}/scanner/whep",
            "hlsUrl": f"{scheme}://{host}:{settings.mediamtx_hls_port}/player/index.m3u8",
            "rtspUrl": f"rtsp://{host}:{settings.mediamtx_rtsp_port}/player",
            "appVersion": settings.app_version,
        }

    @app.get("/api/status")
    async def status(fresh: bool = False):
        try:
            return await radio.snapshot(force=fresh)
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.websocket("/api/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        try:
            await radio.snapshot()
        except RadioError:
            log.warning("websocket snapshot failed")
        queue = radio.subscribe()
        try:
            while True:
                payload = await queue.get()
                await websocket.send_json(payload)
        except WebSocketDisconnect:
            pass
        finally:
            radio.unsubscribe(queue)

    @app.post("/api/key")
    async def key(body: KeyBody):
        try:
            return {"fields": await radio.key(body.code, body.mode)}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/vol")
    async def get_vol():
        try:
            return {"level": await radio.vol()}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/vol")
    async def set_vol(body: LevelBody):
        try:
            return {"level": await radio.vol(body.level)}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/sql")
    async def get_sql():
        try:
            return {"level": await radio.sql()}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/sql")
    async def set_sql(body: LevelBody):
        try:
            return {"level": await radio.sql(body.level)}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/hold")
    async def hold(body: TargetBody | None = None):
        try:
            return {"fields": await radio.hold(_require_target(body))}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/next")
    async def nxt(body: TargetBody | None = None):
        try:
            count = body.count if body else 1
            return {"fields": await radio.next(_require_target(body), count)}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/prev")
    async def prv(body: TargetBody | None = None):
        try:
            count = body.count if body else 1
            return {"fields": await radio.prev(_require_target(body), count)}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/avoid")
    async def avoid(body: TargetBody):
        if body.status is None:
            raise HTTPException(status_code=400, detail="status 1=permanent 2=temporary 3=stop")
        try:
            return {"fields": await radio.avoid(body.status, _require_target(body))}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/lists/{kind}")
    async def lists(kind: str, parent: str | None = None):
        try:
            return await radio.glt(kind, parent, timeout=settings.glt_timeout_s)
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/qk/fqk")
    async def get_fqk():
        try:
            return {"fields": await radio.quick_keys("FQK")}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/qk/fqk")
    async def set_fqk(body: QuickKeysBody):
        try:
            return {"fields": await radio.quick_keys("FQK", values=body.values)}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/qk/sqk")
    async def get_sqk(fav: str):
        try:
            return {"fields": await radio.quick_keys("SQK", fav)}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/qk/sqk")
    async def set_sqk(fav: str, body: QuickKeysBody):
        try:
            return {"fields": await radio.quick_keys("SQK", fav, values=body.values)}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/qk/dqk")
    async def get_dqk(fav: str, sys: str):
        try:
            return {"fields": await radio.quick_keys("DQK", fav, sys)}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/qk/dqk")
    async def set_dqk(fav: str, sys: str, body: QuickKeysBody):
        try:
            return {"fields": await radio.quick_keys("DQK", fav, sys, values=body.values)}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/jnt")
    async def jnt(body: JumpTagBody):
        try:
            return {"fields": await radio.jump_number_tag(body.fl, body.sys, body.chan)}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/jpm")
    async def jpm(body: JumpModeBody):
        try:
            return {"fields": await radio.jump_mode(body.mode, body.index)}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/menu")
    async def menu_enter(body: MenuEnterBody):
        try:
            await radio.menu_enter(body.menu_id, body.index)
            return await radio.menu_status()
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/menu")
    async def menu_get():
        try:
            return await radio.menu_status()
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/menu/value")
    async def menu_value(body: MenuValueBody):
        try:
            await radio.menu_set(body.value)
            return await radio.menu_status()
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/menu/back")
    async def menu_back(body: MenuBackBody | None = None):
        try:
            level = body.level if body else ""
            await radio.menu_back(level)
            if level == "RETURN_PREVOUS_MODE":
                return {"exited": True}
            return await radio.menu_status()
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/replay")
    async def replay_get():
        try:
            return {"fields": await radio.record()}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/replay")
    async def replay_set(body: RecordBody):
        try:
            return {"fields": await radio.record(body.start)}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/clock")
    async def clock_get():
        try:
            return {"fields": await radio.clock()}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/clock")
    async def clock_set(body: ClockBody):
        try:
            return {
                "fields": await radio.clock(
                    [body.daylight, body.year, body.month, body.day, body.hour, body.minute, body.second]
                )
            }
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/location")
    async def location_get():
        try:
            return {"fields": await radio.location()}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.post("/api/location")
    async def location_set(body: LocationBody):
        try:
            return {"fields": await radio.location(body.latitude, body.longitude, body.range)}
        except RadioError as exc:
            raise _http_error(exc) from exc

    @app.get("/api/svc")
    async def svc_get():
        try:
            return {"fields": await radio.service_types()}
        except RadioError as exc:
            raise _http_error(exc) from exc

    if STATIC.exists():
        app.mount("/static", StaticFiles(directory=STATIC), name="static")

        @app.get("/")
        async def index():
            return FileResponse(STATIC / "index.html")

        @app.get("/favicon.ico", include_in_schema=False)
        async def favicon():
            return FileResponse(STATIC / "favicon.svg", media_type="image/svg+xml")

    return app


def app() -> FastAPI:
    return create_app()
