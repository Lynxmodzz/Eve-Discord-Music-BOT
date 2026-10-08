import re
import os
import io
import html
import time
import base64
from urllib.parse import quote
from typing import cast
import asyncio
import aiohttp
import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import wavelink
from PIL import Image, ImageDraw, ImageOps, ImageFilter, ImageFont
from utils.ui import (
    build_embed,
    success_embed,
    error_embed,
    info_embed,
    warning_embed,
    format_duration,
    get_emoji,
    card_tite,
    format_track_link,
    SETTINGS
)
from utils.paginator import Paginator
from utils.logging import send_log

track_histories: dict[int, list[wavelink.Playable]] = {}

SPOTIFY_TRACK_REGEX = r"https?://open\.spotify\.com(?:/[a-zA-Z0-9\-]+)?/track/([a-zA-Z0-9]+)"
SPOTIFY_PLAYLIST_REGEX = r"https?://open\.spotify\.com(?:/[a-zA-Z0-9\-]+)?/playlist/([a-zA-Z0-9]+)"
SPOTIFY_ALBUM_REGEX = r"https?://open\.spotify\.com(?:/[a-zA-Z0-9\-]+)?/album/([a-zA-Z0-9]+)"

def make_container(text: str, is_error: bool = False) -> discord.Embed:
    clean_text = re.sub(r"<:[a-zA-Z0-9_]+:[0-9]+>", "", text)
    clean_text = re.sub(r"<a:[a-zA-Z0-9_]+:[0-9]+>", "", clean_text).strip()
    if is_error:
        return error_embed(clean_text)
    return success_embed(clean_text)

