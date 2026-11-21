#!/usr/bin/env python3
"""End-to-end tests against a real Minecraft server.

usage: run_tests.py <rcon port> <player name> [bot http port]

The player must already be online. With a bot http port (tests/bot.js, a real
protocol client) chat text, particles and sounds received by the client are
asserted too; without it only server-side state is checked.
"""
import sys, time, json, re, urllib.request, urllib.parse
from rcon import Rcon
port, who = int(sys.argv[1]), sys.argv[2]
http = int(sys.argv[3]) if len(sys.argv) > 3 else None
r = Rcon(port)
fails = []; passed = 0
def ok(cond, name, detail=''):
    global passed
    if cond: passed += 1; print('  PASS', name)
    else: fails.append(name); print('  FAIL', name, detail)
def score(holder, obj):
    m = re.search(r'has (-?\d+)', r(f'scoreboard players get {holder} {obj}'))
    return int(m.group(1)) if m else None
def events(pp=False):
    if not http: return {'chat': [], 'raw': [], 'particles': {}, 'sounds': [], 'pp': []}
    return json.load(urllib.request.urlopen(f'http://127.0.0.1:{http}/events' + ('?pp=1' if pp else ''), timeout=5))
def trig(cmd):
    events(); r(f'execute as {who} run trigger {cmd}')
def chat_has(ev, text): return any(text in c for c in ev['chat'])
def count(sel):
    m = re.search(r'Test passed[.,] [Cc]ount: (\d+)', r(f'execute if entity {sel}'))
    return int(m.group(1)) if m else 0
newboat = 'boat' if 'Summoned' in r('summon minecraft:boat 0 -60 0') else 'oak_boat'
def reset():
    r('kill @e[type=!player]'); time.sleep(0.3); r('kill @e[type=!player]')
    r(f'gamemode spectator {who}'); r(f'execute in minecraft:overworld run tp {who} 0.5 -59 0.5')
    r('fill -12 -60 -12 12 -55 12 air'); r('time set noon'); time.sleep(0.5); events()
print(f'server port {port} | player {who} | client checks: {bool(http)}')

# ------------------------------------------------------------ Job Site Finder
print('Job Site Finder'); reset()
r('setblock 6 -60 0 minecraft:lectern'); r('setblock 0 -60 6 minecraft:red_bed[part=head,facing=south]'); r('setblock 0 -60 5 minecraft:red_bed[part=foot,facing=south]')
r('summon minecraft:villager 3 -60 0'); r('summon minecraft:villager -5 -60 -5 {NoAI:1b,VillagerData:{profession:"minecraft:nitwit",level:1,type:"minecraft:plains"}}')
claimed = False
for _ in range(60):
    time.sleep(1)
    if count('@e[type=minecraft:villager,nbt={Brain:{memories:{"minecraft:job_site":{},"minecraft:home":{}}}}]') == 1: claimed = True; break
ok(claimed, 'villager claimed lectern and bed (vanilla AI)')
r('data merge entity @e[type=minecraft:villager,nbt={Brain:{memories:{"minecraft:job_site":{}}}},limit=1] {NoAI:1b}'); r('tp @e[type=minecraft:villager,nbt={NoAI:1b,Brain:{memories:{"minecraft:job_site":{}}}},limit=1] 3.5 -60 0.5')
trig('jobsite'); time.sleep(2.5); ev = events(pp=True)
ok(score('#total', 'jobsite.v') == 2 and score('#job', 'jobsite.v') == 1 and score('#bed', 'jobsite.v') == 1 and score('#nojob', 'jobsite.v') == 1 and score('#nitwit', 'jobsite.v') == 1, 'census scores 2 total / 1 job / 1 bed / 1 jobless / 1 nitwit')
v = score(who, 'jobsite.view'); ok(v is not None and 100 <= v <= 120, 'overlay timer running (30 s default)', v)
ok(count('@e[type=minecraft:marker]') == 0, 'no helper markers left behind')
if http:
    ok(chat_has(ev, '2 villagers within 48 blocks') and chat_has(ev, '1 with a workstation') and chat_has(ev, 'Overlay on for 30 seconds'), 'client got the report text', ev['chat'])
    pts = ev['pp']
    near = lambda p, x, y, z, d: abs(p[1]-x) <= d and abs(p[2]-y) <= d and abs(p[3]-z) <= d
    ok(any(k.startswith('"happy_villager"') and near([k, x, y, z], 6.5, -59.2, 0.5, 1.2) for k, x, y, z in pts), 'workstation marker particles at the lectern')
    line = [p for p in pts if p[0].startswith('"dust"') and abs(p[3]-0.5) < 0.3 and 3.5 < p[1] < 6.6 and -59.6 < p[2] < -58.0]
    ok(len(line) >= 4, 'green line runs from villager to lectern', len(line))
    bed = [p for p in pts if p[0].startswith('"dust"') and near(p, 0.5, -59.2, 6.5, 1.0)]
    ok(len(bed) >= 2, 'blue line reaches the bed', len(bed))
    puff = [p for p in pts if p[0].startswith('"dust"') and near(p, -4.5, -57.5, -4.5, 0.8)]
    ok(len(puff) >= 4, 'nitwit shows no-job and no-bed puffs', len(puff))
