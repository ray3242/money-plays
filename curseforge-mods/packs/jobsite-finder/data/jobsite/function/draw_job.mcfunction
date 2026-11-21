data modify storage jobsite:tmp p.x set from storage jobsite:tmp v."minecraft:job_site".value.pos[0]
data modify storage jobsite:tmp p.y set from storage jobsite:tmp v."minecraft:job_site".value.pos[1]
data modify storage jobsite:tmp p.z set from storage jobsite:tmp v."minecraft:job_site".value.pos[2]
function jobsite:mark with storage jobsite:tmp p
scoreboard players set #steps jobsite.v 0
execute anchored eyes facing entity @e[type=minecraft:marker,tag=jobsite.target,limit=1] feet positioned ^ ^ ^0.5 run function jobsite:ray_job
execute at @e[type=minecraft:marker,tag=jobsite.target,limit=1] run particle minecraft:happy_villager ~ ~0.35 ~ 0.3 0.3 0.3 0 4 force @a[tag=jobsite.viewer]
execute as @e[type=minecraft:marker,tag=jobsite.target] run function jobsite:unmark
