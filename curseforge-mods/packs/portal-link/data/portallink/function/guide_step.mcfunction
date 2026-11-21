scoreboard players remove @s portallink.guide 1
# stop if the player changed dimension
scoreboard players set #ok portallink.v 0
execute if dimension minecraft:overworld if score @s portallink.dim matches 0 run scoreboard players set #ok portallink.v 1
execute if dimension minecraft:the_nether if score @s portallink.dim matches 1 run scoreboard players set #ok portallink.v 1
execute if score #ok portallink.v matches 0 run return run scoreboard players set @s portallink.guide 0
# horizontal distance to the target
execute store result score #dx portallink.v run data get entity @s Pos[0]
execute store result score #dz portallink.v run data get entity @s Pos[2]
scoreboard players operation #dx portallink.v -= @s portallink.tx
scoreboard players operation #dz portallink.v -= @s portallink.tz
scoreboard players operation #n portallink.v = #dx portallink.v
scoreboard players operation #n portallink.v *= #dx portallink.v
scoreboard players operation #t portallink.v = #dz portallink.v
scoreboard players operation #t portallink.v *= #dz portallink.v
scoreboard players operation #n portallink.v += #t portallink.v
scoreboard players set #d portallink.v 2048
function portallink:sqrt_step
function portallink:sqrt_step
function portallink:sqrt_step
function portallink:sqrt_step
function portallink:sqrt_step
function portallink:sqrt_step
function portallink:sqrt_step
function portallink:sqrt_step
function portallink:sqrt_step
function portallink:sqrt_step
function portallink:sqrt_step
function portallink:sqrt_step
function portallink:sqrt_step
function portallink:sqrt_step
execute if score #n portallink.v matches 0 run scoreboard players set #d portallink.v 0
# far away (or overflow): no beam, just the heading
execute unless score #dx portallink.v matches -20000..20000 run scoreboard players set #d portallink.v 99999
execute unless score #dz portallink.v matches -20000..20000 run scoreboard players set #d portallink.v 99999
execute store result storage portallink:tmp g.x int 1 run scoreboard players get @s portallink.tx
execute store result storage portallink:tmp g.y int 1 run scoreboard players get @s portallink.ty
execute store result storage portallink:tmp g.z int 1 run scoreboard players get @s portallink.tz
execute if score #d portallink.v matches ..200 run function portallink:beam with storage portallink:tmp g
execute if score #d portallink.v matches 3..99998 run title @s actionbar [{"text":"Portal spot ","color":"light_purple"},{"score":{"name":"@s","objective":"portallink.tx"},"color":"yellow"},{"text":" "},{"score":{"name":"@s","objective":"portallink.ty"},"color":"yellow"},{"text":" "},{"score":{"name":"@s","objective":"portallink.tz"},"color":"yellow"},{"text":"  \u2022  ","color":"dark_gray"},{"score":{"name":"#d","objective":"portallink.v"},"color":"white"},{"text":" blocks away","color":"gray"}]
execute if score #d portallink.v matches 99999 run title @s actionbar [{"text":"Portal spot ","color":"light_purple"},{"score":{"name":"@s","objective":"portallink.tx"},"color":"yellow"},{"text":" "},{"score":{"name":"@s","objective":"portallink.ty"},"color":"yellow"},{"text":" "},{"score":{"name":"@s","objective":"portallink.tz"},"color":"yellow"},{"text":"  \u2022  far away","color":"gray"}]
execute if score #d portallink.v matches ..2 run title @s actionbar [{"text":"Portal spot ","color":"light_purple"},{"score":{"name":"@s","objective":"portallink.tx"},"color":"yellow"},{"text":" "},{"score":{"name":"@s","objective":"portallink.ty"},"color":"yellow"},{"text":" "},{"score":{"name":"@s","objective":"portallink.tz"},"color":"yellow"},{"text":"  \u2022  build here","color":"green"}]
