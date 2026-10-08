import discord
from utils.ui import get_emoji, error_embed

class Paginator(discord.ui.View):
    def __init__(self, author: discord.User | discord.Member, pages: list[discord.Embed], timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.author = author
        self.pages = pages
        self.current_page = 0
        self.message = None
        self._update_buttons()

    def _update_buttons(self):
        self.clear_items()
        total_pages = len(self.pages)
        if total_pages <= 1:
            return

        prev_emoji = get_emoji("previous")
        prev_btn = discord.ui.Button(
            emoji=prev_emoji if prev_emoji else None,
            label="Prev" if not prev_emoji else None,
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page == 0)
        )
        prev_btn.callback = self.prev_callback
        self.add_item(prev_btn)

        stop_emoji = get_emoji("stop")
        stop_btn = discord.ui.Button(
            emoji=stop_emoji if stop_emoji else None,
            label="Stop" if not stop_emoji else None,
            style=discord.ButtonStyle.danger
        )
        stop_btn.callback = self.stop_callback
        self.add_item(stop_btn)

        skip_emoji = get_emoji("skip")
        next_btn = discord.ui.Button(
            emoji=skip_emoji if skip_emoji else None,
            label="Next" if not skip_emoji else None,
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page >= total_pages - 1)
        )
        next_btn.callback = self.next_callback
        self.add_item(next_btn)

    def get_current_embed(self) -> discord.Embed:
        if not self.pages:
            return discord.Embed(description="No pages available")
        if self.current_page >= len(self.pages):
            self.current_page = max(0, len(self.pages) - 1)
        embed = self.pages[self.current_page]
        total_pages = len(self.pages)
        if total_pages > 1:
            page_str = f"Page {self.current_page + 1} of {total_pages}"
            icon_url = None
            base_text = ""
            if embed.footer:
                icon_url = embed.footer.icon_url
                if embed.footer.text:
                    parts = [p for p in embed.footer.text.split(" • ") if not p.startswith("Page ")]
                    base_text = " • ".join(parts)
            final_text = f"{base_text} • {page_str}" if base_text else page_str
            embed.set_footer(text=final_text, icon_url=icon_url)
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                embed=error_embed("You cannot control this paginator"),
                ephemeral=True
            )
            return False
        return True

    async def prev_callback(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.get_current_embed(), view=self)

    async def next_callback(self, interaction: discord.Interaction):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.get_current_embed(), view=self)

    async def stop_callback(self, interaction: discord.Interaction):
        self.stop()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

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
        if len(self.pages) <= 1:
            self.message = await ctx.send(embed=embed)
        else:
            self.message = await ctx.send(embed=embed, view=self)
        return self.message

