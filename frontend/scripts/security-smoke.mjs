import { chromium } from "playwright";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { mkdtemp, mkdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import { createServer } from "node:net";

// A disposable real authenticated server; no paid jobs or remote publications.
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const temporary = await mkdtemp(resolve(tmpdir(), "edgerunners-gate-"));
const socket = createServer();
await new Promise((r) => socket.listen(0, "127.0.0.1", r));
const port = socket.address().port;
await new Promise((r) => socket.close(r));
const url = `http://127.0.0.1:${port}`;
const python =
  process.env.STUDIO_TEST_PYTHON || resolve(root, ".venv/bin/python");
const script = `from studio.web import create_app
app=create_app({'HOSTED':False,'PREVIEW':False,'SECRET_KEY':'private-browser-fixture-${"x".repeat(40)}','DB_PATH':${JSON.stringify(resolve(temporary, "studio.db"))},'WORKER_ENABLED':False,'IMPORT_PRODUCTIONS':False})
app.run(host='127.0.0.1',port=${port},debug=False,threaded=True)`;
const server = spawn(python, ["-c", script], {
  cwd: root,
  env: {
    ...process.env,
    STUDIO_BOOTSTRAP_TOKEN: "private-browser-installation-fixture",
  },
  stdio: ["ignore", "pipe", "pipe"],
});
let serverLog = "";
server.stdout.on("data", (b) => {
  serverLog = (serverLog + b).slice(-1500);
});
server.stderr.on("data", (b) => {
  serverLog = (serverLog + b).slice(-1500);
});
const closed = new Promise((r) => server.once("exit", r));
let browser;
const errors = [];
const password = "private browser password phrase for Drylow";
const username = "drylow";

function totp(secret, offset = 0) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const char of secret)
    bits += alphabet.indexOf(char).toString(2).padStart(5, "0");
  const bytes = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const count = Buffer.alloc(8);
  count.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000) + offset));
  const hmac = createHmac("sha1", bytes).update(count).digest();
  const at = hmac[hmac.length - 1] & 15;
  return ((hmac.readUInt32BE(at) & 0x7fffffff) % 1000000)
    .toString()
    .padStart(6, "0");
}

async function noOverflow(page) {
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
    "Gate must fit the viewport",
  );
}

