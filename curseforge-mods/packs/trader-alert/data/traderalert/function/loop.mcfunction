schedule function traderalert:loop 20t replace
execute as @e[type=minecraft:wandering_trader,tag=!traderalert.seen] at @s run function traderalert:arrive
