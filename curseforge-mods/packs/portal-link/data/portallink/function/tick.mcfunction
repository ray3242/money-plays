scoreboard players enable @a portal
execute as @a[scores={portal=1}] at @s run function portallink:calc
execute as @a[scores={portal=2}] at @s run function portallink:guide
execute as @a[scores={portal=3..}] run function portallink:help
