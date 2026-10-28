#!/bin/bash
# Serveur de rendu des timelapses 3D Keystone sur ce VPS. À lancer en root.
# Fichier généré par production/vps_citylapse_setup.py : ne pas modifier à la main.
set -e
DIR=/opt/drylow-city
mkdir -p "$DIR"
cat > "$DIR/worker.mjs" <<'DRYLOW_CITY_EOF'
// Serveur de rendu Keystone Timelapse sur le VPS (installé par production/vps_citylapse_setup.sh, Docker + HTTPS).
// Pas de carte graphique : WebGL logiciel (SwiftShader), une ville rendue par morceaux par plusieurs navigateurs
// (tools/cloud_render.mjs), puis assemblage avec la musique. Chaque requête porte X-Worker-Token.
//   GET    /status                              {busy, job, stage, parts, total, error, log, disk}
//   PUT    /job?name=N&slug=S[&fps=30&workers=6&ss=1]  corps = .tgz contenant citylapse/ (shared, tools, cities/S)
//                                               → rendu lancé ; une seule vidéo à la fois
//   GET    /file?name=N&path=P                  un fichier du job (ex. citylapse/cities/S/renders/S.mp4, render.log)
//   DELETE /job?name=N                          arrête et efface tout le dossier (à faire après chaque livraison)
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';

const DATA = process.env.DATA_DIR || '/data', TOKEN = process.env.WORKER_TOKEN || '';
const JOBS = path.join(DATA, 'jobs'), TL = process.env.TL_DIR || '/opt/tl';
fs.mkdirSync(JOBS, { recursive: true });
const chrome = () => { const b = '/ms-playwright';
  const d = fs.existsSync(b) ? fs.readdirSync(b).find(x => x.startsWith('chromium_headless_shell-')) : null;
  return d ? `${b}/${d}/chrome-linux/headless_shell` : process.env.CHROME; };
const st = { busy: false, job: null, slug: null, stage: 'idle', error: null, total: 0 };
let child = null;

function run(name, slug, o) {
  const d = path.join(JOBS, name), cl = path.join(d, 'citylapse'), log = fs.openSync(path.join(d, 'render.log'), 'a');
  const env = { ...process.env, CHROME: chrome(), FFMPEG: 'ffmpeg' };
  const tools = path.join(cl, 'tools', 'cloud_render.mjs');
  const step = (args, next) => {
    child = spawn('node', [tools, slug, ...args], { cwd: cl, env, stdio: ['ignore', log, log] });
    child.on('exit', code => { child = null;
      if (code !== 0) { st.error = `rendu : code ${code} (voir render.log)`; st.busy = false; st.stage = 'failed'; return; }
      next(); });
  };
  st.stage = 'render';
  step(['--fps', o.fps, '--workers', o.workers, '--ss', o.ss], () => {
    st.stage = 'join';
    step(['--join'], () => { st.stage = 'done'; st.busy = false; });
  });
}

function parts(name, slug) {
  const p = path.join(JOBS, name, 'citylapse', 'cities', slug, 'renders', 'cloud');
  try { return fs.readdirSync(p).filter(f => /^part_\d+\.mp4$/.test(f)).length; } catch { return 0; }
}
function tail(f, n = 30) { try { return fs.readFileSync(f, 'utf8').split('\n').slice(-n); } catch { return []; } }
const send = (r, code, obj) => { const b = Buffer.from(JSON.stringify(obj)); r.writeHead(code, { 'content-type': 'application/json', 'content-length': b.length }); r.end(b); };
const okName = n => /^[A-Za-z0-9._-]{1,80}$/.test(n || '');

