schedule function portallink:loop 5t replace
execute as @a[scores={portallink.guide=1..}] at @s run function portallink:guide_step
