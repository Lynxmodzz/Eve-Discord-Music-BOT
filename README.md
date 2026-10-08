<div align="center">

  <h1>Eve Music</h1>
  <p>A simple, fast, and feature-rich Discord music bot built with discord.py and Wavelink.</p>

  <p>
    <a href="https://github.com/Rapptz/discord.py"><img src="https://img.shields.io/badge/discord.py-v2.3.2+-5865F2?style=flat-square&logo=python&logoColor=white" alt="discord.py"></a>
    <a href="https://github.com/PythonistaGuild/Wavelink"><img src="https://img.shields.io/badge/Wavelink-v3.5.0+-1DB954?style=flat-square&logo=spotify&logoColor=white" alt="Wavelink"></a>
    <a href="https://github.com/omnilib/aiosqlite"><img src="https://img.shields.io/badge/aiosqlite-SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white" alt="aiosqlite"></a>
    <a href="https://dsc.gg/lynx-modz"><img src="https://img.shields.io/badge/Discord-Support%20Server-5865F2?style=flat-square&logo=discord&logoColor=white" alt="Support Server"></a>
  </p>

  <p>
    <a href="#features">Features</a> •
    <a href="#commands">Commands</a> •
    <a href="#installation">Installation</a> •
    <a href="#configuration">Configuration</a> •
    <a href="#support">Support</a>
  </p>

</div>

---

## Features

- **Music Playback**: Play audio from Spotify, YouTube, SoundCloud, and direct URLs with zero delay.
- **Button Controls**: Interactive player buttons (pause, resume, skip, stop, previous).
- **24/7 Mode**: Keep the bot inside your voice channel constantly.
- **Autoplay**: Automatically finds and plays similar songs when the queue ends.
- **Custom Playlists**: Save and load your own personal playlists directly in Discord.
- **Custom Prefix & No-Prefix**: Support for custom server prefixes and user/server no-prefix mode.
- **Profile Cards**: Built-in profile card generator displaying user stats and badges.

---

## Commands

### Music Commands

| Command | Aliases | Description |
|---|---|---|
| `?play <song/URL>` | `?p` | Play a song or playlist |
| `?pause` | — | Pause the current song |
| `?resume` | — | Resume playback |
| `?skip` | `?s` | Skip the current song |
| `?previous` | `?prev` | Play the previous song |
| `?stop` | — | Stop music and leave the voice channel |
| `?queue` | `?q` | Show the current song queue |
| `?nowplaying` | `?np` | Show current song information |
| `?seek <time>` | — | Jump to a timestamp (e.g. `?seek 1:30`) |
| `?volume <1-100>` | `?vol` | Change player volume |
| `?loop <track/queue/off>` | — | Loop current track or queue |
| `?autoplay` | `?ap` | Toggle automatic song recommendations |
| `?shuffle` | — | Shuffle the queue |
| `?replay` | — | Replay the current song from the start |
| `?clearqueue` | `?clear_queue` | Remove all songs from the queue |
| `?247` | — | Toggle 24/7 stay-in-voice mode |
| `?playlist` | `?pl` | Manage personal saved playlists |

### General Commands

| Command | Aliases | Description |
|---|---|---|
| `?help` | — | Open the help menu |
| `?ping` | — | Check bot latency and node status |
| `?stats` | — | View bot and system stats |
| `?profile [@user]` | `?whois` | View a user's generated profile card |
| `?avatar [@user]` | — | View a user's avatar |
| `?banner [@user]` | — | View a user's banner |
| `?setprefix <prefix>` | `?prefix` | Change bot prefix for the server |
| `?guildnoprefix` | `?gnoprefix` | Toggle no-prefix mode for the server |
| `?settings` | `?config` | View current server settings |

### Owner Commands

| Command | Description |
|---|---|
| `?reload <cog>` | Reload a cog file without restart |
| `?restart` | Restart the bot |
| `?noprefix <add/remove> <user>` | Manage global no-prefix users |
| `?admin <add/remove> <user>` | Manage bot administrators |
| `?premium <add/remove> <user>` | Manage premium users |
| `?slist` | View list of servers the bot is in |

---

## Installation

### 1. Requirements
- Python 3.10 or higher
- A Discord Bot Token
- A Lavalink v4 server

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Setup Environment
Rename `example.env` to `.env` and add your bot token:
```env
TOKEN=your_bot_token_here
```

### 4. Run the Bot
```bash
python main.py
```

---

## Configuration

### Lavalink Nodes (`config/lava_nodes.json`)
Set your Lavalink server details in `config/lava_nodes.json`:
```json
[
    {
        "identifier": "Main-Node",
        "uri": "http://lavalink.serenetia.com:80",
        "password": "https://dsc.gg/ajidevserver",
        "secure": false
    }
]
```

### Bot Settings (`config/settings.json`)
Set your Owner ID and default settings in `config/settings.json`:
```json
{
    "bot-name": "Eve",
    "default_prefix": "?",
    "owner_ids": [
        "YOUR_DISCORD_USER_ID"
    ],
    "admin_ids": [],
    "development_server_id": "",
    "theme_color": "#FFFFFF",
    "default_volume": 80,
    "activity_name": "music | ?help",
    "activity_type": "listening",
    "support_server": "https://dsc.gg/lynx-modz"
}
```

---

## Support

If you need help or have questions, join the support server:
- **Discord**: [dsc.gg/lynx-modz](https://dsc.gg/lynx-modz)
