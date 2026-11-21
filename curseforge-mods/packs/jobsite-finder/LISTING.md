<!-- CurseForge listing for Job Site Finder. Everything below "DESCRIPTION" is the project description (CurseForge accepts Markdown). -->
- **Project name:** Job Site Finder
- **Summary (short description):** See which workstation and bed each villager owns. Type /trigger jobsite and coloured lines appear.
- **Class:** Mods (upload the `.jar`). Loaders: Fabric, Quilt, NeoForge, Forge. Game versions: 1.21 to 1.21.11, 26.1 to 26.3. Environment: server (optional on client).
- **Categories:** Utility & QoL, Server Utility
- **License:** MIT
- **Source URL:** https://github.com/ray3242/money-plays/tree/main/curseforge-mods
- **Logo:** `pack.png` in this folder (400x400)
- **Files:** `dist/jobsite-finder-1.0.0-mod.jar` (main file), `dist/jobsite-finder-1.0.0-datapack.zip` (additional file, or as its own Data Packs project if you prefer)
- **Changelog for 1.0.0:** First release.

---- DESCRIPTION ----
# Job Site Finder

Trading halls break in the same way every time: a villager quietly links to the wrong lectern, or to a bed two floors down, and you only find out when the trades stop restocking. Job Site Finder shows you the links.

Type `/trigger jobsite` and, for the next 30 seconds, every villager within 48 blocks gets:

- a **green line** to the workstation it has claimed,
- a **blue line** to the bed it has claimed,
- a **red puff** over its head if it has no workstation,
- an **orange puff** if it has no bed.

You also get a count in chat: how many villagers are nearby, how many have a job, how many have a bed, how many are nitwits.

Only the player who ran the command sees the lines, so it is safe on a shared server. No operator rights are needed.

## Commands

| Command | What it does |
|---|---|
| `/trigger jobsite` | Overlay on for 30 seconds. Run it again to turn it off. |
| `/trigger jobsite set 120` | Overlay on for 120 seconds (5 to 600). |

## Good to know

- The lines come from the villager's own memory, the same data the game uses, so what you see is what the game will do.
- A workstation that no villager has claimed has no line; that is how you spot the spare ones.
- Villagers further than 48 blocks from you are not drawn. Walk around; the overlay follows you.

## Install

**As a mod (Fabric, Quilt, NeoForge or Forge):** drop the `.jar` into your `mods` folder. Fabric and Quilt also need Fabric API. It is only needed on the server (or in single player); players joining a server do not need it.

**As a data pack (vanilla, Paper, Realms worlds you upload):** put the `-datapack.zip` in your world's `datapacks` folder and run `/reload`.

Works on Minecraft Java 1.21 through 26.3. There is no Java code in the jar, only data pack functions, so it does not conflict with other mods.

## Uninstall

Run `/function jobsite:uninstall` (operator), then remove the file. It deletes the scoreboards the pack created and leaves nothing behind.

## How this was made

The commands in this pack were written with an AI coding assistant and then run through an automated test suite on real Minecraft servers (1.21.1, 1.21.11 and 26.3, Fabric, NeoForge and Forge) before release. The icon is hand-placed pixel art drawn by a script, not an image generator. Source and tests: https://github.com/ray3242/money-plays/tree/main/curseforge-mods
