"""Bootstrap completo del proyecto.

Crea el entorno virtual local si falta, instala las dependencias fijadas y
luego delega en `run.py` para levantar Lavalink y el bot.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from getpass import getpass


ROOT_DIR = Path(__file__).resolve().parent
VENV_DIR = ROOT_DIR / "venv"
VENV_PYTHON = VENV_DIR / "bin" / "python"
REQUIREMENTS_FILE = ROOT_DIR / "requirements.txt"
RUNNER_SCRIPT = ROOT_DIR / "run.py"
ENV_PATH = ROOT_DIR / ".env"
ENV_EXAMPLE_PATH = ROOT_DIR / ".env.example"


def read_env_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def parse_env_lines(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env_value(path: Path, key: str, value: str) -> None:
    lines = read_env_file(path)
    updated = False
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            current_key = stripped.split("=", 1)[0].strip()
            if current_key == key:
                new_lines.append(f"{key}={value}")
                updated = True
                continue
        new_lines.append(line)

    if not updated:
        if new_lines and new_lines[-1] != "":
            new_lines.append("")
        new_lines.append(f"{key}={value}")

    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def ensure_dotenv() -> None:
    if not ENV_PATH.exists() and ENV_EXAMPLE_PATH.exists():
        ENV_PATH.write_text(ENV_EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")


def ensure_bot_token() -> None:
    env_values = parse_env_lines(read_env_file(ENV_PATH))
    for key, value in env_values.items():
        os.environ.setdefault(key, value)

    bot_token = os.getenv("BOT_TOKEN")
    if bot_token:
        if env_values.get("BOT_TOKEN") != bot_token:
            write_env_value(ENV_PATH, "BOT_TOKEN", bot_token)
        return

    if not sys.stdin.isatty():
        raise RuntimeError("BOT_TOKEN no encontrado. Exporta BOT_TOKEN o crea .env antes de ejecutar bootstrap.py")

    print("BOT_TOKEN no encontrado en .env.")
    token = getpass("Pega el token del bot de Discord: ").strip()
    if not token:
        raise RuntimeError("No se recibio BOT_TOKEN")

    write_env_value(ENV_PATH, "BOT_TOKEN", token)
    os.environ["BOT_TOKEN"] = token


def ensure_java() -> None:
    java_path = shutil.which("java")
    if java_path is None:
        raise RuntimeError("No se encontro Java en PATH. Instala un JDK compatible con Lavalink antes de ejecutar bootstrap.py")


def ensure_venv() -> None:
    if VENV_PYTHON.exists():
        return

    subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True, cwd=ROOT_DIR)


def install_requirements() -> None:
    if not REQUIREMENTS_FILE.exists():
        raise RuntimeError(f"No se encontro requirements.txt en {REQUIREMENTS_FILE}")

    subprocess.run(
        [str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"],
        check=True,
        cwd=ROOT_DIR,
    )
    subprocess.run(
        [str(VENV_PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
        check=True,
        cwd=ROOT_DIR,
    )


def main() -> int:
    ensure_venv()
    install_requirements()
    ensure_dotenv()
    ensure_java()
    ensure_bot_token()

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    process = subprocess.run([str(VENV_PYTHON), str(RUNNER_SCRIPT)], cwd=ROOT_DIR, env=env)
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
