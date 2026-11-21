# Running the tests

You need a Minecraft server with RCON on (`enable-rcon=true`, `rcon.password=test`), `online-mode=false`, a flat world, and the packs installed (folders in `world/datapacks/` or jars in `mods/`).

1. Get a player online.
   - Real client (Minecraft up to 1.21.11): `npm i mineflayer`, then `node bot.js <server port> <http port> <version>`. It joins as `Bot`.
   - Or a Carpet mod fake player: `/player Tester spawn`.
2. `python3 run_tests.py <rcon port> <player name> [bot http port]`

With the bot's http port the suite also checks what the client received (chat text, click events, particle positions, sounds). Without it, only server-side state is checked. The suite clears entities and blocks around 0,0, so use a throwaway world.
