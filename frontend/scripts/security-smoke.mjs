import { chromium } from "playwright";
import assert from "node:assert/strict";
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
  await page.getByRole("button", { name: "Afficher le mot de passe" }).click();
  assert.equal(
    await page.getByLabel("Mot de passe", { exact: true }).getAttribute("type"),
    "text",
  );
  await page.getByRole("button", { name: "Masquer le mot de passe" }).click();
  await page
    .getByRole("button", { name: "Entrer dans le studio", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "Accès & sécurité", exact: true })
    .waitFor();
  await page
    .getByText("Accès privé par mot de passe", { exact: true })
    .waitFor();
  await page
    .getByRole("button", { name: "Déconnecter les autres appareils" })
    .click();
  await page
    .getByText("Les autres appareils ont été déconnectés.", { exact: true })
    .waitFor();
  await noOverflow(page);
  await page.getByRole("button", { name: "Changer mon mot de passe" }).click();
  const replacement = "another private browser password phrase for Drylow";
  await page.getByLabel("Mot de passe actuel", { exact: true }).fill(password);
  await page
    .getByLabel("Nouveau mot de passe", { exact: true })
    .fill(replacement);
  assert.equal(await page.locator(".gate-qr").count(), 0);
  assert.equal(
    await page.getByLabel("Nouveau code de sécurité", { exact: true }).count(),
    0,
  );
  await page
    .getByRole("button", { name: "Enregistrer mon mot de passe" })
    .click();
  await page
    .getByText("Mot de passe changé. Les anciennes sessions ont été fermées.", {
      exact: true,
    })
    .waitFor();
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
    "Real mobile access: direct password login, intended page, password visibility, password change, logout/replay rejection and private UI locking passed",
  );
  await context.close();
} finally {
  await browser?.close();
  if (server.exitCode === null) server.kill("SIGTERM");
  await closed;
  await rm(temporary, { recursive: true, force: true });
}
