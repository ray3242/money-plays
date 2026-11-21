#!/usr/bin/env python3
"""Package every pack in packs/ as a datapack .zip and as a mod .jar (Fabric/Quilt + NeoForge).

The jar holds the same data files plus loader metadata; there is no Java code in it.
usage: python3 build.py   ->  dist/
"""
import json, os, zipfile, pathlib
ROOT = pathlib.Path(__file__).parent
VERSION = '1.0.0'
META = {
    'jobsite-finder': ('jobsite_finder', 'Job Site Finder', 'Shows which workstation and bed every villager owns, with particle lines only you can see.'),
    'trader-alert': ('trader_alert', 'Trader Alert', 'Tells you when a Wandering Trader arrives, where it is, and how long it stays.'),
    'portal-link': ('portal_link', 'Portal Link', 'Gives the matching Nether/Overworld portal coordinates and a guide beam to the spot.'),
    'lag-scanner': ('lag_scanner', 'Lag Scanner', 'Counts the entities around you by kind and points at the densest pile.'),
}
FIXED = (2026, 1, 1, 0, 0, 0)  # reproducible archives
def add(z, name, data):
    zi = zipfile.ZipInfo(name, FIXED); zi.compress_type = zipfile.ZIP_DEFLATED; zi.external_attr = 0o644 << 16
    z.writestr(zi, data)
def files(pack):
    for p in sorted(pack.rglob('*')):
        if p.is_file() and p.name not in ('LISTING.md',) and not p.name.startswith('.'):
            yield p.relative_to(pack).as_posix(), p.read_bytes()
def main():
    dist = ROOT / 'dist'; dist.mkdir(exist_ok=True)
    lic = (ROOT / 'LICENSE').read_bytes()
    for pid, (modid, name, desc) in META.items():
        pack = ROOT / 'packs' / pid
        fs = list(files(pack))
        with zipfile.ZipFile(dist / f'{pid}-{VERSION}-datapack.zip', 'w') as z:
            for n, d in fs: add(z, n, d)
            add(z, 'LICENSE', lic)
        with zipfile.ZipFile(dist / f'{pid}-{VERSION}-mod.jar', 'w') as z:
            add(z, 'META-INF/MANIFEST.MF', 'Manifest-Version: 1.0\r\n')
            for n, d in fs: add(z, n, d)
            add(z, 'LICENSE', lic)
            add(z, 'fabric.mod.json', json.dumps({
                'schemaVersion': 1, 'id': modid, 'version': VERSION, 'name': name, 'description': desc,
                'authors': ['ray3242'], 'license': 'MIT', 'icon': 'pack.png', 'environment': '*',
                'contact': {'sources': 'https://github.com/ray3242/money-plays/tree/main/curseforge-mods'},
                'depends': {'minecraft': '>=1.21', 'fabric-api': '*'}}, indent=2))
            add(z, 'META-INF/neoforge.mods.toml', f'''modLoader="lowcodefml"
loaderVersion="[1,)"
license="MIT"

[[mods]]
modId="{modid}"
version="{VERSION}"
displayName="{name}"
logoFile="pack.png"
authors="ray3242"
description="{desc}"

[[dependencies.{modid}]]
modId="minecraft"
type="required"
versionRange="[1.21,)"
ordering="NONE"
side="BOTH"
''')
        print('built', pid)
if __name__ == '__main__': main()
