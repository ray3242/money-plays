# Runs as the player who used /trigger jobsite [set <seconds>]
execute if score @s jobsite.view matches 1.. run return run function jobsite:off
scoreboard players operation @s jobsite.view = @s jobsite
execute if score @s jobsite matches 1 run scoreboard players set @s jobsite.view 30
execute if score @s jobsite matches 601.. run scoreboard players set @s jobsite.view 600
scoreboard players operation @s jobsite.view *= #4 jobsite.v
scoreboard players set @s jobsite 0
function jobsite:report
