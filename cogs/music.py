import asyncio

import discord
from discord import app_commands
from discord.ext import commands
import lavalink
from lavalink.errors import ClientError

from utils.embeds import BOT_ERROR, BOT_PRIMARY, BOT_SUCCESS, BOT_WARNING, build_base_embed, format_duration, progress_bar
from utils.lavalink_voice import LavalinkVoiceClient
from utils.search import (
    _canonicalize_youtube_playlist_url,
    is_youtube_url,
    search_public_youtube_playlist,
    search_youtube_best_match,
)


class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _get_bot_member(self, interaction: discord.Interaction):
        if interaction.guild is None or self.bot.user is None:
            return None

        return interaction.guild.me or interaction.guild.get_member(self.bot.user.id)

    def _get_lavalink_client(self):
        return getattr(self.bot, "lavalink", None)

    def _get_player(self, guild_id: int):
        lavalink_client = self._get_lavalink_client()

        if lavalink_client is None:
            return None

        return lavalink_client.player_manager.get(guild_id)

    def _build_embed(self, interaction: discord.Interaction, title: str, description: str | None = None, *, color=BOT_PRIMARY):
        embed = build_base_embed(title=title, description=description, color=color)

        if interaction.guild and interaction.guild.icon:
            embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url)

        requester_name = interaction.user.display_name if interaction.user else "Usuario"
        requester_avatar = getattr(getattr(interaction.user, "display_avatar", None), "url", None)
        if requester_avatar:
            embed.set_footer(text=f"Solicitado por {requester_name}", icon_url=requester_avatar)
        else:
            embed.set_footer(text=f"Solicitado por {requester_name}")

        return embed

    async def _send_embed(self, interaction: discord.Interaction, embed: discord.Embed):
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)

    async def _send_reply(self, interaction: discord.Interaction, content: str):
        await self._send_embed(interaction, self._build_embed(interaction, "Actualización", content, color=BOT_PRIMARY))

    async def _send_error(self, interaction: discord.Interaction, content: str):
        await self._send_embed(interaction, self._build_embed(interaction, "No se pudo completar", content, color=BOT_ERROR))

    def _require_voice_channel(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return None, "Este comando solo funciona en servidores."

        if not interaction.user.voice:
            return None, "Debes estar en un canal de voz para usar este comando."

        return interaction.user.voice.channel, None

    def _require_control_player(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return None, "Este comando solo funciona en servidores."

        if not interaction.user.voice:
            return None, "Debes estar en un canal de voz para controlar la reproduccion."

        player = self._get_player(interaction.guild.id)
        if player is None:
            return None, "No estoy conectado a ningun canal de voz."

        user_channel = interaction.user.voice.channel
        if player.channel_id != user_channel.id:
            return None, "Debes estar en el mismo canal de voz que el bot."

        return player, None

    async def _wait_for_remote_voice(self, player, timeout: float = 10.0) -> bool:
        """Espera a que Lavalink marque la sesión de voz como conectada."""
        deadline = asyncio.get_running_loop().time() + timeout

        while asyncio.get_running_loop().time() < deadline:
            try:
                raw_player = await player.node.get_player(player.guild_id)
            except Exception as exc:
                print(f"[VOICE] estado remoto no disponible todavía: {type(exc).__name__}: {exc}", flush=True)
                await asyncio.sleep(0.5)
                continue

            state = raw_player.get("state", {})
            print(
                f"[VOICE] estado remoto guild={player.guild_id} connected={state.get('connected')} position={state.get('position')} ping={state.get('ping')}",
                flush=True,
            )

            if state.get("connected"):
                return True

            await asyncio.sleep(0.5)

        return False

    async def _ensure_player(self, interaction: discord.Interaction):
        lavalink_client = self._get_lavalink_client()

        if lavalink_client is None:
            return None, "Lavalink todavía no está inicializado."

        voice_channel, error_message = self._require_voice_channel(interaction)
        if voice_channel is None:
            return None, error_message

        bot_member = self._get_bot_member(interaction)
        if bot_member is None:
            return None, "No pude identificar al bot en este servidor."

        perms = voice_channel.permissions_for(bot_member)
        if not perms.connect or not perms.speak:
            missing = []
            if not perms.connect:
                missing.append("CONNECT")
            if not perms.speak:
                missing.append("SPEAK")
            return None, f"No tengo permisos de voz suficientes en **{voice_channel.name}**: {', '.join(missing)}."

        voice_client = interaction.guild.voice_client

        if voice_client is None:
            try:
                await voice_channel.connect(cls=LavalinkVoiceClient, self_deaf=True)
            except ClientError as exc:
                print(f"[VOICE] no se pudo crear el player: {exc}", flush=True)
                return None, "Lavalink no tiene nodos disponibles ahora mismo. Espera unos segundos e inténtalo otra vez."
        elif voice_client.channel.id != voice_channel.id:
            return None, "Debes estar en el mismo canal de voz que el bot."

        player = lavalink_client.player_manager.get(interaction.guild.id)
        if player is None:
            try:
                player = lavalink_client.player_manager.create(interaction.guild.id)
            except ClientError as exc:
                print(f"[VOICE] no se pudo recuperar el player: {exc}", flush=True)
                return None, "Lavalink no tiene nodos disponibles ahora mismo. Espera unos segundos e inténtalo otra vez."

        for _ in range(20):
            if player.is_connected:
                break
            await asyncio.sleep(0.1)

        if not await self._wait_for_remote_voice(player, timeout=10.0):
            print("[VOICE] Lavalink no confirmó la conexión de voz a tiempo", flush=True)
            return None, "No pude confirmar la conexión de voz con Lavalink. Inténtalo otra vez en unos segundos."

        return player, None

    async def _queue_query(self, interaction: discord.Interaction, query: str, *, log_prefix: str):
        player, error_message = await self._ensure_player(interaction)
        if player is None:
            return None, None, False, error_message

        normalized_query = query
        search_result = None

        if not is_youtube_url(query):
            search_result = await search_youtube_best_match(query, limit=12)
            if search_result:
                normalized_query = search_result["url"]
                uploader = search_result.get("uploader") or search_result.get("channel") or "desconocido"
                print(f"[{log_prefix}] Mejor coincidencia: {search_result['title']} | {uploader}")
            else:
                normalized_query = f"ytsearch:{query}"

        print(f"[{log_prefix}] Consultando Lavalink: {normalized_query}")
        try:
            results = await player.node.get_tracks(normalized_query)
        except Exception as exc:
            if search_result is not None:
                fallback_query = f"ytsearch:{query}"
                print(f"[{log_prefix}] Fallback a búsqueda directa: {type(exc).__name__}: {exc}")
                print(f"[{log_prefix}] Consultando Lavalink: {fallback_query}")
                results = await player.node.get_tracks(fallback_query)
            else:
                raise

        if not results or not results.tracks:
            print(f"[{log_prefix}] ✗ No se encontraron resultados")
            return None, None, False, f"No se encontró ninguna canción con: '{query}'"

        tracks = results.tracks
        display_title = ""

        if results.load_type == lavalink.LoadType.PLAYLIST:
            for track in tracks:
                track.requester = interaction.user.id
                player.add(track)

            playlist_name = getattr(results.playlist_info, "name", "Playlist")
            display_title = f"{playlist_name} ({len(tracks)} canciones)"
        else:
            track = tracks[0]
            track.requester = interaction.user.id
            player.add(track)
            display_title = track.title or query

        print(f"[{log_prefix}] ✓ En cola: {display_title}")

        started = False
        if not player.is_playing:
            await player.play()
            started = True
            print(f"[{log_prefix}] ✓ Reproducción iniciada")

        return player, display_title, started, None

    async def _queue_playlist_query(self, interaction: discord.Interaction, query: str, *, log_prefix: str):
        player, error_message = await self._ensure_player(interaction)
        if player is None:
            return None, None, False, error_message

        playlist_url = _canonicalize_youtube_playlist_url(query) or query.strip()
        playlist_result = None

        if not is_youtube_url(playlist_url):
            playlist_result = await search_public_youtube_playlist(query, limit=8)
            if playlist_result:
                playlist_url = playlist_result['url']
                print(f"[{log_prefix}] Mejor coincidencia de playlist: {playlist_result['title']} | {playlist_url}")
            else:
                return None, None, False, (
                    f"No encontré una playlist pública con: '{query}'. "
                    "Prueba con el título exacto + autor o pega la URL directa."
                )

        print(f"[{log_prefix}] Consultando Lavalink: {playlist_url}")
        try:
            results = await player.node.get_tracks(playlist_url)
        except Exception as exc:
            return None, None, False, f"No pude cargar esa playlist: {exc}"

        if not results or not results.tracks:
            return None, None, False, f"No se encontró ninguna playlist pública con: '{query}'"

        tracks = results.tracks
        for track in tracks:
            track.requester = interaction.user.id
            player.add(track)

        playlist_name = getattr(results.playlist_info, 'name', None) or (playlist_result['title'] if playlist_result else 'Playlist')
        display_title = f"{playlist_name} ({len(tracks)} canciones)"

        print(f"[{log_prefix}] ✓ En cola playlist: {display_title}")

        started = False
        if not player.is_playing:
            await player.play()
            started = True
            print(f"[{log_prefix}] ✓ Reproducción de playlist iniciada")

        return player, display_title, started, None

    @app_commands.command(name="play", description="Reproduce una canción (nombre o URL)")
    @app_commands.describe(query="Nombre de la canción o URL de YouTube")
    async def play(self, interaction: discord.Interaction, query: str):
        """
        Buscar y reproducir una canción desde YouTube.
        Acepta nombre de canción o URL directa.
        """
        await interaction.response.defer()

        print(f"\n[PLAY] Iniciando reproducción: {query}")

        try:
            player, display_title, started, error_message = await self._queue_query(
                interaction,
                query,
                log_prefix="PLAY",
            )
            if player is None:
                print(f"[PLAY] ✗ {error_message}")
                return await self._send_error(interaction, error_message)

            description = f"**{display_title}**"
            if started:
                await self._send_embed(
                    interaction,
                    self._build_embed(interaction, "Reproduciendo ahora", description, color=BOT_SUCCESS),
                )
            else:
                await self._send_embed(
                    interaction,
                    self._build_embed(interaction, "Añadida a la cola", description, color=BOT_PRIMARY),
                )

        except Exception as e:
            print(f"[PLAY] ✗ ERROR NO CAPTURADO: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()
            await self._send_error(interaction, f"Error: {e}")

    @app_commands.command(name="add", description="Añade una canción a la cola")
    @app_commands.describe(query="Nombre de la canción o URL de YouTube")
    async def add(self, interaction: discord.Interaction, query: str):
        """Buscar y añadir una canción a la cola sin interrumpir la actual."""
        await interaction.response.defer()

        print(f"\n[ADD] Añadiendo a la cola: {query}")

        try:
            player, display_title, started, error_message = await self._queue_query(
                interaction,
                query,
                log_prefix="ADD",
            )
            if player is None:
                print(f"[ADD] ✗ {error_message}")
                return await self._send_error(interaction, error_message)

            description = f"**{display_title}**"
            if started:
                await self._send_embed(
                    interaction,
                    self._build_embed(interaction, "Añadida y en reproducción", description, color=BOT_SUCCESS),
                )
            else:
                await self._send_embed(
                    interaction,
                    self._build_embed(interaction, "Añadida a la cola", description, color=BOT_PRIMARY),
                )

        except Exception as e:
            print(f"[ADD] ✗ ERROR NO CAPTURADO: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()
            await self._send_error(interaction, f"Error: {e}")

    @app_commands.command(name="playlist", description="Reproduce una playlist pública")
    @app_commands.describe(query="Nombre de la playlist + autor o URL de YouTube/YouTube Music")
    async def playlist(self, interaction: discord.Interaction, query: str):
        """Buscar y reproducir una playlist pública desde YouTube o YouTube Music."""
        await interaction.response.defer()

        print(f"\n[PLAYLIST] Iniciando reproducción de playlist: {query}")

        try:
            player, display_title, started, error_message = await self._queue_playlist_query(
                interaction,
                query,
                log_prefix="PLAYLIST",
            )
            if player is None:
                print(f"[PLAYLIST] ✗ {error_message}")
                return await self._send_error(interaction, error_message)

            description = f"**{display_title}**"
            if started:
                await self._send_embed(
                    interaction,
                    self._build_embed(interaction, "Playlist en reproducción", description, color=BOT_SUCCESS),
                )
            else:
                await self._send_embed(
                    interaction,
                    self._build_embed(interaction, "Playlist añadida", description, color=BOT_PRIMARY),
                )

        except Exception as e:
            print(f"[PLAYLIST] ✗ ERROR NO CAPTURADO: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()
            await self._send_error(interaction, f"Error: {e}")

    @app_commands.command(name="queue", description="Muestra la cola de canciones")
    async def queue(self, interaction: discord.Interaction):
        """Ver la cola actual"""
        try:
            player, error_message = self._require_control_player(interaction)
            if player is None:
                return await self._send_error(interaction, error_message)

            message = "**Cola de reproducción:**\n"

            if player.current:
                duration = player.current.duration // 1000
                message += f"▶️ **Actual:** {player.current.title}\n"
                message += f"   Duración: {duration}s\n\n"
            else:
                message += "❌ No hay nada reproduciéndose\n\n"

            if not player.queue:
                message += "**Cola vacía**"
            else:
                queue_list = player.queue
                total_duration = sum(t.duration for t in queue_list) // 1000
                message += f"**En cola ({len(queue_list)} canciones):**\n"

                for i, track in enumerate(queue_list[:10], 1):
                    dur = track.duration // 1000
                    message += f"{i}. {track.title} ({dur}s)\n"

                if len(queue_list) > 10:
                    message += f"... y {len(queue_list) - 10} más\n"

                message += f"\n**Duración total en cola:** {total_duration}s"

            embed = self._build_embed(interaction, "Cola de reproducción", color=BOT_PRIMARY)
            if player.current:
                current = player.current
                embed.add_field(name="Ahora sonando", value=current.title or "Desconocido", inline=False)
                embed.add_field(name="Autor", value=current.author or "Desconocido", inline=True)
                embed.add_field(name="Duración", value=format_duration(current.duration), inline=True)
            else:
                embed.add_field(name="Ahora sonando", value="Nada en reproducción", inline=False)

            if not player.queue:
                embed.add_field(name="Siguiente", value="Cola vacía", inline=False)
            else:
                queue_list = player.queue
                total_duration = sum(t.duration for t in queue_list)
                queue_preview = []
                for i, track in enumerate(queue_list[:10], 1):
                    queue_preview.append(f"{i}. {track.title} · {format_duration(track.duration)}")
                if len(queue_list) > 10:
                    queue_preview.append(f"... y {len(queue_list) - 10} más")

                embed.add_field(name=f"En cola ({len(queue_list)})", value="\n".join(queue_preview), inline=False)
                embed.add_field(name="Duración total", value=format_duration(total_duration), inline=True)

            await self._send_embed(interaction, embed)

        except Exception as e:
            print(f"[QUEUE] ✗ Error: {e}")
            await self._send_error(interaction, f"Error: {e}")

    @app_commands.command(name="skip", description="Salta a la siguiente canción")
    async def skip(self, interaction: discord.Interaction):
        """Saltar canción actual"""
        try:
            player, error_message = self._require_control_player(interaction)
            if player is None:
                return await self._send_error(interaction, error_message)

            if player.current:
                current_title = player.current.title
                await player.skip()
                print(f"[SKIP] ✓ Saltada: {current_title}")
                await self._send_embed(
                    interaction,
                    self._build_embed(interaction, "Canción saltada", f"**{current_title}**", color=BOT_WARNING),
                )
            else:
                await self._send_error(interaction, "No hay nada reproduciéndose.")

        except Exception as e:
            print(f"[SKIP] ✗ Error: {e}")
            await self._send_error(interaction, f"Error: {e}")

    @app_commands.command(name="pause", description="Pausa la reproducción")
    async def pause(self, interaction: discord.Interaction):
        """Pausar reproducción"""
        try:
            player, error_message = self._require_control_player(interaction)
            if player is None:
                return await self._send_error(interaction, error_message)

            if player.current:
                if not player.paused:
                    await player.set_pause(True)
                    print(f"[PAUSE] ✓ Pausado: {player.current.title}")
                    await self._send_embed(
                        interaction,
                        self._build_embed(interaction, "Reproducción en pausa", "La salida quedó detenida temporalmente.", color=BOT_WARNING),
                    )
                else:
                    await self._send_embed(
                        interaction,
                        self._build_embed(interaction, "Ya estaba en pausa", "No se hicieron cambios.", color=BOT_WARNING),
                    )
            else:
                await self._send_error(interaction, "No hay nada reproduciéndose.")

        except Exception as e:
            print(f"[PAUSE] ✗ Error: {e}")
            await self._send_error(interaction, f"Error: {e}")

    @app_commands.command(name="resume", description="Reanuda la reproducción")
    async def resume(self, interaction: discord.Interaction):
        """Reanudar reproducción"""
        try:
            player, error_message = self._require_control_player(interaction)
            if player is None:
                return await self._send_error(interaction, error_message)

            if player.current:
                if player.paused:
                    await player.set_pause(False)
                    print(f"[RESUME] ✓ Reanudado: {player.current.title}")
                    await self._send_embed(
                        interaction,
                        self._build_embed(interaction, "Reproducción reanudada", "La cola sigue avanzando con normalidad.", color=BOT_SUCCESS),
                    )
                else:
                    await self._send_embed(
                        interaction,
                        self._build_embed(interaction, "Ya estaba reproduciendo", "No se hicieron cambios.", color=BOT_PRIMARY),
                    )
            else:
                await self._send_error(interaction, "No hay nada reproduciéndose.")

        except Exception as e:
            print(f"[RESUME] ✗ Error: {e}")
            await self._send_error(interaction, f"Error: {e}")

    @app_commands.command(name="stop", description="Detiene y desconecta")
    async def stop(self, interaction: discord.Interaction):
        """Detener y desconectar"""
        try:
            player, error_message = self._require_control_player(interaction)
            if player is None:
                return await self._send_error(interaction, error_message)

            voice_client = interaction.guild.voice_client if interaction.guild else None

            player.queue.clear()
            if player.current:
                await player.stop()

            if voice_client:
                await voice_client.disconnect(force=True)

            if player or voice_client:
                print("[STOP] ✓ Bot desconectado")
                await self._send_embed(
                    interaction,
                    self._build_embed(interaction, "Reproducción detenida", "La cola se vació y el bot salió del canal.", color=BOT_ERROR),
                )
            else:
                await self._send_error(interaction, "No estoy conectado.")

        except Exception as e:
            print(f"[STOP] ✗ Error: {e}")
            await self._send_error(interaction, f"Error: {e}")

    @app_commands.command(name="nowplaying", description="Muestra la canción actual")
    async def nowplaying(self, interaction: discord.Interaction):
        """Ver canción actual"""
        try:
            player, error_message = self._require_control_player(interaction)
            if player is None:
                return await self._send_error(interaction, error_message)

            if player.current:
                track = player.current
                position_ms = player.position
                position_s = position_ms // 1000

                if track.is_stream:
                    duration_label = "En vivo"
                    progress_label = "En vivo"
                else:
                    duration_s = track.duration // 1000
                    progress_label = progress_bar(position_ms, track.duration)
                    duration_label = f"{format_duration(position_ms)} / {format_duration(track.duration)}"

                embed = self._build_embed(interaction, track.title or "Reproducción actual", color=BOT_PRIMARY)
                if track.uri:
                    embed.url = track.uri

                embed.add_field(name="Autor", value=track.author or "Desconocido", inline=True)
                embed.add_field(name="Estado", value="En vivo" if track.is_stream else "En reproducción", inline=True)
                embed.add_field(name="Duración", value=duration_label, inline=True)
                embed.add_field(name="Progreso", value=f"`{progress_label}`", inline=False)

                if not track.is_stream:
                    percent = min((position_ms / max(track.duration, 1)) * 100, 100.0)
                    embed.add_field(name="Avance", value=f"{percent:.1f}%", inline=True)

                if track.uri:
                    embed.add_field(name="URL", value=track.uri, inline=False)

                await self._send_embed(interaction, embed)
            else:
                await self._send_error(interaction, "No hay nada reproduciéndose.")

        except Exception as e:
            print(f"[NOWPLAYING] ✗ Error: {e}")
            await self._send_error(interaction, f"Error: {e}")


async def setup(bot):
    """Setup del cog"""
    await bot.add_cog(MusicCog(bot))
    print("MusicCog cargado correctamente")
