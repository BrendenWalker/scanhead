# ScanHead

ScanHead turns a network-connected Uniden scanner into a **browser-based remote head**. It is a modern, self-hosted replacement for Uniden’s Siren app. Run it on a trusted LAN, point it at a supported scanner, and use any modern browser for live audio, the scanner’s display, physical keys, favorites, quick keys, and menus.

Unlike a scanner audio streamer, ScanHead implements a full remote head: the browser mirrors the scanner’s display and provides its physical controls, favorites, quick keys, and menu navigation.

Audio and control are separate paths:

- Scanner → RTSP audio → ScanHead (MediaMTX) → WebRTC → browser
- Browser → ScanHead (control API) → ASCII/XML commands → scanner

The scanner’s remote-control and audio interfaces do not provide authentication. ScanHead is designed for **trusted LAN deployments** and should not be exposed directly to the Internet. “LAN-only” here is a deployment assumption, not a claim that the app refuses WAN access.

**Status:** planning. The design is in [docs/PLAN.md](docs/PLAN.md). Runtime code is not in this repository yet.

## Scanner support (v1)

| Scanner | Network audio / control | v1 |
|---|---|---|
| **BCD536HP** | Wi-Fi, RTSP + UDP 50536 | Primary target |
| UBCD536PT | Wi-Fi, RTSP + UDP 50536 | Compatible (EU 536) |
| **SDS200** | Ethernet, RTSP + UDP 50536 | First-class target |
| SDS200E / USDS200 | Ethernet, RTSP + UDP 50536 | Expected compatible |
| BCD436HP / UBCD436PT | USB serial (no RTSP) | Future USB backend |
| SDS100 / SDS100E / USDS100 | USB serial (no RTSP) | Future USB backend |
| SDS150 | USB serial (same SDS commands); phone app is BLE/U-AWARE | USB future; U-AWARE not a ScanHead backend |

Handhelds share the command family but have no native RTSP for ScanHead to proxy. USB support would be a later, separate backend.

**Out of scope:** HomePatrol-1/2, BCD996P2 / BCD325P2 / XT and other Bearcats, analog-only Uniden, Whistler — different interfaces and protocols.

## How it will work

The scanner already exposes digital audio over the network as G.711 µ-law RTSP:

```text
rtsp://<scanner-ip>/au:scanner.au
```

Browsers cannot play RTSP, so ScanHead will pull that stream once (the scanner typically allows a single RTSP client) and republish it as WebRTC.

Control uses Uniden’s published ASCII/XML remote-command protocol on **UDP port 50536** — the same family used by HomePatrol/SDS scanners (`KEY`, `GLT`, `MNU`, `GSI`, `PSI`, and related commands). ScanHead uses `MDL` to identify the connected model and adapt the UI.

See [docs/PLAN.md](docs/PLAN.md) for architecture, protocol notes, UI scope, and delivery phases.

## Security

The radio’s network interfaces are unauthenticated. Keep ScanHead and the scanner on a trusted LAN. Do not publish ScanHead or the scanner’s UDP/RTSP ports on the public Internet.

Do not run Siren, ProScan, or Uniden’s RH-536HP remote-head tool at the same time as ScanHead. Only one controller should own the scanner’s `PSI` session.
