scoreboard objectives add jobsite trigger
scoreboard objectives add jobsite.view dummy
scoreboard objectives add jobsite.v dummy
scoreboard players set #4 jobsite.v 4
schedule function jobsite:loop 5t replace
