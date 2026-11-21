# As/at the entity in the middle of the densest pile
execute store result storage lagscan:tmp h.x int 1 run data get entity @s Pos[0]
execute store result storage lagscan:tmp h.y int 1 run data get entity @s Pos[1]
execute store result storage lagscan:tmp h.z int 1 run data get entity @s Pos[2]
execute store result storage lagscan:tmp h.n int 1 run scoreboard players get #max lagscan.v
execute store result score #h_items lagscan.v if entity @e[type=#lagscan:drops,distance=..8]
execute store result score #h_mobs lagscan.v if entity @e[type=#lagscan:hostile,distance=..8]
execute store result score #t lagscan.v if entity @e[type=#lagscan:animals,distance=..8]
scoreboard players operation #h_mobs lagscan.v += #t lagscan.v
execute store result score #t lagscan.v if entity @e[type=#lagscan:villagers,distance=..8]
scoreboard players operation #h_mobs lagscan.v += #t lagscan.v
particle minecraft:end_rod ~ ~6 ~ 0.05 6 0.05 0 60 force @a[scores={lagscan.cd=100}]
execute as @a[scores={lagscan.cd=100}] run function lagscan:text_hotspot with storage lagscan:tmp h
