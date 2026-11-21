# As a wandering trader that has not been announced yet
tag @s add traderalert.seen
function traderalert:read_trader
execute if score #glow traderalert.cfg matches 1.. run function traderalert:glow
execute store result storage traderalert:tmp a.r int 1 run scoreboard players get #range traderalert.cfg
function traderalert:announce with storage traderalert:tmp a
