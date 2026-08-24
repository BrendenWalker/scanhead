# Windows local development

Use this file when running, restarting, or debugging ScanHead **on a Windows workstation**, not when documenting Linux Docker production.

Production remains Linux Compose with **host networking** (`compose.yaml`). Docker Desktop on Windows cannot provide that, so local UI/control work uses **uvicorn**, not Compose.

## Lab scanner

The primary lab radio is a **BCD536HP** at `scanner.plud.org` (LAN `192.168.42.10`). UDP **50536** for control, RTSP `rtsp://scanner.plud.org/au:scanner.au` for audio.

`SCANNER_IP` is required. PowerShell and Git Bash set it differently:

```powershell
# PowerShell (this repo’s default local shell)
$env:SCANNER_IP='scanner.plud.org'; python -m uvicorn scanhead.main:app --factory --host 127.0.0.1 --port 8080
```

```bash
# Git Bash / MINGW — do not use $env:
SCANNER_IP=scanner.plud.org python -m uvicorn scanhead.main:app --factory --host 127.0.0.1 --port 8080
```

Run those from `app/`. Success looks like `connected to BCD536HP` then `Uvicorn running on http://127.0.0.1:8080`.

## Process model (do not mix this up)

| What | Role |
|---|---|
| **uvicorn** | The Windows local app. This is what you start/stop for UI and control. |
| **Compose / MediaMTX** | Linux Docker host on the scanner LAN. Not how we iterate on Windows. |

“Restart ScanHead” on Windows means **stop the old uvicorn, then start a new one**. It does **not** mean `docker compose restart`. A container (or leftover uvicorn) bound to **8080** will block the new process (`WinError 10048`). Stop the listener first; do not start a second one beside it.

Find and stop a stale `127.0.0.1:8080`:

```powershell
netstat -ano | findstr ":8080"
taskkill /PID <pid> /F
```

Python changes need a uvicorn restart. Static JS/CSS need a hard refresh (Ctrl+F5) after the server is on the new code.

## Exclusive scanner session

Uniden allows **one** PSI subscriber and typically **one** RTSP client. Do not run Siren, ProScan, RH-536HP, Compose, and uvicorn against the same radio at once.

PSI is pushed only to the **last UDP client** that sent `PSI,<interval>`. One-shot probe scripts (`MDL`/`GSI`/`PSI` from a throwaway socket) steal the live display. The app reclaims PSI if it goes quiet; still avoid extra UDP clients while testing the UI.

VOL/SQL can work while the display looks frozen: those are request/response. Live channel text is PSI. If the display is stuck, restart uvicorn so it owns PSI again, then reload the page.

## Tests

From `app/`:

```powershell
python -m pytest
$env:SCANHEAD_LIVE='1'; python -m pytest tests/test_live.py
```

Unit tests do not need the radio. `SCANHEAD_LIVE=1` hits `scanner.plud.org`. TDD is the default; see [`tdd.md`](tdd.md).

## Audio on Windows

Control UI works without MediaMTX. **Play audio** needs MediaMTX on a Linux host with host networking. Do not expect WebRTC from Docker Desktop on Windows.
