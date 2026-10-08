import os
import json
import time
import asyncio
import aiohttp
import discord

class WebhookLogger:
    def __init__(self, config_path="config/logging.json"):
        self.config_path = config_path
        self.queue = asyncio.Queue(maxsize=1000)
        self.session = None
        self.worker_task = None
        self.rate_limited_until = {}

    def _get_webhook_url(self, key: str) -> str | None:
        try:
            if not os.path.exists(self.config_path):
                return None
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            url = data.get(key, "").strip()
            return url if url.startswith("http") else None
        except Exception:
            return None

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def start(self):
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._process_queue())

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
        if self.worker_task:
            self.worker_task.cancel()

    async def log(self, event_key: str, embed: discord.Embed = None, content: str = None):
        webhook_url = self._get_webhook_url(event_key)
        if not webhook_url:
            return

        payload = {}
        if content:
            payload["content"] = content
        if embed:
            payload["embeds"] = [embed.to_dict()]

        if not payload:
            return

        try:
            self.queue.put_nowait((webhook_url, payload))
        except asyncio.QueueFull:
            pass

    async def _process_queue(self):
        while True:
            try:
                webhook_url, payload = await self.queue.get()
                await self._ensure_session()

                now = time.time()
                blocked_until = self.rate_limited_until.get(webhook_url, 0)
                if now < blocked_until:
                    await asyncio.sleep(blocked_until - now)

                async with self.session.post(webhook_url, json=payload) as resp:
                    if resp.status == 429:
                        try:
                            data = await resp.json()
                            retry_after = float(data.get("retry_after", 1.0))
                        except Exception:
                            retry_after = 2.0
                        self.rate_limited_until[webhook_url] = time.time() + retry_after
                        await asyncio.sleep(retry_after)
                        try:
                            self.queue.put_nowait((webhook_url, payload))
                        except asyncio.QueueFull:
                            pass
                    elif resp.status >= 500:
                        await asyncio.sleep(1.0)
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.5)

logger = WebhookLogger()

async def send_log(event_key: str, embed: discord.Embed = None, content: str = None):
    await logger.log(event_key, embed=embed, content=content)

# @Author: LynxModz
 #   + Discord: ifwlynx_
 #   + Community: https://dsc.gg/lynx-modz
 #   + Eve Bot source is free for everyone. Paid distribution is not allowed.