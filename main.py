from __future__ import annotations

import asyncio

import discord
from discord.ext import commands
import lavalink

from config import BOT_TOKEN, LAVALINK_HOST, LAVALINK_PASSWORD, LAVALINK_PORT


INTENTS = discord.Intents.default()
INTENTS.guilds = True
INTENTS.voice_states = True


class MusicBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=INTENTS)
        self._lavalink_ready = False
        self._slash_synced = False

    async def setup_hook(self) -> None:
        await self.load_extension("cogs.music")

    def _ensure_lavalink(self) -> None:
        if self._lavalink_ready:
            return

        if self.user is None:
            raise RuntimeError("No se pudo inicializar Lavalink sin el usuario del bot.")

        self.lavalink = lavalink.Client(self.user.id)
        self.lavalink.add_node(
            host=LAVALINK_HOST,
            port=LAVALINK_PORT,
            password=LAVALINK_PASSWORD,
            region="us",
            name="main_node",
        )
        self._lavalink_ready = True

    async def on_ready(self) -> None:
        self._ensure_lavalink()

        if not self._slash_synced:
            synced = await self.tree.sync()
            self._slash_synced = True
            print(f"[{self.user}] {len(synced)} comandos slash sincronizados", flush=True)

        print(f"Bot listo como {self.user} en {len(self.guilds)} servidores", flush=True)


async def main() -> int:
    bot = MusicBot()

    async with bot:
        await bot.start(BOT_TOKEN)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
