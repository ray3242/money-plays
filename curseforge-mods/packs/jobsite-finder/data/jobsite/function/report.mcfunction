# Census of villagers within 48 blocks of the player
execute store result score #total jobsite.v if entity @e[type=minecraft:villager,distance=..48]
execute store result score #job jobsite.v if entity @e[type=minecraft:villager,distance=..48,nbt={Brain:{memories:{"minecraft:job_site":{}}}}]
execute store result score #bed jobsite.v if entity @e[type=minecraft:villager,distance=..48,nbt={Brain:{memories:{"minecraft:home":{}}}}]
execute store result score #nitwit jobsite.v if entity @e[type=minecraft:villager,distance=..48,nbt={VillagerData:{profession:"minecraft:nitwit"}}]
scoreboard players operation #secs jobsite.v = @s jobsite.view
scoreboard players operation #secs jobsite.v /= #4 jobsite.v
scoreboard players operation #nojob jobsite.v = #total jobsite.v
scoreboard players operation #nojob jobsite.v -= #job jobsite.v
scoreboard players operation #nobed jobsite.v = #total jobsite.v
scoreboard players operation #nobed jobsite.v -= #bed jobsite.v
execute if score #total jobsite.v matches 0 run tellraw @s [{"text":"[Job Site Finder] ","color":"green"},{"text":"No villagers within 48 blocks. Overlay stays on while you walk around.","color":"gray"}]
execute if score #total jobsite.v matches 1.. run function jobsite:report_text
