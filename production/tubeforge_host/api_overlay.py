"""Scoped API release from the running application, preserving unrelated hotfixes.

Invoked by update.sh --api-overlay DIRECTORY. No project migration or generation.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs).stdout


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if sys.platform != 'linux':
        raise SystemExit('Deploy on the VPS only')
    patch = Path(sys.argv[1]).resolve()
    if not patch.is_relative_to(Path('/opt/tubeforge/api-patches')):
        raise SystemExit('Patch must be staged under /opt/tubeforge/api-patches')
    names = {'app/forge_api.py', 'app/forge_migrations.py', 'app/workspace_generation.py', 'app/forge_docs/LLM.txt'}
    expected = json.loads((patch / 'expected-files.json').read_text())
    assert set(expected) == names - {'app/forge_migrations.py'}
    assert {p.relative_to(patch).as_posix() for p in (patch/'app').rglob('*') if p.is_file()} == names
    info = json.loads(run(['docker', 'inspect', 'drylow-tubeforge']))[0]
    compose_files = info['Config']['Labels']['com.docker.compose.project.config_files'].split(',')
    project = info['Config']['Labels']['com.docker.compose.project']
    assert project == 'tubeforge'
    assert all(Path(f).resolve().is_relative_to(Path('/opt/tubeforge')) for f in compose_files)
    stamp = str(int(time.time()))
    release = Path('/opt/tubeforge/api-releases') / ('model-migration-' + stamp)
    release.mkdir(parents=True, exist_ok=False)
    run(['docker', 'cp', 'drylow-tubeforge:/opt/studio/work/TubeForge/app', str(release/'app')])
    for name, value in expected.items():
        assert digest(release/name) == value, 'Live source changed: ' + name
    shutil.make_archive(str(release/'app-before'), 'tar', root_dir=release, base_dir='app')
    for name in names:
        dest=release/name; dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(patch/name,dest)
    for name in names:
        if name.endswith('.py'):
            compile((release/name).read_text(),name,'exec')
    tag='drylow-tubeforge:model-migration-'+stamp
    assert json.loads(run(['docker','image','inspect',info['Config']['Image']]))[0]['Id'] == info['Image']
    (release/'Dockerfile').write_text('FROM '+info['Config']['Image']+'\nCOPY --chown=10001:10001 app /opt/studio/work/TubeForge/app\n')
    run(['docker','build','-t',tag,str(release)])
    # Recheck just before replacement. Background production container is not touched.
    busy_code="""import json,sys
from pathlib import Path
busy=[]
for f in Path('data/projects').glob('*/project.json'):
 p=json.loads(f.read_text())
 if any(s.get('state') in ('running','queued') for s in p.get('steps',{}).values()) or any((p.get(k)or{}).get('state')in('running','queued','stopping') for k in ('workspace_batch','workspace_external_execution','workspace_generation')):busy.append(p['id'])
if busy:sys.exit('Active project jobs; deployment deferred')
"""
    run(['docker','exec','-i','-w','/opt/studio/work/TubeForge','drylow-tubeforge','python','-'], input=busy_code)
    current = run(['docker','exec','-i','-w','/opt/studio/work/TubeForge','drylow-tubeforge','python','-'],input="import hashlib,json\nfrom pathlib import Path\nprint(json.dumps({n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in "+repr(list(expected))+"}))\n")
    assert json.loads(current)==expected, 'Source changed during build'
    env_path=Path('/opt/tubeforge/compose.env')
    backup=release/'compose-before.env';shutil.copy2(env_path,backup);os.chmod(backup,0o600)
    old=env_path.read_text()
    new='\n'.join(l for l in old.splitlines() if not l.startswith('TUBEFORGE_IMAGE='))+'\nTUBEFORGE_IMAGE='+tag+'\n'
    env_path.write_text(new)
    compose=['docker','compose','--project-name',project,'--env-file',str(env_path)]
    for f in compose_files:compose.extend(['-f',f])
    command=compose+['up','-d','--no-deps','tubeforge']
    try:
        run(command)
        ok=False
        for _ in range(12):
            try:
                run(['docker','exec','drylow-tubeforge','python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8766/healthz',timeout=5)"])
                ok=True;break
            except subprocess.CalledProcessError:time.sleep(3)
        if not ok:raise RuntimeError('New API did not become healthy')
    except Exception:
        env_path.write_text(old);run(command)
        raise
    result={'state':'deployed','image':tag,'previous_image':info['Config']['Image'],
            'release':str(release),'files':{n:digest(release/n)for n in names},
            'production_container_restarted':False,'data_migrated':False}
    (release/'deployment.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':
    main()
