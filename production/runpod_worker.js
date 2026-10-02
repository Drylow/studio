// Serveur d'une machine de rendu RunPod (format Histoire). Aucune dépendance : node + tar + curl de l'image.
// Lancé au démarrage du pod (services/runpod_render.py) ; écoute le port 8000 (proxy https://<pod>-8000.proxy.runpod.net).
//   PUT  /bundle?part=N     morceau N du paquet (moteur + médias), en .tgz découpé (le proxy limite la taille d'un envoi)
//   POST /unpack?parts=K    réassemble les K morceaux et décompresse dans /work
//   POST /fetch?from=URL    récupère le paquet déjà reçu par un autre pod (GET URL/bundle.tgz)
//   GET  /bundle.tgz        le paquet reçu, pour les autres pods
//   POST /render?chunks=3,4,9&frames=900&audio=0|1   rend ces morceaux (render.mjs --chunk-dir)
//   GET  /status            {ready, stage, progress, files, error}
//   GET  /file/NOM          un morceau rendu (part_XXX.mp4) ou audio.wav
const http = require('http');
const fs = require('fs');
const path = require('path');
const {spawn, spawnSync} = require('child_process');

const W = process.env.WORK_DIR || '/work';
const CH = path.join(W, 'chunks');
const st = {ready: false, stage: 'idle', progress: 0, error: null, log: []};
fs.mkdirSync(path.join(W, 'parts'), {recursive: true});

function note(s) {
  st.log.push(String(s).slice(0, 300));
  if (st.log.length > 30) st.log.shift();
}

function run(cmd, args, opts = {}) {
  return new Promise((resolve) => {
    const p = spawn(cmd, args, Object.assign({stdio: ['ignore', 'pipe', 'pipe']}, opts));
    p.stdout.on('data', (d) => {
      for (const line of String(d).split('\n')) {
        if (!line.startsWith('{')) continue;
        try {
          const ev = JSON.parse(line);
          if (ev.stage === 'render') st.progress = ev.progress;
          if (ev.stage) st.stage = ev.stage;
        } catch (e) { /* ligne partielle */ }
      }
    });
    p.stderr.on('data', (d) => note(d));
    p.on('close', (code) => resolve(code));
  });
}

function browser() {
  const r = spawnSync('bash', ['-c', 'ls -d /ms-playwright/chromium_headless_shell-*/chrome-*/headless_shell 2>/dev/null | tail -1']);
  return String(r.stdout).trim();
}

async function unpack(bundle) {
  st.stage = 'unpack';
  const code = await run('tar', ['xzf', bundle, '-C', W]);
  if (code !== 0) throw new Error('tar ' + code);
  st.stage = 'npm';
  const npm = await run('npm', ['install', '--no-audit', '--no-fund', '--loglevel=error'], {cwd: path.join(W, 'engine')});
  if (npm !== 0) throw new Error('npm install ' + npm);
  st.ready = true;
  st.stage = 'ready';
}

async function render(q) {
  const args = [path.join(W, 'engine', 'render.mjs'), '--project', path.join(W, 'media'), '--chunk-dir', CH,
    '--chunk-frames', q.get('frames') || '900', '--concurrency', String(q.get('conc') || Math.max(1, require('os').cpus().length - 1))];
  if (q.get('chunks')) args.push('--chunks', q.get('chunks'));
  if (q.get('audio') === 'only') args.push('--audio-only');
  else if (q.get('audio') !== '1') args.push('--no-audio');
  st.stage = 'bundle';
  const code = await run('node', args, {cwd: path.join(W, 'engine'), env: Object.assign({}, process.env, {REMOTION_BROWSER: browser()})});
  st.stage = code === 0 ? 'done' : 'failed';
  if (code !== 0) st.error = 'render ' + code;
}

function body(req, dest) {
  return new Promise((resolve, reject) => {
    const out = fs.createWriteStream(dest);
    req.pipe(out);
    out.on('finish', resolve);
    out.on('error', reject);
  });
}

http.createServer(async (req, res) => {
  const u = new URL(req.url, 'http://pod');
  const send = (code, obj) => {
    res.writeHead(code, {'Content-Type': 'application/json'});
    res.end(JSON.stringify(obj));
  };
  try {
    if (req.method === 'PUT' && u.pathname === '/bundle') {
      await body(req, path.join(W, 'parts', String(Number(u.searchParams.get('part')) || 0).padStart(4, '0')));
      return send(200, {ok: true});
    }
    if (req.method === 'POST' && u.pathname === '/unpack') {
      const k = Number(u.searchParams.get('parts'));
      const files = Array.from({length: k}, (_, i) => path.join(W, 'parts', String(i).padStart(4, '0')));
      const bundle = path.join(W, 'bundle.tgz');
      fs.writeFileSync(bundle, '');
      for (const f of files) fs.appendFileSync(bundle, fs.readFileSync(f));
      unpack(bundle).catch((e) => { st.error = String(e); st.stage = 'failed'; });
      return send(200, {ok: true});
    }
    if (req.method === 'POST' && u.pathname === '/fetch') {
      const bundle = path.join(W, 'bundle.tgz');
      st.stage = 'fetch';
      run('curl', ['-sfL', '--retry', '5', '-o', bundle, u.searchParams.get('from') + '/bundle.tgz'])
        .then((c) => (c === 0 ? unpack(bundle) : Promise.reject(new Error('curl ' + c))))
        .catch((e) => { st.error = String(e); st.stage = 'failed'; });
      return send(200, {ok: true});
    }
    if (req.method === 'GET' && u.pathname === '/bundle.tgz') {
      res.writeHead(200, {'Content-Type': 'application/gzip'});
      return fs.createReadStream(path.join(W, 'bundle.tgz')).pipe(res);
    }
    if (req.method === 'POST' && u.pathname === '/render') {
      if (!st.ready) return send(409, {error: 'not ready'});
      st.error = null;
      render(u.searchParams).catch((e) => { st.error = String(e); st.stage = 'failed'; });
      return send(200, {ok: true});
    }
    if (req.method === 'GET' && u.pathname === '/status') {
      const files = fs.existsSync(CH) ? fs.readdirSync(CH).filter((f) => /^(part_\d{3}\.mp4|audio\.wav)$/.test(f)) : [];
      return send(200, Object.assign({}, st, {files}));
    }
    if (req.method === 'GET' && u.pathname.startsWith('/file/')) {
      const name = path.basename(u.pathname.slice(6));
      const f = path.join(CH, name);
      if (!fs.existsSync(f)) return send(404, {error: 'missing'});
      res.writeHead(200, {'Content-Length': fs.statSync(f).size});
      return fs.createReadStream(f).pipe(res);
    }
    send(404, {error: 'unknown'});
  } catch (e) {
    send(500, {error: String(e)});
  }
}).listen(8000, '0.0.0.0');