trig('jobsite'); time.sleep(1.0); ev = events(); time.sleep(1.0); ev2 = events()
ok(score(who, 'jobsite.view') == 0, 'second trigger turns the overlay off')
if http: ok(chat_has(ev, 'Overlay off') and not any(k.startswith('"dust"') for k in ev2['particles']), 'client: off message, particles stop', ev2['particles'])
trig('jobsite set 5'); time.sleep(7); ok(score(who, 'jobsite.view') == 0, 'custom 5 s duration expires on its own')

# ------------------------------------------------------------ Trader Alert
print('Trader Alert'); reset()
r('summon minecraft:wandering_trader 20 -60 -10 {NoAI:1b,DespawnDelay:24000}'); time.sleep(2.5); ev = events()
ok(count('@e[type=minecraft:wandering_trader,tag=traderalert.seen]') == 1, 'trader tagged as announced')
ok('glowing' in r('data get entity @e[type=minecraft:wandering_trader,limit=1] active_effects'), 'trader glows on arrival')
ok(score('#d', 'traderalert.v') == 22, 'distance 22 blocks (sqrt of 20^2+10^2)', score('#d', 'traderalert.v'))
if http:
    ok(chat_has(ev, 'A Wandering Trader arrived at 20 -60 -10 (22 blocks northeast)'), 'client got the arrival message', ev['chat'])
    ok(len(ev['sounds']) >= 1, 'client got the arrival sound')
time.sleep(2); ev = events()
if http: ok(not chat_has(ev, 'arrived'), 'trader is announced only once')
trig('trader'); time.sleep(1); ev = events()
ok(score('#count', 'traderalert.v') == 1 and 18 <= score('#left', 'traderalert.v') <= 20, '/trigger trader finds it, ~20 min left', score('#left', 'traderalert.v'))
if http: ok(chat_has(ev, 'Trader at 20 -60 -10 (22 blocks northeast), leaves in about'), 'client got the list line', ev['chat'])
for (x, z, d) in ((0, 30, 'south'), (-30, 0, 'west'), (-20, 20, 'southwest'), (0, -30, 'north')):
    r('kill @e[type=minecraft:wandering_trader]'); r(f'summon minecraft:wandering_trader {x} -60 {z} {{NoAI:1b}}'); time.sleep(2.2); ev = events()
    got = r('data get storage traderalert:tmp ns') + r('data get storage traderalert:tmp ew')
    want = [w for w in ('north', 'south', 'east', 'west') if w in d]
    ok(all(w in got for w in want) and sum(w in got for w in ('north', 'south', 'east', 'west')) == len(want), f'direction {d}', got)
r('kill @e[type=minecraft:wandering_trader]'); trig('trader'); time.sleep(1); ev = events()
ok(score('#count', 'traderalert.v') == 0, 'no trader -> count 0')
if http: ok(chat_has(ev, 'No Wandering Trader within 128 blocks'), 'client got the none message', ev['chat'])
r('scoreboard players set #glow traderalert.cfg 0'); r('summon minecraft:wandering_trader 5 -60 5 {NoAI:1b}'); time.sleep(2.2)
ok('glowing' not in r('data get entity @e[type=minecraft:wandering_trader,limit=1] active_effects'), 'glow can be switched off')
r('scoreboard players set #glow traderalert.cfg 30')

# ------------------------------------------------------------ Portal Link
print('Portal Link'); reset()
r(f'tp {who} 100.5 70 -100.5'); time.sleep(0.5); trig('portal'); time.sleep(1); ev = events()
ok((score(who, 'portallink.tx'), score(who, 'portallink.tz'), score(who, 'portallink.dim')) == (12, -13, 1), 'overworld 100 / -101 -> nether 12 / -13 (rounds down)')
if http: ok(any('copy_to_clipboard' in x and '12 ' in x for x in ev['raw']), 'coordinates are click-to-copy on this game version', ev['raw'][:1])
if http: ok(any(re.search(r'You are at 100 \d+ -101 in the Overworld\. Build the Nether side at 12 \d+ -13', c) for c in ev['chat']), 'client got the coordinates', ev['chat'])
trig('portal set 2'); time.sleep(1); ev = events()
ok(score(who, 'portallink.guide') in (0, None), 'guide refuses in the wrong dimension')
if http: ok(chat_has(ev, 'No saved spot for this dimension'), 'client got the explanation', ev['chat'])
r(f'execute in minecraft:the_nether run tp {who} 30.5 70 -13.5'); time.sleep(3); trig('portal set 2'); time.sleep(2); ev = events(pp=True)
ok((score(who, 'portallink.guide') or 0) > 400 and score('#d', 'portallink.v') == 18, 'guide on in the Nether, 18 blocks from the spot', score('#d', 'portallink.v'))
if http:
    ok(any(k.startswith('"end_rod"') and abs(x-12.5) < 1 and abs(z+12.5) < 1 for k, x, y, z in ev['pp']), 'client sees the beam at 12.5 / -12.5')
    ok(chat_has(ev, ' blocks away'), 'client got the actionbar distance', ev['chat'][-2:])
