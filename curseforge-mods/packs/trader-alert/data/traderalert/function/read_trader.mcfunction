execute store result score #x traderalert.v run data get entity @s Pos[0]
execute store result score #y traderalert.v run data get entity @s Pos[1]
execute store result score #z traderalert.v run data get entity @s Pos[2]
execute store result score #left traderalert.v run data get entity @s DespawnDelay
scoreboard players operation #left traderalert.v /= #1200 traderalert.v
