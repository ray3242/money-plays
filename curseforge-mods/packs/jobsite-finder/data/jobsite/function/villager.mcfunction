data remove storage jobsite:tmp v
data modify storage jobsite:tmp v set from entity @s Brain.memories
execute if data storage jobsite:tmp v."minecraft:job_site".value.pos run function jobsite:draw_job
execute if data storage jobsite:tmp v."minecraft:home".value.pos run function jobsite:draw_home
execute unless data storage jobsite:tmp v."minecraft:job_site".value.pos run particle minecraft:dust{color:[1.0,0.15,0.15],scale:1.0} ~ ~2.3 ~ 0.12 0.05 0.12 0 3 force @a[tag=jobsite.viewer]
execute unless data storage jobsite:tmp v."minecraft:home".value.pos run particle minecraft:dust{color:[1.0,0.6,0.0],scale:1.0} ~ ~2.6 ~ 0.12 0.05 0.12 0 3 force @a[tag=jobsite.viewer]