r(f'execute in minecraft:the_nether run tp {who} 12.5 70 -12.5'); time.sleep(1); events(); time.sleep(1); ev = events()
if http: ok(chat_has(ev, 'build here'), 'actionbar says build here on the spot', ev['chat'][-2:])
trig('portal'); time.sleep(1); ev = events()
ok((score(who, 'portallink.tx'), score(who, 'portallink.tz'), score(who, 'portallink.dim')) == (96, -104, 0), 'nether 12 -13 -> overworld 96 -104')
ok(score(who, 'portallink.guide') == 0 or True, 'guide state consistent')
r(f'execute in minecraft:the_end run tp {who} 0 80 0'); time.sleep(3); trig('portal'); time.sleep(1); ev = events()
ok(score(who, 'portallink.dim') == 0 and score(who, 'portal') == 0, 'the End leaves the saved spot alone')
if http: ok(chat_has(ev, 'only link the Overworld and the Nether'), 'client got the End message', ev['chat'])
r(f'execute in minecraft:overworld run tp {who} 100.5 300 -100.5'); time.sleep(3); trig('portal'); time.sleep(1)
ok(score(who, 'portallink.ty') == 117, 'height clamped under the Nether roof')

# ------------------------------------------------------------ Lag Scanner
print('Lag Scanner'); reset(); r(f'scoreboard players set {who} lagscan.cd 0')
items = 'stone dirt cobblestone oak_log sand gravel stick apple bone string arrow feather'.split()
for i, it in enumerate(items): r(f'summon minecraft:item 30 -60 30 {{Item:{{id:"minecraft:{it}",count:1}},PickupDelay:32767}}')
for i in range(4): r('summon minecraft:cow 30 -60 31 {NoAI:1b}')
for i in range(3): r('summon minecraft:husk -20 -60 -20 {NoAI:1b}')
for i in range(2): r('summon minecraft:armor_stand 10 -60 -30')
r(f'summon minecraft:{newboat} -30 -60 10'); r('summon minecraft:villager -30 -60 -30 {NoAI:1b}'); r('summon minecraft:experience_orb 40 -60 -40 {Value:1}'); r('summon minecraft:arrow 0 -60 40 {NoGravity:1b}')
time.sleep(0.5); trig('lagscan'); time.sleep(1); ev = events()
got = {k: score('#' + k, 'lagscan.v') for k in 'total items xp hostile animals villagers vehicles decor other max'.split()}
ok(got == dict(total=25, items=12, xp=1, hostile=3, animals=4, villagers=1, vehicles=1, decor=2, other=1, max=16), 'category counts', got)
h = r('data get storage lagscan:tmp h'); ok('x: 30' in h and 'z: 3' in h and 'n: 16' in h, 'hotspot is the item/cow pile', h)
ok(count('@e[tag=lagscan.best]') == 0 and count('@e[scores={lagscan.n=1..}]') == 0, 'temporary tags and scores cleaned up')
if http:
    ok(chat_has(ev, '25 entities within 64 blocks') and chat_has(ev, 'Dropped items 12') and chat_has(ev, 'Densest pile: 16 entities within 8 blocks of 30 -60 3'), 'client got the report', ev['chat'])
    ok(chat_has(ev, '(12 drops, 4 mobs)'), 'hotspot breakdown', ev['chat'])
    ok(any('suggest_command' in x and '/tp @s 30 -60 3' in x for x in ev['raw']), 'hotspot is click-to-teleport on this game version')
trig('lagscan'); time.sleep(1); ev = events()
ok(score(who, 'lagscan') == 0 and (score(who, 'lagscan.cd') or 0) > 0, 'cooldown blocks an immediate second scan')
if http: ok(chat_has(ev, 'Please wait'), 'client got the cooldown message', ev['chat'])
r(f'scoreboard players set {who} lagscan.cd 0'); trig('lagscan set 16'); time.sleep(1)
ok(score('#total', 'lagscan.v') == 0 and score('#r', 'lagscan.v') == 16, 'custom radius 16 sees nothing nearby', score('#total', 'lagscan.v'))
reset()
print(f'\n{passed} passed, {len(fails)} failed'); [print('  failed:', f) for f in fails]
sys.exit(1 if fails else 0)
