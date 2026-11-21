<!-- CurseForge listing for Trader Alert. Everything below "DESCRIPTION" is the project description (CurseForge accepts Markdown). -->
- **Project name:** Trader Alert
- **Summary (short description):** Get a chat message with coordinates, distance and direction when a Wandering Trader arrives near you.
- **Class:** Mods (upload the `.jar`). Loaders: Fabric, Quilt, NeoForge. Game versions: 1.21 to 1.21.11, 26.1 to 26.3. Environment: server (optional on client).
- **Categories:** Utility & QoL, Server Utility
- **License:** MIT
- **Source URL:** https://github.com/ray3242/money-plays/tree/main/curseforge-mods
- **Logo:** `pack.png` in this folder (400x400)
- **Files:** `dist/trader-alert-1.0.0-mod.jar` (main file), `dist/trader-alert-1.0.0-datapack.zip` (additional file, or as its own Data Packs project if you prefer)
- **Changelog for 1.0.0:** First release.

---- DESCRIPTION ----
# Trader Alert

Wandering Traders show up without a sound, stand behind a hill for 40 minutes and leave. Trader Alert tells you when one arrives and where it is.

When a trader spawns within 128 blocks of you:

- you get a chat line: `A Wandering Trader arrived at 212 68 -40 (37 blocks northeast)`,
- you hear the trader's voice once,
- the trader glows through walls for 30 seconds so you can walk straight to it.

Lost it again? `/trigger trader` lists every trader near you with coordinates, distance, direction and how many minutes it has left before it leaves.

No operator rights are needed to use it.

## Commands

| Command | What it does |
|---|---|
| `/trigger trader` | List Wandering Traders within range and make them glow for 15 seconds. |

## Settings (operators)

| Command | Effect |
|---|---|
| `/scoreboard players set #glow traderalert.cfg 0` | No glow on arrival (any number = seconds, default 30). |
| `/scoreboard players set #sound traderalert.cfg 0` | No sound (1 = on). |
| `/scoreboard players set #range traderalert.cfg 64` | Who gets told: players within this many blocks (default 128). |

## Good to know

- Each trader is announced once. Traders that were already in the world when you installed the pack are announced the first time their chunk is loaded.
- Traders from a spawn egg never leave on their own; the list says so.

## Install

**As a mod (Fabric, Quilt or NeoForge):** drop the `.jar` into your `mods` folder. Fabric and Quilt also need Fabric API. It is only needed on the server (or in single player); players joining a server do not need it.

**As a data pack (vanilla, Paper, Realms worlds you upload):** put the `-datapack.zip` in your world's `datapacks` folder and run `/reload`.

Works on Minecraft Java 1.21 through 26.3. There is no Java code in the jar, only data pack functions, so it does not conflict with other mods.

## Uninstall

Run `/function traderalert:uninstall` (operator), then remove the file. It deletes the scoreboards the pack created and leaves nothing behind.

## How this was made

The commands in this pack were written with an AI coding assistant and then run through an automated test suite on real Minecraft servers (1.21.1, 1.21.11 and 26.3, Fabric and NeoForge) before release. The icon is hand-placed pixel art drawn by a script, not an image generator. Source and tests: https://github.com/ray3242/money-plays/tree/main/curseforge-mods
