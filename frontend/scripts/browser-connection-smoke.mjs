import assert from "node:assert/strict";
import {
  generateKeyPairSync,
  privateDecrypt,
  constants,
  createDecipheriv,
} from "node:crypto";
import { readFileSync } from "node:fs";
import { chromium } from "playwright";

// Synthetic UI only: every browser-service request is intercepted. No Google
// login page, account or credential is used by this local Chromium test.
const url = process.env.STUDIO_SMOKE_URL || "http://127.0.0.1:5004";
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  args: ["--no-sandbox"],
});
const context = await browser.newContext({
  viewport: { width: 390, height: 844 },
  isMobile: true,
  hasTouch: true,
});
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
const keys = generateKeyPairSync("rsa", { modulusLength: 3072 });
const publicKey = keys.publicKey
  .export({ type: "spki", format: "der" })
  .toString("base64");
const sid = "e".repeat(32);
const image = readFileSync(
  process.env.BROWSER_FIXTURE_IMAGE ||
    "/tmp/edgerunners-browser-ui-fixture.jpg",
).toString("base64");
let role = "owner",
  sequence = 0,
  closed = 0;
const commands = new Map(),
  inputs = [];
try {
  const boot = await (
    await context.request.get(url + "/api/studio/bootstrap")
  ).json();
  assert.equal(boot.preview, true, "Use a dedicated local preview fixture");
  const workspace = await (
    await context.request.get(url + "/api/studio/workspace")
  ).json();
  const channel = workspace.channels.find((entry) => entry.key === "mma_en");
  await page.route("**/api/studio/bootstrap", (route) =>
    route.fulfill({
      json: { ...boot, preview: false, user: { ...boot.user, role } },
    }),
  );
  await page.route("**/api/studio/youtube-browser/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const body =
      route.request().method() === "POST"
        ? route.request().postDataJSON()
        : null;
    if (body) assert.ok(route.request().headers()["x-csrf-token"]);
    if (path.endsWith("/status"))
      return route.fulfill({
        json: { enabled: true, available: true, publication_validated: false },
      });
    if (path.endsWith("/start-service"))
      return route.fulfill({ json: { starting: false } });
    if (path.endsWith("/sessions")) {
      assert.equal(body.revision, channel.revision);
      return route.fulfill({
        json: {
          session_id: sid,
          public_key: publicKey,
          expires_at: Date.now() / 1000 + 1200,
        },
      });
    }
    if (path.endsWith("/close")) {
      closed++;
      return route.fulfill({ json: { closed: true } });
    }
    if (path.endsWith("/commands")) {
      const identity = String(++sequence);
      let result = { image, width: 480, height: 820 };
      if (body.kind === "input") {
        assert.equal(Object.hasOwn(body, "text"), false);
        assert.equal(JSON.stringify(body).includes("fixture-typing"), false);
        const key = privateDecrypt(
          {
            key: keys.privateKey,
            padding: constants.RSA_PKCS1_OAEP_PADDING,
            oaepHash: "sha256",
          },
          Buffer.from(body.key, "base64"),
        );
        const cipher = Buffer.from(body.ciphertext, "base64");
        const decipher = createDecipheriv(
          "aes-256-gcm",
          key,
          Buffer.from(body.iv, "base64"),
        );
        decipher.setAAD(Buffer.from(sid));
        decipher.setAuthTag(cipher.subarray(-16));
        const input = JSON.parse(
          Buffer.concat([
            decipher.update(cipher.subarray(0, -16)),
            decipher.final(),
          ]).toString(),
        );
        inputs.push(input);
        result = { input_delivered: true };
      }
      if (body.kind === "inspect")
        result = {
          channel_access_observed: false,
          login_required: true,
          publication_validated: false,
        };
      commands.set(identity, result);
      return route.fulfill({ json: { command_id: identity } });
    }
    return route.fulfill({
      json: { state: "done", result: commands.get(path.split("/").at(-1)) },
    });
  });
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto(url + "/channels", { waitUntil: "networkidle" });
    await page
      .getByRole("button", {
        name: "Connexion YouTube de Cage Dispatch",
        exact: true,
      })
      .click();
    await page
      .getByRole("button", {
        name: "Ouvrir YouTube sur le serveur",
        exact: true,
      })
      .click();
    await page
      .getByAltText("Écran privé de connexion Google sur le VPS")
      .waitFor();
    await page
      .getByLabel("Texte à écrire dans le champ Google sélectionné")
      .fill("fixture-typing");
    await page
      .getByRole("button", { name: "Écrire dans Google", exact: true })
      .click();
    await page.waitForFunction(
      () =>
        !document.querySelector(".private-browser-connection .button.primary")
          ?.disabled,
    );
    await page.getByRole("button", { name: "Entrée", exact: true }).click();
    await page
      .getByRole("button", {
        name: "J’ai terminé la connexion Google",
        exact: true,
      })
      .click();
    await page
      .getByText("La chaîne attendue n’a pas été confirmée.", { exact: false })
      .waitFor();
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
      `Page overflows at ${width}px`,
    );
    if (width === 390)
      await page.screenshot({
        path: "/tmp/edgerunners-browser-ui-390.png",
        fullPage: true,
      });
    await page
      .getByRole("button", { name: "Fermer l’écran privé", exact: true })
      .click();
    await page
      .getByRole("button", {
        name: "Ouvrir YouTube sur le serveur",
        exact: true,
      })
      .waitFor();
  }
  role = "editor";
  await page.reload({ waitUntil: "networkidle" });
  await page
    .getByRole("button", {
      name: "Connexion YouTube de Cage Dispatch",
      exact: true,
    })
    .click();
  assert.equal(
    await page
      .getByRole("button", {
        name: "Ouvrir YouTube sur le serveur",
        exact: true,
      })
      .count(),
    0,
  );
  assert.equal(
    inputs.filter((input) => input.text === "fixture-typing").length,
    4,
  );
  assert.equal(inputs.filter((input) => input.key === "Return").length, 4);
  assert.ok(closed >= 4);
  assert.deepEqual(errors, []);
  console.log(
    JSON.stringify({
      synthetic_ui: true,
      widths: [320, 390, 768, 1440],
      encrypted_input_verified: true,
      editor_denied: true,
      actual_login_or_upload: false,
    }),
  );
} finally {
  await browser.close();
}
