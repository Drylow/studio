import { chromium } from "playwright";
import assert from "node:assert/strict";

// Synthetic public counters in a dedicated preview. No real Google credentials.
const url = process.env.STUDIO_SMOKE_URL || "http://127.0.0.1:5011";
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  args: ["--no-sandbox"],
});
const context = await browser.newContext({
  viewport: { width: 390, height: 844 },
  hasTouch: true,
});
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
try {
  const bootstrap = await (
    await context.request.get(url + "/api/studio/bootstrap")
  ).json();
  assert.equal(
    bootstrap.preview,
    true,
    "Only run this against the dedicated preview",
  );
  const original = await (
    await context.request.get(url + "/api/studio/statistics")
  ).json();
  assert.equal(
    original.channels.length,
    3,
    "Seed the public-statistics fixture first",
  );
  const first = original.channels.find((c) => c.totals.subscribers === null);
  const workspace = await (
    await context.request.get(url + "/api/studio/workspace")
  ).json();
  assert.ok(
    workspace.channels.every((c) => !c.connected),
    "The statistics fixture must not use OAuth",
  );
  await page.route("**/api/studio/bootstrap", (route) =>
    route.fulfill({ json: { ...bootstrap, preview: false } }),
  );
  let refreshes = 0;
  await page.route(
    "**/api/studio/statistics/channels/*/refresh",
    async (route) => {
      assert.equal(route.request().method(), "POST");
      assert.ok(route.request().headers()["x-csrf-token"]);
      refreshes++;
      await route.fulfill({ json: { status: "cached" } });
    },
  );
  async function noOverflow() {
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
      "No page-wide horizontal overflow",
    );
    for (const dialog of await page.getByRole("dialog").all())
      assert.ok(
        await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
        "Dialog must fit mobile",
      );
  }
  for (const width of [320, 390, 768, 1440]) {
    console.log(`Checking public statistics at ${width}px`);
    await page.setViewportSize({ width, height: 920 });
    await page.goto(url + "/statistics", { waitUntil: "networkidle" });
    await page
      .getByRole("heading", { name: "Classement des chaînes", exact: true })
      .waitFor();
    assert.equal(
      await page.locator(".public-channel-table tbody tr").count(),
      3,
    );
    await page
      .getByRole("img", { name: /Progression observée des vues de 3/ })
      .waitFor();
    await noOverflow();
    await page
      .getByLabel("Chaîne suivie", { exact: true })
      .selectOption(first.id);
    await page
      .getByRole("heading", { name: "Vidéos de " + first.name, exact: true })
      .waitFor();
    await page.locator(".public-video-table tbody tr").first().waitFor();
    assert.equal(await page.locator(".public-video-table tbody tr").count(), 2);
    assert.equal(
      await page.locator(".public-stats-summary strong").nth(1).textContent(),
      "—",
    );
    await page
      .getByLabel("Période des statistiques publiques")
      .selectOption("168");
    await page
      .getByRole("button", { name: "Actualiser " + first.name, exact: true })
      .click();
    await page.getByRole("status").filter({ hasText: "15 minutes" }).waitFor();
    await page
      .getByLabel("Seulement les vidéos publiées sur la période choisie")
      .check();
    assert.equal(await page.locator(".public-video-table tbody tr").count(), 2);
    await page
      .getByLabel("Période des statistiques publiques")
      .selectOption("48");
    await page.waitForFunction(
      () =>
        document.querySelectorAll(".public-video-table tbody tr").length === 1,
    );
    await noOverflow();
    if (width === 390)
      await page.screenshot({
        path: "../work/studio/public-statistics-mobile-fixture.png",
        fullPage: true,
      });
    if (width === 1440)
      await page.screenshot({
        path: "../work/studio/public-statistics-desktop-fixture.png",
        fullPage: true,
      });
    await page
      .getByRole("button", { name: "Configurer la clé de lecture publique" })
      .click();
    const keyDialog = page.getByRole("dialog", {
      name: "Activer les statistiques publiques",
      exact: true,
    });
    await keyDialog.waitFor();
    assert.equal(await keyDialog.locator("input[type=password]").count(), 1);
    assert.equal(await keyDialog.getByRole("link").count(), 2);
    await noOverflow();
    await page.keyboard.press("Escape");
  }
  assert.equal(refreshes, 4);
  await page.getByLabel("Chaîne suivie", { exact: true }).selectOption("all");
  await page
    .getByLabel("Responsable des statistiques", { exact: true })
    .selectOption("collegue");
  assert.equal(await page.locator(".public-channel-table tbody tr").count(), 1);
  await page
    .getByLabel("Responsable des statistiques", { exact: true })
    .selectOption("all");
  await page
    .getByLabel("Rechercher dans les statistiques")
    .fill("no-results-fixture");
  await page
    .getByText("Aucun résultat avec ces filtres", { exact: true })
    .waitFor();
  await page.getByLabel("Rechercher dans les statistiques").fill("");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Exporter CSV" }).click(),
  ]);
  assert.equal(download.suggestedFilename(), "statistiques-youtube.csv");
  await page
    .getByRole("button", { name: "Ajouter une chaîne", exact: true })
    .first()
    .click();
  const addDialog = page.getByRole("dialog", {
    name: "Suivre une chaîne YouTube",
    exact: true,
  });
  await addDialog.getByLabel("@pseudo ou lien YouTube").fill("@NoOAuthFixture");
  await page.route("**/api/studio/statistics/channels", async (route) => {
    const data = route.request().postDataJSON();
    assert.equal(data.handle, "@NoOAuthFixture");
    assert.ok(route.request().headers()["x-csrf-token"]);
    await route.fulfill({ json: { id: first.id, created: false } });
  });
  await addDialog
    .getByRole("button", { name: "Suivre cette chaîne", exact: true })
    .click();
  await page.waitForFunction(() => !document.querySelector("[role=dialog]"));
  await page
    .getByRole("heading", { name: "Vidéos de " + first.name, exact: true })
    .waitFor();
  await page
    .getByRole("button", {
      name: "Retirer le suivi de " + first.name,
      exact: true,
    })
    .click();
  const removeDialog = page.getByRole("dialog", {
    name: `Retirer le suivi de ${first.name} ?`,
    exact: true,
  });
  await removeDialog.waitFor();
  await page.route(
    `**/api/studio/statistics/channels/${first.id}`,
    async (route) => {
      if (route.request().method() === "DELETE")
        return route.fulfill({
          status: 409,
          json: { error: "Retrait de test refusé" },
        });
      return route.continue();
    },
  );
  await removeDialog
    .getByRole("button", { name: "Retirer le suivi", exact: true })
    .click();
  await removeDialog
    .getByRole("alert")
    .filter({ hasText: "Retrait de test refusé" })
    .waitFor();
  await page.keyboard.press("Escape");
  await page.goto(url + "/channels", { waitUntil: "networkidle" });
  await page
    .getByRole("button", { name: new RegExp("^" + first.name) })
    .first()
    .click();
  await page.waitForURL(url + "/statistics");
  await page
    .getByRole("heading", { name: "Vidéos de " + first.name, exact: true })
    .waitFor();
  await page.getByRole("button", { name: "Statistiques", exact: true }).click();
  await page.waitForFunction(
    () =>
      document.querySelectorAll(".public-channel-table tbody tr").length === 3,
  );
  await page.route("**/api/studio/bootstrap", (route) =>
    route.fulfill({
      json: {
        ...bootstrap,
        preview: false,
        user: { ...bootstrap.user, role: "editor" },
      },
    }),
  );
  await page.reload({ waitUntil: "networkidle" });
  assert.equal(
    await page
      .getByRole("button", { name: "Configurer la clé de lecture publique" })
      .count(),
    0,
  );
  assert.deepEqual(errors, []);
  console.log(
    "Public statistics without OAuth: ranges, charts, video details, responsible filters, CSV, add/setup/delete feedback, private navigation and 320–1440px layouts passed. Google was not contacted.",
  );
} finally {
  await browser.close();
}
