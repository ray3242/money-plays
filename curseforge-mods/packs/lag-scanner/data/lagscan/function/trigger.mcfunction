# /trigger lagscan [set <radius>] : radius 8..256 blocks, default 64
execute if score @s lagscan.cd matches 1.. run scoreboard players set @s lagscan 0
execute if score @s lagscan.cd matches 1.. run return run tellraw @s [{"text":"[Lag Scanner] ","color":"gold"},{"text":"Please wait a few seconds between scans.","color":"gray"}]
scoreboard players set @s lagscan.cd 100
scoreboard players operation #r lagscan.v = @s lagscan
execute if score #r lagscan.v matches 1 run scoreboard players set #r lagscan.v 64
execute if score #r lagscan.v matches ..7 run scoreboard players set #r lagscan.v 8
execute if score #r lagscan.v matches 257.. run scoreboard players set #r lagscan.v 256
scoreboard players set @s lagscan 0
execute store result storage lagscan:tmp a.r int 1 run scoreboard players get #r lagscan.v
function lagscan:scan with storage lagscan:tmp a
