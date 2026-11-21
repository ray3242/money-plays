scoreboard players operation #t traderalert.v = #n traderalert.v
scoreboard players operation #t traderalert.v /= #d traderalert.v
scoreboard players operation #d traderalert.v += #t traderalert.v
scoreboard players operation #d traderalert.v /= #2 traderalert.v
execute if score #d traderalert.v matches ..0 run scoreboard players set #d traderalert.v 1
