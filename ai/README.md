# AI instruction files

Generic, tool-agnostic guidance for agents working in this repo. Cursor and Claude load a short base file (`AGENTS.md`, `CLAUDE.md`) and open files here when the task matches.

| File | Read when |
|---|---|
| [windows_local_dev.md](windows_local_dev.md) | Starting, restarting, or debugging the app on a Windows machine; ports; PowerShell vs Git Bash; Docker Desktop vs uvicorn; live scanner / PSI / UDP |
| [tdd.md](tdd.md) | Adding a feature, fixing a bug, or writing tests; TDD is the default loop |

Add a new file here for each distinct workflow. Keep each file one concern. Update the table and the “when to read” lists in `AGENTS.md` and `CLAUDE.md` in the same change.
