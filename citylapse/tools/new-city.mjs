// new-city.mjs: start a new city time-lapse from the worked example (cities/babylon).
//   node tools/new-city.mjs <slug> ["CITY NAME"] ["1900 BC – AD 200"]
// Copies the example's scene, page and score generator into cities/<slug>, puts the current shared engine, libraries
// and fonts beside them (each city folder is self-contained and portable), and resets the title and notes.
// Then edit cities/<slug>/scene.js (land, growth curves, landmarks, events, camera, captions); see CLAUDE.md.
import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const [slug, name = "", span = ""] = process.argv.slice(2);
if (!slug || !/^[a-z0-9-]+$/.test(slug)) { console.error('usage: node tools/new-city.mjs <slug: lowercase-with-dashes> ["CITY NAME"] ["START – END"]'); process.exit(1); }
const src = join(root, "cities", "babylon"), dst = join(root, "cities", slug);
if (existsSync(dst)) { console.error(`cities/${slug} already exists`); process.exit(1); }

mkdirSync(join(dst, "assets"), { recursive: true });
for (const f of ["scene.js", "index.html", "music.mjs", "hyperframes.json"]) cpSync(join(src, f), join(dst, f));
cpSync(join(root, "shared", "engine.js"), join(dst, "engine.js"));
cpSync(join(root, "shared", "lib"), join(dst, "lib"), { recursive: true });
cpSync(join(root, "shared", "fonts"), join(dst, "assets", "fonts"), { recursive: true });

const title = (name || slug.replace(/-/g, " ")).toUpperCase();
let html = readFileSync(join(dst, "index.html"), "utf8");
html = html.replace(/<title>.*?<\/title>/, `<title>${title} 3D Timelapse</title>`)
  .replace(/<div class="big">.*?<\/div><div class="small">.*?<\/div>/, `<div class="big">${title}</div><div class="small">${span}</div>`);
writeFileSync(join(dst, "index.html"), html);
writeFileSync(join(dst, "package.json"), JSON.stringify({ name: slug, private: true, type: "module", scripts: { dev: "npx --yes hyperframes@0.8.162 preview", check: "npx --yes hyperframes@0.8.162 check" } }, null, 2) + "\n");
writeFileSync(join(dst, "meta.json"), JSON.stringify({ id: slug, name: `${title} - 3D TIMELAPSE`, createdAt: new Date().toISOString() }, null, 2) + "\n");
writeFileSync(join(dst, "SPEC.md"), `# ${title} – 3D TIMELAPSE${span ? " – " + span : ""}\n\nWrite the beats here before touching scene.js: setting (land, water, plan), a beat table (t, year, era label + flag, what happens on screen), and every caption with the source you checked it against. See cities/babylon/SPEC.md for the format.\n`);
rmSync(join(dst, "renders"), { recursive: true, force: true });
console.log(`cities/${slug} created from the Babylon example.
Next: write SPEC.md, then rework scene.js (it still builds Babylon until you change it), run node music.mjs, snapshot, render.`);
