# ScanHead — Claude

Tool-specific entry for Claude Code. Durable workflow notes live under [`ai/`](ai/README.md), not in this file.

## Always

- Match existing code style. Do not add drive-by refactors or extra markdown the user did not ask for.
- TDD is the default. Read [`ai/tdd.md`](ai/tdd.md) before adding features, fixing bugs, or writing tests.
- Do not commit unless asked. Do not force-push or skip hooks.
- The scanner’s UDP/RTSP interfaces have no auth. Keep probes on the trusted LAN. Do not expose ScanHead or the radio to the Internet.

## When to read `ai/`

| Situation | File |
|---|---|
| Run, restart, ports, PowerShell vs Git Bash, Docker vs uvicorn, frozen display, PSI, Windows local testing | [`ai/windows_local_dev.md`](ai/windows_local_dev.md) |
| Adding features, fixing bugs, writing or running pytest, TDD | [`ai/tdd.md`](ai/tdd.md) |

If you add a new `ai/*.md` file, list it in [`ai/README.md`](ai/README.md) and add a row here.

## Humans

Contributor-facing process (including how we test on Windows) is [`CONTRIBUTING.md`](CONTRIBUTING.md). Protocol and design: [`docs/protocol.md`](docs/protocol.md), [`docs/PLAN.md`](docs/PLAN.md).
