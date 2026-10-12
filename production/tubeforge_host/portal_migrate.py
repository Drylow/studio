"""Align personal history with the existing portal without changing scripts or media."""
import argparse
import json
import os
from pathlib import Path
import shutil


def migrate(home):
    home = Path(home).resolve()
    primary = 'admin'
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
        changed = not project.get('owner_id')
        if changed:
            project['owner_id'] = primary
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
    print(f'Portal migration: {count} existing videos assigned to {primary}; media preserved.')



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('home', type=Path)
    migrate(parser.parse_args().home)
