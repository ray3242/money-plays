schedule clear traderalert:loop
scoreboard objectives remove trader
scoreboard objectives remove traderalert.v
scoreboard objectives remove traderalert.cfg
tag @e[type=minecraft:wandering_trader] remove traderalert.seen
data remove storage traderalert:tmp a
data remove storage traderalert:tmp ns
data remove storage traderalert:tmp ew
tellraw @s [{"text":"[Trader Alert] ","color":"aqua"},{"text":"Scoreboards removed. Now delete the pack file and run /reload.","color":"gray"}]
