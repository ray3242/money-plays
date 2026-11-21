particle minecraft:dust{color:[0.25,0.6,1.0],scale:0.7} ~ ~ ~ 0 0 0 0 1 force @a[tag=jobsite.viewer]
scoreboard players add #steps jobsite.v 1
execute if score #steps jobsite.v matches ..140 unless entity @e[type=minecraft:marker,tag=jobsite.target,distance=..0.6] positioned ^ ^ ^0.6 run function jobsite:ray_home
