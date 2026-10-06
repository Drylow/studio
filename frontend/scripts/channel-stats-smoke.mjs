import { chromium } from "playwright";
import assert from "node:assert/strict";

// A dedicated preview with synthetic snapshots; never call Google or a live account.
const url = process.env.STUDIO_SMOKE_URL || "http://127.0.0.1:5010";
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
  assert.equal(bootstrap.preview, true, "Use a dedicated preview only");
  const workspace = await (
    await context.request.get(url + "/api/studio/workspace")
  ).json();
  const channel = workspace.channels.find((c) => c.key === "mma_en");
  const unconnected = workspace.channels.find((c) => !c.connected);
  assert.ok(channel.connected && unconnected);
  const initial = await (
    await context.request.get(url + `/api/studio/channels/${channel.id}/stats`)
  ).json();
  assert.ok(
    initial.history.length > 1,
    "Seed dedicated snapshots before running this browser test",
  );
  // Enables the refresh UI only; the POST below is intercepted and no real token is used.
  await page.route("**/api/studio/bootstrap", (route) =>
    route.fulfill({ json: { ...bootstrap, preview: false } }),
  );
  let refreshes = 0;
  await page.route(
    `**/api/studio/channels/${channel.id}/stats/refresh?*`,
    async (route) => {
      assert.equal(route.request().method(), "POST");
      assert.ok(route.request().headers()["x-csrf-token"]);
      refreshes++;
      const days = new URL(route.request().url()).searchParams.get("days");
      const cached = await (
        await context.request.get(
          url + `/api/studio/channels/${channel.id}/stats?days=${days}`,
        )
      ).json();
      return route.fulfill({ json: { ...cached, status: "cached" } });
    },
  );
  const dialog = () =>
    page.getByRole("dialog", { name: channel.name, exact: true });
  const ranking = () =>
    page.getByRole("region", { name: "Progression des chaînes" });
  async function noOverflow() {
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    );
    assert.ok(
      await dialog().evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
    );
  }
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 920 });
    await page.goto(url + "/channels", { waitUntil: "networkidle" });
    assert.equal(await ranking().locator(".ranking-row").count(), 3);
    await page
      .getByRole("button", { name: new RegExp(`^${channel.name}`) })
      .first()
      .click();
    await dialog().waitFor();
    await dialog()
      .getByText("Vues cumulées", { exact: true })
      .first()
      .waitFor();
    await dialog()
      .getByRole("img", { name: /^Vues cumulées du/ })
      .waitFor();
    await dialog()
      .getByText("Abonnés · arrondis par YouTube", { exact: true })
      .waitFor();
    assert.equal(
      await dialog().locator(".youtube-metrics strong").nth(1).textContent(),
      "—",
    );
    await noOverflow();
    await dialog().getByRole("button", { name: `Connexion YouTube de ${channel.name}`, exact: true }).click();
    await page.getByRole("dialog", { name: `YouTube · ${channel.name}`, exact: true }).waitFor();
    await page.keyboard.press("Escape");
    await dialog().waitFor();
    await Promise.all([
      page.waitForResponse((r) =>
        r.url().endsWith(`/channels/${channel.id}/stats?days=1`),
      ),
      dialog().getByLabel("Période des statistiques").selectOption("1"),
    ]);
    await dialog()
      .getByRole("button", { name: "Actualiser", exact: true })
      .click();
    await dialog()
      .getByRole("status")
      .filter({ hasText: "15 minutes" })
      .waitFor();
    await noOverflow();
    if (width === 390)
      await page.screenshot({
        path: "../work/studio/channel-stats-mobile-fixture.png",
        fullPage: true,
      });
    if (width === 1440)
      await page.screenshot({
        path: "../work/studio/channel-stats-desktop-fixture.png",
        fullPage: true,
      });
    await page.keyboard.press("Escape");
    assert.equal(await dialog().count(), 0);
  }
  assert.equal(refreshes, 4);
  await page
    .getByLabel("Filtrer les chaînes par responsable")
    .selectOption("mine");
  assert.equal(await ranking().locator(".ranking-row").count(), 2);
  await page
    .getByLabel("Filtrer les chaînes par responsable")
    .selectOption("all");
  await page
    .getByRole("button", { name: "Fiches des chaînes", exact: true })
    .click();
  await page
    .getByRole("button", { name: unconnected.name, exact: true })
    .click();
  const empty = page.getByRole("dialog", {
    name: unconnected.name,
    exact: true,
  });
  await empty
    .getByText("Connecte cette chaîne à YouTube", { exact: false })
    .waitFor();
  assert.equal(await empty.locator(".youtube-metrics").count(), 0);
  await empty.getByRole("button", { name: "Réglages", exact: true }).click();
  assert.equal(await page.locator(".channel-detail").count(), 0);
  await page.getByText("Les règles de cette chaîne, au même endroit.", { exact: true }).waitFor();
  await page.keyboard.press("Escape");
  assert.deepEqual(errors, []);
  console.log(
    "Channel details, real local snapshot API, ranking filters, periods, masked counts, refresh feedback, settings and 320–1440px layouts passed; Google was not contacted.",
  );
} finally {
  await browser.close();
}
