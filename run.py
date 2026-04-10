"""Arranque automatizado del bot y Lavalink.

Si `LAVALINK_PASSWORD` esta vacio, se genera uno nuevo, se guarda en `.env`
y se usa para arrancar ambos procesos.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
ENV_PATH = ROOT_DIR / ".env"
ENV_EXAMPLE_PATH = ROOT_DIR / ".env.example"
LAVALINK_DIR = ROOT_DIR / "lavalink"
LAVALINK_JAR = LAVALINK_DIR / "Lavalink.jar"
LAVALINK_VERSION = os.getenv("LAVALINK_VERSION", "4.2.2")
LAVALINK_JAR_URL = os.getenv(
    "LAVALINK_JAR_URL",
    f"https://github.com/lavalink-devs/Lavalink/releases/download/{LAVALINK_VERSION}/Lavalink.jar",
)
BOT_ENTRYPOINT = ROOT_DIR / "main.py"


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


def ensure_env() -> dict[str, str]:
    if not ENV_PATH.exists() and ENV_EXAMPLE_PATH.exists():
        ENV_PATH.write_text(ENV_EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    env_values = parse_env_lines(read_env_file(ENV_PATH))
    for key, value in env_values.items():
        os.environ.setdefault(key, value)

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN must be set in .env before using run.py")

    lavalink_password = os.getenv("LAVALINK_PASSWORD")
    if not lavalink_password:
        lavalink_password = secrets.token_urlsafe(24)
        write_env_value(ENV_PATH, "LAVALINK_PASSWORD", lavalink_password)
        os.environ["LAVALINK_PASSWORD"] = lavalink_password

    return {
        "BOT_TOKEN": bot_token,
        "LAVALINK_HOST": os.getenv("LAVALINK_HOST", "localhost"),
        "LAVALINK_PORT": os.getenv("LAVALINK_PORT", "2333"),
        "LAVALINK_PASSWORD": lavalink_password,
    }


def wait_for_lavalink(host: str, port: str, password: str, timeout_seconds: int = 60) -> None:
    deadline = time.monotonic() + timeout_seconds
    url = f"http://{host}:{port}/version"
    request = urllib.request.Request(url, headers={"Authorization": password})

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            time.sleep(1)

    raise RuntimeError("Lavalink no respondio a tiempo en /version")


def ensure_lavalink_jar() -> None:
    if LAVALINK_JAR.exists() and LAVALINK_JAR.stat().st_size > 0:
        return

    LAVALINK_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = LAVALINK_JAR.with_suffix(".jar.part")

    try:
        print(f"[Lavalink] Descargando {LAVALINK_VERSION} desde {LAVALINK_JAR_URL}")
        with urllib.request.urlopen(LAVALINK_JAR_URL, timeout=30) as response:
            status = getattr(response, "status", None)
            if status is not None and status >= 400:
                raise RuntimeError(f"Respuesta inesperada al descargar Lavalink: {status}")

            with temp_path.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)

        temp_path.replace(LAVALINK_JAR)
    except Exception as exc:
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(
            f"No se pudo preparar Lavalink.jar desde {LAVALINK_JAR_URL}: {exc}"
        ) from exc


def main() -> int:
    env = os.environ.copy()
    configured = ensure_env()
    env.update(configured)

    ensure_lavalink_jar()

    lavalink_process = subprocess.Popen(
        ["java", "-jar", "Lavalink.jar", "--spring.config.additional-location=file:./"],
        cwd=LAVALINK_DIR,
        env=env,
    )

    bot_process: subprocess.Popen[str] | None = None

    try:
        wait_for_lavalink(env["LAVALINK_HOST"], env["LAVALINK_PORT"], env["LAVALINK_PASSWORD"])
        bot_process = subprocess.Popen([sys.executable, str(BOT_ENTRYPOINT)], cwd=ROOT_DIR, env=env)
        return bot_process.wait()
    except KeyboardInterrupt:
        return 130
    finally:
        if bot_process and bot_process.poll() is None:
            bot_process.terminate()
            try:
                bot_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                bot_process.kill()

        if lavalink_process.poll() is None:
            lavalink_process.terminate()
            try:
                lavalink_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                lavalink_process.kill()


if __name__ == "__main__":
    raise SystemExit(main())