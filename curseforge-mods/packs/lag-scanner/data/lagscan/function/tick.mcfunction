scoreboard players enable @a lagscan
scoreboard players remove @a[scores={lagscan.cd=1..}] lagscan.cd 1
execute as @a[scores={lagscan=1..}] at @s run function lagscan:trigger
