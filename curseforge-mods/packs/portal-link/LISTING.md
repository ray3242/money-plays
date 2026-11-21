<!-- CurseForge listing for Portal Link. Everything below "DESCRIPTION" is the project description (CurseForge accepts Markdown). -->
- **Project name:** Portal Link
- **Summary (short description):** Where do I build the other portal? /trigger portal gives the exact coordinates and a guide beam.
- **Class:** Mods (upload the `.jar`). Loaders: Fabric, Quilt, NeoForge, Forge. Game versions: 1.21 to 1.21.11, 26.1 to 26.3. Environment: server (optional on client).
- **Categories:** Utility & QoL
- **License:** MIT
- **Source URL:** https://github.com/ray3242/money-plays/tree/main/curseforge-mods
- **Logo:** `pack.png` in this folder (400x400)
- **Files:** `dist/portal-link-1.0.0-mod.jar` (main file), `dist/portal-link-1.0.0-datapack.zip` (additional file, or as its own Data Packs project if you prefer)
- **Changelog for 1.0.0:** First release.

---- DESCRIPTION ----
# Portal Link

Stand where you want your portal and type `/trigger portal`. Portal Link tells you where the other side has to be:

`You are at 100 64 -101 in the Overworld. Build the Nether side at 12 64 -13`

Click the coordinates to copy them. The maths is the game's own (divide or multiply by 8, rounding down, which matters for negative coordinates and is where most calculators and most people get it wrong). The suggested height is kept under the Nether roof.

Then go through to the other dimension and type `/trigger portal set 2`. A beam only you can see marks the exact block, and your action bar counts down the distance until it says **build here**.

It works in both directions: run it in the Nether to find the Overworld spot. No operator rights are needed, and every player has their own saved spot.

## Commands

| Command | What it does |
|---|---|
| `/trigger portal` | Work out and save the matching spot in the other dimension. |
| `/trigger portal set 2` | Guide beam to the saved spot for 2 minutes. Run it again to turn it off. |
| `/trigger portal set 3` | Short help. |

## Good to know

- When you walk through a portal, the game first looks for an existing portal near the matching spot: within 16 blocks in the Nether, within 128 blocks in the Overworld. Building at the exact spot is what guarantees two portals pair up with each other and not with a neighbour's.
- The pack does not place blocks or portals. It only tells you where to build.
- The beam is drawn when you are within 200 blocks; further away the action bar still shows the distance.

## Install

**As a mod (Fabric, Quilt, NeoForge or Forge):** drop the `.jar` into your `mods` folder. Fabric and Quilt also need Fabric API. It is only needed on the server (or in single player); players joining a server do not need it.

**As a data pack (vanilla, Paper, Realms worlds you upload):** put the `-datapack.zip` in your world's `datapacks` folder and run `/reload`.

Works on Minecraft Java 1.21 through 26.3. There is no Java code in the jar, only data pack functions, so it does not conflict with other mods.

## Uninstall

Run `/function portallink:uninstall` (operator), then remove the file. It deletes the scoreboards the pack created and leaves nothing behind.

## How this was made

The commands in this pack were written with an AI coding assistant and then run through an automated test suite on real Minecraft servers (1.21.1, 1.21.11 and 26.3, Fabric, NeoForge and Forge) before release. The icon is hand-placed pixel art drawn by a script, not an image generator. Source and tests: https://github.com/ray3242/money-plays/tree/main/curseforge-mods
