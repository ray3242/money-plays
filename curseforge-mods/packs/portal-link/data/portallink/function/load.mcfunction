scoreboard objectives add portal trigger
scoreboard objectives add portallink.tx dummy
scoreboard objectives add portallink.ty dummy
scoreboard objectives add portallink.tz dummy
scoreboard objectives add portallink.dim dummy
scoreboard objectives add portallink.guide dummy
scoreboard objectives add portallink.v dummy
scoreboard players set #8 portallink.v 8
scoreboard players set #2 portallink.v 2
scoreboard players set #-1 portallink.v -1
schedule function portallink:loop 5t replace
