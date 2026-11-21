schedule clear jobsite:loop
scoreboard objectives remove jobsite
scoreboard objectives remove jobsite.view
scoreboard objectives remove jobsite.v
data remove storage jobsite:tmp v
data remove storage jobsite:tmp p
kill @e[type=minecraft:marker,tag=jobsite.target]
tellraw @s [{"text":"[Job Site Finder] ","color":"green"},{"text":"Scoreboards removed. Now delete the pack file and run /reload.","color":"gray"}]
