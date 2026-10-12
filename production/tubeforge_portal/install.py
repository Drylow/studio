"""Install the gateway and native page into an existing Kanye Tools checkout.

Preserve all other tools. Back up changed files; reuse portal auth unmodified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from datetime import datetime, timezone

ENTRY = '<a class="rtool" href="/2d" aria-label="2D Studio" data-nav="/2d"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M3 9h18M8 4l-2 5M14 4l-2 5"/></svg><span class="tip">2D Studio</span></a>'


def install(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not (destination/'server.js').is_file() or not (destination/'public/sleep.html').is_file():
        raise ValueError('Choose the existing tools.kanye.studio checkout')
    plans = {}
    server = (destination/'server.js').read_text(encoding='utf-8')
    if "import mount2D from './routes/2d.js'" not in server:
        marker = "import mountSleep from './routes/sleep.js'"
        if server.count(marker) != 1: raise ValueError('Portal import target changed')
        server = server.replace(marker, marker+"\nimport mount2D from './routes/2d.js'",1)
    if 'mount2D(app, auth)' not in server:
        marker = 'mountSleep(app, auth, logDiscord)'
        if server.count(marker) != 1: raise ValueError('Portal route mount target changed')
        server = server.replace(marker,marker+'\nmount2D(app, auth)',1)
    page = "app.get('/2d', (req, res) => res.sendFile(path.join(__dirname, 'public', '2d.html')))"
    if page not in server:
        marker = "app.get('/sleep', (req, res) => res.sendFile(path.join(__dirname, 'public', 'sleep.html')))"
        if server.count(marker) != 1: raise ValueError('Portal page route target changed')
        server = server.replace(marker,marker+'\n'+page,1)
    plans[destination/'server.js'] = server.encode()
    for file in (destination/'public').glob('*.html'):
        text = file.read_text(encoding='utf-8')
        if '<nav class="rail"' not in text: continue
        if 'href="/2d"' not in text:
            text,count = re.subn(r'(<a class="rtool" href="/sleep".*?</a>)',lambda m:m.group(1)+'\n  '+ENTRY,text,count=1,flags=re.S)
            if count != 1: raise ValueError('Nav target changed: '+file.name)
        if file.name == 'index.html' and "['/2d','" not in text:
            marker = "  ['/sleep','sleep','Sleep Studio','Long-form sleep videos people fall asleep to.',[]],"
            if text.count(marker) != 1: raise ValueError('Hub launcher target changed')
            text = text.replace(marker,marker+"\n  ['/2d','scripts','2D Studio','Create illustrated videos with consistent characters and shared styles.',[]],",1)
        plans[file] = text.encode()
    plans[destination/'routes/2d.js'] = (source/'production/tubeforge_portal/2d.js').read_bytes()
    plans[destination/'public/2d.html'] = (source/'production/tubeforge_portal/2d.html').read_bytes()
    for ext in ('js','css'):
        plans[destination/f'public/2d-workspace.{ext}'] = (source/f'production/tubeforge_support/workspace.{ext}').read_bytes()
    changed = {file:data for file,data in plans.items() if not file.exists() or file.read_bytes()!=data}
    backup = destination/'backups'/('before-tubeforge-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True,exist_ok=True)
    existed=[]
    for file,data in changed.items():
        relative = file.relative_to(destination)
        if file.exists():
            saved=backup/relative;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,saved);existed.append(relative.as_posix())
        file.parent.mkdir(parents=True,exist_ok=True)
        # server.js is a file bind mount: overwrite its inode, never replace it.
        file.write_bytes(data)
    (backup/'manifest.json').write_text(json.dumps({'changed':[p.relative_to(destination).as_posix() for p in changed],'existed':existed},indent=2)+'\n')
    print(json.dumps({'changed':len(changed),'backup':str(backup),'portal_auth_changed':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('destination',type=Path)
    parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[2])
    args=parser.parse_args();install(args.source,args.destination)
