import os
import sys
import asyncio
import platform
import datetime
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import wavelink
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.columns import Columns
from rich.align import Align

from DB.database import Database
from utils.ui import (
    SETTINGS,
    LAVA_NODES,
    build_embed,
    error_embed,
    warning_embed,
    get_theme_color,
    get_emoji
)
from utils.logging import logger, send_log

load_dotenv()
console = Console()

def get_prefix(bot, message):
    default_p = SETTINGS.get("default_prefix", "?")
    if not message.guild:
        return commands.when_mentioned_or(default_p)(bot, message)
    
    guild_settings = bot.db.get_guild_settings(message.guild.id)
    guild_p = guild_settings.get("prefix") or default_p
    
    user_noprefix = bot.db.is_noprefix(message.author.id)
    guild_noprefix = bot.db.is_guild_noprefix_enabled(message.guild.id)
    
    if user_noprefix or guild_noprefix:
        return commands.when_mentioned_or(guild_p, "")(bot, message)
    return commands.when_mentioned_or(guild_p)(bot, message)

intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.messages = True
intents.message_content = True
intents.members = True

class EveBot(commands.AutoShardedBot):
    def __init__(self):
        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True
        )
        self.db = Database()
        raw_owner_ids = SETTINGS.get("owner_ids", [])
        self.owner_ids = {int(x) for x in raw_owner_ids if str(x).isdigit()}
        raw_admin_ids = SETTINGS.get("admin_ids", [])
        self.admin_ids = {int(x) for x in raw_admin_ids if str(x).isdigit()}

    async def is_owner(self, user: discord.User | discord.Member) -> bool:
        if user.id in self.owner_ids:
            return True
        return await super().is_owner(user)

    def is_admin(self, user: discord.User | discord.Member) -> bool:
        return user.id in self.admin_ids or user.id in self.owner_ids

    @tasks.loop(seconds=60)
    async def cleanup_loop(self):
        try:
            await self.db.cleanup_expired()
        except Exception:
            pass

    @cleanup_loop.before_loop
    async def before_cleanup(self):
        await self.wait_until_ready()

    async def setup_hook(self):
        self.display_banner()
        await logger.start()
        await self.db.initialize()

        nodes = []
        for node_data in LAVA_NODES:
            uri = node_data.get("uri")
            password = node_data.get("password")
            identifier = node_data.get("identifier", "Main-Node")
            if uri and password:
                node = wavelink.Node(
                    identifier=identifier,
                    uri=uri,
                    password=password
                )
                nodes.append(node)

        if nodes:
            try:
                await wavelink.Pool.connect(nodes=nodes, client=self, cache_capacity=100)
                console.print(f"  [bold green]✓[/bold green] [dim]Lavalink[/dim]  [cyan]{len(nodes)} node(s) connected[/cyan]")
            except Exception as e:
                console.print(f"  [bold red]✗[/bold red] [dim]Lavalink[/dim]  [red]{e}[/red]")

        initial_extensions = [
            "cogs.general",
            "cogs.music",
            "cogs.owner"
        ]
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                cog_name = ext.split(".")[-1].capitalize()
                console.print(f"  [bold green]✓[/bold green] [dim]Cog[/dim]       [cyan]{cog_name}[/cyan] loaded")
            except Exception as e:
                cog_name = ext.split(".")[-1].capitalize()
                console.print(f"  [bold red]✗[/bold red] [dim]Cog[/dim]       [red]{cog_name}[/red] failed — {e}")

        self.cleanup_loop.start()

    async def close(self):
        try:
            if self.user:
                embed = build_embed(title="Bot Offline")
                embed.description = f"**Client:** {self.user} (`{self.user.id}`)\n**Status:** Offline / Shutdown initiated"
                await send_log("Bot-offline-logs", embed=embed)
                await asyncio.sleep(0.5)
        except Exception:
            pass
        await logger.close()
        await super().close()

    def display_banner(self):
        # Clear the terminal
        os.system("cls" if os.name == "nt" else "clear")

        bot_name = SETTINGS.get("bot-name", "Eve")

        # ASCII logo
        logo_lines = [
            r"  ______               __  __           _      ",
            r" |  ____|             |  \/  |         (_)     ",
            r" | |__ __   _____     | \  / |_   _ ___ _  ___ ",
            r" |  __|\ \ / / _ \    | |\/| | | | / __| |/ __|",
            r" | |____\ V /  __/    | |  | | |_| \__ \ | (__ ",
            r" |______|\_/ \___|    |_|  |_|\__,_|___/_|\___|",
        ]

        logo_text = Text()
        colors = ["bright_cyan", "bright_cyan", "cyan", "cyan", "blue", "blue"]
        for line, color in zip(logo_lines, colors):
            logo_text.append(line + "\n", style=f"bold {color}")

        version_line = Text()
        version_line.append(f"  {bot_name} Music Bot", style="bold white")
        version_line.append("  ·  ", style="dim")
        version_line.append("By - LynxModz", style="dim cyan")
        version_line.append("  ·  ", style="dim")
        version_line.append("Powered by Wavelink", style="dim cyan")
        logo_text.append_text(version_line)

        console.print()
        console.print(Align.center(logo_text))
        console.print()
        console.print(Align.center(Text("─" * 56, style="dim cyan")))
        console.print()
        console.print(f"  [dim]Settingup modules...[/dim]")
        console.print()

    async def on_shard_connect(self, shard_id: int):
        console.print(f"  [bold green]✓[/bold green] [dim]Shard #{shard_id}[/dim]   connected")

    async def on_shard_ready(self, shard_id: int):
        console.print(f"  [bold green]✓[/bold green] [dim]Shard #{shard_id}[/dim]   ready")

    async def on_shard_disconnect(self, shard_id: int):
        console.print(f"  [bold yellow]⚠[/bold yellow] [dim]Shard #{shard_id}[/dim]   [yellow]disconnected — reconnecting...[/yellow]")

    async def on_shard_resumed(self, shard_id: int):
        console.print(f"  [bold green]✓[/bold green] [dim]Shard #{shard_id}[/dim]   resumed")

    async def on_ready(self):
        act_name = SETTINGS.get("activity_name", "music | ?help")
        act_type_str = SETTINGS.get("activity_type", "listening").lower()

        act_type = discord.ActivityType.listening
        if act_type_str == "playing":
            act_type = discord.ActivityType.playing
        elif act_type_str == "watching":
            act_type = discord.ActivityType.watching
        elif act_type_str == "competing":
            act_type = discord.ActivityType.competing

        activity = discord.Activity(type=act_type, name=act_name)
        await self.change_presence(activity=activity)

        bot_name = SETTINGS.get("bot-name", "Eve")
        prefix = SETTINGS.get("default_prefix", "?")
        now = datetime.datetime.now().strftime("%d %b %Y  %H:%M:%S")
        py_ver = platform.python_version()
        discord_ver = discord.__version__
        shard_count = self.shard_count or 1
        guild_count = len(self.guilds)
        total_members = sum(g.member_count or 0 for g in self.guilds)

        # Build info table
        table = Table(
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 2),
            border_style="dim cyan"
        )
        table.add_column(justify="right", style="dim", no_wrap=True)
        table.add_column(style="bold white", no_wrap=True)

        table.add_row("Client", f"{self.user}  [dim]({self.user.id})[/dim]")
        table.add_row("Prefix", f"[cyan]{prefix}[/cyan]")
        table.add_row("Guilds", f"[cyan]{guild_count}[/cyan]")
        table.add_row("Members", f"[cyan]{total_members}[/cyan]")
        table.add_row("Shards", f"[cyan]{shard_count}[/cyan]")
        table.add_row("Python", f"[cyan]{py_ver}[/cyan]")
        table.add_row("discord.py", f"[cyan]{discord_ver}[/cyan]")
        table.add_row("Started", f"[cyan]{now}[/cyan]")

        console.print()
        console.print(Align.center(Text("─" * 56, style="dim cyan")))
        console.print()
        console.print(
            Align.center(
                Panel(
                    Align.center(table),
                    title=f"[bold cyan] {bot_name} [/bold cyan]",
                    subtitle="[bold green]  Online  [/bold green]",
                    border_style="cyan",
                    padding=(1, 4),
                    width=62
                )
            )
        )
        console.print()