try {
  for (let i = 0; i < 100; i++) {
    if (server.exitCode !== null)
      throw new Error("Private test server failed: " + serverLog);
    try {
      if ((await fetch(url + "/health/studio")).ok) break;
    } catch {}
    if (i === 99) throw new Error("Private test server did not start");
    await new Promise((r) => setTimeout(r, 100));
  }
  browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
    args: ["--no-sandbox"],
  });
  await mkdir(resolve(root, "work/studio"), { recursive: true });
  for (const [width, height] of [
    [320, 844],
    [390, 844],
    [768, 1024],
    [1440, 900],
    [844, 390],
  ]) {
    const context = await browser.newContext({
      viewport: { width, height },
      isMobile: width < 900,
      hasTouch: width < 900,
    });
    const page = await context.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(url + "/agent", { waitUntil: "networkidle" });
    await page
      .getByRole("heading", { name: "Crée ton accès privé." })
      .waitFor();
    assert.ok(new URL(page.url()).pathname === "/login");
    await noOverflow(page);
    assert.equal(
      (await context.request.get(url + "/api/studio/workspace")).status(),
      401,
    );
    const input = page.getByLabel("Mot de passe", { exact: true });
    assert.ok((await input.boundingBox()).height >= 44);
    assert.ok(
      await input.evaluate(
        (node) => parseFloat(getComputedStyle(node).fontSize) >= 16,
      ),
    );
    if (width === 1440 || width === 390)
      await page.screenshot({
        path: resolve(
          root,
          `work/studio/private-gate-${width === 1440 ? "desktop" : "mobile"}.png`,
        ),
        fullPage: true,
      });
    await context.close();
  }
  console.log(
    "Private login: five viewport sizes, direct URL redirection and locked APIs passed",
  );
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(url + "/tasks", { waitUntil: "networkidle" });
  await page
    .getByLabel("Code d’installation")
    .fill("private-browser-installation-fixture");
  await page.getByLabel("Ton nom", { exact: true }).fill("Drylow");
  await page.getByLabel("Identifiant", { exact: true }).fill(username);
  await page.getByLabel("Mot de passe", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Créer mon compte" }).click();
  await page.getByRole("heading", { name: "Sécurise ton accès." }).waitFor();
  await page.locator(".gate-qr").waitFor();
  await page.locator("summary").click();
  const secret = await page.locator(".gate-secret").textContent();
  await noOverflow(page);
  assert.equal(
    (await context.request.get(url + "/media/anything/video")).status(),
    401,
  );
  await page
    .getByLabel("Code de sécurité", { exact: true })
    .fill(totp(secret, -1));
  await page.getByRole("button", { name: "Confirmer mon accès" }).click();
  await page
    .getByRole("heading", { name: "Garde tes codes de secours." })
    .waitFor();
  await noOverflow(page);
  assert.equal(
    (await context.request.get(url + "/api/studio/workspace")).status(),
    401,
  );
  assert.ok(
    await page
      .getByRole("button", { name: "Entrer dans le studio" })
      .isDisabled(),
  );
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Télécharger mes codes" }).click();
  assert.equal(
    (await download).suggestedFilename(),
    "edgerunners-codes-de-secours.txt",
  );
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Entrer dans le studio" }).click();
  await page.locator("main h1").waitFor();
  assert.equal(
    new URL(page.url()).pathname,
    "/tasks",
    "Restore the intended local page after complete authentication",
  );
  assert.equal(
    (await context.request.get(url + "/api/studio/workspace")).status(),
    200,
  );
  const oldCookies = await context.cookies();
  const boot = await (
    await context.request.get(url + "/api/studio/bootstrap")
  ).json();
  assert.equal(
    (
      await context.request.post(url + "/api/studio/logout", {
        data: {},
        headers: { "X-CSRF-Token": boot.csrf },
      })
    ).status(),
    200,
  );
  const replay = await browser.newContext();
  await replay.addCookies(oldCookies);
  assert.equal(
    (await replay.request.get(url + "/api/studio/workspace")).status(),
    401,
  );
  await replay.close();
  await page.goto(url + "/settings", { waitUntil: "networkidle" });
  await page.getByLabel("Identifiant", { exact: true }).fill(username);
  await page.getByLabel("Mot de passe", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await page
    .getByRole("heading", { name: "Confirme que c’est toi." })
    .waitFor();
  await page.getByRole("button", { name: "J’ai perdu mon téléphone" }).click();
  await page.getByLabel("Code de secours", { exact: true }).waitFor();
  await page
    .getByRole("button", { name: "Utiliser le code sur mon téléphone" })
    .click();
  await page.getByLabel("Code de sécurité", { exact: true }).fill(totp(secret));
  await page.getByRole("button", { name: "Confirmer mon accès" }).click();
  await page
    .getByRole("heading", { name: "Accès & sécurité", exact: true })
    .waitFor();
  await page
    .getByText("Double authentification active", { exact: true })
    .waitFor();
  await page
    .getByRole("button", { name: "Déconnecter les autres appareils" })
    .click();
  await page
    .getByText("Les autres appareils ont été déconnectés.", { exact: true })
    .waitFor();
  await noOverflow(page);
  const lastBoot = await (
    await context.request.get(url + "/api/studio/bootstrap")
  ).json();
  await context.request.post(url + "/api/studio/logout", {
    data: {},
    headers: { "X-CSRF-Token": lastBoot.csrf },
  });
  await page
    .getByRole("button", { name: "Déconnecter les autres appareils" })
    .click();
  await page
    .getByRole("heading", { name: "Bienvenue dans le crew." })
    .waitFor();
  assert.equal(
    await page
      .getByRole("heading", { name: "Accès & sécurité", exact: true })
      .count(),
    0,
    "A revoked session must remove private UI",
  );
  assert.deepEqual(errors, []);
  console.log(
    "Real mobile access: account creation, QR enrolment, one-time code, backup download, intended page, logout/replay rejection and security settings passed",
  );
  await context.close();
} finally {
  await browser?.close();
  if (server.exitCode === null) server.kill("SIGTERM");
  await closed;
  await rm(temporary, { recursive: true, force: true });
}
