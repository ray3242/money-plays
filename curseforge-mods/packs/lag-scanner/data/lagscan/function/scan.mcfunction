# Macro: r = radius. Counts loaded entities around the player by kind.
$execute store result score #total lagscan.v if entity @e[type=!minecraft:player,distance=..$(r)]
$execute store result score #items lagscan.v if entity @e[type=minecraft:item,distance=..$(r)]
$execute store result score #xp lagscan.v if entity @e[type=minecraft:experience_orb,distance=..$(r)]
$execute store result score #hostile lagscan.v if entity @e[type=#lagscan:hostile,distance=..$(r)]
$execute store result score #animals lagscan.v if entity @e[type=#lagscan:animals,distance=..$(r)]
$execute store result score #villagers lagscan.v if entity @e[type=#lagscan:villagers,distance=..$(r)]
$execute store result score #vehicles lagscan.v if entity @e[type=#lagscan:vehicles,distance=..$(r)]
$execute store result score #decor lagscan.v if entity @e[type=#lagscan:decor,distance=..$(r)]
scoreboard players operation #other lagscan.v = #total lagscan.v
scoreboard players operation #other lagscan.v -= #items lagscan.v
scoreboard players operation #other lagscan.v -= #xp lagscan.v
scoreboard players operation #other lagscan.v -= #hostile lagscan.v
scoreboard players operation #other lagscan.v -= #animals lagscan.v
scoreboard players operation #other lagscan.v -= #villagers lagscan.v
scoreboard players operation #other lagscan.v -= #vehicles lagscan.v
scoreboard players operation #other lagscan.v -= #decor lagscan.v
tellraw @s [{"text":"[Lag Scanner] ","color":"gold"},{"score":{"name":"#total","objective":"lagscan.v"},"color":"white"},{"text":" entities within ","color":"white"},{"score":{"name":"#r","objective":"lagscan.v"},"color":"white"},{"text":" blocks","color":"white"}]
tellraw @s [{"text":"  Dropped items ","color":"gray"},{"score":{"name":"#items","objective":"lagscan.v"},"color":"yellow"},{"text":"  XP orbs ","color":"gray"},{"score":{"name":"#xp","objective":"lagscan.v"},"color":"yellow"},{"text":"  Hostile ","color":"gray"},{"score":{"name":"#hostile","objective":"lagscan.v"},"color":"yellow"},{"text":"  Animals ","color":"gray"},{"score":{"name":"#animals","objective":"lagscan.v"},"color":"yellow"}]
tellraw @s [{"text":"  Villagers ","color":"gray"},{"score":{"name":"#villagers","objective":"lagscan.v"},"color":"yellow"},{"text":"  Boats/minecarts ","color":"gray"},{"score":{"name":"#vehicles","objective":"lagscan.v"},"color":"yellow"},{"text":"  Frames/stands/displays ","color":"gray"},{"score":{"name":"#decor","objective":"lagscan.v"},"color":"yellow"},{"text":"  Other ","color":"gray"},{"score":{"name":"#other","objective":"lagscan.v"},"color":"yellow"}]
# Hotspot: look at up to 256 random entities and find the one with the most neighbours within 8 blocks
scoreboard players set #max lagscan.v 0
$execute as @e[type=!minecraft:player,distance=..$(r),limit=256,sort=random] at @s run function lagscan:neighbours
execute if score #max lagscan.v matches ..9 run tellraw @s [{"text":"  No dense pile found (nothing with 10+ entities inside 8 blocks).","color":"dark_gray"}]
$execute if score #max lagscan.v matches 10.. as @e[type=!minecraft:player,distance=..$(r),scores={lagscan.n=1..}] if score @s lagscan.n = #max lagscan.v run tag @s add lagscan.best
execute if score #max lagscan.v matches 10.. as @e[tag=lagscan.best,limit=1] at @s run function lagscan:hotspot
tag @e[tag=lagscan.best] remove lagscan.best
$scoreboard players reset @e[type=!minecraft:player,distance=..$(r),scores={lagscan.n=1..}] lagscan.n
