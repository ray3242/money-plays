scoreboard objectives remove lagscan
scoreboard objectives remove lagscan.v
scoreboard objectives remove lagscan.n
scoreboard objectives remove lagscan.cd
data remove storage lagscan:tmp a
data remove storage lagscan:tmp h
tellraw @s [{"text":"[Lag Scanner] ","color":"gold"},{"text":"Scoreboards removed. Now delete the pack file and run /reload.","color":"gray"}]
