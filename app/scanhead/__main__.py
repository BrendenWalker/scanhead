"""python -m scanhead"""

from __future__ import annotations

import os

import uvicorn

from scanhead.main import app


def main() -> None:
    port = int(os.environ.get("APP_PORT", "8080"))
    uvicorn.run(app, factory=True, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
