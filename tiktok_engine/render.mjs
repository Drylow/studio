// Rendu d'une timeline en vidéo : Chromium dessine chaque image (engine.js), ffmpeg encode.
//   node render.mjs --spec timeline.json --out video.mp4 [--audio mix.wav] [--workers 4] [--fps 30]
//   node render.mjs --spec timeline.json --stills 1.5,7,20 --stills-dir dossier
//   node render.mjs --serve [--port 8765]     (lecteur : http://127.0.0.1:8765/engine.html?spec=...)
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith("--")) acc.push([a.slice(2), all[i + 1] && !all[i + 1].startsWith("--") ? all[i + 1] : true]);
  return acc;
}, []));

function loadPlaywright() {
  for (const base of [HERE, path.join(HERE, "..", "frontend"), process.cwd()]) {
    try { return createRequire(path.join(base, "package.json"))("playwright"); } catch { /* suivant */ }
  }
  throw new Error("playwright introuvable (npm install playwright dans tiktok_engine/ ou frontend/)");
}
function chromiumPath() {
  if (process.env.TT_CHROMIUM) return process.env.TT_CHROMIUM;
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH || "/opt/pw-browsers";
  try {
    const dir = fs.readdirSync(base).filter(d => /^chromium-\d+$/.test(d)).sort().pop();
    const exe = dir && path.join(base, dir, "chrome-linux", "chrome");
    if (exe && fs.existsSync(exe)) return exe;
  } catch { /* navigateur par défaut de playwright */ }
  return undefined;
}

// petit serveur de fichiers : le moteur, ses polices, et (en lecture) les dossiers de travail
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".ttf": "font/ttf",
  ".wav": "audio/wav", ".mp3": "audio/mpeg", ".png": "image/png" };
function serve(port) {
  return new Promise(res => {
    const srv = http.createServer((req, rsp) => {
      const u = decodeURIComponent(new URL(req.url, "http://x").pathname);
      const file = u.startsWith("/abs/") ? u.slice(4) : path.join(HERE, u);
      fs.readFile(file, (err, buf) => {
        if (err) { rsp.writeHead(404); rsp.end(); return; }
        rsp.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" });
        rsp.end(buf);
      });
    });
    srv.listen(port || 0, "127.0.0.1", () => res(srv));
  });
}

async function openPage(browser, port, spec) {
  const page = await browser.newPage({ viewport: { width: 540, height: 960 }, deviceScaleFactor: 1 });
  page.on("pageerror", e => console.error("page:", e.message));
  await page.goto(`http://127.0.0.1:${port}/engine.html`);
  await page.evaluate(s => TT.load(s), spec);
  return page;
}
const grab = (page, t) => page.evaluate(t => { TT.frame(t); return document.getElementById("c").toDataURL("image/png"); }, t)
  .then(d => Buffer.from(d.slice(22), "base64"));

function ffmpeg(argv) {
  const p = spawn(args.ffmpeg || process.env.FFMPEG || "ffmpeg", argv, { stdio: ["pipe", "ignore", "pipe"] });
  let err = ""; p.stderr.on("data", d => (err += d));
  p.done = new Promise((ok, ko) => p.on("close", c => (c === 0 ? ok() : ko(new Error("ffmpeg: " + err.slice(-800))))));
  return p;
}
const write = (stream, buf) => new Promise(ok => (stream.write(buf) ? ok() : stream.once("drain", ok)));

async function main() {
  if (args.serve) {
    const srv = await serve(Number(args.port) || 8765);
    console.log(`lecteur : http://127.0.0.1:${srv.address().port}/engine.html?spec=/abs/<chemin>/timeline.json&audio=/abs/<chemin>/mix.wav`);
    return;
  }
  const spec = JSON.parse(fs.readFileSync(args.spec, "utf8"));
  const srv = await serve(0), port = srv.address().port;
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({ executablePath: chromiumPath() });
  try {
    if (args.stills) {
      const dir = args["stills-dir"] || path.dirname(args.spec);
      fs.mkdirSync(dir, { recursive: true });
      const page = await openPage(browser, port, spec);
      for (const t of String(args.stills).split(",").map(Number)) {
        fs.writeFileSync(path.join(dir, `still_${t.toFixed(2)}.png`), await grab(page, t));
      }
      console.log("STILLS DONE");
      return;
    }
    const fps = Number(args.fps || spec.fps || 30), total = Math.ceil(spec.duration * fps);
    const workers = Math.max(1, Number(args.workers || 3));
    const out = path.resolve(args.out), tmp = out + ".parts";
    fs.mkdirSync(tmp, { recursive: true });
    const per = Math.ceil(total / workers);
    let done = 0;
    const started = Date.now();
    await Promise.all([...Array(workers).keys()].map(async w => {
      const a = w * per, b = Math.min(total, a + per);
      if (a >= b) return;
      const seg = path.join(tmp, `seg_${w}.mp4`);
      const page = await openPage(browser, port, spec);
      const ff = ffmpeg(["-y", "-f", "image2pipe", "-framerate", String(fps), "-c:v", "png", "-i", "-",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", seg]);
      for (let f = a; f < b; f++) {
        await write(ff.stdin, await grab(page, f / fps));
        if (++done % 150 === 0) console.log(`images ${done}/${total} (${((Date.now() - started) / 1000).toFixed(0)} s)`);
      }
      ff.stdin.end(); await ff.done; await page.close();
    }));
    const list = path.join(tmp, "list.txt");
    fs.writeFileSync(list, [...Array(workers).keys()].filter(w => fs.existsSync(path.join(tmp, `seg_${w}.mp4`)))
      .map(w => `file '${path.join(tmp, `seg_${w}.mp4`)}'`).join("\n"));
    const mux = ["-y", "-f", "concat", "-safe", "0", "-i", list];
    if (args.audio) mux.push("-i", args.audio, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest");
    mux.push("-c:v", "copy", "-movflags", "+faststart", out);
    await ffmpeg(mux).done;
    fs.rmSync(tmp, { recursive: true, force: true });
    console.log(`RENDER DONE ${out} (${((Date.now() - started) / 1000).toFixed(0)} s)`);
  } finally {
    await browser.close(); srv.close();
  }
}
main().catch(e => { console.error(e); process.exit(1); });
