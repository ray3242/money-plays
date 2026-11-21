# As a player: toggle the guide beam to the saved target
scoreboard players set @s portal 0
execute if score @s portallink.guide matches 1.. run return run function portallink:guide_off
scoreboard players set #ok portallink.v 0
execute if dimension minecraft:overworld if score @s portallink.dim matches 0 run scoreboard players set #ok portallink.v 1
execute if dimension minecraft:the_nether if score @s portallink.dim matches 1 run scoreboard players set #ok portallink.v 1
execute if score #ok portallink.v matches 0 run return run tellraw @s [{"text":"[Portal Link] ","color":"light_purple"},{"text":"No saved spot for this dimension. Stand at your portal in the other dimension and run /trigger portal first.","color":"gray"}]
# 2 minutes at 4 updates per second
scoreboard players set @s portallink.guide 480
tellraw @s [{"text":"[Portal Link] ","color":"light_purple"},{"text":"Guide beam on for 2 minutes. Run /trigger portal set 2 again to turn it off.","color":"gray"}]