bot = EveBot()

@bot.event
async def on_guild_join(guild: discord.Guild):
    embed = build_embed(title="Joined Server")
    embed.description = f"**Name:** **{guild.name}** (`{guild.id}`)\n**Members:** `{guild.member_count}`\n**Owner:** `{guild.owner_id}`"
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await send_log("Server-join", embed=embed)

@bot.event
async def on_guild_remove(guild: discord.Guild):
    embed = build_embed(title="Left Server")
    embed.description = f"**Name:** **{guild.name}** (`{guild.id}`)\n**Members:** `{guild.member_count}`"
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await send_log("Server-left", embed=embed)

@bot.check
async def check_development_mode(ctx: commands.Context) -> bool:
    if not bot.db.development_mode:
        return True

    if await bot.is_owner(ctx.author) or bot.is_admin(ctx.author):
        return True

    dev_server_id = str(SETTINGS.get("development_server_id", "")).strip()
    if dev_server_id and ctx.guild and str(ctx.guild.id) == dev_server_id:
        return True

    await ctx.send(embed=error_embed("Bot is currently in development mode"))
    return False

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.NotOwner):
        await ctx.send(embed=error_embed("You do not have permission to use this command"))
        return

    if isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=error_embed("You lack the required permissions to use this command"))
        return

    if isinstance(error, commands.BotMissingPermissions):
        await ctx.send(embed=error_embed("I lack the required permissions to execute this command"))
        return

    if isinstance(error, commands.CommandOnCooldown):
        log_embed = build_embed(title="Command Rate Limited")
        log_embed.description = f"**User:** {ctx.author} (`{ctx.author.id}`)\n**Command:** `{ctx.command}`\n**Retry After:** `{error.retry_after:.1f}s`"
        await send_log("Rate-limit", embed=log_embed)
        await ctx.send(embed=warning_embed(f"Command is on cooldown. Try again in {error.retry_after:.1f}s"))
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=error_embed(f"Missing required argument: `{error.param.name}`"))
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send(embed=error_embed("Invalid argument provided"))
        return

    if isinstance(error, commands.CheckFailure):
        return

    original = getattr(error, "original", error)
    err_str = str(original).lower()
    if "unable to get" in err_str or "queueempty" in str(type(original)).lower():
        return

    log_embed = build_embed(title="Command Error Log")
    log_embed.description = f"**Command:** `{ctx.command}`\n**User:** {ctx.author} (`{ctx.author.id}`)\n**Error:** ```\n{str(original)[:1500]}\n```"
    await send_log("Error-log", embed=log_embed)

    console.print(f"[bold red]Command Error in {ctx.command}:[/bold red] {original}")
    await ctx.send(embed=error_embed("An unexpected error occurred while executing the command"))

def main():
    token = os.getenv("TOKEN")
    if not token:
        console.print("[bold red]Error:[/bold red] TOKEN not found in environment variables.")
        sys.exit(1)
    
    try:
        bot.run(token)
    except Exception as e:
        console.print(f"[bold red]Fatal Bot Error:[/bold red] {e}")

if __name__ == "__main__":
    main()


# @Author: LynxModz
 #   + Discord: ifwlynx_
 #   + Community: https://dsc.gg/lynx-modz
 #   + Eve Bot source is free for everyone. Paid distribution is not allowed.