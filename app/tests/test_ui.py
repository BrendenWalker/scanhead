"""Markup contracts for Normal vs Advanced UI. No browser required."""

from html.parser import HTMLParser
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "static"
VOID = {"input", "meta", "link", "img", "br", "hr", "source", "area", "col", "embed", "wbr"}


class _Node:
    def __init__(self, tag: str, attrs: dict, parent: "_Node | None"):
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children: list[_Node] = []
        self.text = ""

    @property
    def id(self) -> str | None:
        return self.attrs.get("id")

    @property
    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = _Node("document", {}, None)
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, dict(attrs), self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].text += data

    def handle_startendtag(self, tag, attrs):
        node = _Node(tag, dict(attrs), self.stack[-1])
        self.stack[-1].children.append(node)


def _parse() -> _Node:
    parser = _Tree()
    parser.feed((STATIC / "index.html").read_text(encoding="utf-8"))
    return parser.root


def _by_id(root: _Node, ident: str) -> _Node:
    for node in root.walk():
        if node.id == ident:
            return node
    raise AssertionError(f"missing #{ident}")


def _in_advanced(node: _Node) -> bool:
    cur: _Node | None = node
    while cur is not None:
        if "advanced" in cur.classes:
            return True
        cur = cur.parent
    return False


def _button_by_text(root: _Node, text: str) -> _Node:
    needle = text.casefold()
    for node in root.walk():
        if node.tag == "button" and node.text.strip().casefold() == needle:
            return node
    raise AssertionError(f"missing button {text!r}")


def test_advanced_checkbox_defaults_off_at_page_bottom():
    root = _parse()
    box = _by_id(root, "advanced-controls")
    assert box.tag == "input"
    assert box.attrs.get("type") == "checkbox"
    assert "checked" not in box.attrs
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert html.rfind("advanced-controls") > html.rfind("id=\"play\"")
    assert "Advanced Controls" in html


def test_header_play_and_normal_listen_are_visible_by_default():
    root = _parse()
    assert not _in_advanced(_by_id(root, "play"))
    assert not _in_advanced(_by_id(root, "channel-name"))
    assert not _in_advanced(_by_id(root, "dept"))
    hold = _button_by_text(root, "Hold")
    temp = _button_by_text(root, "Temp avoid")
    assert hold.attrs.get("data-act") == "hold"
    assert temp.attrs.get("data-act") == "avoid"
    assert temp.attrs.get("data-status") == "2"
    assert not _in_advanced(hold)
    assert not _in_advanced(temp)


def test_advanced_controls_are_marked_and_hidden_by_css():
    root = _parse()
    for ident in ("vol", "sql", "freq", "mode", "qk-load", "menu-top"):
        assert _in_advanced(_by_id(root, ident)), ident
    for label in ("Prev", "Skip", "Avoid", "Unavoid"):
        assert _in_advanced(_button_by_text(root, label)), label
    assert _in_advanced(_by_id(root, "panel-lists"))
    assert _in_advanced(_by_id(root, "panel-qk"))
    assert _in_advanced(_by_id(root, "panel-menu"))
    assert _in_advanced(_by_id(root, "panel-more"))

    css = (STATIC / "css" / "app.css").read_text(encoding="utf-8")
    assert "body:not(.advanced-on) .advanced" in css
    assert "display: none" in css

    js = (STATIC / "js" / "app.js").read_text(encoding="utf-8")
    assert "advanced-controls" in js
    assert "advanced-on" in js


def test_department_renders_above_channel_name():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    display = html.split('id="display"', 1)[1]
    assert display.find('id="dept"') < display.find('id="channel-name"')


def test_normal_display_has_no_min_height():
    css = (STATIC / "css" / "app.css").read_text(encoding="utf-8")
    assert "min-height: 280px" in css
    assert "body:not(.advanced-on) .display" in css
    assert "min-height: 0" in css


def test_action_buttons_send_displayed_channel_target():
    js = (STATIC / "js" / "app.js").read_text(encoding="utf-8")
    assert "state.displayed" in js
    assert "displayed.target" in js
    assert "displayedChannelBody" in js
    assert "tkw: t.tkw" in js
