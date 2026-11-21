# As a viewing player: draw lines for every villager nearby, only visible to this player
scoreboard players remove @s jobsite.view 1
execute if score @s jobsite.view matches 0 run tellraw @s [{"text":"[Job Site Finder] ","color":"green"},{"text":"Overlay ended.","color":"gray"}]
tag @s add jobsite.viewer
execute as @e[type=minecraft:villager,distance=..48] at @s run function jobsite:villager
tag @s remove jobsite.viewer
