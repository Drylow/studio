import { chromium } from "playwright";
import assert from "node:assert/strict";

// Test UI states against a disposable preview; never enqueue a real deployment.
const url = process.env.STUDIO_SMOKE_URL || "http://127.0.0.1:5002";
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  args: ["--no-sandbox"],
});
const context = await browser.newContext();
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
try {
  const boot = await (
    await context.request.get(url + "/api/studio/bootstrap")
  ).json();
  assert.equal(boot.preview, true, "Use a dedicated preview instance");
  const workspace = await (
    await context.request.get(url + "/api/studio/workspace")
  ).json();
  await page.goto(url + "/agent", { waitUntil: "networkidle" });
  await page
    .getByRole("button", { name: "Modifier le site", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Message à Delamain" })
    .fill("Ajoute une fonction utile au site");
  assert.ok(
    await page
      .getByRole("button", { name: "Envoyer à Delamain", exact: true })
      .isDisabled(),
  );
  await page
    .getByRole("button", { name: "Ouvrir les réglages", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "Modifications du site", exact: true })
    .waitFor();
  const guide = await context.request.get(
    url + "/api/studio/development/setup-guide",
  );
  assert.equal(guide.status(), 200);
  assert.match(await guide.text(), /python -m studio.developer --check/);

  let role = "owner";
  let messages = [];
  let submitted = 0;
  const change = {
    id: "ui-development-fixture",
    user_id: "drylow",
    request: "Ajoute un repère visuel aux tâches",
    status: "queued",
    message: "En attente",
    summary: "",
    error: "",
    commit_id: "",
    checks: "",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  Object.assign(workspace.development.configuration, {
    ready: true,
    configured: true,
    preview: false,
    worker_online: true,
    verified: true,
    missing: [],
  });
  await page.route("**/api/studio/bootstrap", (route) =>
    route.fulfill({
      json: { ...boot, preview: false, user: { ...boot.user, role } },
    }),
  );
  await page.route("**/api/studio/workspace", (route) =>
    route.fulfill({ json: workspace }),
  );
  await page.route("**/api/studio/chat", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      assert.equal(body.mode, "development");
      assert.equal(body.message, change.request);
      assert.ok(route.request().headers()["x-csrf-token"]);
      submitted++;
      workspace.development.changes = [change];
      messages = [
        {
          id: 1001,
          role: "assistant",
          actor: "Delamain",
          content: "Modification reçue.",
          created_at: new Date().toISOString(),
          attachments: [
            {
              kind: "development",
              id: change.id,
              title: "Modification du site",
            },
          ],
        },
      ];
      await route.fulfill({ status: 202, json: { development_id: change.id } });
    } else await route.fulfill({ json: { messages } });
  });
  await page.route(`**/api/studio/development/${change.id}`, (route) =>
    route.fulfill({
      json: {
        ...change,
        diff: "Fixture de changement de code",
        checks: "Fixture de tests terminés",
      },
    }),
  );
  await page.goto(url + "/agent", { waitUntil: "networkidle" });
  await page
    .getByRole("button", { name: "Modifier le site", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Message à Delamain" })
    .fill(change.request);
  await page
    .getByRole("button", { name: "Envoyer à Delamain", exact: true })
    .click();
  await page.locator(".development-card").waitFor();
  assert.equal(submitted, 1);
  assert.match(await page.locator(".development-card").innerText(), /EN COURS/);

  change.status = "done";
  change.summary = "Repère visuel ajouté";
  change.commit_id = "1234567890abcdef";
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(url + "/agent", { waitUntil: "networkidle" });
    await page.locator(".development-card").waitFor();
    assert.match(
      await page.locator(".development-card").innerText(),
      /EN LIGNE/,
    );
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
      JSON.stringify(
        await page.evaluate(() => ({
          width: innerWidth,
          scroll: document.documentElement.scrollWidth,
          elements: Array.from(document.querySelectorAll("body *"))
            .filter((e) => e.getBoundingClientRect().right > innerWidth + 1)
            .slice(0, 12)
            .map((e) => ({
              tag: e.tagName,
              class: e.className,
              width: e.getBoundingClientRect().width,
              text: e.textContent.slice(0, 80),
            })),
        })),
      ),
    );
    await page
      .getByRole("button", { name: "Voir le résultat", exact: true })
      .click();
    const modal = page.getByRole("dialog", {
      name: "Résultat de la modification",
      exact: true,
    });
    await modal.waitFor();
    assert.match(await modal.innerText(), /Fixture de tests terminés/);
    await modal.getByText("Code modifié", { exact: true }).click();
    await modal
      .getByText("Fixture de changement de code", { exact: true })
      .waitFor();
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    );
    await modal.getByRole("button", { name: "Fermer", exact: true }).click();
    console.log(`Development progress and details ${width}px: passed`);
  }
  change.status = "failed";
  change.error = "Tests échoués ; aucun déploiement effectué";
  await page.goto(url + "/settings", { waitUntil: "networkidle" });
  await page
    .getByRole("heading", { name: "Modifications du site", exact: true })
    .waitFor();
  assert.match(await page.locator(".development-card").innerText(), /ARRÊTÉ/);
  assert.match(
    await page.locator(".development-card").innerText(),
    /aucun déploiement/,
  );
  role = "editor";
  await page.goto(url + "/agent", { waitUntil: "networkidle" });
  await page.getByRole("textbox", { name: "Message à Delamain" }).waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "Modifier le site", exact: true })
      .count(),
    0,
  );
  assert.equal(
    await page
      .getByRole("button", { name: "Voir le résultat", exact: true })
      .count(),
    0,
  );
  assert.equal(submitted, 1);
  assert.deepEqual(errors, []);
  console.log(
    "Disconnected blocking, explicit owner mode, one request, real progress rendering, guide, failure and role restrictions: passed",
  );
} finally {
  await browser.close();
}