class FilteredPaginator(discord.ui.View):
    def __init__(self, author: discord.User | discord.Member, categorized_data: dict[str, list], page_generator_func, timeout: float = 90.0, filter_placeholder: str = "Filter by duration..."):
        super().__init__(timeout=timeout)
        self.author = author
        self.categorized_data = categorized_data
        self.page_generator_func = page_generator_func
        self.filter_placeholder = filter_placeholder
        self.current_filter = "all"
        self.current_page = 0
        self.pages = []
        self.message = None
        self._rebuild_pages()
        self._rebuild_components()

    def _rebuild_pages(self):
        items = self.categorized_data.get(self.current_filter, [])
        self.pages = self.page_generator_func(items, self.current_filter)
        if not self.pages:
            fallback = discord.Embed(description="No items found for this filter.")
            self.pages = [fallback]
        if self.current_page >= len(self.pages):
            self.current_page = 0

    def _rebuild_components(self):
        self.clear_items()
        
        filter_options = [
            discord.SelectOption(label="All Durations", value="all", description=f"Total: {len(self.categorized_data.get('all', []))}", default=(self.current_filter == "all")),
            discord.SelectOption(label="1 Week", value="1w", description=f"Total: {len(self.categorized_data.get('1w', []))}", default=(self.current_filter == "1w")),
            discord.SelectOption(label="1 Month", value="1m", description=f"Total: {len(self.categorized_data.get('1m', []))}", default=(self.current_filter == "1m")),
            discord.SelectOption(label="3 Months", value="3m", description=f"Total: {len(self.categorized_data.get('3m', []))}", default=(self.current_filter == "3m")),
            discord.SelectOption(label="6 Months", value="6m", description=f"Total: {len(self.categorized_data.get('6m', []))}", default=(self.current_filter == "6m")),
            discord.SelectOption(label="Lifetime", value="lifetime", description=f"Total: {len(self.categorized_data.get('lifetime', []))}", default=(self.current_filter == "lifetime"))
        ]
        
        select_menu = discord.ui.Select(
            placeholder=self.filter_placeholder,
            options=filter_options,
            row=0
        )
        select_menu.callback = self.filter_callback
        self.add_item(select_menu)

        total_pages = len(self.pages)
        if total_pages > 1:
            prev_emoji = get_emoji("previous")
            prev_btn = discord.ui.Button(
                emoji=prev_emoji if prev_emoji else None,
                label="Prev" if not prev_emoji else None,
                style=discord.ButtonStyle.secondary,
                disabled=(self.current_page == 0),
                row=1
            )
            prev_btn.callback = self.prev_callback
            self.add_item(prev_btn)

            stop_emoji = get_emoji("stop")
            stop_btn = discord.ui.Button(
                emoji=stop_emoji if stop_emoji else None,
                label="Stop" if not stop_emoji else None,
                style=discord.ButtonStyle.danger,
                row=1
            )
            stop_btn.callback = self.stop_callback
            self.add_item(stop_btn)

            skip_emoji = get_emoji("skip")
            next_btn = discord.ui.Button(
                emoji=skip_emoji if skip_emoji else None,
                label="Next" if not skip_emoji else None,
                style=discord.ButtonStyle.secondary,
                disabled=(self.current_page >= total_pages - 1),
                row=1
            )
            next_btn.callback = self.next_callback
            self.add_item(next_btn)

    def get_current_embed(self) -> discord.Embed:
        if not self.pages:
            return discord.Embed(description="No entries found")
        if self.current_page >= len(self.pages):
            self.current_page = max(0, len(self.pages) - 1)
        embed = self.pages[self.current_page]
        total_pages = len(self.pages)
        if total_pages > 1:
            page_str = f"Page {self.current_page + 1} of {total_pages}"
            icon_url = None
            base_text = ""
            if embed.footer:
                icon_url = embed.footer.icon_url
                if embed.footer.text:
                    parts = [p for p in embed.footer.text.split(" • ") if not p.startswith("Page ")]
                    base_text = " • ".join(parts)
            final_text = f"{base_text} • {page_str}" if base_text else page_str
            embed.set_footer(text=final_text, icon_url=icon_url)
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                embed=error_embed("You cannot control this paginator"),
                ephemeral=True
            )
            return False
        return True

    async def filter_callback(self, interaction: discord.Interaction):
        selected = interaction.data["values"][0]
        self.current_filter = selected
        self.current_page = 0
        self._rebuild_pages()
        self._rebuild_components()
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)

    async def prev_callback(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self._rebuild_components()
            await interaction.response.edit_message(embed=self.get_current_embed(), view=self)

    async def next_callback(self, interaction: discord.Interaction):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self._rebuild_components()
            await interaction.response.edit_message(embed=self.get_current_embed(), view=self)

    async def stop_callback(self, interaction: discord.Interaction):
        self.stop()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

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
        self.message = await ctx.send(embed=embed, view=self)
        return self.message


# @Author: LynxModz
 #   + Discord: ifwlynx_
 #   + Community: https://dsc.gg/lynx-modz
 #   + Eve Bot source is free for everyone. Paid distribution is not allowed.