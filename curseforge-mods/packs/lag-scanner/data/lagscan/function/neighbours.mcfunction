execute store result score @s lagscan.n if entity @e[type=!minecraft:player,distance=..8]
scoreboard players operation #max lagscan.v > @s lagscan.n
