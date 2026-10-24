// render.mjs: render a city on this machine (HyperFrames headless capture with the GPU).
//   node tools/render.mjs <slug> [--fps 60] [--workers 4] [--quality looks]
// Writes cities/<slug>/renders/<slug>.mp4. A 5-minute 1080p60 video is about 18,000 frames: expect a long render
// on a laptop GPU. Lower --workers if the machine struggles, or render at --fps 30 for drafts.
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 && args[i + 1] ? args[i + 1] : d; };
const slug = args.find((a, i) => !a.startsWith("--") && !(i > 0 && args[i - 1].startsWith("--")));
if (!slug) { console.error("usage: node tools/render.mjs <slug> [--fps 60] [--workers 4] [--quality looks]"); process.exit(1); }
const dir = join(root, "cities", slug);
if (!existsSync(join(dir, "index.html"))) { console.error(`no cities/${slug}/index.html`); process.exit(1); }
mkdirSync(join(dir, "renders"), { recursive: true });
const t0 = Date.now();
const r = spawnSync("npx", ["--yes", "hyperframes@0.8.162", "render", ".", "--fps", opt("fps", "60"), "--quality", opt("quality", "looks"), "--workers", opt("workers", "4"), "--browser-gpu", "--gpu", "-o", `renders/${slug}.mp4`], { cwd: dir, stdio: "inherit", shell: process.platform === "win32" });
console.log(r.status === 0 ? `done in ${((Date.now() - t0) / 60000).toFixed(1)} min -> cities/${slug}/renders/${slug}.mp4` : `render failed (exit ${r.status})`);
process.exit(r.status ?? 1);
