"""Integración de voz para lavalink.py con discord.py."""

from __future__ import annotations

import asyncio

import discord
import lavalink
from lavalink.errors import ClientError


class LavalinkVoiceClient(discord.VoiceProtocol):
    """Voice protocol que enlaza discord.py con lavalink.py."""

    def __init__(self, client: discord.Client, channel: discord.abc.Connectable):
        self.client = client
        self.channel = channel
        self.guild_id = channel.guild.id
        self._destroyed = False

        lavalink_client = getattr(self.client, "lavalink", None)
        if lavalink_client is None:
            raise RuntimeError("Lavalink client not initialized on the bot.")

        self.lavalink = lavalink_client

    def _log_player_state(self, label: str) -> None:
        player = self.lavalink.player_manager.get(self.guild_id)

        if player is None:
            print(f"[VOICE] {label} player=None", flush=True)
            return

        voice_state = getattr(player, "_voice_state", {})
        print(
            f"[VOICE] {label} player_connected={player.is_connected} "
            f"channel_id={player.channel_id} voice_keys={sorted(voice_state.keys())} "
            f"session={voice_state.get('sessionId')!r} endpoint={voice_state.get('endpoint')!r}",
            flush=True,
        )

    async def _wait_for_available_node(self, timeout: float = 10.0):
        deadline = asyncio.get_running_loop().time() + timeout

        while asyncio.get_running_loop().time() < deadline:
            node = self.lavalink.node_manager.find_ideal_node()
            if node is not None:
                return node

            await asyncio.sleep(0.25)

        return None

    async def on_voice_server_update(self, data):
        print(f"[VOICE] server update guild={data.get('guild_id')} endpoint={data.get('endpoint')}", flush=True)
        await self.lavalink.voice_update_handler({"t": "VOICE_SERVER_UPDATE", "d": data})
        self._log_player_state("after server update")

    async def on_voice_state_update(self, data):
        channel_id = data["channel_id"]

        print(
            f"[VOICE] state update guild={data.get('guild_id')} user={data.get('user_id')} channel={channel_id}",
            flush=True,
        )

        if not channel_id:
            await self._destroy()
            return

        channel = self.client.get_channel(int(channel_id))
        if channel is not None:
            self.channel = channel

        await self.lavalink.voice_update_handler({"t": "VOICE_STATE_UPDATE", "d": data})
        self._log_player_state("after state update")

    async def connect(
        self,
        *,
        timeout: float,
        reconnect: bool,
        self_deaf: bool = True,
        self_mute: bool = False,
    ) -> None:
        print(
            f"[VOICE] connect guild={self.channel.guild.id} channel={self.channel.id} deaf={self_deaf} mute={self_mute}",
            flush=True,
        )

        node = await self._wait_for_available_node(timeout=timeout)
        if node is None:
            raise ClientError("No available nodes!")

        self.lavalink.player_manager.create(guild_id=self.channel.guild.id, node=node)
        await self.channel.guild.change_voice_state(
            channel=self.channel, self_mute=self_mute, self_deaf=self_deaf
        )
        self._log_player_state("after connect request")

    async def disconnect(self, *, force: bool = False) -> None:
        print(f"[VOICE] disconnect guild={self.guild_id} force={force}", flush=True)
        player = self.lavalink.player_manager.get(self.channel.guild.id)

        if not force and (player is None or not player.is_connected):
            return

        await self.channel.guild.change_voice_state(channel=None)

        if player is not None:
            player.channel_id = None

        await self._destroy()

    async def _destroy(self):
        self.cleanup()

        if self._destroyed:
            return

        self._destroyed = True

        try:
            await self.lavalink.player_manager.destroy(self.guild_id)
        except ClientError:
            pass