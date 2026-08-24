# ScanHead

ScanHead turns a network-connected Uniden scanner into a **browser-based remote head**. It is a modern, self-hosted replacement for Uniden’s Siren app. Run it on a trusted LAN, point it at a supported scanner, and use any modern browser for live audio, the scanner’s display, physical keys, favorites, quick keys, and menus.

Unlike a scanner audio streamer, ScanHead implements a full remote head: the browser mirrors the scanner’s display and provides its physical controls, favorites, quick keys, and menu navigation.

Audio and control are separate paths:

- Scanner → RTSP audio → ScanHead (MediaMTX) → WebRTC → browser
- Browser → ScanHead (control API) → ASCII/XML commands → scanner

The scanner’s remote-control and audio interfaces do not provide authentication. ScanHead is designed for **trusted LAN deployments** and should not be exposed directly to the Internet. “LAN-only” here is a deployment assumption, not a claim that the app refuses WAN access.

**Status:** v1 runtime. Design notes remain in [docs/PLAN.md](docs/PLAN.md). Command reference: [docs/protocol.md](docs/protocol.md).

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

## Run (Linux Docker host on the scanner LAN)

Host networking is required. The scanner’s RTP uses dynamic UDP ports; Docker bridge NAT commonly breaks that.

```bash
cp .env.example .env
# set SCANNER_IP to the scanner’s reserved address
docker compose up --build
```

Open `http://<docker-host>:8080`. Play audio uses WebRTC from MediaMTX on port 8889 (WHEP `/scanner/whep`). VLC should use `rtsp://<docker-host>:8554/scanner` (HLS cannot carry G.711). Do not run Siren, ProScan, or RH-536HP at the same time.

If RTSP UDP still fails, set `rtspTransport: tcp` in `mediamtx.yml` (interleaved TCP fallback).

To run the published image instead of building:

```bash
IMAGE_TAG=latest docker compose pull
docker compose up -d
```

### Portainer (Linux Docker Standalone)

Do not deploy this as a Swarm stack. The Portainer stack **publishes ports** on a bridge network (so they show in Portainer). MediaMTX pulls the scanner over RTSP UDP; interleaved TCP is not supported and MediaMTX will log `400 Bad Request`.

1. Stacks → Add stack → Web editor; paste [portainer-stack.yml](portainer-stack.yml).
2. Add environment variables from [portainer-stack.env.example](portainer-stack.env.example). Set `SCANNER_IP`, `SCANNER_RTSP_IP` (dotted-quad, not a DNS name — Uniden RTSP returns 400 on hostnames), and `WEBRTC_HOST` (the LAN IP or hostname of the Docker host).
3. Deploy. Portainer should list **8080** on `scanhead-app` and **8554**, **8888**, **8889**, **8189/udp** on `scanhead-mediamtx`. Open `http://<docker-host>:8080`.

Published app images are on Docker Hub as `derpmhichurp/scanhead`. Compose still builds locally by default; to pull instead, set `IMAGE_TAG` (and optionally `DOCKER_HUB_REGISTRY_USERNAME` / `DOCKER_HUB_IMAGE_NAME`).

| Git tag | Docker tags |
|---|---|
| `scanhead/1.0.0` on `main` | `1.0.0`, `latest` |
| `scanhead/1.0.0-beta.1` on `main` | `1.0.0-beta.1` only |
| `scanhead/<version>` on any other branch | `{version}`, `beta` |

```bash
git tag scanhead/1.0.0
git push origin scanhead/1.0.0
```

### App-only (control UI without Compose)

Useful on Windows, or when MediaMTX already runs elsewhere:

```bash
cd app
python -m venv .venv
.venv/Scripts/activate   # Windows
pip install -r requirements-dev.txt
set SCANNER_IP=scanner.plud.org
python -m uvicorn scanhead.main:app --factory --host 0.0.0.0 --port 8080
```

```bash
cd app
python -m pytest
SCANHEAD_LIVE=1 python -m pytest tests/test_live.py
```

## Security

The radio’s network interfaces are unauthenticated. Keep ScanHead and the scanner on a trusted LAN. Do not publish ScanHead or the scanner’s UDP/RTSP ports on the public Internet.

Do not run Siren, ProScan, or Uniden’s RH-536HP remote-head tool at the same time as ScanHead. Only one controller should own the scanner’s `PSI` session.
