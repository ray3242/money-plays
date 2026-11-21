scoreboard objectives add trader trigger
scoreboard objectives add traderalert.v dummy
scoreboard objectives add traderalert.cfg dummy
# Settings (kept across reloads): glow seconds for a new trader (0 = off), sound 1/0
execute unless score #glow traderalert.cfg matches -2147483648.. run scoreboard players set #glow traderalert.cfg 30
execute unless score #sound traderalert.cfg matches -2147483648.. run scoreboard players set #sound traderalert.cfg 1
execute unless score #range traderalert.cfg matches -2147483648.. run scoreboard players set #range traderalert.cfg 128
scoreboard players set #2 traderalert.v 2
scoreboard players set #-1 traderalert.v -1
scoreboard players set #1200 traderalert.v 1200
schedule function traderalert:loop 20t replace
