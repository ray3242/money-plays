schedule clear portallink:loop
scoreboard objectives remove portal
scoreboard objectives remove portallink.tx
scoreboard objectives remove portallink.ty
scoreboard objectives remove portallink.tz
scoreboard objectives remove portallink.dim
scoreboard objectives remove portallink.guide
scoreboard objectives remove portallink.v
data remove storage portallink:tmp a
data remove storage portallink:tmp g
tellraw @s [{"text":"[Portal Link] ","color":"light_purple"},{"text":"Scoreboards removed. Now delete the pack file and run /reload.","color":"gray"}]
