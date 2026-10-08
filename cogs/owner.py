import os
import sys
import time
import subprocess
import discord
from discord.ext import commands
from utils.ui import (
    SETTINGS,
    save_settings,
    build_embed,
    success_embed,
    error_embed,
    info_embed,
    parse_duration_string,
    format_expiration
)
from utils.paginator import Paginator, FilteredPaginator
from utils.logging import send_log

class DurationSelectView(discord.ui.View):
    def __init__(self, requester: discord.User | discord.Member, target_name: str, on_select_callback, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.requester = requester
        self.target_name = target_name
        self.on_select_callback = on_select_callback
        self.message = None

        options = [
            discord.SelectOption(label="1 Week", value="1w", description="Active for 7 days"),
            discord.SelectOption(label="1 Month", value="1m", description="Active for 30 days"),
            discord.SelectOption(label="3 Months", value="3m", description="Active for 90 days"),
            discord.SelectOption(label="6 Months", value="6m", description="Active for 180 days"),
            discord.SelectOption(label="Lifetime", value="lifetime", description="Permanent access without expiration")
        ]
        select_menu = discord.ui.Select(
            placeholder="Select duration period...",
            options=options
        )
        select_menu.callback = self.select_callback
        self.add_item(select_menu)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                embed=error_embed("Only the command requester can operate this selection."),
                ephemeral=True
            )
            return False
        return True

    async def select_callback(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]
        for item in self.children:
            item.disabled = True
        await self.on_select_callback(interaction, value)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        is_owner = await self.bot.is_owner(ctx.author)
        is_admin = self.bot.is_admin(ctx.author)
        if not (is_owner or is_admin):
            raise commands.NotOwner("You do not have permission to use staff commands.")
        return True

    @commands.group(name="owner", aliases=["ownerhelp", "staff"], invoke_without_command=True)
    async def owner_help_cmd(self, ctx: commands.Context):
        prefix = ctx.prefix
        embed = build_embed(title="Staff & Owner Command Panel")
        
        is_actual_owner = await self.bot.is_owner(ctx.author)
        role_label = "Bot Owner" if is_actual_owner else "Bot Administrator"
        embed.set_author(name=f"Authorized Access: {ctx.author.name} ({role_label})", icon_url=ctx.author.display_avatar.url)

        owner_only_cmds = (
            f"`{prefix}admin add <user>` — Add a bot administrator\n"
            f"`{prefix}admin remove <user>` — Remove a bot administrator\n"
            f"`{prefix}development mode <on|off>` — Toggle maintenance mode\n"
            f"`{prefix}reload <cog|all>` — Hot reload cogs\n"
            f"`{prefix}restart` — Restart bot core process\n"
        )
        staff_cmds = (
            f"`{prefix}admin list` — View all owners and administrators\n"
            f"`{prefix}noprefix add <user> [duration]` — Grant no-prefix access with duration\n"
            f"`{prefix}noprefix remove <user>` — Revoke no-prefix access\n"
            f"`{prefix}noprefix list` — Filtered paginator for all no-prefix users\n"
            f"`{prefix}premium guild add <guild_id> [duration]` — Grant server premium\n"
            f"`{prefix}premium guild remove <guild_id>` — Revoke server premium\n"
            f"`{prefix}premium guild list` — Filtered paginator for premium servers\n"
            f"`{prefix}server list` (`{prefix}slist`) — View connected servers\n"
            f"`{prefix}owner commands` — View this commands list\n"
        )

        embed.add_field(name="Owner Only Commands", value=owner_only_cmds, inline=False)
        embed.add_field(name="Staff / Admin Manageable Commands", value=staff_cmds, inline=False)
        embed.set_footer(text="Duration options: 1 week, 1 month, 3 months, 6 months, lifetime")
        await ctx.send(embed=embed)

    @owner_help_cmd.command(name="commands", aliases=["cmds", "help"])
    async def owner_commands_list(self, ctx: commands.Context):
        await self.owner_help_cmd(ctx)

    @commands.command(name="reload")
    async def reload(self, ctx: commands.Context, *, cog: str = "all"):
        if not await self.bot.is_owner(ctx.author):
            return await ctx.send(embed=error_embed("Only bot owners can reload extensions."))
        
        target = cog.strip().lower()
        all_extensions = ["cogs.general", "cogs.music", "cogs.owner"]
        
        if target in ["all", "*"]:
            reloaded = []
            failed = []
            for ext in all_extensions:
                try:
                    await self.bot.reload_extension(ext)
                    reloaded.append(f"`{ext}`")
                except Exception as e:
                    failed.append(f"`{ext}`: {e}")
            
            desc_parts = []
            if reloaded:
                desc_parts.append(f"Successfully reloaded: {', '.join(reloaded)}")
            if failed:
                desc_parts.append(f"Failed to reload:\n" + "\n".join(failed))
            
            if failed:
                await ctx.send(embed=error_embed("\n\n".join(desc_parts)))
            else:
                await ctx.send(embed=success_embed("\n\n".join(desc_parts)))
            return

        if not target.startswith("cogs."):
            target = f"cogs.{target}"
            
        try:
            await self.bot.reload_extension(target)
            await ctx.send(embed=success_embed(f"Reloaded `{target}`"))
        except Exception as e:
            await ctx.send(embed=error_embed(f"Failed to reload `{target}`: {e}"))

    @commands.command(name="restart")
    async def restart(self, ctx: commands.Context):
        if not await self.bot.is_owner(ctx.author):
            return await ctx.send(embed=error_embed("Only bot owners can restart the bot."))
        await ctx.send(embed=info_embed("Restarting bot core..."))
        await self.bot.close()
        subprocess.Popen([sys.executable] + sys.argv)
        os._exit(0)

    @commands.group(name="admin", aliases=["admins"], invoke_without_command=True)
    async def admin(self, ctx: commands.Context):
        await ctx.send(embed=info_embed(f"Usage: `{ctx.prefix}admin <add|remove|list> [user]`"))

    @admin.command(name="add")
    async def admin_add(self, ctx: commands.Context, *, user: discord.User):
        if not await self.bot.is_owner(ctx.author):
            return await ctx.send(embed=error_embed("Only bot owners can add administrators."))

        uid_str = str(user.id)
        current_admins = [str(x) for x in SETTINGS.get("admin_ids", []) if str(x).isdigit()]
        if uid_str in current_admins:
            return await ctx.send(embed=info_embed(f"{user.mention} is already a bot administrator."))

        current_admins.append(uid_str)
        SETTINGS["admin_ids"] = current_admins
        self.bot.admin_ids.add(user.id)
        save_settings(SETTINGS)
        await ctx.send(embed=success_embed(f"Added {user.mention} (`{user.id}`) as bot administrator."))

    @admin.command(name="remove", aliases=["rem", "del"])
    async def admin_remove(self, ctx: commands.Context, *, user: discord.User):
        if not await self.bot.is_owner(ctx.author):
            return await ctx.send(embed=error_embed("Only bot owners can remove administrators."))

        uid_str = str(user.id)
        current_admins = [str(x) for x in SETTINGS.get("admin_ids", []) if str(x).isdigit()]
        if uid_str not in current_admins:
            return await ctx.send(embed=error_embed(f"{user.mention} is not in the bot administrator list."))

        current_admins = [x for x in current_admins if x != uid_str]
        SETTINGS["admin_ids"] = current_admins
        self.bot.admin_ids.discard(user.id)
        save_settings(SETTINGS)
        await ctx.send(embed=success_embed(f"Removed {user.mention} (`{user.id}`) from bot administrators."))

    @admin.command(name="list")
    async def admin_list(self, ctx: commands.Context):
        admin_ids = [int(x) for x in SETTINGS.get("admin_ids", []) if str(x).isdigit()]
        owner_ids = [int(x) for x in SETTINGS.get("owner_ids", []) if str(x).isdigit()]

        embed = build_embed(title="Bot Staff Team")

        owner_lines = []
        for oid in owner_ids:
            u = self.bot.get_user(oid)
            name = str(u) if u else f"User ID: {oid}"
            owner_lines.append(f"• `{oid}` - **{name}** (Owner)")

        admin_lines = []
        for aid in admin_ids:
            u = self.bot.get_user(aid)
            name = str(u) if u else f"User ID: {aid}"
            admin_lines.append(f"• `{aid}` - **{name}** (Admin)")

        desc = ""
        if owner_lines:
            desc += "**Bot Owners:**\n" + "\n".join(owner_lines) + "\n\n"
        if admin_lines:
            desc += "**Bot Admins:**\n" + "\n".join(admin_lines)
        elif not admin_lines and not owner_lines:
            desc = "No bot staff configured."
        else:
            desc += "**Bot Admins:**\nNo admins added yet."

        embed.description = desc
        await ctx.send(embed=embed)

    @commands.group(name="noprefix", aliases=["nopref"], invoke_without_command=True)
    async def noprefix(self, ctx: commands.Context):
        await ctx.send(embed=info_embed(f"Usage: `{ctx.prefix}noprefix <add|remove|list> [user] [duration]`"))

    @noprefix.command(name="add")
    async def noprefix_add(self, ctx: commands.Context, user: discord.User, *, duration: str = None):
        if duration:
            parsed = parse_duration_string(duration)
            if not parsed:
                return await ctx.send(embed=error_embed("Invalid duration provided. Choose: `1 week`, `1 month`, `3 months`, `6 months`, or `lifetime`."))
            dur_key, expires_at, dur_label = parsed
            await self.bot.db.add_noprefix_user(
                user_id=user.id,
                duration_type=dur_key,
                expires_at=expires_at,
                added_by=ctx.author.id
            )
            exp_str = format_expiration(expires_at)
            
            log_embed = build_embed(title="No-Prefix Granted")
            log_embed.description = f"**User:** {user.mention} (`{user.id}`)\n**Duration:** `{dur_label}`\n**Expires:** {exp_str}\n**Authorized By:** {ctx.author.mention} (`{ctx.author.id}`)"
            await send_log("Noprefix-add", embed=log_embed)

            return await ctx.send(embed=success_embed(f"Added {user.mention} (`{user.id}`) to no-prefix list.\n**Duration:** `{dur_label}`\n**Expires:** {exp_str}"))

        prompt_embed = build_embed(
            title="Select No-Prefix Duration",
            description=f"Select the subscription duration for {user.mention} (`{user.id}`)."
        )

        async def on_duration_selected(interaction: discord.Interaction, selected_value: str):
            parsed_inner = parse_duration_string(selected_value)
            dur_key_inner, expires_at_inner, dur_label_inner = parsed_inner
            await self.bot.db.add_noprefix_user(
                user_id=user.id,
                duration_type=dur_key_inner,
                expires_at=expires_at_inner,
                added_by=ctx.author.id
            )
            exp_str_inner = format_expiration(expires_at_inner)

            log_embed = build_embed(title="No-Prefix Granted")
            log_embed.description = f"**User:** {user.mention} (`{user.id}`)\n**Duration:** `{dur_label_inner}`\n**Expires:** {exp_str_inner}\n**Authorized By:** {ctx.author.mention} (`{ctx.author.id}`)"
            await send_log("Noprefix-add", embed=log_embed)

            resp_embed = success_embed(
                f"Added {user.mention} (`{user.id}`) to no-prefix list.\n"
                f"**Duration:** `{dur_label_inner}`\n"
                f"**Expires:** {exp_str_inner}"
            )
            await interaction.response.edit_message(embed=resp_embed, view=None)

        view = DurationSelectView(
            requester=ctx.author,
            target_name=user.name,
            on_select_callback=on_duration_selected
        )
        view.message = await ctx.send(embed=prompt_embed, view=view)

    @noprefix.command(name="remove", aliases=["rem", "del"])
    async def noprefix_remove(self, ctx: commands.Context, *, user: discord.User):
        await self.bot.db.remove_noprefix_user(user.id)

        log_embed = build_embed(title="No-Prefix Removed")
        log_embed.description = f"**User:** {user.mention} (`{user.id}`)\n**Authorized By:** {ctx.author.mention} (`{ctx.author.id}`)"
        await send_log("Noprefix-removed", embed=log_embed)

        await ctx.send(embed=success_embed(f"Removed {user.mention} from no-prefix list"))

    @noprefix.command(name="list")
    async def noprefix_list(self, ctx: commands.Context):
        all_data = self.bot.db.get_all_noprefix_data()
        if not all_data:
            await ctx.send(embed=info_embed("No users in no-prefix list"))
            return

        now = time.time()
        active_items = [
            item for item in all_data.values()
            if item.get("expires_at") is None or item["expires_at"] > now
        ]
        if not active_items:
            await ctx.send(embed=info_embed("No active users in no-prefix list"))
            return

        categorized = {
            "all": active_items,
            "1w": [x for x in active_items if x.get("duration_type") == "1w"],
            "1m": [x for x in active_items if x.get("duration_type") == "1m"],
            "3m": [x for x in active_items if x.get("duration_type") == "3m"],
            "6m": [x for x in active_items if x.get("duration_type") == "6m"],
            "lifetime": [x for x in active_items if x.get("duration_type") == "lifetime"]
        }

        chunk_size = 8

        def build_pages_for_filter(items: list, filter_name: str) -> list[discord.Embed]:
            if not items:
                empty_embed = build_embed(title="No-Prefix Users")
                empty_embed.description = "No users found in this duration filter."
                return [empty_embed]

            chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
            pages_list = []
            dur_labels = {
                "all": "All Durations",
                "1w": "1 Week",
                "1m": "1 Month",
                "3m": "3 Months",
                "6m": "6 Months",
                "lifetime": "Lifetime"
            }
            filter_title = dur_labels.get(filter_name, filter_name.title())

            for idx, chunk in enumerate(chunks):
                embed = build_embed(title="No-Prefix Subscribers")
                lines = []
                for item in chunk:
                    uid = item["user_id"]
                    user = self.bot.get_user(uid)
                    name_str = f"**{user.name}**" if user else f"`{uid}`"
                    dur_type = item.get("duration_type", "lifetime")
                    dur_display = {
                        "1w": "1 Week",
                        "1m": "1 Month",
                        "3m": "3 Months",
                        "6m": "6 Months",
                        "lifetime": "Lifetime"
                    }.get(dur_type, dur_type.title())
                    exp_val = item.get("expires_at")
                    exp_display = format_expiration(exp_val)
                    lines.append(f"• {name_str} (`{uid}`)\n  └ Plan: `{dur_display}` | Expiry: {exp_display}")

                embed.description = f"**Filter:** `{filter_title}` | **Total:** `{len(items)}`\n\n" + "\n\n".join(lines)
                embed.set_footer(text=f"Total Users: {len(items)}")
                pages_list.append(embed)
            return pages_list

        paginator = FilteredPaginator(
            author=ctx.author,
            categorized_data=categorized,
            page_generator_func=build_pages_for_filter,
            filter_placeholder="Filter no-prefix by duration..."
        )
        await paginator.send(ctx)

    @commands.group(name="server", aliases=["servers"], invoke_without_command=True)
    async def server(self, ctx: commands.Context):
        await ctx.send(embed=info_embed(f"Usage: `{ctx.prefix}server list`"))

    @server.command(name="list")
    async def server_list(self, ctx: commands.Context):
        guilds = sorted(self.bot.guilds, key=lambda g: g.member_count or 0, reverse=True)
        if not guilds:
            await ctx.send(embed=info_embed("Bot is not in any servers"))
            return

        chunk_size = 10
        chunks = [guilds[i:i + chunk_size] for i in range(0, len(guilds), chunk_size)]
        pages = []

        for chunk in chunks:
            embed = build_embed(title="Server List")
            lines = []
            for g in chunk:
                lines.append(f"• **{g.name}** (`{g.id}`) - {g.member_count} members")
            embed.description = "\n".join(lines)
            pages.append(embed)

        paginator = Paginator(author=ctx.author, pages=pages)
        await paginator.send(ctx)

    @commands.command(name="slist")
    async def slist(self, ctx: commands.Context):
        await self.server_list(ctx)

    @commands.group(name="development", aliases=["dvm", "dev"], invoke_without_command=True)
    async def development(self, ctx: commands.Context):
        if not await self.bot.is_owner(ctx.author):
            return await ctx.send(embed=error_embed("Only bot owners can modify development mode."))
        await ctx.send(embed=info_embed(f"Usage: `{ctx.prefix}development mode <on|off>`"))

    @development.group(name="mode", invoke_without_command=True)
    async def dev_mode(self, ctx: commands.Context):
        if not await self.bot.is_owner(ctx.author):
            return await ctx.send(embed=error_embed("Only bot owners can modify development mode."))
        state = "enabled" if self.bot.db.development_mode else "disabled"
        await ctx.send(embed=info_embed(f"Development mode is currently **{state}**"))

    @dev_mode.command(name="on")
    async def dev_mode_on(self, ctx: commands.Context):
        if not await self.bot.is_owner(ctx.author):
            return await ctx.send(embed=error_embed("Only bot owners can modify development mode."))
        await self.bot.db.set_development_mode(True)
        await ctx.send(embed=success_embed("Development mode enabled"))

    @dev_mode.command(name="off")
    async def dev_mode_off(self, ctx: commands.Context):
        if not await self.bot.is_owner(ctx.author):
            return await ctx.send(embed=error_embed("Only bot owners can modify development mode."))
        await self.bot.db.set_development_mode(False)
        await ctx.send(embed=success_embed("Development mode disabled"))

    @development.command(name="on")
    async def dev_on_alias(self, ctx: commands.Context):
        await self.dev_mode_on(ctx)

    @development.command(name="off")
    async def dev_off_alias(self, ctx: commands.Context):
        await self.dev_mode_off(ctx)

    @commands.group(name="premium", invoke_without_command=True)
    async def premium(self, ctx: commands.Context):
        await ctx.send(embed=info_embed(f"Usage: `{ctx.prefix}premium guild <add|remove|list> [guild_id] [duration]`"))

    @premium.group(name="guild", invoke_without_command=True)
    async def premium_guild(self, ctx: commands.Context):
        await ctx.send(embed=info_embed(f"Usage: `{ctx.prefix}premium guild <add|remove|list> [guild_id] [duration]`"))

    @premium_guild.command(name="add")
    async def premium_guild_add(self, ctx: commands.Context, guild_id: int, *, duration: str = None):
        target_guild = self.bot.get_guild(guild_id)
        guild_name = target_guild.name if target_guild else f"Server ({guild_id})"

        if duration:
            parsed = parse_duration_string(duration)
            if not parsed:
                return await ctx.send(embed=error_embed("Invalid duration provided. Choose: `1 week`, `1 month`, `3 months`, `6 months`, or `lifetime`."))
            dur_key, expires_at, dur_label = parsed
            await self.bot.db.add_premium_guild(
                guild_id=guild_id,
                duration_type=dur_key,
                expires_at=expires_at,
                added_by=ctx.author.id
            )
            exp_str = format_expiration(expires_at)

            log_embed = build_embed(title="Premium Guild Added")
            log_embed.description = f"**Guild:** **{guild_name}** (`{guild_id}`)\n**Duration:** `{dur_label}`\n**Expires:** {exp_str}\n**Authorized By:** {ctx.author.mention} (`{ctx.author.id}`)"
            await send_log("Premium-Guild-Add", embed=log_embed)

            return await ctx.send(embed=success_embed(f"Added **{guild_name}** (`{guild_id}`) to premium servers.\n**Duration:** `{dur_label}`\n**Expires:** {exp_str}"))

        prompt_embed = build_embed(
            title="Select Premium Guild Duration",
            description=f"Select the premium subscription duration for **{guild_name}** (`{guild_id}`)."
        )

        async def on_duration_selected(interaction: discord.Interaction, selected_value: str):
            parsed_inner = parse_duration_string(selected_value)
            dur_key_inner, expires_at_inner, dur_label_inner = parsed_inner
            await self.bot.db.add_premium_guild(
                guild_id=guild_id,
                duration_type=dur_key_inner,
                expires_at=expires_at_inner,
                added_by=ctx.author.id
            )
            exp_str_inner = format_expiration(expires_at_inner)

            log_embed = build_embed(title="Premium Guild Added")
            log_embed.description = f"**Guild:** **{guild_name}** (`{guild_id}`)\n**Duration:** `{dur_label_inner}`\n**Expires:** {exp_str_inner}\n**Authorized By:** {ctx.author.mention} (`{ctx.author.id}`)"
            await send_log("Premium-Guild-Add", embed=log_embed)

            resp_embed = success_embed(
                f"Added **{guild_name}** (`{guild_id}`) to premium servers.\n"
                f"**Duration:** `{dur_label_inner}`\n"
                f"**Expires:** {exp_str_inner}"
            )
            await interaction.response.edit_message(embed=resp_embed, view=None)

        view = DurationSelectView(
            requester=ctx.author,
            target_name=guild_name,
            on_select_callback=on_duration_selected
        )
        view.message = await ctx.send(embed=prompt_embed, view=view)

    @premium_guild.command(name="remove", aliases=["rem", "del"])
    async def premium_guild_remove(self, ctx: commands.Context, guild_id: int):
        await self.bot.db.remove_premium_guild(guild_id)
        target_guild = self.bot.get_guild(guild_id)
        guild_name = target_guild.name if target_guild else f"`{guild_id}`"

        log_embed = build_embed(title="Premium Guild Removed")
        log_embed.description = f"**Guild:** **{guild_name}** (`{guild_id}`)\n**Authorized By:** {ctx.author.mention} (`{ctx.author.id}`)"
        await send_log("Premium-Guild-Removed", embed=log_embed)

        await ctx.send(embed=success_embed(f"Removed server **{guild_name}** (`{guild_id}`) from premium list"))

    @premium_guild.command(name="list")
    async def premium_guild_list(self, ctx: commands.Context):
        all_data = self.bot.db.get_all_premium_guilds_data()
        if not all_data:
            await ctx.send(embed=info_embed("No premium guilds registered"))
            return

        now = time.time()
        active_items = [
            item for item in all_data.values()
            if item.get("expires_at") is None or item["expires_at"] > now
        ]
        if not active_items:
            await ctx.send(embed=info_embed("No active premium guilds found"))
            return

        categorized = {
            "all": active_items,
            "1w": [x for x in active_items if x.get("duration_type") == "1w"],
            "1m": [x for x in active_items if x.get("duration_type") == "1m"],
            "3m": [x for x in active_items if x.get("duration_type") == "3m"],
            "6m": [x for x in active_items if x.get("duration_type") == "6m"],
            "lifetime": [x for x in active_items if x.get("duration_type") == "lifetime"]
        }

        chunk_size = 8

        def build_pages_for_filter(items: list, filter_name: str) -> list[discord.Embed]:
            if not items:
                empty_embed = build_embed(title="Premium Guilds")
                empty_embed.description = "No servers found in this duration filter."
                return [empty_embed]

            chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
            pages_list = []
            dur_labels = {
                "all": "All Durations",
                "1w": "1 Week",
                "1m": "1 Month",
                "3m": "3 Months",
                "6m": "6 Months",
                "lifetime": "Lifetime"
            }
            filter_title = dur_labels.get(filter_name, filter_name.title())

            for idx, chunk in enumerate(chunks):
                embed = build_embed(title="Premium Guilds")
                lines = []
                for item in chunk:
                    gid = item["guild_id"]
                    g = self.bot.get_guild(gid)
                    name_str = f"**{g.name}**" if g else f"Server `{gid}`"
                    member_count_str = f"({g.member_count} members)" if g and g.member_count else ""
                    dur_type = item.get("duration_type", "lifetime")
                    dur_display = {
                        "1w": "1 Week",
                        "1m": "1 Month",
                        "3m": "3 Months",
                        "6m": "6 Months",
                        "lifetime": "Lifetime"
                    }.get(dur_type, dur_type.title())
                    exp_val = item.get("expires_at")
                    exp_display = format_expiration(exp_val)
                    lines.append(f"• {name_str} `{gid}` {member_count_str}\n  └ Plan: `{dur_display}` | Expiry: {exp_display}")

                embed.description = f"**Filter:** `{filter_title}` | **Total:** `{len(items)}`\n\n" + "\n\n".join(lines)
                embed.set_footer(text=f"Total Premium Servers: {len(items)}")
                pages_list.append(embed)
            return pages_list

        paginator = FilteredPaginator(
            author=ctx.author,
            categorized_data=categorized,
            page_generator_func=build_pages_for_filter,
            filter_placeholder="Filter premium servers by duration..."
        )
        await paginator.send(ctx)

async def setup(bot):
    await bot.add_cog(Owner(bot))


# @Author: LynxModz
 #   + Discord: ifwlynx_
 #   + Community: https://dsc.gg/lynx-modz
 #   + Eve Bot source is free for everyone. Paid distribution is not allowed.