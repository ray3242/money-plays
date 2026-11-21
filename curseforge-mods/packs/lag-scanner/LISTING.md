<!-- CurseForge listing for Lag Scanner. Everything below "DESCRIPTION" is the project description (CurseForge accepts Markdown). -->
- **Project name:** Lag Scanner
- **Summary (short description):** Find what is lagging your base: counts entities around you by kind and points at the densest pile.
- **Class:** Mods (upload the `.jar`). Loaders: Fabric, Quilt, NeoForge. Game versions: 1.21 to 1.21.11, 26.1 to 26.3. Environment: server (optional on client).
- **Categories:** Server Utility, Utility & QoL
- **License:** MIT
- **Source URL:** https://github.com/ray3242/money-plays/tree/main/curseforge-mods
- **Logo:** `pack.png` in this folder (400x400)
- **Files:** `dist/lag-scanner-1.0.0-mod.jar` (main file), `dist/lag-scanner-1.0.0-datapack.zip` (additional file, or as its own Data Packs project if you prefer)
- **Changelog for 1.0.0:** First release.

---- DESCRIPTION ----
# Lag Scanner

When a server starts to stutter, the cause is nearly always a pile of entities somewhere: a farm that overflowed, a cow pit, a thousand item frames. Lag Scanner finds the pile without plugins or operator tools.

Type `/trigger lagscan`:

```
[Lag Scanner] 1312 entities within 64 blocks
  Dropped items 941  XP orbs 12  Hostile 30  Animals 248
  Villagers 22  Boats/minecarts 9  Frames/stands/displays 41  Other 9
  Densest pile: 873 entities within 8 blocks of 104 63 -220 (861 drops, 12 mobs)
```

The coordinates of the densest pile are clickable (they put a `/tp` command in your chat box, for operators), and a beam only you can see marks the spot.

Works on vanilla servers, Realms and single player. Any player can run it; a 5 second cooldown per player keeps it from being spammed.

## Commands

| Command | What it does |
|---|---|
| `/trigger lagscan` | Scan 64 blocks around you. |
| `/trigger lagscan set 200` | Scan a different radius (8 to 256 blocks). |

## Good to know

- Only loaded entities can be counted, so stand in or near the area you suspect.
- The pile search samples up to 256 entities per scan to stay cheap on busy servers; run it twice if the first answer looks off.
- It reports and never removes anything. What to do with the pile is up to you.
- Mobs added by other mods are counted under "Other".

## Install

**As a mod (Fabric, Quilt or NeoForge):** drop the `.jar` into your `mods` folder. Fabric and Quilt also need Fabric API. It is only needed on the server (or in single player); players joining a server do not need it.

**As a data pack (vanilla, Paper, Realms worlds you upload):** put the `-datapack.zip` in your world's `datapacks` folder and run `/reload`.

Works on Minecraft Java 1.21 through 26.3. There is no Java code in the jar, only data pack functions, so it does not conflict with other mods.

## Uninstall

Run `/function lagscan:uninstall` (operator), then remove the file. It deletes the scoreboards the pack created and leaves nothing behind.

## How this was made

The commands in this pack were written with an AI coding assistant and then run through an automated test suite on real Minecraft servers (1.21.1, 1.21.11 and 26.3, Fabric and NeoForge) before release. The icon is hand-placed pixel art drawn by a script, not an image generator. Source and tests: https://github.com/ray3242/money-plays/tree/main/curseforge-mods
