# Uniden remote-command cheat sheet

ScanHead talks to the scanner on **UDP port 50536**. Commands are ASCII, CR-terminated, no handshake and no header. Validated against a BCD536HP (firmware 1.28.14) at lab time.

Official references:

- [BCDx36HP Remote Command Specification v1.05](https://info.uniden.com/twiki/pub/UnidenMan4/BCD536HPFirmwareUpdate/BCDx36HP_RemoteCommand_Specification_V1_05.pdf)
- [UB375Z Menu Tree Specification v1.07](https://info.uniden.com/twiki/pub/UnidenMan4/BCD536HPFirmwareUpdate/BCDx36HP_MenuTreeSpecification_V1_07.pdf)
- [SDS200 Virtual Serial on Network Specification](https://info.uniden.com/twiki/pub/UnidenMan4/SDS200FirmwareUpdate/SDS200_Virtual_Serial_on_Network_Specification_V1_00.pdf)

## Framing

Simple replies: `MDL,BCD536HP\r`

XML replies start with `CMD,<XML>,\r` then an XML document. Large XML (`GSI` / `PSI` / `GLT` / `MSI`) is split across UDP datagrams. Reassemble with the `Footer` node (`No` sequence, `EOT="1"` on the last packet). Retry the command if a `No` is missing. This radio uses `Footer`; some docs say `Foot`.

`PSI,500\r` starts periodic `ScannerInfo` pushes (interval in ms). `PSI,0\r` stops. Bare `PSI\r` returns the current interval (`PSI,0` when stopped).

## Identify / levels

| Command | Meaning |
|---|---|
| `MDL` | Model (`BCD536HP`, `SDS200`, …) |
| `VER` | Firmware (`VER,Version 1.28.14`) |
| `VOL` / `VOL,<0-29>` | Get/set volume (436: 0–15) |
| `SQL` / `SQL,<0-19>` | Get/set squelch (436: 0–15) |

## Keys

`KEY,[CODE],[MODE]\r` with MODE `P` press, `L` long, `H` hold, `R` release. Yes is `KEY,E,P`.

| Code | 536 | Notes |
|---|---|---|
| `0`–`9` `.` | Digit / No | `.` is No |
| `E` | Yes / Enter | |
| `M` | Menu | |
| `F` | Func | |
| `L` | Avoid | |
| `A` `B` `C` | System / Dept / Channel | SDS: soft keys |
| `Y` | Replay | |
| `Z` `T` `R` | Zip / Service / Range | |
| `>` `<` `^` | Rotary right / left / push | |
| `V` `Q` | Volume / squelch knob push | |

## Status

`GSI` one-shot `ScannerInfo` XML. `PSI,<ms>` periodic. Useful nodes: `Property` (VOL, SQL, Sig, Rssi, Mute, P25Status), `System`, `Department`, `TGID` / `ConvFrequency`, `ViewDescription` (overwrite text and popups).

## Hold / skip / avoid

Indexes from `GLT` (and the current `GSI`/`PSI` snapshot) are the handles.

| Command | Shape |
|---|---|
| `HLD,[tkw],[xxx1],[xxx2]` | Hold |
| `NXT,[tkw],[xxx1],[xxx2],[COUNT]` | Next (COUNT 1–8) |
| `PRV,[tkw],[xxx1],[xxx2],[COUNT]` | Previous |
| `AVD,[tkw],[xxx1],[xxx2],[STATUS]` | 1 permanent, 2 temporary, 3 stop |

Common `tkw`: `SYS`, `DEPT`, `SITE`, `CFREQ`, `TGID`, `WX`, `FTO`.

## Lists and quick keys

`GLT,FL` then `GLT,SYS,<fl>` / `GLT,DEPT,<sys>` / `GLT,TGID,<dept>` / `GLT,CFREQ,<dept>` / `GLT,SITE,<sys>` / `GLT,SFREQ,<site>` plus `IREC_FILE`, `UREC`, `UREC_FILE`, discovery, FTO, avoid lists.

`FQK` / `SQK,<fav>` / `DQK,<fav>,<sys>` — 100 slots, `0` missing, `1` off, `2` on.

`JNT,<fl>,<sys>,<chan>` jumps by number tag.

## Modes and menus

`JPM,[MODE],[INDEX]` — `SCN_MODE`, `CC_MODE`, `WX_MODE` (`NORMAL`, `A_ONLY`, `SAME_1`…), `FTO_MODE`, `IREC_MODE`, `UREC_MODE`, `TDIS_MODE`, `CDIS_MODE`, …

`MNU,[MENU_ID],[INDEX]` then `MSI` XML (`TypeSelect` / `TypeInput` / `TypeLocation` / `TypeError`). `MSV,,[VALUE]` sets (commas in VALUE become tabs). `MSB,,` back one level; `MSB,,RETURN_PREVOUS_MODE` exits (Uniden’s spelling).

## Other

`URC` / `URC,0|1` user recording. `DTM` clock. `LCR` lat/lon/range. `SVC` service-type bits. `AST,RAW_DATA_OUTPUT` is USB-only.

## Audio

```text
rtsp://<scanner-dotted-quad>/au:scanner.au
```

Uniden’s RTSP server returns **400** if the URL host is a DNS name (`OPTIONS *` also 400s). Use the radio’s dotted-quad. G.711 µ-law (PCMU) over RTSP/RTP. ScanHead’s MediaMTX process is the sole RTSP client of the radio (path `raw`). ffmpeg then high-pass filters, noise-gates scan hiss, and compresses speech, republishing PCMU on path `scanner`. The UI uses WebRTC (WHEP `/scanner/whep`); VLC uses `rtsp://<host>:8554/scanner`. HLS cannot mux G.711, so `/scanner/index.m3u8` is not usable. The MediaMTX image must be the `*-ffmpeg` variant.
