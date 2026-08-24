"""Uniden UDP ASCII/XML framing: split datagrams and reassemble Footer packets."""

from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

FOOTER_TAGS = ("Footer", "Foot")
NONE_VALUES = {"", "None", "TGID None", "UID None", "Slot None"}
CHANNEL_TAGS = (
    "ConvFrequency",
    "TGID",
    "SrchFrequency",
    "CcHitsChannel",
    "WxChannel",
    "ToneOutChannel",
)


@dataclass
class Frame:
    cmd: str
    fields: list[str]
    is_xml: bool
    xml: str = ""
    raw: str = ""

    @property
    def ok(self) -> bool:
        return len(self.fields) >= 2 and self.fields[1] == "OK"

    @property
    def err(self) -> bool:
        return len(self.fields) >= 2 and self.fields[1] in {"ERR", "NG"}


def decode_datagram(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def split_frame(data: bytes | str) -> Frame:
    text = data if isinstance(data, str) else decode_datagram(data)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if "\n" in normalized:
        header, rest = normalized.split("\n", 1)
    else:
        header, rest = normalized, ""
    header = header.strip()
    fields = header.split(",")
    cmd = fields[0] if fields else ""
    if len(fields) >= 2 and fields[1] == "<XML>":
        xml = rest.lstrip("\n")
        if not xml.strip() and len(fields) > 2:
            xml = ",".join(fields[2:])
        return Frame(cmd=cmd, fields=fields, is_xml=True, xml=xml, raw=text)
    return Frame(cmd=cmd, fields=fields, is_xml=False, xml="", raw=text.strip())


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def parse_xml(xml: str) -> ET.Element:
    xml = xml.strip()
    if xml.startswith("\ufeff"):
        xml = xml.lstrip("\ufeff")
    return ET.fromstring(xml)


def footer_info(root: ET.Element) -> tuple[int | None, bool | None]:
    for child in list(root):
        if _local_tag(child.tag) in FOOTER_TAGS:
            no_raw = child.get("No")
            eot_raw = child.get("EOT")
            no = int(no_raw) if no_raw is not None else None
            eot = None if eot_raw is None else eot_raw == "1"
            return no, eot
    return None, None


def strip_footers(root: ET.Element) -> list[ET.Element]:
    return [child for child in list(root) if _local_tag(child.tag) not in FOOTER_TAGS]


def element_to_json(el: ET.Element) -> dict:
    node: dict = dict(el.attrib)
    text = (el.text or "").strip()
    if text:
        node["_text"] = text
    grouped: dict[str, list] = {}
    for child in el:
        tag = _local_tag(child.tag)
        if tag in FOOTER_TAGS:
            continue
        grouped.setdefault(tag, []).append(element_to_json(child))
    for tag, items in grouped.items():
        node[tag] = items if len(items) > 1 else items[0]
    return node


def _clean(value: str | None) -> str:
    text = (value or "").strip()
    if text in NONE_VALUES:
        return ""
    return text


def _node_name(node: dict | None) -> str:
    if not node:
        return ""
    return _clean(node.get("Name"))


def compose_listen(info: dict) -> dict:
    """Fields the radio view should show for the current PSI/GSI snapshot."""
    channel = info.get("channel") or {}
    site = info.get("site") or {}
    site_freq = info.get("siteFrequency") or {}
    department = info.get("department") or {}
    system = info.get("system") or {}
    overwrite = _clean((info.get("view") or {}).get("overwrite"))
    tgid = _clean(channel.get("TGID"))
    if tgid.lower().startswith("tgid:"):
        tgid = tgid.split(":", 1)[1].strip()
    freq = _clean(channel.get("Freq")) or _clean(site_freq.get("Freq"))
    title = _node_name(channel) or _node_name(department) or _node_name(system) or overwrite
    landed = bool(_node_name(channel) or tgid) and not overwrite
    unit = _clean((info.get("unitId") or {}).get("Name") or (info.get("unitId") or {}).get("U_Id"))
    if unit.lower().startswith("uid:"):
        unit = unit.split(":", 1)[1].strip()
    return {
        "title": title,
        "frequency": freq,
        "tgid": tgid,
        "modulation": _clean(channel.get("Mod")) or _clean(site.get("Mod")),
        "service": _clean(channel.get("SvcType")),
        "unit": unit,
        "system": _node_name(system),
        "department": _node_name(department),
        "site": _node_name(site),
        "overwrite": overwrite,
        "landed": landed,
        "scanning": bool(overwrite),
    }


def flatten_scanner_info(root: ET.Element) -> dict:
    info = {
        "mode": root.get("Mode"),
        "vScreen": root.get("V_Screen"),
        "property": {},
        "agc": {},
        "dualWatch": {},
        "monitorList": {},
        "system": {},
        "department": {},
        "site": {},
        "siteFrequency": {},
        "unitId": {},
        "channel": {},
        "channelTag": None,
        "view": {},
        "replay": {},
        "raw": element_to_json(root),
    }
    for child in root:
        tag = _local_tag(child.tag)
        payload = element_to_json(child)
        if tag == "Property":
            info["property"] = payload
        elif tag == "AGC":
            info["agc"] = payload
        elif tag == "DualWatch":
            info["dualWatch"] = payload
        elif tag == "MonitorList":
            info["monitorList"] = payload
        elif tag == "System":
            info["system"] = payload
        elif tag == "Department":
            info["department"] = payload
        elif tag == "Site":
            info["site"] = payload
        elif tag == "SiteFrequency":
            info["siteFrequency"] = payload
        elif tag == "UnitID":
            info["unitId"] = payload
        elif tag in CHANNEL_TAGS:
            info["channel"] = payload
            info["channelTag"] = tag
        elif tag == "ViewDescription":
            info["view"] = {
                "info1": _nested_text(payload, "InfoArea1", "Text"),
                "info2": _nested_text(payload, "InfoArea2", "Text"),
                "overwrite": _nested_text(payload, "OverWrite", "Text"),
                "popup": payload.get("PopupScreen") or {},
                "plain": _nested_text(payload, "PlainText", "Text"),
            }
        elif tag == "ReplayDescription":
            info["replay"] = payload
        elif tag == "DispFormat":
            info["dispFormat"] = payload
    info["listen"] = compose_listen(info)
    return info


def _nested_text(payload: dict, key: str, attr: str) -> str:
    value = payload.get(key)
    if isinstance(value, dict):
        return value.get(attr) or value.get("_text") or ""
    return ""


def flatten_menu(root: ET.Element) -> dict:
    data = element_to_json(root)
    items = data.get("MenuItem") or []
    if isinstance(items, dict):
        items = [items]
    return {
        "name": data.get("Name") or root.get("Name"),
        "index": data.get("Index") or root.get("Index"),
        "menuType": data.get("MenuType") or root.get("MenuType"),
        "value": data.get("Value") or root.get("Value"),
        "selected": data.get("Selected") or root.get("Selected"),
        "items": items,
        "input": data.get("MenuInput") or {},
        "location": data.get("MenuLocation") or {},
        "error": data.get("MenuErrorMsg") or {},
        "raw": data,
    }


def flatten_glt(root: ET.Element) -> dict:
    items = []
    kind = None
    for child in strip_footers(root):
        kind = _local_tag(child.tag)
        items.append(element_to_json(child))
    return {"kind": kind, "items": items, "raw": element_to_json(root)}


@dataclass
class XmlAssembler:
    """Reassemble Uniden multi-datagram XML using Footer No / EOT."""

    parts: dict[int, ET.Element] = field(default_factory=dict)
    complete_root: ET.Element | None = None
    expected_last: int | None = None

    def add(self, xml: str) -> str | None:
        """
        Feed one XML document.

        Returns the merged XML string when the message is complete, otherwise None.
        Raises ValueError on a sequence gap once EOT has been seen.
        """
        root = parse_xml(xml)
        no, eot = footer_info(root)
        if no is None:
            self.complete_root = root
            return xml.strip()
        self.parts[no] = root
        if eot:
            self.expected_last = no
        if self.expected_last is None:
            return None
        expected = set(range(1, self.expected_last + 1))
        have = set(self.parts)
        if expected <= have:
            merged = self.merge()
            return ET.tostring(merged, encoding="unicode")
        missing = sorted(expected - have)
        if missing:
            raise ValueError(f"XML packet gap: missing {missing}")
        return None

    def merge(self) -> ET.Element:
        if self.complete_root is not None:
            return self.complete_root
        first = self.parts[1]
        merged = ET.Element(first.tag, first.attrib)
        for no in range(1, (self.expected_last or 1) + 1):
            for child in strip_footers(self.parts[no]):
                merged.append(child)
        return merged
