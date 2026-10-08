import os
import io
import time
import random
import aiohttp
import discord
from discord.ext import commands
import psutil
from PIL import Image, ImageDraw, ImageOps, ImageFont
from utils.ui import (
    build_embed,
    info_embed,
    error_embed,
    success_embed,
    get_emoji,
    SETTINGS,
    format_expiration
)
from utils.paginator import Paginator

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

async def generate_profile_card(
    user: discord.User | discord.Member,
    db,
    is_owner: bool,
    is_admin: bool,
    guild: discord.Guild | str | None = None
) -> io.BytesIO:
    bg_candidates = ["bg.jpg", "bg2.jpg", "bg3.jpg", "bg4.jpg", "bg5.jpg", "bg6.jpg"]
    existing_bgs = [os.path.join("assets", f) for f in bg_candidates if os.path.exists(os.path.join("assets", f))]

    if existing_bgs:
        chosen_bg = random.choice(existing_bgs)
        base_img = Image.open(chosen_bg).convert("RGBA")
        base_img = ImageOps.fit(base_img, (728, 410), method=Image.Resampling.LANCZOS)
    else:
        base_img = Image.new("RGBA", (728, 410), (20, 20, 30, 255))

    card = base_img.copy()

    panel_overlay = Image.new("RGBA", card.size, (0, 0, 0, 0))
    p_draw = ImageDraw.Draw(panel_overlay)
    p_draw.rounded_rectangle([(20, 20), (370, 390)], radius=18, fill=(15, 15, 25, 195), outline=(255, 255, 255, 40), width=1)
    
    card = Image.alpha_composite(card, panel_overlay)
    draw = ImageDraw.Draw(card)

    font_bold_paths = ("arialbd.ttf", "segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf")
    font_reg_paths = ("arial.ttf", "segoeui.ttf", "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf")
    
    font_name = load_font(font_bold_paths, 20)
    font_badge = load_font(font_bold_paths, 11)
    font_label = load_font(font_bold_paths, 12)
    font_val = load_font(font_reg_paths, 13)
    font_id = load_font(font_reg_paths, 11)

    avatar_img = None
    if user.display_avatar:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(user.display_avatar.url, timeout=4) as resp:
                    if resp.status == 200:
                        av_bytes = await resp.read()
                        avatar_raw = Image.open(io.BytesIO(av_bytes)).convert("RGBA")
                        avatar_img = ImageOps.fit(avatar_raw, (64, 64), method=Image.Resampling.LANCZOS)
        except Exception:
            pass

    if avatar_img:
        mask = Image.new("L", (64, 64), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse([(0, 0), (64, 64)], fill=255)
        card.paste(avatar_img, (35, 35), mask=mask)
        draw.ellipse([(34, 34), (99, 99)], outline=(255, 255, 255, 100), width=2)
    else:
        draw.ellipse([(35, 35), (99, 99)], fill=(40, 40, 55, 255), outline=(255, 255, 255, 80), width=2)

    display_name = user.display_name
    if len(display_name) > 14:
        display_name = display_name[:12] + "..."
    draw.text((112, 36), display_name, fill=(255, 255, 255, 255), font=font_name)
    draw.text((112, 60), f"ID: {user.id}", fill=(180, 180, 200, 255), font=font_id)

    if is_owner:
        badge_text = "BOT OWNER"
        badge_bg = (235, 75, 75, 230)
    elif is_admin:
        badge_text = "BOT ADMIN"
        badge_bg = (88, 101, 242, 230)
    else:
        badge_text = "USER"
        badge_bg = (60, 65, 80, 230)

    try:
        b_box = font_badge.getbbox(badge_text)
        b_w = b_box[2] - b_box[0]
    except Exception:
        b_w = len(badge_text) * 7
    badge_rect = [(112, 76), (112 + b_w + 14, 94)]
    draw.rounded_rectangle(badge_rect, radius=5, fill=badge_bg)
    draw.text((119, 79), badge_text, fill=(255, 255, 255, 255), font=font_badge)

    draw.line([(35, 108), (355, 108)], fill=(255, 255, 255, 30), width=1)

    if isinstance(guild, discord.Guild):
        server_str = guild.name
    elif isinstance(guild, str) and guild.strip():
        server_str = guild.strip()
    elif hasattr(user, "guild") and getattr(user, "guild", None):
        server_str = user.guild.name
    else:
        server_str = "Direct Message"

    if len(server_str) > 28:
        server_str = server_str[:25] + "..."

    created_str = user.created_at.strftime("%d %b %Y") if hasattr(user, "created_at") and user.created_at else "Unknown"

    np_data = db.get_noprefix_user(user.id)
    if np_data and db.is_noprefix(user.id):
        dur_type = np_data.get("duration_type", "lifetime")
        dur_display = {
            "1w": "Active (1 Week)",
            "1m": "Active (1 Month)",
            "3m": "Active (3 Months)",
            "6m": "Active (6 Months)",
            "lifetime": "Active (Lifetime)"
        }.get(dur_type, f"Active ({dur_type})")
        exp_val = np_data.get("expires_at")
        if exp_val:
            exp_str = time.strftime("%d %b %Y", time.localtime(exp_val))
        else:
            exp_str = "Never (Lifetime)"
    else:
        dur_display = "Inactive"
        exp_str = "None"

    fields = [
        ("Server", server_str),
        ("User Since", created_str),
        ("No-Prefix Status", dur_display),
        ("Subscription Expiry", exp_str),
        ("Bot Role", "Bot Owner" if is_owner else ("Bot Administrator" if is_admin else "Standard User"))
    ]

    y = 118
    for label, val in fields:
        draw.text((38, y), label, fill=(160, 165, 190, 255), font=font_label)
        draw.text((38, y + 16), val, fill=(245, 245, 255, 255), font=font_val)
        y += 50

    fp = io.BytesIO()
    card.convert("RGB").save(fp, format="PNG")
    fp.seek(0)
    return fp

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()

    def _get_display_prefix(self, ctx: commands.Context) -> str:
        default_p = SETTINGS.get("default_prefix", "?")
        if not ctx.guild:
            return default_p
        guild_settings = self.bot.db.get_guild_settings(ctx.guild.id)
        return guild_settings.get("prefix") or default_p

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        start = time.perf_counter()
        msg = await ctx.send(embed=info_embed("Pinging..."))
        end = time.perf_counter()
        msg_latency = round((end - start) * 1000)
        ws_latency = round(self.bot.latency * 1000)
        
        info_icon = get_emoji("info")
        prefix_str = f"{info_icon} " if info_icon else ""
        embed = build_embed(
            description=f"{prefix_str}**Latency:** {ws_latency}ms\n**Response:** {msg_latency}ms"
        )
        await msg.edit(embed=embed)

    @commands.command(name="stats")
    async def stats(self, ctx: commands.Context):
        uptime_seconds = int(time.time() - self.start_time)
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

        process = psutil.Process()
        mem_info = process.memory_info()
        mem_usage = f"{mem_info.rss / 1024 / 1024:.2f} MB"
        cpu_usage = f"{psutil.cpu_percent()}%"

        total_members = sum(g.member_count for g in self.bot.guilds if g.member_count)
        total_guilds = len(self.bot.guilds)
        total_channels = sum(len(g.channels) for g in self.bot.guilds)
        shard_count = self.bot.shard_count or 1

        bot_name = SETTINGS.get('bot-name', 'Eve')
        info_icon = get_emoji("info")
        title = f"{info_icon} {bot_name} Statistics" if info_icon else f"{bot_name} Statistics"
        
        embed = build_embed(title=title)
        embed.add_field(name="Servers", value=f"`{total_guilds}`", inline=True)
        embed.add_field(name="Users", value=f"`{total_members}`", inline=True)
        embed.add_field(name="Channels", value=f"`{total_channels}`", inline=True)
        embed.add_field(name="Shards", value=f"`{shard_count}`", inline=True)
        embed.add_field(name="Uptime", value=f"`{uptime_str}`", inline=True)
        embed.add_field(name="Ping", value=f"`{round(self.bot.latency * 1000)}ms`", inline=True)
        embed.add_field(name="Memory", value=f"`{mem_usage}`", inline=True)
        embed.add_field(name="CPU", value=f"`{cpu_usage}`", inline=True)

        bot_avatar = self.bot.user.display_avatar.url if self.bot.user and self.bot.user.display_avatar else None
        embed.set_footer(text=f"{bot_name} • System Overview", icon_url=bot_avatar)

        await ctx.send(embed=embed)

    @commands.command(name="profile", aliases=["userinfo", "whois"])
    async def profile(self, ctx: commands.Context, *, member: discord.User | discord.Member = None):
        target = member or ctx.author
        try:
            is_owner = await self.bot.is_owner(target)
            is_admin = self.bot.is_admin(target)
            fp = await generate_profile_card(target, self.bot.db, is_owner, is_admin, guild=ctx.guild)
            file = discord.File(fp, filename="profile.png")
            await ctx.send(file=file)
        except Exception as e:
            await ctx.send(embed=error_embed(f"Failed to generate profile card: {e}"))

    @commands.command(name="avatar")
    async def avatar(self, ctx: commands.Context, *, member: discord.User | discord.Member = None):
        user = member or ctx.author
        avatar_url = user.display_avatar.url
        embed = build_embed(title=f"{user.name}'s Avatar")
        embed.set_image(url=avatar_url)
        await ctx.send(embed=embed)

    @commands.command(name="banner")
    async def banner(self, ctx: commands.Context, *, member: discord.User | discord.Member = None):
        user_target = member or ctx.author
        try:
            user = await self.bot.fetch_user(user_target.id)
        except Exception:
            user = user_target

        if not user.banner:
            await ctx.send(embed=error_embed("User has no banner"))
            return

        embed = build_embed(title=f"{user.name}'s Banner")
        embed.set_image(url=user.banner.url)
        await ctx.send(embed=embed)

    @commands.command(name="setprefix", aliases=["prefix", "changeprefix"])
    @commands.guild_only()
    async def setprefix(self, ctx: commands.Context, *, new_prefix: str = None):
        is_admin = ctx.author.guild_permissions.administrator if ctx.guild else False
        is_bot_staff = await self.bot.is_owner(ctx.author) or self.bot.is_admin(ctx.author)
        if not is_admin and not is_bot_staff:
            return await ctx.send(embed=error_embed("You need Administrator permissions to change the server prefix."))

        if not self.bot.db.is_premium_guild(ctx.guild.id):
            return await ctx.send(embed=error_embed("Custom server prefix is a **Premium Guild** feature. Ask bot owners to activate premium for your server!"))

        if not new_prefix or new_prefix.lower() in ["reset", "default", "none"]:
            await self.bot.db.set_guild_prefix(ctx.guild.id, None)
            default_p = SETTINGS.get("default_prefix", "?")
            return await ctx.send(embed=success_embed(f"Server prefix has been reset to default: `{default_p}`"))

        cleaned_prefix = new_prefix.strip()
        if len(cleaned_prefix) > 5:
            return await ctx.send(embed=error_embed("Prefix length cannot exceed 5 characters."))

        await self.bot.db.set_guild_prefix(ctx.guild.id, cleaned_prefix)
        await ctx.send(embed=success_embed(f"Server prefix has been successfully updated to `{cleaned_prefix}`"))

    @commands.command(name="guildnoprefix", aliases=["gnoprefix", "servernoprefix"])
    @commands.guild_only()
    async def guild_noprefix_cmd(self, ctx: commands.Context, state: str = None):
        is_admin = ctx.author.guild_permissions.administrator if ctx.guild else False
        is_bot_staff = await self.bot.is_owner(ctx.author) or self.bot.is_admin(ctx.author)
        if not is_admin and not is_bot_staff:
            return await ctx.send(embed=error_embed("You need Administrator permissions to configure guild no-prefix."))

        if not self.bot.db.is_premium_guild(ctx.guild.id):
            return await ctx.send(embed=error_embed("Guild-wide No-Prefix access is an exclusive **Premium Guild** feature."))

        guild_settings = self.bot.db.get_guild_settings(ctx.guild.id)
        current_state = guild_settings.get("guild_noprefix", False)

        if not state:
            toggle_state = not current_state
        else:
            toggle_state = state.lower() in ["enable", "on", "true", "yes", "1"]

        await self.bot.db.set_guild_noprefix(ctx.guild.id, toggle_state)
        status_word = "enabled" if toggle_state else "disabled"
        desc = (
            f"Guild-wide No-Prefix is now **{status_word}** for **{ctx.guild.name}**!\n"
            f"{'Anyone in this server can now use commands without needing a prefix.' if toggle_state else 'Commands now require the server prefix.'}"
        )
        await ctx.send(embed=success_embed(desc))

    @commands.group(name="settings", aliases=["serversettings", "guildsettings", "config"], invoke_without_command=True)
    @commands.guild_only()
    async def settings_panel(self, ctx: commands.Context):
        guild = ctx.guild
        is_premium = self.bot.db.is_premium_guild(guild.id)
        premium_data = self.bot.db.get_premium_guild(guild.id) if is_premium else None
        guild_settings = self.bot.db.get_guild_settings(guild.id)

        embed = build_embed(title=f"Server Settings — {guild.name}")
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        if is_premium and premium_data:
            dur_type = premium_data.get("duration_type", "lifetime")
            dur_label = {
                "1w": "1 Week",
                "1m": "1 Month",
                "3m": "3 Months",
                "6m": "6 Months",
                "lifetime": "Lifetime"
            }.get(dur_type, dur_type.title())
            exp_str = format_expiration(premium_data.get("expires_at"))
            premium_status = f"**Active** (`{dur_label}`)\n└ Expiry: {exp_str}"
        else:
            premium_status = "**Inactive** (Standard Tier)"

        prefix_val = guild_settings.get("prefix") or SETTINGS.get("default_prefix", "?")
        gnoprefix_val = "Enabled" if guild_settings.get("guild_noprefix", False) and is_premium else "Disabled"
        
        is_247 = guild_settings.get("is_247", False)
        vc_id = guild_settings.get("voice_channel_id", 0)
        vc_channel = guild.get_channel(vc_id) if vc_id else None
        mode_247_str = f"Enabled in {vc_channel.mention}" if is_247 and vc_channel else ("Enabled" if is_247 else "Disabled")

        embed.add_field(name="Premium Status", value=premium_status, inline=False)
        embed.add_field(name="Server Prefix", value=f"`{prefix_val}`", inline=True)
        embed.add_field(name="Guild No-Prefix", value=f"`{gnoprefix_val}`", inline=True)
        embed.add_field(name="24/7 Mode", value=f"`{mode_247_str}`", inline=True)

        prefix = self._get_display_prefix(ctx)
        embed.set_footer(text=f"Change settings: {prefix}setprefix, {prefix}guildnoprefix, {prefix}247")
        await ctx.send(embed=embed)

    @settings_panel.command(name="noprefix", aliases=["gnoprefix"])
    @commands.guild_only()
    async def settings_noprefix_subcmd(self, ctx: commands.Context, state: str = None):
        await self.guild_noprefix_cmd(ctx, state=state)

    @settings_panel.command(name="prefix")
    @commands.guild_only()
    async def settings_prefix_subcmd(self, ctx: commands.Context, *, new_prefix: str = None):
        await self.setprefix(ctx, new_prefix=new_prefix)

    @commands.command(name="help")
    async def help(self, ctx: commands.Context, *, command_or_cog: str = None):
        prefix = self._get_display_prefix(ctx)
        footer_text = f"Requested by {ctx.author.display_name}"
        author_icon = ctx.author.display_avatar.url
        bot_avatar = self.bot.user.display_avatar.url if self.bot.user and self.bot.user.display_avatar else None

        if command_or_cog:
            target = command_or_cog.lower().strip()
            cmd = self.bot.get_command(target)
            if cmd and not cmd.hidden:
                if cmd.cog_name == "Owner":
                    await ctx.send(embed=error_embed("Command not found"))
                    return
                embed = build_embed()
                embed.set_author(name=f"Command: {cmd.name}", icon_url=bot_avatar)
                desc = cmd.help or "No description provided."
                aliases = ", ".join(f"`{a}`" for a in cmd.aliases) if cmd.aliases else "None"
                usage_sig = f" {cmd.signature}" if cmd.signature else ""
                usage = f"{prefix}{cmd.name}{usage_sig}"
                
                subcommands_str = ""
                if isinstance(cmd, commands.Group) and cmd.commands:
                    subs = [f"`{s.name}`" for s in cmd.commands if not s.hidden]
                    if subs:
                        subcommands_str = f"\n\n**Subcommands**\n{', '.join(subs)}"

                embed.description = (
                    f"**Description**\n{desc}\n\n"
                    f"**Usage**\n`{usage}`\n\n"
                    f"**Aliases**\n{aliases}"
                    f"{subcommands_str}"
                )
                embed.set_footer(text=footer_text, icon_url=author_icon)
                await ctx.send(embed=embed)
                return

            matched_cog = None
            for name, cog in self.bot.cogs.items():
                if name.lower() == target and name != "Owner":
                    matched_cog = (name, cog)
                    break

            if matched_cog:
                name, cog = matched_cog
                cog_commands = [c for c in cog.get_commands() if not c.hidden]
                embed = build_embed()
                embed.set_author(name=f"{name} Commands", icon_url=bot_avatar)
                cmd_list = " , ".join(f"`{c.name}`" for c in cog_commands)
                embed.description = (
                    f"Use `{prefix}help <command>` for detailed info on a command.\n\n"
                    f"**Commands**\n{cmd_list if cmd_list else 'No commands available.'}"
                )
                embed.set_footer(text=footer_text, icon_url=author_icon)
                await ctx.send(embed=embed)
                return

            await ctx.send(embed=error_embed("Command or category not found"))
            return

        pages = []
        cogs_to_show = ["General", "Music"]

        for cog_name in cogs_to_show:
            cog = self.bot.get_cog(cog_name)
            if not cog:
                continue
            cog_cmds = [c for c in cog.get_commands() if not c.hidden]
            if not cog_cmds:
                continue

            embed = build_embed()
            embed.set_author(name=f"{SETTINGS.get('bot-name', 'Eve')} — {cog_name} Commands", icon_url=bot_avatar)
            cmd_list = " , ".join(f"`{cmd.name}`" for cmd in cog_cmds)
            embed.description = (
                f"Type `{prefix}help <command>` for command details.\n\n"
                f"**Commands**\n{cmd_list}"
            )
            embed.set_footer(text=footer_text, icon_url=author_icon)
            pages.append(embed)

        if not pages:
            await ctx.send(embed=info_embed("No help pages available"))
            return

        paginator = Paginator(author=ctx.author, pages=pages)
        await paginator.send(ctx)

async def setup(bot):
    await bot.add_cog(General(bot))



# @Author: LynxModz
 #   + Discord: ifwlynx_
 #   + Community: https://dsc.gg/lynx-modz
 #   + Eve Bot source is free for everyone. Paid distribution is not allowed.

