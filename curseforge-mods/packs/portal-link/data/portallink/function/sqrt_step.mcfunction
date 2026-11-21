scoreboard players operation #t portallink.v = #n portallink.v
scoreboard players operation #t portallink.v /= #d portallink.v
scoreboard players operation #d portallink.v += #t portallink.v
scoreboard players operation #d portallink.v /= #2 portallink.v
execute if score #d portallink.v matches ..0 run scoreboard players set #d portallink.v 1
