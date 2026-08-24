from __future__ import annotations

from pydantic import BaseModel, Field


class KeyBody(BaseModel):
    code: str
    mode: str = "P"


class LevelBody(BaseModel):
    level: int = Field(ge=0, le=29)


class TargetBody(BaseModel):
    tkw: str | None = None
    xxx1: str = ""
    xxx2: str = ""
    count: int = 1
    status: int | None = None


class QuickKeysBody(BaseModel):
    values: list[int]
    fav: str | None = None
    sys: str | None = None


class JumpTagBody(BaseModel):
    fl: int
    sys: int
    chan: int


class JumpModeBody(BaseModel):
    mode: str
    index: str = ""


class MenuEnterBody(BaseModel):
    menu_id: str
    index: str = ""


class MenuValueBody(BaseModel):
    value: str


class MenuBackBody(BaseModel):
    level: str = ""


class RecordBody(BaseModel):
    start: bool


class LocationBody(BaseModel):
    latitude: str
    longitude: str
    range: str


class ClockBody(BaseModel):
    daylight: str
    year: str
    month: str
    day: str
    hour: str
    minute: str
    second: str
