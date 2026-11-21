# As a player: work out the matching position in the other dimension and remember it
scoreboard players set @s portal 0
execute unless dimension minecraft:overworld unless dimension minecraft:the_nether run return run tellraw @s [{"text":"[Portal Link] ","color":"light_purple"},{"text":"Nether portals only link the Overworld and the Nether.","color":"gray"}]
execute store result score #x portallink.v run data get entity @s Pos[0]
execute store result score #y portallink.v run data get entity @s Pos[1]
execute store result score #z portallink.v run data get entity @s Pos[2]
scoreboard players operation @s portallink.tx = #x portallink.v
scoreboard players operation @s portallink.ty = #y portallink.v
scoreboard players operation @s portallink.tz = #z portallink.v
# Overworld -> Nether: divide by 8 (rounds down, like the game). Nether -> Overworld: multiply by 8.
execute if dimension minecraft:overworld run scoreboard players operation @s portallink.tx /= #8 portallink.v
execute if dimension minecraft:overworld run scoreboard players operation @s portallink.tz /= #8 portallink.v
execute if dimension minecraft:overworld run scoreboard players set @s portallink.dim 1
execute if dimension minecraft:the_nether run scoreboard players operation @s portallink.tx *= #8 portallink.v
execute if dimension minecraft:the_nether run scoreboard players operation @s portallink.tz *= #8 portallink.v
execute if dimension minecraft:the_nether run scoreboard players set @s portallink.dim 0
# keep the suggested height buildable in the Nether (below the bedrock roof, above the lava sea floor)
execute if score @s portallink.dim matches 1 if score @s portallink.ty matches 118.. run scoreboard players set @s portallink.ty 117
execute if score @s portallink.dim matches 1 if score @s portallink.ty matches ..4 run scoreboard players set @s portallink.ty 5
execute store result storage portallink:tmp a.x int 1 run scoreboard players get #x portallink.v
execute store result storage portallink:tmp a.y int 1 run scoreboard players get #y portallink.v
execute store result storage portallink:tmp a.z int 1 run scoreboard players get #z portallink.v
execute store result storage portallink:tmp a.tx int 1 run scoreboard players get @s portallink.tx
execute store result storage portallink:tmp a.ty int 1 run scoreboard players get @s portallink.ty
execute store result storage portallink:tmp a.tz int 1 run scoreboard players get @s portallink.tz
execute if score @s portallink.dim matches 1 run function portallink:text_to_nether with storage portallink:tmp a
execute if score @s portallink.dim matches 0 run function portallink:text_to_overworld with storage portallink:tmp a
