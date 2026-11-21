# As a player; #x/#z hold the trader position. Outputs #d (blocks) and storage traderalert:tmp dir
execute store result score #dx traderalert.v run data get entity @s Pos[0]
execute store result score #dz traderalert.v run data get entity @s Pos[2]
scoreboard players operation #dx traderalert.v *= #-1 traderalert.v
scoreboard players operation #dz traderalert.v *= #-1 traderalert.v
scoreboard players operation #dx traderalert.v += #x traderalert.v
scoreboard players operation #dz traderalert.v += #z traderalert.v
scoreboard players operation #n traderalert.v = #dx traderalert.v
scoreboard players operation #n traderalert.v *= #dx traderalert.v
scoreboard players operation #t traderalert.v = #dz traderalert.v
scoreboard players operation #t traderalert.v *= #dz traderalert.v
scoreboard players operation #n traderalert.v += #t traderalert.v
# integer square root (Newton, from above)
scoreboard players set #d traderalert.v 1024
function traderalert:sqrt_step
function traderalert:sqrt_step
function traderalert:sqrt_step
function traderalert:sqrt_step
function traderalert:sqrt_step
function traderalert:sqrt_step
function traderalert:sqrt_step
function traderalert:sqrt_step
function traderalert:sqrt_step
function traderalert:sqrt_step
function traderalert:sqrt_step
function traderalert:sqrt_step
execute if score #n traderalert.v matches 0 run scoreboard players set #d traderalert.v 0
# compass direction: 8 sectors, compare |dx| and |dz|
scoreboard players operation #ax traderalert.v = #dx traderalert.v
execute if score #ax traderalert.v matches ..-1 run scoreboard players operation #ax traderalert.v *= #-1 traderalert.v
scoreboard players operation #az traderalert.v = #dz traderalert.v
execute if score #az traderalert.v matches ..-1 run scoreboard players operation #az traderalert.v *= #-1 traderalert.v
scoreboard players operation #ax2 traderalert.v = #ax traderalert.v
scoreboard players operation #ax2 traderalert.v *= #2 traderalert.v
scoreboard players operation #az2 traderalert.v = #az traderalert.v
scoreboard players operation #az2 traderalert.v *= #2 traderalert.v
data modify storage traderalert:tmp ns set value ""
data modify storage traderalert:tmp ew set value ""
execute if score #az2 traderalert.v >= #ax traderalert.v if score #dz traderalert.v matches ..-1 run data modify storage traderalert:tmp ns set value "north"
execute if score #az2 traderalert.v >= #ax traderalert.v if score #dz traderalert.v matches 1.. run data modify storage traderalert:tmp ns set value "south"
execute if score #ax2 traderalert.v >= #az traderalert.v if score #dx traderalert.v matches ..-1 run data modify storage traderalert:tmp ew set value "west"
execute if score #ax2 traderalert.v >= #az traderalert.v if score #dx traderalert.v matches 1.. run data modify storage traderalert:tmp ew set value "east"
execute if score #n traderalert.v matches 0 run data modify storage traderalert:tmp ns set value "here"
