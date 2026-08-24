# Tests and TDD

TDD is the **default** way we change ScanHead. Do not implement a behavior and “add tests later.” Agents read this file before adding features, fixing bugs, or writing tests.

## Loop

1. Write a failing pytest under `app/tests/` (red).
2. Write the smallest production change that makes it pass (green).
3. Refactor if needed; keep tests green.
4. From `app/`, run `python -m pytest` before claiming the work is done.

A bug fix starts the same way: reproduce with a failing test, then change production code.

## Where tests live

| Layer | How | File |
|---|---|---|
| Settings | `monkeypatch` env vars | `tests/test_config.py` |
| Protocol helpers | Pure functions, no UDP | `tests/test_protocol.py` |
| XML framing / listen view | Captured `GSI`/`PSI`/`GLT` strings | `tests/test_xmlutil.py` |
| Radio UDP client | Fake scanner on `127.0.0.1` | `tests/test_radio.py` |
| FastAPI routes | `FakeRadio` + `TestClient` | `tests/test_api.py` |
| Live BCD536HP | Real UDP to the lab radio | `tests/test_live.py` |

Unit tests must not touch `scanner.plud.org`. Do not set `SCANHEAD_LIVE` in CI.

`create_app(settings, radio=...)` accepts a stand-in radio so HTTP tests never open a UDP socket. Do not talk to the lab scanner to prove a route works.

## Commands

From `app/` (PowerShell):

```powershell
python -m pytest
python -m pytest tests/test_api.py -q
```

Live radio (exclusive PSI; do not run beside Siren, ProScan, or another ScanHead):

```powershell
$env:SCANHEAD_LIVE='1'; python -m pytest tests/test_live.py
```

## What to cover

- New command, XML field, or listen-view rule: pytest first, then `protocol.py` / `xmlutil.py` / `radio.py`.
- New or changed HTTP route: `tests/test_api.py` first (status codes, validation, RadioError → 502).
- Validation that does not need the radio (bad GLT kind, avoid status, missing `SCANNER_IP`) stays a unit test.

## Out of scope for pytest

Browser DOM, MediaMTX/WebRTC audio, and Docker Hub publish. After protocol and API tests are green, exercise the UI in the browser against uvicorn. Audio still needs Linux host-network MediaMTX.

## CI

`.github/workflows/docker-build.yml` runs `python -m pytest` from `app/` on pull requests and before publishing an image. Keep that job green; do not skip tests to land a feature.
