# Contributing

## Windows local testing (this repo’s default loop)

On Windows we do **not** use Docker Compose for day-to-day UI/control work. Compose needs Linux **host networking** for scanner RTP; Docker Desktop cannot do that.

Local loop:

1. Work from `app/` with the live lab radio (`scanner.plud.org`, a BCD536HP).
2. Start **one** uvicorn process (PowerShell). Do not start a second copy, and do not leave Compose bound to 8080 at the same time.
3. Open `http://127.0.0.1:8080`. Restart uvicorn after Python changes; hard-refresh after JS/CSS changes.

```powershell
cd app
python -m pytest
$env:SCANNER_IP='scanner.plud.org'; python -m uvicorn scanhead.main:app --factory --host 127.0.0.1 --port 8080
```

Agents (and anyone hitting env-var, port, or “stuck display” issues) should follow [`ai/windows_local_dev.md`](ai/windows_local_dev.md). That file is the source of truth for PowerShell vs Git Bash, exclusive PSI, and what “restart” means.

Linux production deploy stays `docker compose up --build` with `SCANNER_IP` in `.env` — see the README.

## Tests

TDD is the default: write a failing pytest first, then the production change. Agents follow [`ai/tdd.md`](ai/tdd.md).

```powershell
cd app
python -m pytest
$env:SCANHEAD_LIVE='1'; python -m pytest tests/test_live.py
```

Unit tests do not need the radio. Live tests send UDP to the lab scanner. Do not run them in parallel with another PSI owner (Siren, ProScan, a second ScanHead).

## Changes

- Keep diffs scoped to the task. No drive-by refactors or extra docs unless the task is documentation.
- Do not commit `.env` or secrets. `.env.example` is the template.
- Do not commit unless asked.
- Protocol notes: [`docs/protocol.md`](docs/protocol.md). Design: [`docs/PLAN.md`](docs/PLAN.md).
