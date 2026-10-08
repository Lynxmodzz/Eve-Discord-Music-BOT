import json
import os
import re
import time
import discord

def card_tite(title: str) -> str:
    if not title:
        return ""
    cleaned = re.sub(r"\s*[\(\[].*?[\)\]]", "", title)
    if "|" in cleaned:
        cleaned = cleaned.split("|")[0]
    return cleaned.strip(" -|/")

def format_track_link(track, fallback: str = "Unknown Track") -> str:
    if not track:
        return f"**{fallback}**"
    title = card_tite(getattr(track, "title", "") or fallback)
    uri = getattr(track, "uri", None)
    if not uri and hasattr(track, "extras") and track.extras:
        try:
            uri = track.extras.get("source_uri")
        except Exception:
            pass
    if uri:
        return f"[**{title}**]({uri})"
    return f"**{title}**"

def load_json(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

SETTINGS = load_json(os.path.join("config", "settings.json"))
EMOJIS = load_json(os.path.join("config", "emojis.json"))
LAVA_NODES = load_json(os.path.join("config", "lava_nodes.json"))
LOGGING_CONFIG = load_json(os.path.join("config", "logging.json"))

def save_settings(data=None):
    if data is None:
        data = SETTINGS
    filepath = os.path.join("config", "settings.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def get_emoji(name: str) -> str:
    return EMOJIS.get(name, "")

def get_theme_color() -> discord.Color:
    hex_str = SETTINGS.get("theme_color", "#FFFFFF").lstrip("#")
    try:
        return discord.Color(int(hex_str, 16))
    except Exception:
        return discord.Color.default()

def build_embed(title: str = None, description: str = None, color: discord.Color = None) -> discord.Embed:
    if color is None:
        color = get_theme_color()
    embed = discord.Embed(color=color)
    if title:
        embed.title = title
    if description:
        embed.description = description
    return embed

def success_embed(text: str) -> discord.Embed:
    emoji = get_emoji("success")
    desc = f"{emoji} {text}" if emoji else text
    return build_embed(description=desc)

def error_embed(text: str) -> discord.Embed:
    emoji = get_emoji("error")
    desc = f"{emoji} {text}" if emoji else text
    return build_embed(description=desc)

def info_embed(text: str) -> discord.Embed:
    emoji = get_emoji("info")
    desc = f"{emoji} {text}" if emoji else text
    return build_embed(description=desc)

def warning_embed(text: str) -> discord.Embed:
    emoji = get_emoji("warning")
    desc = f"{emoji} {text}" if emoji else text
    return build_embed(description=desc)

def format_duration(ms: int) -> str:
    if not ms or ms <= 0:
        return "00:00"
    seconds = int(ms / 1000)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def parse_duration_string(dur_str: str) -> tuple[str, float | None, str] | None:
    if not dur_str:
        return None
    val = dur_str.strip().lower()
    now = time.time()
    
    if val in ["1w", "1 week", "1week", "7d", "7 days", "1_week"]:
        return "1w", now + (7 * 86400), "1 Week"
    if val in ["1m", "1 month", "1month", "30d", "30 days", "1_month"]:
        return "1m", now + (30 * 86400), "1 Month"
    if val in ["3m", "3 month", "3 months", "3months", "90d", "3_months"]:
        return "3m", now + (90 * 86400), "3 Months"
    if val in ["6m", "6 month", "6 months", "6months", "180d", "6_months"]:
        return "6m", now + (180 * 86400), "6 Months"
    if val in ["lifetime", "permanent", "perm", "life", "forever", "inf", "infinity"]:
        return "lifetime", None, "Lifetime"
    
    return None

def format_expiration(expires_at: float | None) -> str:
    if expires_at is None:
        return "`Lifetime`"
    ts = int(expires_at)
    return f"<t:{ts}:R> (<t:{ts}:d>)"

class PlayerControlView(discord.ui.View):
    def __init__(self, player, timeout: float = 300.0):
        super().__init__(timeout=timeout)
        self.player = player
        self.message = None
        self._update_buttons()

    def _update_buttons(self):
        self.clear_items()
        is_paused = getattr(self.player, "paused", False)
        play_pause_emoji = get_emoji("play") if is_paused else get_emoji("pause")
        
        play_pause_btn = discord.ui.Button(
            emoji=play_pause_emoji if play_pause_emoji else None,
            label="Resume" if is_paused and not play_pause_emoji else ("Pause" if not play_pause_emoji else None),
            style=discord.ButtonStyle.secondary,
            custom_id="btn_play_pause"
        )
        play_pause_btn.callback = self.play_pause_callback
        self.add_item(play_pause_btn)

        skip_emoji = get_emoji("skip")
        skip_btn = discord.ui.Button(
            emoji=skip_emoji if skip_emoji else None,
            label="Skip" if not skip_emoji else None,
            style=discord.ButtonStyle.secondary,
            custom_id="btn_skip"
        )
        skip_btn.callback = self.skip_callback
        self.add_item(skip_btn)

        stop_emoji = get_emoji("stop")
        stop_btn = discord.ui.Button(
            emoji=stop_emoji if stop_emoji else None,
            label="Stop" if not stop_emoji else None,
            style=discord.ButtonStyle.secondary,
            custom_id="btn_stop"
        )
        stop_btn.callback = self.stop_callback
        self.add_item(stop_btn)

        queue_emoji = get_emoji("info")
        queue_btn = discord.ui.Button(
            emoji=queue_emoji if queue_emoji else None,
            label="Queue",
            style=discord.ButtonStyle.secondary,
            custom_id="btn_queue"
        )
        queue_btn.callback = self.queue_callback
        self.add_item(queue_btn)

    async def _check_user(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.voice or not self.player.channel:
            await interaction.response.send_message(
                embed=error_embed("You are not connected to a voice channel"),
                ephemeral=True
            )
            return False
        if interaction.user.voice.channel.id != self.player.channel.id:
            await interaction.response.send_message(
                embed=error_embed("You must be in the same voice channel as the bot"),
                ephemeral=True
            )
            return False
        return True

    async def play_pause_callback(self, interaction: discord.Interaction):
        if not await self._check_user(interaction):
            return
        if self.player.paused:
            await self.player.pause(False)
            self._update_buttons()
            await interaction.response.edit_message(view=self)
        else:
            await self.player.pause(True)
            self._update_buttons()
            await interaction.response.edit_message(view=self)

    async def skip_callback(self, interaction: discord.Interaction):
        if not await self._check_user(interaction):
            return
        await self.player.skip(force=True)
        await interaction.response.send_message(
            embed=success_embed("Skipped"),
            ephemeral=True
        )

    async def stop_callback(self, interaction: discord.Interaction):
        if not await self._check_user(interaction):
            return
        self.player.queue.clear()
        await self.player.skip(force=True)
        await interaction.response.send_message(
            embed=success_embed("Stopped"),
            ephemeral=True
        )

    async def queue_callback(self, interaction: discord.Interaction):
        if not await self._check_user(interaction):
            return
        if not self.player.current and self.player.queue.is_empty:
            await interaction.response.send_message(
                embed=info_embed("Queue is empty"),
                ephemeral=True
            )
            return
        current_link = format_track_link(self.player.current) if self.player.current else "**None**"
        q_count = len(self.player.queue)
        msg = f"**Now Playing:** {current_link}\n**Tracks in queue:** `{q_count}`"
        await interaction.response.send_message(
            embed=build_embed(description=msg),
            ephemeral=True
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

# @Author: LynxModz
 #   + Discord: ifwlynx_
 #   + Community: https://dsc.gg/lynx-modz
 #   + Eve Bot source is free for everyone. Paid distribution is not allowed.