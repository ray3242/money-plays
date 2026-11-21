# Minecraft helper packs (CurseForge)

Four small, separate utilities for Minecraft Java 1.21 to 26.3. Each is a data pack, also packaged as a no-code mod jar for Fabric/Quilt and NeoForge.

| Pack | Command | What it does |
|---|---|---|
| [Job Site Finder](packs/jobsite-finder/LISTING.md) | `/trigger jobsite` | Lines from each villager to the workstation and bed it owns |
| [Trader Alert](packs/trader-alert/LISTING.md) | `/trigger trader` | Announces Wandering Traders with coordinates, distance, direction |
| [Portal Link](packs/portal-link/LISTING.md) | `/trigger portal` | Matching Nether/Overworld portal coordinates plus a guide beam |
| [Lag Scanner](packs/lag-scanner/LISTING.md) | `/trigger lagscan` | Entity counts by kind and the densest pile |

Ready-to-upload files are in [`dist/`](dist). `python3 build.py` rebuilds them from `packs/`.

## Layout

- `packs/<name>/` is a working data pack folder: `pack.mcmeta`, `data/`, and `overlay_modern/` (the same chat text with the click/hover spelling Minecraft 1.21.5+ expects). `LISTING.md` is the store page text, `pack.png` the icon.
- `build.py` zips each pack and builds the jar (adds `fabric.mod.json` and `META-INF/neoforge.mods.toml`).
- `tests/` is the end-to-end suite.

## Tests

`tests/run_tests.py` drives a real server over RCON and, where a client library exists for the version, a real protocol client (`tests/bot.js`, mineflayer) that records the chat text, particles and sounds it actually receives. Results for 1.0.0:

| Server | Form | Checks |
|---|---|---|
| Fabric 1.21.1 | data pack folders, then mod jars | 50/50 (server state + client) |
| Fabric 1.21.11 | data pack folders, then mod jars | 50/50 (server state + client) |
| Fabric 26.3 | data pack folders, then mod jars | 28/28 (server state only: no client library speaks 26.3 yet) |
| NeoForge 21.1.200 (1.21.1) | mod jars | 50/50 (server state + client) |

Not tested: Forge, Quilt (expected to work through the Fabric metadata), and how the particles look in the real game client. See [`tests/README.md`](tests/README.md) to run it yourself.

## AI disclosure

The pack code, tests and listing text were written by an AI coding agent (Devin) working for the repository owner, and verified by the test suite above. The icons are pixel art placed by a script. Listings say so.

## License

MIT
