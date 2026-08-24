"""Uniden BCDx36HP / SDS remote-command constants and helpers."""

from __future__ import annotations

from dataclasses import dataclass

CONTROL_PORT = 50536

# KEY_MODE: P press, L long, H hold until R, R release
KEY_MODES = ("P", "L", "H", "R")

# Physical / virtual keys (BCDx36HP Remote Command Spec v1.05)
KEYS_536 = {
    "0": "0",
    "1": "1",
    "2": "2",
    "3": "3",
    "4": "4",
    "5": "5",
    "6": "6",
    "7": "7",
    "8": "8",
    "9": "9",
    ".": ". / No",
    "E": "Yes / Enter",
    "M": "Menu",
    "F": "Func",
    "L": "Avoid",
    "A": "System",
    "B": "Department",
    "C": "Channel",
    "Y": "Replay",
    "Z": "Zip",
    "T": "Service type",
    "R": "Range",
    "V": "Volume knob push / backlight",
    "Q": "Squelch knob push",
    ">": "Rotary right",
    "<": "Rotary left",
    "^": "Rotary push",
}

# SDS200 A/B/C are soft keys; still send the same codes.
KEYS_SDS = dict(KEYS_536)
KEYS_SDS.update({"A": "Soft 1", "B": "Soft 2", "C": "Soft 3"})

AVOID_PERMANENT = 1
AVOID_TEMPORARY = 2
AVOID_STOP = 3

JUMP_MODES = (
    "SCN_MODE",
    "CTM_MODE",
    "QSH_MODE",
    "CC_MODE",
    "WX_MODE",
    "FTO_MODE",
    "IREC_MODE",
    "UREC_MODE",
    "TDIS_MODE",
    "CDIS_MODE",
)

WX_INDEXES = (
    "NORMAL",
    "A_ONLY",
    "SAME_1",
    "SAME_2",
    "SAME_3",
    "SAME_4",
    "SAME_5",
    "ALL_FIPS",
)

MENU_IDS = (
    "TOP",
    "MONITOR_LIST",
    "SCAN_SYSTEM",
    "SCAN_DEPARTMENT",
    "SCAN_SITE",
    "SCAN_CHANNEL",
    "SRCH_RANGE",
    "SRCH_OPT",
    "CC",
    "CC_BAND",
    "WX",
    "FTO_CHANNEL",
    "SETTINGS",
    "BRDCST_SCREEN",
)

GLT_KINDS = (
    "FL",
    "SYS",
    "DEPT",
    "SITE",
    "CFREQ",
    "TGID",
    "SFREQ",
    "AFREQ",
    "ATGID",
    "FTO",
    "CS_BANK",
    "UREC",
    "IREC_FILE",
    "UREC_FILE",
    "TRN_DISCOV",
    "CNV_DISCOV",
)

# GLT kinds that take a parent index as the second argument
GLT_NEEDS_PARENT = {
    "SYS",
    "DEPT",
    "SITE",
    "CFREQ",
    "TGID",
    "SFREQ",
    "ATGID",
    "UREC_FILE",
}

CHANNEL_TAGS = ("ConvFrequency", "TGID", "SrchFrequency", "CcHitsChannel", "WxChannel", "ToneOutChannel")


@dataclass(frozen=True)
class Target:
    tkw: str
    xxx1: str = ""
    xxx2: str = ""


def key_labels_for_model(model: str) -> dict[str, str]:
    upper = (model or "").upper()
    if "SDS" in upper:
        return KEYS_SDS
    return KEYS_536


def vol_max_for_model(model: str) -> int:
    upper = (model or "").upper()
    if "436" in upper:
        return 15
    return 29


def sql_max_for_model(model: str) -> int:
    upper = (model or "").upper()
    if "436" in upper:
        return 15
    return 19


def csv_cmd(*parts: object) -> str:
    return ",".join("" if p is None else str(p) for p in parts)


def msv_value(value: str) -> str:
    """MSV replaces commas in the value with tabs."""
    return value.replace(",", "\t")


def _usable_index(node: dict | None) -> str:
    if not node:
        return ""
    value = str(node.get("Index") or "").strip()
    if not value or value in {"4294967295", "None"}:
        return ""
    return value


def target_from_status(status: dict) -> Target | None:
    """Pick HLD/NXT/PRV/AVD handles from the latest PSI/GSI snapshot."""
    channel = status.get("channel") or {}
    tag = status.get("channelTag")
    dept = status.get("department") or {}
    site = status.get("site") or {}
    system = status.get("system") or {}
    chan_idx = _usable_index(channel)

    if tag == "TGID" and chan_idx:
        return Target("TGID", chan_idx, _usable_index(dept))
    if tag == "ConvFrequency" and chan_idx:
        return Target("CFREQ", chan_idx, "")
    if tag == "SrchFrequency" and channel.get("Freq"):
        return Target("QS_FREQ", _freq_hz(channel.get("Freq", "")), "")
    if tag == "WxChannel" and chan_idx:
        return Target("WX", chan_idx, "")
    if tag == "ToneOutChannel" and chan_idx:
        return Target("FTO", chan_idx, "")
    if tag == "CcHitsChannel" and chan_idx:
        return Target("CCHIT", chan_idx, "")
    if _usable_index(dept):
        return Target("DEPT", _usable_index(dept), _usable_index(system))
    if _usable_index(site):
        return Target("SITE", _usable_index(site), "")
    if _usable_index(system):
        return Target("SYS", _usable_index(system), "")
    return None


def _freq_hz(freq: str) -> str:
    digits = "".join(ch for ch in freq if ch.isdigit())
    return digits