http.createServer((q, r) => {
  if (TOKEN && q.headers['x-worker-token'] !== TOKEN) return send(r, 401, { error: 'token' });
  const u = new URL(q.url, 'http://x'), name = u.searchParams.get('name');
  if (q.method === 'GET' && u.pathname === '/status') {
    const df = spawnSync('df', ['-h', DATA], { encoding: 'utf8' }).stdout.split('\n')[1] || '';
    return send(r, 200, { ...st, parts: st.job ? parts(st.job, st.slug) : 0,
      log: st.job ? tail(path.join(JOBS, st.job, 'render.log')) : [], disk: df.trim(), jobs: fs.readdirSync(JOBS) });
  }
  if (q.method === 'PUT' && u.pathname === '/job') {
    const slug = u.searchParams.get('slug');
    if (!okName(name) || !okName(slug)) return send(r, 400, { error: 'name/slug' });
    if (st.busy) return send(r, 409, { error: 'busy', job: st.job });
    const d = path.join(JOBS, name); fs.rmSync(d, { recursive: true, force: true }); fs.mkdirSync(d, { recursive: true });
    const tgz = path.join(d, 'job.tgz'), out = fs.createWriteStream(tgz);
    q.pipe(out); out.on('finish', () => {
      const x = spawnSync('tar', ['-xzf', tgz, '-C', d, '--no-same-owner'], { encoding: 'utf8' }); fs.rmSync(tgz, { force: true });
      if (x.status !== 0 || !fs.existsSync(path.join(d, 'citylapse', 'cities', slug, 'scene.js'))) return send(r, 400, { error: 'archive', detail: x.stderr });
      // cloud_render.mjs charge playwright-core depuis ../timelapse_engine/node_modules
      fs.symlinkSync(TL, path.join(d, 'timelapse_engine'));
      const DUR = +(/DUR = (\d+(\.\d+)?)/.exec(fs.readFileSync(path.join(d, 'citylapse', 'cities', slug, 'scene.js'), 'utf8')) || [0, 0])[1];
      Object.assign(st, { busy: true, job: name, slug, error: null, total: Math.ceil(DUR / 20) });
      run(name, slug, { fps: u.searchParams.get('fps') || '30', workers: u.searchParams.get('workers') || '6', ss: u.searchParams.get('ss') || '1' });
      send(r, 200, { ok: true, total: st.total });
    });
    return;
  }
  if (q.method === 'GET' && u.pathname === '/file') {
    const rel = u.searchParams.get('path') || '';
    if (!okName(name) || rel.includes('..')) return send(r, 400, { error: 'path' });
    const f = path.join(JOBS, name, rel);
    if (!fs.existsSync(f) || !fs.statSync(f).isFile()) return send(r, 404, { error: 'absent' });
    r.writeHead(200, { 'content-type': 'application/octet-stream', 'content-length': fs.statSync(f).size });
    return fs.createReadStream(f).pipe(r);
  }
  if (q.method === 'DELETE' && u.pathname === '/job') {
    if (!okName(name)) return send(r, 400, { error: 'name' });
    if (st.job === name) { if (child) child.kill('SIGKILL'); spawnSync('pkill', ['-f', 'headless_shell']); Object.assign(st, { busy: false, job: null, slug: null, stage: 'idle', error: null }); }
    fs.rmSync(path.join(JOBS, name), { recursive: true, force: true });
    return send(r, 200, { ok: true });
  }
  send(r, 404, { error: 'route' });
}).listen(+(process.env.PORT || 8000), '0.0.0.0');
console.log('citylapse worker ready');
DRYLOW_CITY_EOF
[ -s "$DIR/token" ] || (openssl rand -hex 24 2>/dev/null || head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n') > "$DIR/token"
TOKEN=$(cat "$DIR/token")
IP=$(curl -fs4 https://api.ipify.org || curl -fs4 https://ifconfig.me)
HOST=${DOMAIN:-city.$(echo "$IP" | tr . -).sslip.io}
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
IMAGE=mcr.microsoft.com/playwright:v1.48.2-jammy
docker pull -q $IMAGE >/dev/null
docker rm -f drylow-city >/dev/null 2>&1 || true
RUN="(command -v ffmpeg >/dev/null || (apt-get update -qq && apt-get install -y -qq --no-install-recommends ffmpeg >/dev/null)) && mkdir -p /opt/tl && cd /opt/tl && ([ -d node_modules/playwright-core ] || npm i -s --no-audit --no-fund playwright-core@1.48.2 >/dev/null) && exec node /w.mjs"
BASE=(-d --name drylow-city --restart unless-stopped -e WORKER_TOKEN="$TOKEN" -e DATA_DIR=/data --shm-size=2g
      -v "$DIR/worker.mjs:/w.mjs:ro" -v drylow-city:/data -v drylow-city-tl:/opt/tl)
if docker ps --format '{{.Names}}' | grep -qx coolify-proxy; then
  docker run "${BASE[@]}" --network coolify \
    -l traefik.enable=true \
    -l "traefik.http.routers.drylow-city.rule=Host(\`$HOST\`)" \
    -l traefik.http.routers.drylow-city.entrypoints=https \
    -l traefik.http.routers.drylow-city.tls=true \
    -l traefik.http.routers.drylow-city.tls.certresolver=letsencrypt \
    -l traefik.http.services.drylow-city.loadbalancer.server.port=8000 \
    $IMAGE sh -c "$RUN"
elif docker ps --format '{{.Names}}' | grep -qx drylow-caddy; then
  # le Caddy déjà là (serveur de rendu / d'actu) : on lui ajoute cette adresse, certificats gardés
  docker run "${BASE[@]}" --network drylow $IMAGE sh -c "$RUN"
  CF=$(docker inspect drylow-caddy --format '{{range .Mounts}}{{if eq .Destination "/etc/caddy/Caddyfile"}}{{.Source}}{{end}}{{end}}')
  if [ -z "$CF" ]; then
    # Caddy lancé en « reverse-proxy --from A --to B » : on écrit un Caddyfile avec les deux
    CF="$DIR/Caddyfile"
    ARGS=$(docker inspect drylow-caddy --format '{{join .Args " "}}')
    FROM=$(echo "$ARGS" | sed -n 's/.*--from \([^ ]*\).*/\1/p'); TO=$(echo "$ARGS" | sed -n 's/.*--to \([^ ]*\).*/\1/p')
    [ -n "$FROM" ] && printf '%s {\n\treverse_proxy %s\n}\n' "$FROM" "$TO" > "$CF" || : > "$CF"
  fi
  grep -q "drylow-city:8000" "$CF" || printf '%s {\n\treverse_proxy drylow-city:8000\n}\n' "$HOST" >> "$CF"
  docker rm -f drylow-caddy >/dev/null
  docker run -d --name drylow-caddy --restart unless-stopped --network drylow -p 80:80 -p 443:443 \
    -v drylow-caddy:/data -v "$CF:/etc/caddy/Caddyfile:ro" caddy:2
else
  if ss -ltn 2>/dev/null | grep -qE ':(80|443)\s' || docker ps --format '{{.Ports}}' | grep -qE ':(80|443)->'; then
    echo "!! Les ports 80/443 sont déjà pris : envoie ceci à Claude :"
    ss -ltnp | grep -E ':(80|443)\s'; docker ps --format '{{.Names}} {{.Ports}}' | grep -E ':(80|443)->'
    exit 1
  fi
  command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q active && ufw allow 80/tcp && ufw allow 443/tcp || true
  docker network create drylow >/dev/null 2>&1 || true
  docker run "${BASE[@]}" --network drylow $IMAGE sh -c "$RUN"
  docker run -d --name drylow-caddy --restart unless-stopped --network drylow -p 80:80 -p 443:443 \
    -v drylow-caddy:/data caddy:2 caddy reverse-proxy --from "$HOST" --to drylow-city:8000
fi
echo "Démarrage (1 à 3 min)…"
OK=""
for i in $(seq 1 40); do
  curl -fs -H "X-Worker-Token: $TOKEN" "https://$HOST/status" >/dev/null 2>&1 && OK=1 && break
  sleep 6
done
echo
echo "=== À envoyer à Claude ==="
echo "CITY_WORKER_URL=https://$HOST"
echo "CITY_WORKER_TOKEN=$TOKEN"
echo "Serveur : ${OK:+OK}${OK:-pas de réponse (envoie aussi : docker logs drylow-city | tail -30)}"
echo "Cœurs : $(nproc) — disque libre : $(df -h / | awk 'NR==2{print $4}')"
