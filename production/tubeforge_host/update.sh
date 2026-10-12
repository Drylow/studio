#!/bin/sh
# Build an immutable Git release, back up private state, then replace only TubeForge.
set -eu
home="${TUBEFORGE_HOME:-/opt/tubeforge}"
test "$home" = /opt/tubeforge || { printf 'Set up and review a different host path explicitly.\n' >&2; exit 1; }
repo="$home/repository"
git -C "$repo" fetch origin main
revision=$(git -C "$repo" rev-parse origin/main)
release="$home/releases/$revision"
mkdir -p "$home/releases" "$home/backups"
if [ ! -d "$release" ]; then
    git -C "$repo" worktree add --detach "$release" "$revision"
fi
tag="drylow-tubeforge:$revision"
docker build -t "$tag" -f "$release/production/tubeforge_host/Dockerfile" "$release"
docker exec drylow-tubeforge python -c '
import pathlib,json,sys
busy=[]
for p in pathlib.Path("data/projects").glob("*/project.json"):
 d=json.loads(p.read_text()); batch=d.get("workspace_batch",{})
 if any(s.get("state")=="running" for s in d.get("steps",{}).values()) or batch.get("state") in ("running","stopping"):
  busy.append(d["id"])
if busy: sys.exit("Wait for active jobs before updating TubeForge")
'
stamp=$(date +%Y%m%d-%H%M%S)
umask 077
tar -C "$home" -cf - data config compose.env | gzip -1 > "$home/backups/before-update-$stamp.tar.gz"
cp "$home/compose.env" "$home/backups/compose-$stamp.env"
python3 - "$home/compose.env" "$tag" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); rows=[s for s in p.read_text().splitlines() if not s.startswith('TUBEFORGE_IMAGE=')]
rows.append('TUBEFORGE_IMAGE='+sys.argv[2]); p.write_text('\n'.join(rows)+'\n')
PY
docker compose --project-name tubeforge --env-file "$home/compose.env" \
    -f "$release/production/tubeforge_host/compose.yaml" up -d --no-deps tubeforge
docker inspect drylow-tubeforge --format '{{.State.Status}}'
printf 'TubeForge updated to %s. Check HTTPS, login and project media before further work.\n' "$revision"
printf 'Previous image configuration: %s/backups/compose-%s.env\n' "$home" "$stamp"
