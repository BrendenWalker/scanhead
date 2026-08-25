# ScanHead

Browser-based remote head for network-connected Uniden scanners (BCD536HP, SDS200, and compatible models). Replaces Uniden’s Siren app on a trusted LAN.

This image is the ScanHead control API and SPA. Run it with MediaMTX (see the [compose file](https://github.com/BrendenWalker/scanhead/blob/main/compose.yaml) in the GitHub repo). Do not expose ScanHead or the scanner’s UDP/RTSP ports on the public Internet.

## Tags

- `latest` — stable release from `main`
- `beta` — floating pre-release (tag not on `main`)
- `1.0.0` — pinned semver

## Usage

Prefer Compose on a Linux host on the same LAN as the scanner (host networking is required for RTSP/RTP):

```bash
git clone https://github.com/BrendenWalker/scanhead.git
cd scanhead
cp .env.example .env
# set SCANNER_IP
docker compose up -d
```

To pull this image instead of building locally, set the app service image to `derpmhichurp/scanhead:latest` (or a pinned tag).

## Environment Variables

- `SCANNER_IP` — scanner address (required)
- `SCANNER_PORT` — UDP control port (default: 50536)
- `APP_PORT` — HTTP port (default: 8080)
- `PSI_INTERVAL_MS` — status push interval (default: 500)
- `MEDIAMTX_WHEP_PORT` — WebRTC/WHEP port (default: 8889)
- `MEDIAMTX_HLS_PORT` — listen-only HLS for VLC/MPlayer (default: 8888; AAC path `player`)
- `MEDIAMTX_RTSP_PORT` — MediaMTX RTSP republish (default: 8554)

See the GitHub repository for protocol notes and Windows local-dev instructions.
