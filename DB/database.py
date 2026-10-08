import os
import time
import aiosqlite

class Database:
    def __init__(self, db_path="DB/eve.db"):
        self.db_path = db_path
        self.noprefix_users = {}
        self.premium_guilds = {}
        self.guild_settings = {}
        self.development_mode = False

    async def initialize(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS noprefix_users (
                    user_id INTEGER PRIMARY KEY,
                    duration_type TEXT DEFAULT 'lifetime',
                    expires_at REAL,
                    added_at TEXT,
                    added_by INTEGER
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS premium_guilds (
                    guild_id INTEGER PRIMARY KEY,
                    duration_type TEXT DEFAULT 'lifetime',
                    expires_at REAL,
                    added_at TEXT,
                    added_by INTEGER
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    prefix TEXT,
                    is_247 INTEGER DEFAULT 0,
                    voice_channel_id INTEGER DEFAULT 0,
                    text_channel_id INTEGER DEFAULT 0,
                    guild_noprefix INTEGER DEFAULT 0
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    uri TEXT NOT NULL,
                    author TEXT,
                    length INTEGER DEFAULT 0,
                    added_at TEXT
                )
                """
            )

            async with db.execute("PRAGMA table_info(noprefix_users)") as cursor:
                np_cols = {row[1] for row in await cursor.fetchall()}
            if "duration_type" not in np_cols:
                await db.execute("ALTER TABLE noprefix_users ADD COLUMN duration_type TEXT")
            if "expires_at" not in np_cols:
                await db.execute("ALTER TABLE noprefix_users ADD COLUMN expires_at REAL")
            if "added_at" not in np_cols:
                await db.execute("ALTER TABLE noprefix_users ADD COLUMN added_at TEXT")
            if "added_by" not in np_cols:
                await db.execute("ALTER TABLE noprefix_users ADD COLUMN added_by INTEGER")

            async with db.execute("PRAGMA table_info(premium_guilds)") as cursor:
                pg_cols = {row[1] for row in await cursor.fetchall()}
            if "duration_type" not in pg_cols:
                await db.execute("ALTER TABLE premium_guilds ADD COLUMN duration_type TEXT")
            if "expires_at" not in pg_cols:
                await db.execute("ALTER TABLE premium_guilds ADD COLUMN expires_at REAL")
            if "added_at" not in pg_cols:
                await db.execute("ALTER TABLE premium_guilds ADD COLUMN added_at TEXT")
            if "added_by" not in pg_cols:
                await db.execute("ALTER TABLE premium_guilds ADD COLUMN added_by INTEGER")

            async with db.execute("PRAGMA table_info(guild_settings)") as cursor:
                gs_cols = {row[1] for row in await cursor.fetchall()}
            if "guild_noprefix" not in gs_cols:
                await db.execute("ALTER TABLE guild_settings ADD COLUMN guild_noprefix INTEGER DEFAULT 0")

            await db.commit()
        await self.load_cache()

    async def load_cache(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id, duration_type, expires_at, added_at, added_by FROM noprefix_users") as cursor:
                rows = await cursor.fetchall()
                self.noprefix_users = {
                    row[0]: {
                        "user_id": row[0],
                        "duration_type": row[1] or "lifetime",
                        "expires_at": row[2],
                        "added_at": row[3],
                        "added_by": row[4]
                    }
                    for row in rows
                }

            async with db.execute("SELECT guild_id, duration_type, expires_at, added_at, added_by FROM premium_guilds") as cursor:
                rows = await cursor.fetchall()
                self.premium_guilds = {
                    row[0]: {
                        "guild_id": row[0],
                        "duration_type": row[1] or "lifetime",
                        "expires_at": row[2],
                        "added_at": row[3],
                        "added_by": row[4]
                    }
                    for row in rows
                }

            async with db.execute("SELECT guild_id, prefix, is_247, voice_channel_id, text_channel_id, guild_noprefix FROM guild_settings") as cursor:
                rows = await cursor.fetchall()
                self.guild_settings = {
                    row[0]: {
                        "prefix": row[1],
                        "is_247": bool(row[2]),
                        "voice_channel_id": row[3],
                        "text_channel_id": row[4],
                        "guild_noprefix": bool(row[5]) if len(row) > 5 and row[5] is not None else False
                    }
                    for row in rows
                }

            async with db.execute("SELECT key, value FROM bot_settings WHERE key = 'development_mode'") as cursor:
                row = await cursor.fetchone()
                self.development_mode = (row[1] == "1") if row else False

    def is_noprefix(self, user_id: int) -> bool:
        data = self.noprefix_users.get(user_id)
        if not data:
            return False
        expires_at = data.get("expires_at")
        if expires_at is not None and time.time() > expires_at:
            return False
        return True

    def get_noprefix_user(self, user_id: int) -> dict | None:
        return self.noprefix_users.get(user_id)

    def get_all_noprefix_data(self) -> dict[int, dict]:
        return dict(self.noprefix_users)

    async def add_noprefix_user(self, user_id: int, duration_type: str = "lifetime", expires_at: float | None = None, added_by: int | None = None) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO noprefix_users (user_id, duration_type, expires_at, added_at, added_by)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    duration_type = excluded.duration_type,
                    expires_at = excluded.expires_at,
                    added_at = excluded.added_at,
                    added_by = excluded.added_by
                """,
                (user_id, duration_type, expires_at, time.strftime("%Y-%m-%d %H:%M:%S"), added_by)
            )
            await db.commit()
        self.noprefix_users[user_id] = {
            "user_id": user_id,
            "duration_type": duration_type,
            "expires_at": expires_at,
            "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "added_by": added_by
        }
        return True

    async def remove_noprefix_user(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM noprefix_users WHERE user_id = ?", (user_id,))
            await db.commit()
        self.noprefix_users.pop(user_id, None)
        return True

    def is_premium_guild(self, guild_id: int) -> bool:
        data = self.premium_guilds.get(guild_id)
        if not data:
            return False
        expires_at = data.get("expires_at")
        if expires_at is not None and time.time() > expires_at:
            return False
        return True

    def get_premium_guild(self, guild_id: int) -> dict | None:
        return self.premium_guilds.get(guild_id)

    def get_all_premium_guilds_data(self) -> dict[int, dict]:
        return dict(self.premium_guilds)

    async def add_premium_guild(self, guild_id: int, duration_type: str = "lifetime", expires_at: float | None = None, added_by: int | None = None) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO premium_guilds (guild_id, duration_type, expires_at, added_at, added_by)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    duration_type = excluded.duration_type,
                    expires_at = excluded.expires_at,
                    added_at = excluded.added_at,
                    added_by = excluded.added_by
                """,
                (guild_id, duration_type, expires_at, time.strftime("%Y-%m-%d %H:%M:%S"), added_by)
            )
            await db.commit()
        self.premium_guilds[guild_id] = {
            "guild_id": guild_id,
            "duration_type": duration_type,
            "expires_at": expires_at,
            "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "added_by": added_by
        }
        return True

    async def remove_premium_guild(self, guild_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM premium_guilds WHERE guild_id = ?", (guild_id,))
            await db.commit()
        self.premium_guilds.pop(guild_id, None)
        return True

    def is_guild_noprefix_enabled(self, guild_id: int) -> bool:
        if not self.is_premium_guild(guild_id):
            return False
        settings = self.get_guild_settings(guild_id)
        return bool(settings.get("guild_noprefix", False))

    def get_guild_settings(self, guild_id: int) -> dict:
        return self.guild_settings.get(guild_id, {
            "prefix": None,
            "is_247": False,
            "voice_channel_id": 0,
            "text_channel_id": 0,
            "guild_noprefix": False
        })

    async def set_guild_prefix(self, guild_id: int, prefix: str | None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO guild_settings (guild_id, prefix)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    prefix = excluded.prefix
                """,
                (guild_id, prefix)
            )
            await db.commit()
        current = self.get_guild_settings(guild_id)
        current["prefix"] = prefix
        self.guild_settings[guild_id] = current

    async def set_guild_noprefix(self, guild_id: int, enabled: bool):
        val = 1 if enabled else 0
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO guild_settings (guild_id, guild_noprefix)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    guild_noprefix = excluded.guild_noprefix
                """,
                (guild_id, val)
            )
            await db.commit()
        current = self.get_guild_settings(guild_id)
        current["guild_noprefix"] = enabled
        self.guild_settings[guild_id] = current

    async def set_guild_247(self, guild_id: int, is_247: bool, voice_channel_id: int = 0, text_channel_id: int = 0):
        val = 1 if is_247 else 0
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO guild_settings (guild_id, is_247, voice_channel_id, text_channel_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    is_247 = excluded.is_247,
                    voice_channel_id = excluded.voice_channel_id,
                    text_channel_id = excluded.text_channel_id
                """,
                (guild_id, val, voice_channel_id, text_channel_id)
            )
            await db.commit()
        current = self.get_guild_settings(guild_id)
        current["is_247"] = is_247
        current["voice_channel_id"] = voice_channel_id
        current["text_channel_id"] = text_channel_id
        self.guild_settings[guild_id] = current

    async def set_development_mode(self, enabled: bool):
        val = "1" if enabled else "0"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO bot_settings (key, value)
                VALUES ('development_mode', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (val,)
            )
            await db.commit()
        self.development_mode = enabled

    async def cleanup_expired(self) -> tuple[int, int]:
        now = time.time()
        expired_users = [
            uid for uid, data in self.noprefix_users.items()
            if data.get("expires_at") is not None and now > data["expires_at"]
        ]
        expired_guilds = [
            gid for gid, data in self.premium_guilds.items()
            if data.get("expires_at") is not None and now > data["expires_at"]
        ]
        if expired_users or expired_guilds:
            async with aiosqlite.connect(self.db_path) as db:
                for uid in expired_users:
                    await db.execute("DELETE FROM noprefix_users WHERE user_id = ?", (uid,))
                    self.noprefix_users.pop(uid, None)
                for gid in expired_guilds:
                    await db.execute("DELETE FROM premium_guilds WHERE guild_id = ?", (gid,))
                    self.premium_guilds.pop(gid, None)
                await db.commit()
        return len(expired_users), len(expired_guilds)

    async def add_to_playlist(self, user_id: int, title: str, uri: str, author: str = "", length: int = 0) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT id FROM user_playlists WHERE user_id = ? AND uri = ?", (user_id, uri)) as cursor:
                if await cursor.fetchone():
                    return False
            await db.execute(
                "INSERT INTO user_playlists (user_id, title, uri, author, length, added_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, title, uri, author, length, time.strftime("%Y-%m-%d %H:%M:%S"))
            )
            await db.commit()
        return True

    async def get_user_playlist(self, user_id: int) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT id, title, uri, author, length FROM user_playlists WHERE user_id = ? ORDER BY id ASC",
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "title": row[1],
                        "uri": row[2],
                        "author": row[3],
                        "length": row[4]
                    }
                    for row in rows
                ]

    async def delete_from_playlist_by_position(self, user_id: int, position: int) -> dict | None:
        tracks = await self.get_user_playlist(user_id)
        if 1 <= position <= len(tracks):
            target = tracks[position - 1]
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM user_playlists WHERE id = ?", (target["id"],))
                await db.commit()
            return target
        return None

    async def clear_user_playlist(self, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM user_playlists WHERE user_id = ?", (user_id,))
            deleted_count = cursor.rowcount
            await db.commit()
        return deleted_count


# @Author: LynxModz
 #   + Discord: ifwlynx_
 #   + Community: https://dsc.gg/lynx-modz
 #   + Eve Bot source is free for everyone. Paid distribution is not allowed.