class SpotifyAPI:
    BASE_URL = "https://api.spotify.com/v1"

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None

    async def get_token(self):
        if not self.client_id or not self.client_secret:
            return
        auth_url = "https://accounts.spotify.com/api/token"
        auth_value = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode("utf-8")).decode("utf-8")
        headers = {"Authorization": f"Basic {auth_value}"}
        data = {"grant_type": "client_credentials"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(auth_url, headers=headers, data=data) as response:
                    if response.status == 200:
                        self.token = (await response.json()).get("access_token")
        except Exception:
            pass

    async def request_json(self, url, params=None):
        retries = 2
        for attempt in range(retries):
            if not self.token or attempt > 0:
                await self.get_token()
            if not self.token:
                return None
            headers = {"Authorization": f"Bearer {self.token}"}
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 401 and attempt < retries - 1:
                            continue
                        if response.status == 200:
                            return await response.json()
                        return None
            except Exception:
                return None
        return None

    async def get(self, endpoint, params=None):
        return await self.request_json(f"{self.BASE_URL}/{endpoint}", params=params)

    async def get_url(self, url, params=None):
        return await self.request_json(url, params=params)

    async def get_track(self, track_id):
        return await self.get(f"tracks/{track_id}")

    async def get_playlist(self, playlist_id):
        return await self.get(f"playlists/{playlist_id}")

    async def get_playlist_tracks(self, playlist_id, params=None):
        return await self.get(f"playlists/{playlist_id}/tracks", params=params)

    async def get_album(self, album_id):
        return await self.get(f"albums/{album_id}")

    async def get_album_tracks(self, album_id, params=None):
        return await self.get(f"albums/{album_id}/tracks", params=params)

    async def get_oembed(self, link):
        url = f"https://open.spotify.com/oembed?url={quote(link, safe='')}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception:
            pass
        return None

spotify_api = SpotifyAPI(
    client_id=os.getenv("SPOTIFY_CLIENT_ID", "ac2b614ca5ce46a18dfd1d3475fd6fd9"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", "df7bec95ae88438e8286db597bac8621")
)

class PlatformSelectView(View):
    def __init__(self, ctx, query):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.query = query

        platforms = [
            ("YouTube", "ytsearch", discord.ButtonStyle.danger),
            ("JioSaavn", "jssearch", discord.ButtonStyle.success),
            ("SoundCloud", "scsearch", discord.ButtonStyle.secondary),
        ]

        for name, source, style in platforms:
            button = Button(label=name, style=style, custom_id=source)
            button.callback = self.create_callback(source)
            self.add_item(button)

    def create_callback(self, source):
        async def callback(interaction: discord.Interaction):
            if interaction.user != self.ctx.author:
                await interaction.response.send_message(
                    embed=error_embed("Only the command author can select a platform."),
                    ephemeral=True
                )
                return

            try:
                await interaction.message.delete()
            except Exception:
                pass
            await self.perform_search(source)
        return callback

    async def perform_search(self, source):
        source_label = {"ytsearch": "YouTube", "jssearch": "JioSaavn", "scsearch": "SoundCloud"}.get(source, source)
        clean_q = card_tite(self.query)
        if self.query.startswith("http://") or self.query.startswith("https://"):
            query_display = f"[**{clean_q or self.query}**]({self.query})"
        else:
            query_display = f"**{clean_q or self.query}**"

        await self.ctx.send(embed=info_embed(f"Searching {query_display} on {source_label}..."))
        results = await self.ctx.cog.search_tracks(self.query, source)
        if not results:
            await self.ctx.send(embed=error_embed("No results found."))
            return
        top_results = list(results[:5])
        res_view = SearchResultView(self.ctx, top_results, source)
        await self.ctx.send(embed=res_view.get_embed(), view=res_view)

class SearchResultView(View):
    def __init__(self, ctx, results, source):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.results = results
        self.source = source
        self.index = 0
        self.rebuild_buttons()

    def rebuild_buttons(self):
        self.clear_items()
        prev_emoji = get_emoji("previous")
        prev_btn = Button(
            emoji=prev_emoji if prev_emoji else None,
            label="Prev" if not prev_emoji else None,
            style=discord.ButtonStyle.secondary,
            disabled=(self.index == 0)
        )
        prev_btn.callback = self.previous_callback
        self.add_item(prev_btn)

        play_emoji = get_emoji("play")
        play_btn = Button(
            emoji=play_emoji if play_emoji else None,
            label="Play" if not play_emoji else None,
            style=discord.ButtonStyle.secondary
        )
        play_btn.callback = self.play_callback
        self.add_item(play_btn)

        skip_emoji = get_emoji("skip")
        next_btn = Button(
            emoji=skip_emoji if skip_emoji else None,
            label="Next" if not skip_emoji else None,
            style=discord.ButtonStyle.secondary,
            disabled=(self.index >= len(self.results) - 1)
        )
        next_btn.callback = self.next_callback
        self.add_item(next_btn)

    def get_embed(self) -> discord.Embed:
        track = self.results[self.index]
        source_label = {"ytsearch": "YouTube", "jssearch": "JioSaavn", "scsearch": "SoundCloud"}.get(self.source, self.source)
        search_icon = get_emoji("search")
        title_str = f"{search_icon} Search Result {self.index + 1}/{len(self.results)}" if search_icon else f"Search Result {self.index + 1}/{len(self.results)}"
        embed = build_embed(title=title_str)
        embed.description = (
            f"**Title:** {format_track_link(track)}\n"
            f"**Author:** `{track.author}`\n"
            f"**Duration:** `{format_duration(track.length)}`\n"
            f"**Source:** `{source_label}`"
        )
        if track.artwork:
            embed.set_thumbnail(url=track.artwork)
        return embed

    async def ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                embed=error_embed("Only the command author can use these buttons."),
                ephemeral=True
            )
            return False
        return True

    async def previous_callback(self, interaction: discord.Interaction):
        if not await self.ensure_owner(interaction):
            return
        if self.index > 0:
            self.index -= 1
            self.rebuild_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def next_callback(self, interaction: discord.Interaction):
        if not await self.ensure_owner(interaction):
            return
        if self.index < len(self.results) - 1:
            self.index += 1
            self.rebuild_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def play_callback(self, interaction: discord.Interaction):
        if not await self.ensure_owner(interaction):
            return
        if not self.ctx.author.voice:
            await interaction.response.send_message(
                embed=error_embed("You need to join a voice channel first."),
                ephemeral=True
            )
            return

        track = self.results[self.index]
        self.ctx.cog.set_track_context(track, requester=self.ctx.author)
        if not self.ctx.voice_client:
            vc = await self.ctx.author.voice.channel.connect(cls=wavelink.Player)
        else:
            vc = cast(wavelink.Player, self.ctx.voice_client)
        self.ctx.cog.init_player_state(vc, self.ctx)

        track_link = format_track_link(track)
        if not vc.playing:
            vc.current_requester = track.requester
            await vc.play(track)
            await interaction.response.send_message(
                embed=success_embed(f"Started playing {track_link}."),
                ephemeral=True
            )
        else:
            await vc.queue.put_wait(track)
            await interaction.response.send_message(
                embed=success_embed(f"Added {track_link} to the queue."),
                ephemeral=True
            )

class MusicControlView(View):
    def __init__(self, player: wavelink.Player, ctx, timeout: float = None):
        super().__init__(timeout=timeout)
        self.player = player
        self.ctx = ctx
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()

        prev_emoji = get_emoji("previous")
        self.prev_btn = Button(
            emoji=prev_emoji if prev_emoji else None,
            label="Prev" if not prev_emoji else None,
            style=discord.ButtonStyle.secondary,
            custom_id="btn_prev"
        )
        self.prev_btn.callback = self.previous_callback
        self.add_item(self.prev_btn)

        is_paused = getattr(self.player, "paused", False)
        play_pause_emoji = get_emoji("play") if is_paused else get_emoji("pause")
        self.pause_btn = Button(
            emoji=play_pause_emoji if play_pause_emoji else None,
            label="Resume" if is_paused and not play_pause_emoji else ("Pause" if not play_pause_emoji else None),
            style=discord.ButtonStyle.secondary,
            custom_id="btn_play_pause"
        )
        self.pause_btn.callback = self.pause_callback
        self.add_item(self.pause_btn)

        skip_emoji = get_emoji("skip")
        self.skip_btn = Button(
            emoji=skip_emoji if skip_emoji else None,
            label="Skip" if not skip_emoji else None,
            style=discord.ButtonStyle.secondary,
            custom_id="btn_skip"
        )
        self.skip_btn.callback = self.skip_callback
        self.add_item(self.skip_btn)

        stop_emoji = get_emoji("stop")
        self.stop_btn = Button(
            emoji=stop_emoji if stop_emoji else None,
            label="Stop" if not stop_emoji else None,
            style=discord.ButtonStyle.secondary,
            custom_id="btn_stop"
        )
        self.stop_btn.callback = self.stop_callback
        self.add_item(self.stop_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.ctx.voice_client or not self.player.playing:
            await interaction.response.send_message(
                embed=error_embed("I'm not currently playing anything."),
                ephemeral=True
            )
            return False
        if not interaction.user.voice or interaction.user.voice.channel.id != self.player.channel.id:
            await interaction.response.send_message(
                embed=error_embed("Only members in the same voice channel can control the player."),
                ephemeral=True
            )
            return False
        return True

    async def previous_callback(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        history = track_histories.get(guild_id, [])
        if len(history) > 1:
            history.pop()
            previous_track = history[-1]
            await self.player.play(previous_track)
            await interaction.response.send_message(embed=success_embed(f"Playing previous track: {format_track_link(previous_track)}."))
        else:
            await interaction.response.send_message(embed=error_embed("No previous track available."), ephemeral=True)

    async def pause_callback(self, interaction: discord.Interaction):
        if self.player.paused:
            await self.player.pause(False)
            self._build_buttons()
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(embed=success_embed(f"Resumed by **{interaction.user.display_name}**."))
        elif self.player.playing:
            await self.player.pause(True)
            self._build_buttons()
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(embed=success_embed(f"Paused by **{interaction.user.display_name}**."))

    async def skip_callback(self, interaction: discord.Interaction):
        if self.player and (self.player.playing or not self.player.queue.is_empty):
            if not self.player.queue.is_empty:
                try:
                    next_track = await self.player.queue.get_wait()
                except Exception:
                    next_track = self.player.queue.get() if not self.player.queue.is_empty else None
                if next_track:
                    self.player.current_requester = getattr(next_track, "requester", None)
                    await self.player.play(next_track)
                    await interaction.response.send_message(embed=success_embed(f"Skipped to {format_track_link(next_track)} by **{interaction.user.display_name}**."))
                    return

            current_track = self.player.current
            similar_track = await self.ctx.cog.get_similar_track(current_track, interaction.guild.id)
            if similar_track:
                self.ctx.cog.set_track_context(similar_track, requester=None)
                self.player.current_requester = None
                await self.player.play(similar_track)
                await interaction.response.send_message(embed=success_embed(f"Skipped to similar track: {format_track_link(similar_track)} by **{interaction.user.display_name}**."))
                return

            await self.ctx.cog.delete_player_message(self.player)
            await self.ctx.cog.update_channel_status(self.player.channel, None)
            await self.player.skip(force=True)
            settings = self.ctx.bot.db.get_guild_settings(self.player.guild.id)
            if not settings.get("is_247", False):
                await self.player.disconnect()
                await interaction.response.send_message(embed=info_embed(f"Skipped by **{interaction.user.display_name}**. Queue has ended."))
            else:
                await interaction.response.send_message(embed=info_embed(f"Skipped by **{interaction.user.display_name}**. Queue is empty."))
        else:
            await interaction.response.send_message(embed=error_embed("No song playing to skip."), ephemeral=True)

    async def stop_callback(self, interaction: discord.Interaction):
        if self.player:
            await self.ctx.cog.delete_player_message(self.player)
            await self.ctx.cog.update_channel_status(self.player.channel, None)
            self.player.queue.clear()
            self.player.autoplay = wavelink.AutoPlayMode.disabled
            self.player.manual_autoplay = False
            self.player.skip_autoplay_once = False

            settings = self.ctx.bot.db.get_guild_settings(self.player.guild.id)
            if settings.get("is_247", False):
                await self.player.stop()
                await interaction.response.send_message(embed=success_embed(f"Stopped playback by **{interaction.user.display_name}**."))
            else:
                await self.player.disconnect()
                await interaction.response.send_message(embed=success_embed(f"Stopped and disconnected by **{interaction.user.display_name}**."))

class DeleteSongModal(Modal, title="Delete Song From Playlist"):
    song_number = TextInput(
        label="Song Number",
        placeholder="Enter track number to remove (e.g. 1)",
        min_length=1,
        max_length=4,
        required=True
    )

    def __init__(self, playlist_view):
        super().__init__()
        self.playlist_view = playlist_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            num = int(self.song_number.value.strip())
        except ValueError:
            return await interaction.response.send_message(embed=error_embed("Please enter a valid song number."), ephemeral=True)

        deleted = await self.playlist_view.cog.bot.db.delete_from_playlist_by_position(interaction.user.id, num)
        if not deleted:
            return await interaction.response.send_message(embed=error_embed(f"Track #{num} was not found in your playlist."), ephemeral=True)

        await interaction.response.send_message(embed=success_embed(f"Removed track #{num} (**{deleted['title']}**) from your playlist."), ephemeral=True)
        await self.playlist_view.refresh(interaction)

class PlaylistView(View):
    def __init__(self, cog, author: discord.User | discord.Member, tracks: list[dict], ctx: commands.Context, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.author = author
        self.tracks = tracks
        self.ctx = ctx
        self.current_page = 0
        self.message = None
        self.chunk_size = 8
        self._update_components()

    def _get_pages(self) -> list[discord.Embed]:
        avatar_url = self.author.display_avatar.url if self.author.display_avatar else None
        if not self.tracks:
            embed = build_embed()
            embed.set_author(name=f"{self.author.display_name}'s Playlist", icon_url=avatar_url)
            embed.description = "Your saved playlist is currently empty.\nUse `?save` while listening to music to save tracks!"
            return [embed]

        chunks = [self.tracks[i:i + self.chunk_size] for i in range(0, len(self.tracks), self.chunk_size)]
        pages = []
        total_tracks = len(self.tracks)

        for idx, chunk in enumerate(chunks):
            embed = build_embed()
            embed.set_author(name=f"{self.author.display_name}'s Playlist", icon_url=avatar_url)
            lines = []
            for item_idx, track in enumerate(chunk, start=(idx * self.chunk_size) + 1):
                uri = track.get("uri", "")
                title = track.get("title", "Unknown Track")
                link_str = f"[{title}]({uri})" if uri else f"**{title}**"
                lines.append(f"`{item_idx}.` {link_str}")
            embed.description = "\n".join(lines)
            embed.set_footer(text=f"Total Tracks: {total_tracks} • Page {idx + 1} of {len(chunks)}")
            pages.append(embed)
        return pages

    def _update_components(self):
        self.clear_items()
        pages = self._get_pages()
        total_pages = len(pages)

        if total_pages > 1:
            prev_emoji = get_emoji("previous")
            prev_btn = Button(
                emoji=prev_emoji if prev_emoji else None,
                label="Prev" if not prev_emoji else None,
                style=discord.ButtonStyle.secondary,
                disabled=(self.current_page == 0),
                row=0
            )
            prev_btn.callback = self.prev_callback
            self.add_item(prev_btn)

            stop_emoji = get_emoji("stop")
            stop_btn = Button(
                emoji=stop_emoji if stop_emoji else None,
                label="Stop" if not stop_emoji else None,
                style=discord.ButtonStyle.secondary,
                row=0
            )
            stop_btn.callback = self.stop_callback
            self.add_item(stop_btn)

            skip_emoji = get_emoji("skip")
            next_btn = Button(
                emoji=skip_emoji if skip_emoji else None,
                label="Next" if not skip_emoji else None,
                style=discord.ButtonStyle.secondary,
                disabled=(self.current_page >= total_pages - 1),
                row=0
            )
            next_btn.callback = self.next_callback
            self.add_item(next_btn)

        if self.tracks:
            action_row = 1 if total_pages > 1 else 0

            play_emoji = get_emoji("play")
            play_btn = Button(
                emoji=play_emoji if play_emoji else None,
                label="Play All" if not play_emoji else None,
                style=discord.ButtonStyle.secondary,
                row=action_row
            )
            play_btn.callback = self.play_all_callback
            self.add_item(play_btn)

            warn_emoji = get_emoji("warning")
            del_btn = Button(
                emoji=warn_emoji if warn_emoji else None,
                label="Delete" if not warn_emoji else None,
                style=discord.ButtonStyle.secondary,
                row=action_row
            )
            del_btn.callback = self.delete_callback
            self.add_item(del_btn)

            err_emoji = get_emoji("error")
            clear_btn = Button(
                emoji=err_emoji if err_emoji else None,
                label="Clear" if not err_emoji else None,
                style=discord.ButtonStyle.secondary,
                row=action_row
            )
            clear_btn.callback = self.clear_callback
            self.add_item(clear_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                embed=error_embed("Only the playlist owner can interact with this menu."),
                ephemeral=True
            )
            return False
        return True

    def get_current_embed(self) -> discord.Embed:
        pages = self._get_pages()
        if self.current_page >= len(pages):
            self.current_page = max(0, len(pages) - 1)
        return pages[self.current_page]

    async def prev_callback(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_components()
            await interaction.response.edit_message(embed=self.get_current_embed(), view=self)

    async def next_callback(self, interaction: discord.Interaction):
        pages = self._get_pages()
        if self.current_page < len(pages) - 1:
            self.current_page += 1
            self._update_components()
            await interaction.response.edit_message(embed=self.get_current_embed(), view=self)

    async def stop_callback(self, interaction: discord.Interaction):
        self.stop()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

    async def delete_callback(self, interaction: discord.Interaction):
        modal = DeleteSongModal(self)
        await interaction.response.send_modal(modal)

    async def clear_callback(self, interaction: discord.Interaction):
        deleted_count = await self.cog.bot.db.clear_user_playlist(interaction.user.id)
        self.tracks = []
        self._update_components()
        avatar_url = self.author.display_avatar.url if self.author.display_avatar else None
        embed = build_embed()
        embed.set_author(name=f"{self.author.display_name}'s Playlist", icon_url=avatar_url)
        embed.description = f"Cleared **{deleted_count}** tracks from your playlist."
        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

    async def play_all_callback(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            return await interaction.response.send_message(embed=error_embed("Connect to a voice channel first."), ephemeral=True)

        if not self.tracks:
            return await interaction.response.send_message(embed=error_embed("Your playlist is empty."), ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        vc = guild.voice_client
        if not vc:
            try:
                vc = await interaction.user.voice.channel.connect(cls=wavelink.Player, reconnect=True)
                self.cog.init_player_state(vc, self.ctx)
            except Exception as e:
                return await interaction.followup.send(embed=error_embed(f"Could not connect to voice channel: {e}"), ephemeral=True)
        elif vc.channel.id != interaction.user.voice.channel.id:
            return await interaction.followup.send(embed=error_embed("You must be in the same voice channel as the bot."), ephemeral=True)

        loaded = 0
        first_track = None
        for item in self.tracks:
            try:
                res = await wavelink.Playable.search(item["uri"])
                if res:
                    t = res[0] if isinstance(res, list) else (res.tracks[0] if isinstance(res, wavelink.Playlist) else res)
                    self.cog.set_track_context(t, requester=interaction.user, source_uri=item["uri"])
                    if not vc.playing and loaded == 0:
                        first_track = t
                    else:
                        await vc.queue.put_wait(t)
                    loaded += 1
            except Exception:
                continue

        if first_track:
            vc.current_requester = interaction.user
            await vc.play(first_track)

        await interaction.followup.send(embed=success_embed(f"Queued **{loaded}** tracks from your playlist!"), ephemeral=True)

    async def refresh(self, interaction: discord.Interaction = None):
        self.tracks = await self.cog.bot.db.get_user_playlist(self.author.id)
        self._update_components()
        if self.message:
            try:
                await self.message.edit(embed=self.get_current_embed(), view=self)
            except Exception:
                pass

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    async def send(self, ctx) -> discord.Message:
        embed = self.get_current_embed()
        if not self.tracks:
            self.message = await ctx.send(embed=embed)
        else:
            self.message = await ctx.send(embed=embed, view=self)
        return self.message

def load_font(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()

async def generate_nowplaying_card(track, vc):
    img = None
    original_img = None
    img_bytes = getattr(track, "_artwork_bytes", None)
    if img_bytes:
        try:
            original_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
            img = original_img.copy()
        except Exception:
            pass

    if not img and track.artwork:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(track.artwork, timeout=3) as resp:
                    if resp.status == 200:
                        img_bytes = await resp.read()
                        track._artwork_bytes = img_bytes
                        original_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
                        img = original_img.copy()
        except Exception:
            pass

    if not img:
        img = Image.new("RGBA", (800, 280), (30, 30, 40, 255))
        draw_bg = ImageDraw.Draw(img)
        for y in range(280):
            r = int(30 - (30 - 15) * (y / 280))
            g = int(30 - (30 - 15) * (y / 280))
            b = int(40 - (40 - 20) * (y / 280))
            draw_bg.line([(0, y), (800, y)], fill=(r, g, b, 255))
    else:
        img = ImageOps.fit(img, (800, 280), method=Image.Resampling.LANCZOS)
        img = img.filter(ImageFilter.GaussianBlur(30))
        overlay = Image.new("RGBA", (800, 280), (10, 10, 15, 175))
        img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)
    font_paths_bold = ("arialbd.ttf", "segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf")
    font_paths_reg = ("arial.ttf", "segoeui.ttf", "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf")
    font_title = load_font(font_paths_bold, 32)
    font_artist = load_font(font_paths_reg, 22)
    font_time = load_font(font_paths_reg, 18)

    if original_img:
        art_size = (200, 200)
        art_img = ImageOps.fit(original_img, art_size, method=Image.Resampling.LANCZOS)
        art_mask = Image.new("L", art_size, 0)
        art_draw = ImageDraw.Draw(art_mask)
        art_draw.rounded_rectangle([(0, 0), art_size], radius=20, fill=255)
        img.paste(art_img, (40, 40), mask=art_mask)
    else:
        draw.rounded_rectangle([(40, 40), (240, 240)], radius=20, fill=(45, 45, 55, 255))

    title_text = card_tite(track.title)
    while len(title_text) > 0:
        try:
            bbox = font_title.getbbox(title_text)
            w = bbox[2] - bbox[0]
        except Exception:
            w = len(title_text) * 16
        if w <= 430:
            break
        title_text = title_text[:-1]
    if len(title_text) < len(card_tite(track.title)):
        title_text = title_text.strip() + "..."

    author_text = getattr(track, "author", "Unknown Artist")
    while len(author_text) > 0:
        try:
            bbox = font_artist.getbbox(author_text)
            w = bbox[2] - bbox[0]
        except Exception:
            w = len(author_text) * 11
        if w <= 430:
            break
        author_text = author_text[:-1]
    if len(author_text) < len(getattr(track, "author", "Unknown Artist")):
        author_text = author_text.strip() + "..."

    draw.text((280, 55), title_text, fill=(255, 255, 255, 255), font=font_title)
    draw.text((280, 105), author_text, fill=(200, 200, 215, 255), font=font_artist)

    pos = vc.position
    total = track.length
    percentage = pos / total if total > 0 else 0
    percentage = min(max(percentage, 0), 1)

    draw.line([(280, 185), (750, 185)], fill=(255, 255, 255, 60), width=6)
    filled_x = 280 + int(470 * percentage)
    draw.line([(280, 185), (filled_x, 185)], fill=(255, 255, 255, 255), width=6)
    draw.ellipse([(filled_x - 6, 179), (filled_x + 6, 191)], fill=(255, 255, 255, 255))

    time_str = f"{pos // 1000 // 60:02}:{pos // 1000 % 60:02}"
    total_str = f"{total // 1000 // 60:02}:{total // 1000 % 60:02}"

    draw.text((280, 205), time_str, fill=(200, 200, 200, 255), font=font_time)
    try:
        bbox = font_time.getbbox(total_str)
        total_width = bbox[2] - bbox[0]
    except Exception:
        total_width = 50
    draw.text((750 - total_width, 205), total_str, fill=(200, 200, 200, 255), font=font_time)

    mask = Image.new("L", (800, 280), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle([(0, 0), (800, 280)], radius=25, fill=255)

    card = Image.new("RGBA", (800, 280))
    card.paste(img, (0, 0), mask=mask)

    fp = io.BytesIO()
    card.save(fp, format="PNG")
    fp.seek(0)
    return fp

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.inactivity_timeout = 180

    async def cog_load(self):
        asyncio.create_task(self.monitor_inactivity())
        asyncio.create_task(self.reconnect_247_players())

    async def update_channel_status(self, channel, status_text: str | None):
        if not channel:
            return
        try:
            if hasattr(channel, "edit"):
                trimmed = status_text[:100] if status_text else None
                await channel.edit(status=trimmed)
        except Exception:
            pass

    async def reconnect_247_players(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(4)
        for guild in self.bot.guilds:
            try:
                settings = self.bot.db.get_guild_settings(guild.id)
                if settings.get("is_247", False):
                    vc_id = settings.get("voice_channel_id")
                    if vc_id:
                        channel = guild.get_channel(vc_id)
                        if channel and isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                            if not guild.voice_client:
                                await channel.connect(cls=wavelink.Player, reconnect=True)
            except Exception:
                continue

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.id != self.bot.user.id:
            return
        if before.channel and not after.channel:
            await self.update_channel_status(before.channel, None)
            guild_settings = self.bot.db.get_guild_settings(member.guild.id)
            if guild_settings.get("is_247", False):
                vc_id = guild_settings.get("voice_channel_id")
                channel = member.guild.get_channel(vc_id) if vc_id else before.channel
                if channel and isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                    await asyncio.sleep(2)
                    try:
                        if not member.guild.voice_client:
                            await channel.connect(cls=wavelink.Player, reconnect=True)
                    except Exception:
                        pass

    async def vc_check(self, ctx) -> bool:
        if ctx.voice_client and ctx.voice_client.channel:
            if not ctx.author.voice or ctx.author.voice.channel != ctx.voice_client.channel:
                await ctx.send(embed=error_embed("You must be in the same voice channel as the bot."))
                return False
        return True

    async def monitor_inactivity(self):
        while True:
            try:
                await asyncio.sleep(30)
                now = time.time()
                for player in list(self.bot.voice_clients):
                    if not isinstance(player, wavelink.Player) or not player.channel:
                        continue
                    settings = self.bot.db.get_guild_settings(player.guild.id)
                    if settings.get("is_247", False):
                        continue

                    non_bots = [m for m in player.channel.members if not m.bot]
                    if len(non_bots) == 0:
                        if not hasattr(player, "_empty_since") or player._empty_since is None:
                            player._empty_since = now
                        elif now - player._empty_since >= self.inactivity_timeout:
                            await self.update_channel_status(player.channel, None)
                            await self.delete_player_message(player)
                            await player.disconnect()
                            continue
                    else:
                        player._empty_since = None

                    is_idle = not player.playing and player.queue.is_empty
                    if is_idle:
                        if not hasattr(player, "_idle_since") or player._idle_since is None:
                            player._idle_since = now
                        elif now - player._idle_since >= self.inactivity_timeout:
                            await self.update_channel_status(player.channel, None)
                            await self.delete_player_message(player)
                            await player.disconnect()
                    else:
                        player._idle_since = None
            except Exception:
                pass

    async def get_similar_track(self, current_track, guild_id: int):
        if not current_track:
            return None

        history = track_histories.get(guild_id, [])
        history_titles = {card_tite(getattr(t, "title", "")).lower() for t in history if t}
        current_title = card_tite(getattr(current_track, "title", "")).lower()
        current_author = getattr(current_track, "author", "") or ""

        if getattr(current_track, "identifier", None):
            yt_id = current_track.identifier
            try:
                rec_results = await wavelink.Playable.search(f"https://music.youtube.com/watch?v={yt_id}&list=RD{yt_id}")
                if rec_results:
                    rec_list = rec_results.tracks if isinstance(rec_results, wavelink.Playlist) else list(rec_results)
                    for t in rec_list:
                        t_title = card_tite(getattr(t, "title", "")).lower()
                        if t_title and t_title != current_title and t_title not in history_titles:
                            return t
            except Exception:
                pass

        queries = []
        if current_author and current_title:
            queries.append(f"{current_title} {current_author} mix")
            queries.append(f"{current_author} popular songs")
        elif current_title:
            queries.append(f"{current_title} mix")

        for q in queries:
            try:
                results = await self.search_tracks(q, return_all=True)
                if results:
                    for t in results:
                        t_title = card_tite(getattr(t, "title", "")).lower()
                        if t_title and t_title != current_title and t_title not in history_titles:
                            return t
            except Exception:
                continue

        return None

    async def search_tracks(self, query, source_prefix=None, return_all=False):
        attempts = []
        cleaned_query = query.strip()
        if source_prefix:
            attempts.append(f"{source_prefix}:{cleaned_query}")
        else:
            attempts.extend([f"ytsearch:{cleaned_query}"])

        seen = set()
        all_results = []
        for attempt in attempts:
            if attempt in seen:
                continue
            seen.add(attempt)
            try:
                results = await wavelink.Playable.search(attempt)
                if results:
                    track_list = results.tracks if isinstance(results, wavelink.Playlist) else list(results)
                    if not return_all:
                        return track_list
                    all_results.extend(track_list)
            except Exception:
                continue
        return all_results if return_all and all_results else None

    def normalize_track_text(self, value):
        value = (value or "").lower()
        value = html.unescape(value)
        value = re.sub(r"\b(ft|feat|featuring)\b\.?", " ", value)
        value = re.sub(r"[\(\)\[\]\{\}_\-|/,:;]+", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    def tokenize_track_text(self, value):
        return set(re.findall(r"[a-z0-9]+", self.normalize_track_text(value)))

    def extract_spotify_track_metadata(self, spotify_track, spotify_url):
        return {
            "title": (spotify_track.get("name") or spotify_track.get("title") or "").strip(),
            "artists": [artist.get("name", "").strip() for artist in spotify_track.get("artists", []) if artist and artist.get("name")],
            "album": ((spotify_track.get("album") or {}).get("name") or "").strip(),
            "duration_ms": int(spotify_track.get("duration_ms") or 0),
            "isrc": ((spotify_track.get("external_ids") or {}).get("isrc") or "").strip(),
            "spotify_url": spotify_track.get("external_urls", {}).get("spotify", spotify_url)
        }

    def build_spotify_search_queries(self, title, artists=None, album=None):
        title = (title or "").strip()
        clean_t = re.sub(r"\s*[\(\[].*?[\)\]]", "", title).strip()
        artist_list = [a.strip() for a in (artists or []) if a and a.strip()]
        artist_text = ", ".join(artist_list).strip()
        queries = []
        if artist_text:
            queries.append(f"{clean_t} {artist_text}")
        queries.append(clean_t)
        return queries

    def calculate_match_score(self, track, metadata):
        score = 0
        spotify_title = metadata["title"]
        spotify_artists = metadata["artists"]
        spotify_duration = metadata["duration_ms"]
        track_title = getattr(track, "title", "") or ""
        track_author = getattr(track, "author", "") or ""

        title_tokens = self.tokenize_track_text(track_title)
        spotify_title_tokens = self.tokenize_track_text(spotify_title)
        overlap = len(spotify_title_tokens & title_tokens)
        if overlap:
            score += (overlap / max(len(spotify_title_tokens), 1)) * 100

        for artist in spotify_artists:
            if self.normalize_track_text(artist) in self.normalize_track_text(track_author):
                score += 80
                break

        if spotify_duration:
            delta = abs(int(getattr(track, "length", 0) or 0) - spotify_duration)
            if delta <= 5000:
                score += 50
            elif delta <= 15000:
                score += 20
        return score

    async def resolve_spotify_track(self, spotify_track, spotify_url):
        metadata = self.extract_spotify_track_metadata(spotify_track, spotify_url)
        queries = self.build_spotify_search_queries(metadata["title"], metadata["artists"])
        best_track = None
        best_score = -1

        for query in queries:
            results = await self.search_tracks(query)
            if not results:
                continue
            for track in results[:5]:
                score = self.calculate_match_score(track, metadata)
                if score > best_score:
                    best_score = score
                    best_track = track
                    if score >= 150:
                        best_track.extras = {"source_uri": metadata["spotify_url"]}
                        return best_track

        if best_track:
            best_track.extras = {"source_uri": metadata["spotify_url"]}
            return best_track
        return None

    def get_track_extra(self, track, key, default=None):
        extras = getattr(track, "extras", None)
        if not extras:
            return default
        try:
            if key in extras:
                return extras[key]
        except Exception:
            pass
        return getattr(extras, key, default)

    def set_track_context(self, track, requester=None, source_uri=None):
        payload = {}
        extras = getattr(track, "extras", None)
        if extras:
            try:
                payload.update(dict(extras))
            except Exception:
                pass
        if requester is not None:
            track.requester = requester
            payload["requester_id"] = requester.id
            payload["requester_name"] = str(requester)
        if source_uri is not None:
            payload["source_uri"] = source_uri
        track.extras = payload
        return track

    def init_player_state(self, player, ctx=None):
        if ctx is not None:
            player.ctx = ctx
        if not hasattr(player, "player_message"):
            player.player_message = None
        if not hasattr(player, "manual_autoplay"):
            player.manual_autoplay = False
        if not hasattr(player, "skip_autoplay_once"):
            player.skip_autoplay_once = False
        if not hasattr(player, "autoplay_initialized"):
            player.autoplay = wavelink.AutoPlayMode.disabled
            player.autoplay_initialized = True

    def get_requester_name(self, track, ctx=None) -> str:
        if not track:
            return "Autoplay"
        req = getattr(track, "requester", None)
        if req:
            return getattr(req, "display_name", str(req))
        req_name = self.get_track_extra(track, "requester_name")
        if req_name:
            return str(req_name)
        req_id = self.get_track_extra(track, "requester_id")
        if req_id and ctx and getattr(ctx, "guild", None):
            member = ctx.guild.get_member(req_id)
            if member:
                return member.display_name
        return "Autoplay"

    def get_requester_avatar(self, track, ctx=None) -> str:
        if not track:
            return self.bot.user.display_avatar.url if self.bot.user else ""
        req = getattr(track, "requester", None)
        if req and hasattr(req, "display_avatar"):
            return req.display_avatar.url
        req_id = self.get_track_extra(track, "requester_id")
        if req_id and ctx and getattr(ctx, "guild", None):
            member = ctx.guild.get_member(req_id)
            if member and hasattr(member, "display_avatar"):
                return member.display_avatar.url
        return self.bot.user.display_avatar.url if self.bot.user else ""

    async def delete_player_message(self, player):
        message = getattr(player, "player_message", None)
        if not message:
            return
        try:
            await message.delete()
        except Exception:
            pass
        player.player_message = None

    async def display_player_embed(self, player, track, ctx):
        self.init_player_state(player, ctx)
        await self.delete_player_message(player)

        if hasattr(player, "last_status_msg") and player.last_status_msg:
            try:
                await player.last_status_msg.delete()
            except Exception:
                pass
            player.last_status_msg = None

        embed = build_embed()

        source_key = (getattr(track, "source", "") or "music").lower()
        source_icons = {
            "youtube": "https://cdn-icons-png.flaticon.com/512/1384/1384060.png",
            "spotify": "https://cdn-icons-png.flaticon.com/512/174/174872.png",
            "soundcloud": "https://cdn-icons-png.flaticon.com/512/145/145809.png",
            "jiosaavn": "https://cdn-icons-png.flaticon.com/512/727/727245.png"
        }
        source_icon_url = source_icons.get(source_key, self.bot.user.display_avatar.url if self.bot.user else None)
        track_title = card_tite(getattr(track, "title", str(track)))
        embed.set_author(name=track_title, icon_url=source_icon_url)

        author_str = getattr(track, "author", "Unknown Artist") or "Unknown Artist"
        duration_str = format_duration(getattr(track, "length", 0)) if not getattr(track, "is_stream", False) else "Live"

        embed.description = (
            f"> **Artist:** `{author_str}`\n"
            f"> **Duration:** `{duration_str}`"
        )
        if getattr(track, "artwork", None):
            embed.set_thumbnail(url=track.artwork)

        req_name = self.get_requester_name(track, ctx)
        req_icon = self.get_requester_avatar(track, ctx)
        embed.set_footer(text=f"Requested by {req_name}", icon_url=req_icon)

        control_view = MusicControlView(player, ctx)
        try:
            player.player_message = await ctx.send(embed=embed, view=control_view)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        player = payload.player
        if not player:
            return
        track = payload.track
        self.init_player_state(player)
        if player.skip_autoplay_once:
            player.autoplay = wavelink.AutoPlayMode.disabled
            player.skip_autoplay_once = False

        guild_id = player.guild.id
        if guild_id not in track_histories:
            track_histories[guild_id] = []
        if not track_histories[guild_id] or track_histories[guild_id][-1] != track:
            track_histories[guild_id].append(track)
            if len(track_histories[guild_id]) > 10:
                track_histories[guild_id].pop(0)

        cleaned_t = card_tite(getattr(track, "title", "Music"))
        await self.update_channel_status(player.channel, f"<a:dance_Danceoh:1557775554177138738> Playing: {cleaned_t}")

        if hasattr(player, "ctx"):
            await self.display_player_embed(player, track, player.ctx)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if not player:
            return
        self.init_player_state(player)
        if payload.reason == "replaced" and getattr(player, "playing", False):
            return

        try:
            if not player.queue.is_empty:
                try:
                    next_track = await player.queue.get_wait()
                except Exception:
                    next_track = player.queue.get() if not player.queue.is_empty else None
                if next_track:
                    player.current_requester = getattr(next_track, "requester", None)
                    await player.play(next_track)
                    return

            if player.autoplay == wavelink.AutoPlayMode.enabled and getattr(player, "manual_autoplay", False):
                player.current_requester = None
                return

            await self.update_channel_status(player.channel, None)

            if hasattr(player, "ctx"):
                await self.delete_player_message(player)
                settings = self.bot.db.get_guild_settings(player.guild.id)
                if not settings.get("is_247", False):
                    try:
                        await player.ctx.send(embed=info_embed("Queue has ended."))
                        await player.disconnect()
                    except Exception:
                        pass
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload):
        player = payload.player
        if not player:
            return
        self.init_player_state(player)
        try:
            if not player.queue.is_empty:
                try:
                    next_track = await player.queue.get_wait()
                    if next_track:
                        player.current_requester = getattr(next_track, "requester", None)
                        await player.play(next_track)
                        return
                except Exception:
                    pass

            await self.update_channel_status(player.channel, None)

            if hasattr(player, "ctx"):
                await self.delete_player_message(player)
                settings = self.bot.db.get_guild_settings(player.guild.id)
                if not settings.get("is_247", False):
                    try:
                        await player.ctx.send(embed=info_embed("Queue has ended."))
                        await player.disconnect()
                    except Exception:
                        pass
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        node = payload.node
        embed = build_embed(title="Lavalink Node Ready")
        embed.description = f"**Node:** `{node.identifier}`\n**Status:** Connected & Ready"
        await send_log("Lavalink-node-logs", embed=embed)

    @commands.Cog.listener()
    async def on_wavelink_node_closed(self, node: wavelink.Node, disconnected: list):
        embed = build_embed(title="Lavalink Node Disconnected")
        embed.description = f"**Node:** `{node.identifier}`\n**Status:** Connection Closed"
        await send_log("Lavalink-node-logs", embed=embed)

    async def handle_spotify_link(self, ctx, vc, link, type_, search_msg=None):
        try:
            if search_msg:
                try:
                    await search_msg.delete()
                except Exception:
                    pass

            if type_ == "track":
                track_id = re.search(SPOTIFY_TRACK_REGEX, link).group(1)
                track_info = await spotify_api.get_track(track_id)
                spotify_url = link
                if not track_info:
                    return await ctx.send(embed=error_embed("Could not find track info on Spotify."))

                track = await self.resolve_spotify_track(track_info, spotify_url)
                if not track:
                    return await ctx.send(embed=error_embed("Could not resolve this Spotify track to a playable source."))

                self.set_track_context(track, requester=ctx.author, source_uri=spotify_url)
                self.init_player_state(vc, ctx)
                track_link = format_track_link(track)
                if not vc.playing:
                    vc.current_requester = ctx.author
                    vc.last_status_msg = await ctx.send(embed=success_embed(f"Started playing {track_link}."))
                    await vc.play(track)
                else:
                    await vc.queue.put_wait(track)
                    await ctx.send(embed=success_embed(f"Added {track_link} to queue."))

            elif type_ in ["playlist", "album"]:
                id_ = re.search(SPOTIFY_PLAYLIST_REGEX if type_ == "playlist" else SPOTIFY_ALBUM_REGEX, link).group(1)
                data = await spotify_api.get_playlist(id_) if type_ == "playlist" else await spotify_api.get_album(id_)
                if not data:
                    return await ctx.send(embed=error_embed(f"Could not find {type_} info on Spotify."))

                tracks_data = data.get("tracks", {}).get("items", [])
                collection_name = data.get("name", f"Spotify {type_}")
                count = 0

                for item in tracks_data[:50]:
                    t = item.get("track") if type_ == "playlist" else item
                    if not t:
                        continue
                    spotify_url = t.get("external_urls", {}).get("spotify", link)
                    t_obj = await self.resolve_spotify_track(t, spotify_url)
                    if not t_obj:
                        continue
                    self.set_track_context(t_obj, requester=ctx.author, source_uri=spotify_url)
                    self.init_player_state(vc, ctx)
                    if not vc.playing and count == 0:
                        vc.current_requester = ctx.author
                        vc.last_status_msg = await ctx.send(embed=success_embed(f"Started playing {format_track_link(t_obj)}."))
                        await vc.play(t_obj)
                    else:
                        await vc.queue.put_wait(t_obj)
                    count += 1

                if count == 0:
                    return await ctx.send(embed=error_embed(f"Could not resolve playable tracks from this Spotify {type_}."))

                await ctx.send(embed=success_embed(f"Added **{count}** tracks from [**{collection_name}**]({link}) to queue."))
        except Exception as e:
            if "unable to get" not in str(e).lower():
                await ctx.send(embed=error_embed(f"Error handling Spotify link: {e}"))

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        query = query.strip().strip("<>`")
        if not await self.vc_check(ctx):
            return
        if not ctx.author.voice:
            return await ctx.send(embed=error_embed("You need to join a voice channel first."))

        clean_q = card_tite(query)
        if query.startswith("http://") or query.startswith("https://"):
            query_display = f"[**{clean_q or query}**]({query})"
        else:
            query_display = f"**{clean_q or query}**"

        search_msg = await ctx.send(embed=info_embed(f"Searching {query_display}..."))

        try:
            if not ctx.voice_client:
                vc = await ctx.author.voice.channel.connect(cls=wavelink.Player, reconnect=True)
            else:
                vc = cast(wavelink.Player, ctx.voice_client)
            self.init_player_state(vc, ctx)

            if re.search(SPOTIFY_TRACK_REGEX, query, re.IGNORECASE):
                return await self.handle_spotify_link(ctx, vc, query, "track", search_msg=search_msg)
            if re.search(SPOTIFY_PLAYLIST_REGEX, query, re.IGNORECASE):
                return await self.handle_spotify_link(ctx, vc, query, "playlist", search_msg=search_msg)
            if re.search(SPOTIFY_ALBUM_REGEX, query, re.IGNORECASE):
                return await self.handle_spotify_link(ctx, vc, query, "album", search_msg=search_msg)

            tracks = await self.search_tracks(query)
            try:
                await search_msg.delete()
            except Exception:
                pass

            if not tracks:
                return await ctx.send(embed=error_embed("No results found."))

            if isinstance(tracks, wavelink.Playlist):
                for t in tracks.tracks:
                    self.set_track_context(t, requester=ctx.author)
                pl_name = getattr(tracks, "name", "Playlist")
                pl_url = getattr(tracks, "url", getattr(tracks, "uri", ""))
                pl_link = f"[**{pl_name}**]({pl_url})" if pl_url else f"**{pl_name}**"
                if not vc.playing:
                    first = tracks.tracks[0]
                    vc.current_requester = ctx.author
                    vc.last_status_msg = await ctx.send(embed=success_embed(f"Added playlist {pl_link} to queue."))
                    await vc.play(first)
                    if len(tracks.tracks) > 1:
                        await vc.queue.put_wait(tracks.tracks[1:])
                else:
                    await vc.queue.put_wait(tracks.tracks)
                    await ctx.send(embed=success_embed(f"Added playlist {pl_link} to queue."))
            else:
                track = tracks[0]
                self.set_track_context(track, requester=ctx.author)
                track_link = format_track_link(track)
                if not vc.playing:
                    vc.current_requester = ctx.author
                    vc.last_status_msg = await ctx.send(embed=success_embed(f"Started playing {track_link}."))
                    await vc.play(track)
                else:
                    await vc.queue.put_wait(track)
                    await ctx.send(embed=success_embed(f"Added {track_link} to queue."))
        except Exception as e:
            try:
                await search_msg.delete()
            except Exception:
                pass
            if "unable to get" not in str(e).lower():
                await ctx.send(embed=error_embed(f"Error while searching: {e}"))

    @commands.command(name="search")
    async def search(self, ctx: commands.Context, *, query: str):
        if not await self.vc_check(ctx):
            return
        if not ctx.author.voice:
            return await ctx.send(embed=error_embed("You need to join a voice channel first."))
        await ctx.send(view=PlatformSelectView(ctx, query))

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        if ctx.voice_client:
            self.init_player_state(ctx.voice_client)
            await self.delete_player_message(ctx.voice_client)
            await self.update_channel_status(ctx.voice_client.channel, None)
            ctx.voice_client.queue.clear()
            ctx.voice_client.autoplay = wavelink.AutoPlayMode.disabled
            ctx.voice_client.manual_autoplay = False
            ctx.voice_client.skip_autoplay_once = False

            settings = self.bot.db.get_guild_settings(ctx.guild.id)
            if settings.get("is_247", False):
                await ctx.voice_client.stop()
                await ctx.send(embed=success_embed("Stopped playback and cleared queue."))
            else:
                await ctx.voice_client.disconnect()
                await ctx.send(embed=success_embed("Stopped and disconnected."))
        else:
            await ctx.send(embed=error_embed("Not connected."))

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        vc = ctx.voice_client
        if vc and (vc.playing or not vc.queue.is_empty):
            if not vc.queue.is_empty:
                try:
                    next_track = await vc.queue.get_wait()
                except Exception:
                    next_track = vc.queue.get() if not vc.queue.is_empty else None
                if next_track:
                    vc.current_requester = getattr(next_track, "requester", None)
                    await vc.play(next_track)
                    return await ctx.send(embed=success_embed(f"Skipped to {format_track_link(next_track)}."))

            current_track = vc.current
            similar_track = await self.get_similar_track(current_track, ctx.guild.id)
            if similar_track:
                self.set_track_context(similar_track, requester=None)
                vc.current_requester = None
                await vc.play(similar_track)
                return await ctx.send(embed=success_embed(f"Skipped to similar track: {format_track_link(similar_track)}."))

            await self.delete_player_message(vc)
            await self.update_channel_status(vc.channel, None)
            await vc.skip(force=True)
            settings = self.bot.db.get_guild_settings(ctx.guild.id)
            if not settings.get("is_247", False):
                await vc.disconnect()
                await ctx.send(embed=info_embed("Skipped. Queue has ended."))
            else:
                await ctx.send(embed=info_embed("Skipped. Queue is empty."))
        else:
            await ctx.send(embed=error_embed("Nothing playing."))

    @commands.command(name="previous", aliases=["prev"])
    async def previous(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        if not ctx.voice_client:
            return await ctx.send(embed=error_embed("Not connected to a voice channel."))

        history = track_histories.get(ctx.guild.id, [])
        if len(history) > 1:
            history.pop()
            prev_track = history[-1]
            await ctx.voice_client.play(prev_track)
            await ctx.send(embed=success_embed(f"Playing previous track: {format_track_link(prev_track)}."))
        else:
            await ctx.send(embed=error_embed("No previous track available."))

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        vc = ctx.voice_client
        if not vc or (not vc.current and vc.queue.is_empty):
            return await ctx.send(embed=info_embed("Queue is empty."))

        try:
            pages = []
            upcoming = []
            if hasattr(vc, "queue") and vc.queue:
                for item in vc.queue:
                    upcoming.append(item)

            chunk_size = 8
            total_tracks = len(upcoming) + (1 if vc.current else 0)

            current_desc = ""
            if vc.current:
                pos = format_duration(vc.position)
                length = format_duration(getattr(vc.current, "length", 0)) if not getattr(vc.current, "is_stream", False) else "Live"
                req_name = self.get_requester_name(vc.current, ctx)
                current_desc = f"**Now Playing:**\n{format_track_link(vc.current)} | `{pos}/{length}` | `{req_name}`\n\n"

            if not upcoming:
                embed = build_embed(title="Queue")
                embed.description = f"{current_desc}**Upcoming Tracks:**\nNo tracks in queue."
                embed.set_footer(text=f"Total Tracks: {total_tracks}")
                await ctx.send(embed=embed)
                return

            chunks = [upcoming[i:i + chunk_size] for i in range(0, len(upcoming), chunk_size)]
            for idx, chunk in enumerate(chunks):
                embed = build_embed(title="Queue")
                lines = []
                for item_idx, track in enumerate(chunk, start=(idx * chunk_size) + 1):
                    length = format_duration(getattr(track, "length", 0)) if not getattr(track, "is_stream", False) else "Live"
                    req_name = self.get_requester_name(track, ctx)
                    lines.append(f"`{item_idx}.` {format_track_link(track)} | `{length}` | `{req_name}`")
                queue_str = "\n".join(lines)
                embed.description = f"{current_desc}**Upcoming Tracks:**\n{queue_str}"
                embed.set_footer(text=f"Total Tracks: {total_tracks}")
                pages.append(embed)

            paginator = Paginator(author=ctx.author, pages=pages)
            await paginator.send(ctx)
        except Exception:
            if vc.current:
                req_name = self.get_requester_name(vc.current, ctx)
                pos = format_duration(vc.position)
                length = format_duration(getattr(vc.current, "length", 0)) if not getattr(vc.current, "is_stream", False) else "Live"
                desc = f"**Now Playing:**\n{format_track_link(vc.current)} | `{pos}/{length}` | `{req_name}`\n\n**Tracks in queue:** `{len(vc.queue)}`"
                await ctx.send(embed=build_embed(title="Queue", description=desc))
            else:
                await ctx.send(embed=info_embed("Queue is empty."))

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx: commands.Context, level: int):
        if not await self.vc_check(ctx):
            return
        if ctx.voice_client:
            if not 0 <= level <= 150:
                return await ctx.send(embed=error_embed("Volume must be between 0 and 150."))
            await ctx.voice_client.set_volume(level)
            await ctx.send(embed=success_embed(f"Volume set to `{level}%`."))
        else:
            await ctx.send(embed=error_embed("Not connected."))

    @commands.command(name="nowplaying", aliases=["nop", "np"])
    async def nowplaying(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        vc = ctx.voice_client
        if not vc or not vc.current:
            return await ctx.send(embed=info_embed("Nothing playing."))
        track = vc.current
        try:
            fp = await generate_nowplaying_card(track, vc)
            file = discord.File(fp, filename="nowplaying.png")
            await ctx.send(file=file)
        except Exception:
            await self.display_player_embed(vc, track, ctx)

    @commands.command(name="seek")
    async def seek(self, ctx: commands.Context, seconds: int):
        if not await self.vc_check(ctx):
            return
        if ctx.voice_client and ctx.voice_client.playing:
            await ctx.voice_client.seek(seconds * 1000)
            await ctx.send(embed=success_embed(f"Seeked to `{seconds}s`."))
        else:
            await ctx.send(embed=error_embed("Nothing playing."))

    @commands.command(name="replay")
    async def replay(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        if ctx.voice_client and ctx.voice_client.playing:
            await ctx.voice_client.seek(0)
            await ctx.send(embed=success_embed("Replaying current track."))
        else:
            await ctx.send(embed=error_embed("Nothing playing."))

    @commands.command(name="clearqueue", aliases=["clear_queue"])
    async def clearqueue(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        if ctx.voice_client:
            ctx.voice_client.queue.clear()
            await ctx.send(embed=success_embed("Queue cleared."))
        else:
            await ctx.send(embed=error_embed("Not connected."))

    @commands.command(name="join", aliases=["connect"])
    async def join(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        if ctx.author.voice:
            if not ctx.voice_client:
                player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
                self.init_player_state(player, ctx)
                await ctx.send(embed=success_embed(f"Joined {ctx.author.voice.channel.mention}"))
            else:
                await ctx.send(embed=info_embed("I am already in a voice channel!"))
        else:
            await ctx.send(embed=error_embed("Join a voice channel first."))

    @commands.command(name="disconnect", aliases=["dc", "leave"])
    async def disconnect(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        if ctx.voice_client:
            settings = self.bot.db.get_guild_settings(ctx.guild.id)
            if settings.get("is_247", False):
                return await ctx.send(embed=error_embed(f"24/7 mode is active. Disable it first using `{ctx.prefix}247 disable`."))
            self.init_player_state(ctx.voice_client)
            await self.delete_player_message(ctx.voice_client)
            await self.update_channel_status(ctx.voice_client.channel, None)
            ctx.voice_client.autoplay = wavelink.AutoPlayMode.disabled
            ctx.voice_client.manual_autoplay = False
            ctx.voice_client.skip_autoplay_once = False
            await ctx.voice_client.disconnect()
            await ctx.send(embed=success_embed("Disconnected."))
        else:
            await ctx.send(embed=error_embed("Not connected."))

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        if ctx.voice_client and ctx.voice_client.playing:
            await ctx.voice_client.pause(True)
            await ctx.send(embed=success_embed("Paused the player."))
        else:
            await ctx.send(embed=error_embed("Nothing is playing."))

    @commands.command(name="resume")
    async def resume(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        if ctx.voice_client and ctx.voice_client.paused:
            await ctx.voice_client.pause(False)
            await ctx.send(embed=success_embed("Resumed the player."))
        else:
            await ctx.send(embed=error_embed("Player is not paused."))

    @commands.group(name="loop", invoke_without_command=True)
    async def loop(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        if not ctx.voice_client:
            return await ctx.send(embed=error_embed("Not connected."))
        current = ctx.voice_client.queue.mode
        ctx.voice_client.queue.mode = wavelink.QueueMode.loop if current != wavelink.QueueMode.loop else wavelink.QueueMode.normal
        state = "enabled" if ctx.voice_client.queue.mode == wavelink.QueueMode.loop else "disabled"
        await ctx.send(embed=success_embed(f"Loop `{state}`."))

    @loop.command(name="enable")
    async def loop_enable(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        if not ctx.voice_client:
            return await ctx.send(embed=error_embed("Not connected."))
        ctx.voice_client.queue.mode = wavelink.QueueMode.loop
        await ctx.send(embed=success_embed("Loop enabled."))

    @loop.command(name="disable")
    async def loop_disable(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        if not ctx.voice_client:
            return await ctx.send(embed=error_embed("Not connected."))
        ctx.voice_client.queue.mode = wavelink.QueueMode.normal
        await ctx.send(embed=success_embed("Loop disabled."))

    @commands.group(name="autoplay", aliases=["ap"], invoke_without_command=True)
    async def autoplay(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        if not ctx.voice_client:
            return await ctx.send(embed=error_embed("Not connected."))
        self.init_player_state(ctx.voice_client)
        if ctx.voice_client.autoplay == wavelink.AutoPlayMode.enabled:
            ctx.voice_client.autoplay = wavelink.AutoPlayMode.disabled
            ctx.voice_client.manual_autoplay = False
            state = "disabled"
        else:
            ctx.voice_client.autoplay = wavelink.AutoPlayMode.enabled
            ctx.voice_client.manual_autoplay = True
            ctx.voice_client.skip_autoplay_once = False
            state = "enabled"
        await ctx.send(embed=success_embed(f"Autoplay `{state}`."))

    @autoplay.command(name="on")
    async def autoplay_on(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        if not ctx.voice_client:
            return await ctx.send(embed=error_embed("Not connected."))
        self.init_player_state(ctx.voice_client)
        ctx.voice_client.autoplay = wavelink.AutoPlayMode.enabled
        ctx.voice_client.manual_autoplay = True
        ctx.voice_client.skip_autoplay_once = False
        await ctx.send(embed=success_embed("Autoplay enabled."))

    @autoplay.command(name="off")
    async def autoplay_off(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        if not ctx.voice_client:
            return await ctx.send(embed=error_embed("Not connected."))
        self.init_player_state(ctx.voice_client)
        ctx.voice_client.autoplay = wavelink.AutoPlayMode.disabled
        ctx.voice_client.manual_autoplay = False
        ctx.voice_client.skip_autoplay_once = False
        await ctx.send(embed=success_embed("Autoplay disabled."))

    @commands.command(name="shuffle")
    async def shuffle(self, ctx: commands.Context):
        if not await self.vc_check(ctx):
            return
        if ctx.voice_client and ctx.voice_client.queue:
            ctx.voice_client.queue.shuffle()
            await ctx.send(embed=success_embed("Queue shuffled."))
        else:
            await ctx.send(embed=error_embed("Queue is empty."))

    @commands.command(name="save")
    async def save(self, ctx: commands.Context, *, query: str = None):
        if query:
            try:
                results = await wavelink.Playable.search(query)
                if not results:
                    return await ctx.send(embed=error_embed(f"No results found for `{query}`."))
                track = results[0] if isinstance(results, list) else (results.tracks[0] if isinstance(results, wavelink.Playlist) else results)
                title = card_tite(getattr(track, "title", "Unknown Track"))
                uri = getattr(track, "uri", None) or f"https://www.youtube.com/watch?v={track.identifier}"
                author = getattr(track, "author", "")
                length = getattr(track, "length", 0)
                added = await self.bot.db.add_to_playlist(ctx.author.id, title, uri, author, length)
                if not added:
                    return await ctx.send(embed=info_embed(f"{format_track_link(track)} is already in your saved playlist."))
                return await ctx.send(embed=success_embed(f"Saved {format_track_link(track)} to your personal playlist!"))
            except Exception as e:
                return await ctx.send(embed=error_embed(f"Failed to save track: {e}"))

        vc = ctx.voice_client
        if not vc or not vc.current:
            return await ctx.send(embed=error_embed("Nothing is currently playing. Provide a song name or link to save: `?save <song>`"))

        track = vc.current
        title = card_tite(getattr(track, "title", "Unknown Track"))
        uri = getattr(track, "uri", None)
        if not uri and hasattr(track, "extras") and track.extras:
            uri = track.extras.get("source_uri")
        if not uri and getattr(track, "identifier", None):
            uri = f"https://www.youtube.com/watch?v={track.identifier}"
        author = getattr(track, "author", "")
        length = getattr(track, "length", 0)

        added = await self.bot.db.add_to_playlist(ctx.author.id, title, uri or "", author, length)
        if not added:
            return await ctx.send(embed=info_embed(f"{format_track_link(track)} is already in your saved playlist."))
        await ctx.send(embed=success_embed(f"Saved {format_track_link(track)} to your personal playlist!"))

    @commands.group(name="playlist", aliases=["pl"], invoke_without_command=True)
    async def playlist(self, ctx: commands.Context):
        tracks = await self.bot.db.get_user_playlist(ctx.author.id)
        if not tracks:
            avatar_url = ctx.author.display_avatar.url if ctx.author.display_avatar else None
            embed = build_embed()
            embed.set_author(name=f"{ctx.author.display_name}'s Playlist", icon_url=avatar_url)
            embed.description = "Your saved playlist is currently empty.\nUse `?save` while listening to music to save tracks!"
            return await ctx.send(embed=embed)
        view = PlaylistView(self, ctx.author, tracks, ctx)
        await view.send(ctx)

    @playlist.command(name="view", aliases=["list", "show"])
    async def playlist_view(self, ctx: commands.Context):
        await self.playlist(ctx)

    @playlist.command(name="save", aliases=["add"])
    async def playlist_save(self, ctx: commands.Context, *, query: str = None):
        await self.save(ctx, query=query)

    @playlist.command(name="delete", aliases=["remove", "rem", "del"])
    async def playlist_delete(self, ctx: commands.Context, number: int):
        deleted = await self.bot.db.delete_from_playlist_by_position(ctx.author.id, number)
        if not deleted:
            return await ctx.send(embed=error_embed(f"Track #{number} not found in your playlist."))
        await ctx.send(embed=success_embed(f"Removed track #{number} (**{deleted['title']}**) from your playlist."))

    @playlist.command(name="clear")
    async def playlist_clear(self, ctx: commands.Context):
        count = await self.bot.db.clear_user_playlist(ctx.author.id)
        if count == 0:
            return await ctx.send(embed=info_embed("Your saved playlist is already empty."))
        await ctx.send(embed=success_embed(f"Cleared **{count}** tracks from your playlist."))

    @playlist.command(name="play")
    async def playlist_play(self, ctx: commands.Context):
        if not ctx.author.voice:
            return await ctx.send(embed=error_embed("You must be connected to a voice channel."))

        tracks = await self.bot.db.get_user_playlist(ctx.author.id)
        if not tracks:
            return await ctx.send(embed=info_embed("Your saved playlist is empty."))

        search_msg = await ctx.send(embed=info_embed(f"Loading {len(tracks)} tracks from your playlist..."))

        vc = ctx.voice_client
        if not vc:
            try:
                vc = await ctx.author.voice.channel.connect(cls=wavelink.Player, reconnect=True)
                self.init_player_state(vc, ctx)
            except Exception as e:
                return await search_msg.edit(embed=error_embed(f"Could not connect to voice channel: {e}"))
        elif vc.channel.id != ctx.author.voice.channel.id:
            return await search_msg.edit(embed=error_embed("You must be in the same voice channel as the bot."))

        loaded = 0
        first_track = None
        for item in tracks:
            try:
                res = await wavelink.Playable.search(item["uri"])
                if res:
                    t = res[0] if isinstance(res, list) else (res.tracks[0] if isinstance(res, wavelink.Playlist) else res)
                    self.set_track_context(t, requester=ctx.author, source_uri=item["uri"])
                    if not vc.playing and loaded == 0:
                        first_track = t
                    else:
                        await vc.queue.put_wait(t)
                    loaded += 1
            except Exception:
                continue

        if first_track:
            vc.current_requester = ctx.author
            await vc.play(first_track)

        await search_msg.edit(embed=success_embed(f"Queued **{loaded}** tracks from your saved playlist!"))

    @commands.group(name="247", aliases=["twentyfour_seven"], invoke_without_command=True)
    async def twentyfour_seven(self, ctx: commands.Context):
        is_admin = ctx.author.guild_permissions.administrator if ctx.guild else False
        is_bot_staff = await self.bot.is_owner(ctx.author) or self.bot.is_admin(ctx.author)
        if not is_admin and not is_bot_staff:
            return await ctx.send(embed=error_embed("You need Administrator permissions to use this command."))
        await ctx.send(embed=info_embed(f"Usage: `{ctx.prefix}247 <enable|disable>`"))

    @twentyfour_seven.command(name="enable", aliases=["on"])
    async def enable_247(self, ctx: commands.Context):
        is_admin = ctx.author.guild_permissions.administrator if ctx.guild else False
        is_bot_staff = await self.bot.is_owner(ctx.author) or self.bot.is_admin(ctx.author)
        if not is_admin and not is_bot_staff:
            return await ctx.send(embed=error_embed("You need Administrator permissions to use this command."))

        if not ctx.author.voice:
            return await ctx.send(embed=error_embed("You must be connected to a voice channel."))

        vc_id = ctx.author.voice.channel.id
        await self.bot.db.set_guild_247(
            guild_id=ctx.guild.id,
            is_247=True,
            voice_channel_id=vc_id,
            text_channel_id=ctx.channel.id
        )

        if not ctx.voice_client:
            try:
                await ctx.author.voice.channel.connect(cls=wavelink.Player, reconnect=True)
            except Exception:
                pass

        await ctx.send(embed=success_embed(f"24/7 mode enabled. The bot will stay connected to {ctx.author.voice.channel.mention} permanently."))

    @twentyfour_seven.command(name="disable", aliases=["off"])
    async def disable_247(self, ctx: commands.Context):
        is_admin = ctx.author.guild_permissions.administrator if ctx.guild else False
        is_bot_staff = await self.bot.is_owner(ctx.author) or self.bot.is_admin(ctx.author)
        if not is_admin and not is_bot_staff:
            return await ctx.send(embed=error_embed("You need Administrator permissions to use this command."))

        await self.bot.db.set_guild_247(
            guild_id=ctx.guild.id,
            is_247=False,
            voice_channel_id=0,
            text_channel_id=0
        )
        await ctx.send(embed=success_embed("24/7 mode disabled. The bot will now disconnect when inactive or when queue ends."))

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))


# @Author: LynxModz
 #   + Discord: ifwlynx_
 #   + Community: https://dsc.gg/lynx-modz
 #   + Eve Bot source is free for everyone. Paid distribution is not allowed.