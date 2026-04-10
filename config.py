"""Configuracion del bot y Lavalink.

Lee variables de entorno y, si existe, carga primero el archivo `.env` local.
"""

from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
ENV_PATH = ROOT_DIR / ".env"


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_dotenv_file(ENV_PATH)

BOT_TOKEN = os.getenv("BOT_TOKEN")
LAVALINK_HOST = os.getenv("LAVALINK_HOST", "localhost")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", "2333"))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD")


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN must be set in the environment or .env")

if not LAVALINK_PASSWORD:
    raise RuntimeError("LAVALINK_PASSWORD must be set in the environment or .env")
