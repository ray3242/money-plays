# /trigger trader : list traders around the player
scoreboard players set @s trader 0
scoreboard players set #count traderalert.v 0
tag @s add traderalert.asker
execute store result storage traderalert:tmp a.r int 1 run scoreboard players get #range traderalert.cfg
function traderalert:list_each with storage traderalert:tmp a
tag @s remove traderalert.asker
execute if score #count traderalert.v matches 0 run tellraw @s [{"text":"[Trader Alert] ","color":"aqua"},{"text":"No Wandering Trader within ","color":"gray"},{"score":{"name":"#range","objective":"traderalert.cfg"},"color":"gray"},{"text":" blocks.","color":"gray"}]
