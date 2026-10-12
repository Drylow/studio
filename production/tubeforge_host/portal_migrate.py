"""Align personal history with the existing portal without changing scripts or media."""
import argparse
import json
import os
from pathlib import Path
import shutil


def migrate(home):
    home = Path(home).resolve()
    private = home / 'config/worker.env'
    configured = {}
    if private.exists():
        configured = dict(line.split('=',1) for line in private.read_text().splitlines() if '=' in line and not line.startswith('#'))
    primary = os.getenv('TUBEFORGE_DEFAULT_OWNER') or configured.get('TUBEFORGE_DEFAULT_OWNER') or 'admin'
    marker = home / 'data/workspace-membership.json'
    first_portal_mapping = not marker.exists()

    names = {'survivor-patch': ('Patch Survives – cartoon simple', 'Patch Survives — Simple cartoon'), 'survivor-alien-aftermath': ('Alien Aftermath – cartoon simple', 'Alien Aftermath — Simple cartoon'), 'fictional-god-of-war': ('God of War - tetes blanches', 'God of War — White round heads'), 'fictional-naruto': ('Naruto - tetes blanches', 'Naruto — White round heads'), 'fictional-pokemon': ('Pokemon - tetes blanches', 'Pokémon — White round heads')}
    for file in (home / "data/styles").glob("*/style.json"):
        style = json.loads(file.read_text(encoding="utf-8"))
        old, new = names.get(style.get("id"), (None, None))
        if old and style.get("name", "").replace("—", "–") == old:
            style["name"] = new
            file.write_text(json.dumps(style,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    count = 0
    for file in (home / 'data/projects').glob('*/project.json'):
        project = json.loads(file.read_text(encoding='utf-8'))
        changed = not project.get('owner_id') or first_portal_mapping and project.get('owner_id') == 'admin'
        if changed:
            project['owner_id'] = primary
            project['owner_name'] = 'Studio owner'
        old, new = names.get(project.get('style_id'), (None, None))
        if old and project.get('style_name', '').replace('—', '–') == old:
            project['style_name'] = new
            changed = True
        if changed:
            temp = file.with_suffix('.tmp')
            temp.write_text(json.dumps(project, ensure_ascii=False, indent=2) + '\n',encoding='utf-8')
            temp.replace(file)
            if os.name != 'nt' and os.geteuid() == 0:
                os.chown(file,10001,10001)
            count += 1
    marker.parent.mkdir(parents=True,exist_ok=True)
    if first_portal_mapping:
        marker.write_text(json.dumps({'portal_owner_id':primary,'legacy_owner_migrated':True},indent=2)+'\n',encoding='utf-8')
        if os.name != 'nt' and os.geteuid() == 0:os.chown(marker,10001,10001)
    print(f'Portal migration: {count} existing videos assigned to {primary}; media preserved.')



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('home', type=Path)
    migrate(parser.parse_args().home)
