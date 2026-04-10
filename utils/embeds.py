from __future__ import annotations

from datetime import timedelta

import discord


BOT_ACCENT = discord.Color.from_rgb(43, 45, 49)
BOT_PRIMARY = discord.Color.from_rgb(88, 101, 242)
BOT_SUCCESS = discord.Color.from_rgb(46, 204, 113)
BOT_WARNING = discord.Color.from_rgb(241, 196, 15)
BOT_ERROR = discord.Color.from_rgb(231, 76, 60)


def format_duration(milliseconds: int | float | None) -> str:
    if not milliseconds:
        return "0:00"

    total_seconds = max(int(milliseconds // 1000), 0)
    return str(timedelta(seconds=total_seconds))[2:]


def progress_bar(position_ms: int | float, duration_ms: int | float, *, length: int = 18) -> str:
    if duration_ms <= 0:
        return "■" * length

    ratio = max(0.0, min(float(position_ms) / float(duration_ms), 1.0))
    filled = int(round(length * ratio))
    filled = min(max(filled, 0), length)
    return "■" * filled + "□" * (length - filled)


def build_base_embed(*, title: str, description: str | None = None, color: discord.Color = BOT_PRIMARY) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    return embed


def build_status_embed(*, title: str, description: str | None = None, color: discord.Color = BOT_PRIMARY) -> discord.Embed:
    embed = build_base_embed(title=title, description=description, color=color)
    embed.set_footer(text="bot-discord")
    return embed
