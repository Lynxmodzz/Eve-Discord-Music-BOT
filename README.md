<div align="center">

  <img src="https://media.discordapp.net/attachments/1144179659735572640/1210134958223859742/EveLogo.png?format=webp&quality=lossless" width="130" style="border-radius: 50%;" alt="Eve Music Logo" onerror="this.src='https://cdn.discordapp.com/embed/avatars/0.png'"/>

  # 🎵 Eve Music
  ### *The Next-Generation Ultra Low-Latency Discord Music Bot*

  **High-Fidelity Audio · Interactive Button Player · 24/7 Uptime · Dynamic Profile Cards**

  <br/>

  [![discord.py](https://img.shields.io/badge/discord.py-v2.3.2+-5865F2?style=for-the-badge&logo=python&logoColor=white)](https://github.com/Rapptz/discord.py)
  [![Wavelink](https://img.shields.io/badge/Wavelink-v3.5.0+-1DB954?style=for-the-badge&logo=spotify&logoColor=white)](https://github.com/PythonistaGuild/Wavelink)
  [![Lavalink](https://img.shields.io/badge/Lavalink-v4.x-red?style=for-the-badge&logo=soundcharts&logoColor=white)](https://github.com/lavalink-devs/Lavalink)
  [![aiosqlite](https://img.shields.io/badge/aiosqlite-Async%20DB-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://github.com/omnilib/aiosqlite)
  [![Rich Console](https://img.shields.io/badge/Rich-Terminal%20UI-00C853?style=for-the-badge&logo=gnubash&logoColor=white)](https://github.com/Textualize/rich)

  <br/>

  [**💬 Support Server**](https://dsc.gg/lynx-modz) • [**📖 Documentation**](#-table-of-contents) • [**⚙️ Setup Guide**](#-quick-start) • [**✨ Commands**](#-command-showcase)

</div>

---

## 📖 Table of Contents

- [🌟 Highlights](#-highlights)
- [✨ Core Features](#-core-features)
- [🎵 Command Showcase](#-command-showcase)
- [🚀 Quick Start](#-quick-start)
- [⚙️ Configuration](#-configuration)
  - [Environment Variables](#1-environment-variables-env)
  - [Lavalink Node Configuration](#2-lavalink-nodes-configlava_nodesjson)
  - [Bot Settings](#3-bot-settings-configsettingsjson)
- [🗄️ Project Architecture](#️-project-architecture)
- [👥 Contributing & Support](#-contributing--support)
- [📜 License](#-license)

---

## 🌟 Highlights

**Eve Music** is an advanced, high-performance, and feature-rich Discord music bot crafted with `discord.py 2.x` and `Wavelink v3.5+` (Lavalink v4). It is meticulously engineered for seamless lossless audio delivery, vibrant dynamic image generation, interactive UI button players, and effortless server management.

> 💎 **Crystal Clear Playback**: Lavalink v4 engine with zero stutter, auto-reconnect, and multi-source streaming (Spotify, YouTube, SoundCloud, Apple Music, Deezer, Direct HTTP).  
> 🎛️ **Interactive Controls**: Modern Discord UI components (Buttons, Select Menus, Modals) for real-time player manipulation without typing commands.  
> 🖼️ **Dynamic Canvas Engine**: Built-in Pillow rendering engine that dynamically creates aesthetic user profile cards and rich visual embeds.  
> ⚡ **Ultra Responsive**: Fully asynchronous architecture backed by `aiosqlite` with connection caching and minimal CPU overhead.

---

## ✨ Core Features

<table>
  <thead>
    <tr>
      <th width="30%">Feature</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>🎧 <b>Lossless Music Streaming</b></td>
      <td>Supports high-resolution playback with customizable volume, precise seeking, replay, and instant track buffering.</td>
    </tr>
    <tr>
      <td>🔄 <b>Autoplay & Smart Queue</b></td>
      <td>Intelligent recommendations that continue playing similar tracks automatically when your queue ends.</td>
    </tr>
    <tr>
      <td>🕒 <b>24/7 Voice Channel Mode</b></td>
      <td>Keep the bot connected in your favorite voice or stage channel around the clock, even when the queue finishes.</td>
    </tr>
    <tr>
      <td>📜 <b>Custom Saved Playlists</b></td>
      <td>Create, load, update, and manage your personal music playlists directly within Discord via interactive modals.</td>
    </tr>
    <tr>
      <td>🎛️ <b>Interactive Player View</b></td>
      <td>Modern now-playing embed with real-time dynamic track progress, previous, pause/resume, skip, and stop buttons.</td>
    </tr>
    <tr>
      <td>⚡ <b>Dual Prefix & No-Prefix Support</b></td>
      <td>Customizable per-server prefix plus global user and guild-wide no-prefix system for lightning-fast command execution.</td>
    </tr>
    <tr>
      <td>🎴 <b>Rich Profile Cards</b></td>
      <td>Generates customized PIL graphics showcasing user badges, avatar overlays, premium status, and join stats.</td>
    </tr>
    <tr>
      <td>🛡️ <b>Owner & Admin Control Suite</b></td>
      <td>Comprehensive owner toolset featuring hot module reloading, shard monitors, server browsers, and premium tiers.</td>
    </tr>
  </tbody>
</table>

---

## 🎵 Command Showcase

### 🎶 Music & Player Controls
| Command | Aliases | Description |
|---|---|---|
| `?play <song/URL>` | `?p` | Play a song or playlist from Spotify, YouTube, SoundCloud, or direct URLs |
| `?search <query>` | — | Search for tracks and choose interactively |
| `?pause` / `?resume` | — | Pause or resume current playback |
| `?skip` | `?s` | Skip to the next song in queue or autoplay recommendation |
| `?previous` | `?prev` | Go back and play the previous track from history |
| `?stop` | — | Stop playback, clear queue, and leave voice channel |
| `?queue` | `?q` | Display interactive paginated queue of upcoming tracks |
| `?nowplaying` | `?np`, `?nop` | Show the live interactive now-playing card and controls |
| `?seek <time>` | — | Seek to a specific timestamp (e.g. `?seek 1:30` or `?seek 90`) |
| `?volume <1-100>` | `?vol` | Adjust playback volume level |
| `?loop <track/queue/off>` | — | Toggle looping for the current track or entire queue |
| `?autoplay` | `?ap` | Toggle smart autoplay mode |
| `?shuffle` | — | Shuffle the current queue randomly |
| `?replay` | — | Restart the currently playing track from the beginning |
| `?clearqueue` | `?clear_queue` | Clear all pending tracks in the queue |
| `?247` | `?twentyfour_seven` | Enable or disable 24/7 staying in voice channel |
| `?playlist` | `?pl` | Manage personal playlists (`save`, `play`, `list`, `delete`) |

### 🛠️ General & Server Settings
| Command | Aliases | Description |
|---|---|---|
| `?help` | — | Interactive, categorized help menu with select navigation |
| `?ping` | — | Check bot latency, API heartbeat, and Lavalink websocket status |
| `?stats` | — | View detailed system hardware stats, memory usage, shards & guilds |
| `?profile [@user]` | `?userinfo`, `?whois` | Generate an aesthetic dynamic graphical profile card |
| `?avatar [@user]` | — | View full-resolution avatar of a user |
| `?banner [@user]` | — | View server or user banner image |
| `?setprefix <prefix>` | `?prefix` | Change the bot prefix for the current server |
| `?guildnoprefix` | `?gnoprefix` | Toggle server-wide no-prefix mode (Admins) |
| `?settings` | `?config` | View active server configuration and toggles |

### 👑 Owner & Administration
| Command | Aliases | Description |
|---|---|---|
| `?reload <cog>` | — | Hot reload cogs without restarting the bot process |
| `?restart` | — | Safely reboot the bot process |
| `?noprefix add/remove <user>` | `?nopref` | Grant or revoke user-level no-prefix access |
| `?admin add/remove <user>` | — | Manage bot administrators |
| `?premium add/remove <user>` | — | Grant timed or permanent premium perks |
| `?slist` | `?server list` | View list of connected servers with invite links |

---

## 🚀 Quick Start

### 📋 Prerequisites

- **Python**: `3.10` or higher
- **Discord Bot Token**: From the [Discord Developer Portal](https://discord.com/developers/applications)
- **Lavalink v4 Server**: A running Lavalink node (public or private)

### 📥 1. Clone the Repository

```bash
git clone https://github.com/your-username/eve-music.git
cd "Eve Music"
```

### 📦 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### ⚙️ 3. Setup Configuration

1. Create your `.env` file:
   ```bash
   cp example.env .env
   ```
2. Open `.env` and paste your Discord bot token:
   ```env
   TOKEN=your_bot_token_here
   ```

### 🚀 4. Launch Eve Music

```bash
python main.py
```

---

## ⚙️ Configuration

### 1. Environment Variables (`.env`)
```env
TOKEN=MTIzNDU2Nzg5MDEyMzQ1Njc4OQ.xxxxxx.xxxxxxxxxxxxxxxxxxxxxx
```

### 2. Lavalink Nodes (`config/lava_nodes.json`)
Configure your Lavalink server connection details:
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
> 💡 *Need public Lavalink nodes? You can find an updated list at [lavalinks-list.vercel.app](https://lavalinks-list.vercel.app/).*

### 3. Bot Settings (`config/settings.json`)
Fine-tune global bot behavior, owners, defaults, and branding:
```json
{
    "bot-name": "Eve",
    "default_prefix": "?",
    "owner_ids": [
        "1481652276337709127"
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

## 🗄️ Project Architecture

```plaintext
Eve Music/
├── assets/                  # Dynamic background templates for PIL cards
│   ├── bg.jpg
│   └── bg2.jpg ...
├── cogs/                    # Modular command & event extensions
│   ├── general.py           # Stats, profile cards, help, guild settings
│   ├── music.py             # Lavalink player, interactive UI, playlists, queues
│   └── owner.py             # Management suite, hot-reloading, permissions
├── config/                  # JSON configuration files
│   ├── emojis.json          # Custom emoji mappings
│   ├── lava_nodes.json      # Lavalink v4 node credentials
│   ├── logging.json         # Webhook and log destination channels
│   └── settings.json        # Core bot configurations and theme tokens
├── DB/                      # Database layer
│   └── database.py          # Asynchronous SQLite manager with connection pooling
├── utils/                   # Shared UI helpers, paginators, and logger
│   ├── logging.py
│   ├── paginator.py
│   └── ui.py
├── example.env              # Environment template
├── main.py                  # Bot entry point, sharding, and rich terminal logger
└── requirements.txt         # Project dependencies
```

---

## 👥 Contributing & Support

We welcome contributions and feedback! If you find any bugs or have feature ideas:

1. **Fork the Repository**
2. **Create your feature branch** (`git checkout -b feature/AmazingFeature`)
3. **Commit your changes** (`git commit -m 'Add some AmazingFeature'`)
4. **Push to the branch** (`git push origin feature/AmazingFeature`)
5. **Open a Pull Request**

💬 Need assistance or custom setup? Join our official community:  
[![Support Server](https://img.shields.io/badge/Discord-Join%20Support%20Server-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://dsc.gg/lynx-modz)

---

## 📜 License

Distributed under the **MIT License**. See `LICENSE` for more information.

<br/>

<div align="center">

  <sub>Crafted with ❤️ by the **Eve Development Team**</sub>  
  <br/>
  <sub>⭐ If you enjoy using Eve Music, don't forget to star the repository!</sub>

</div>
