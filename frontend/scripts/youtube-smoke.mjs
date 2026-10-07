import { chromium } from "playwright";
import assert from "node:assert/strict";

// UI-only Google responses on a preview instance; no account or token is connected.
const url = process.env.STUDIO_SMOKE_URL || "http://127.0.0.1:5002";
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
page.on("pageerror", (e) => errors.push(e.message));
try {
  const bootstrap = await (
    await context.request.get(url + "/api/studio/bootstrap")
  ).json();
  assert.equal(
    bootstrap.preview,
    true,
    "Run only against a dedicated preview instance",
  );
  const workspace = await (
    await context.request.get(url + "/api/studio/workspace")
  ).json();
  const channel = workspace.channels.find((c) => c.key === "mma_en");
  Object.assign(channel, {
    connected: 1,
    enabled: 1,
    paused: 0,
    yt_channel_id: "UCbrowserFixtureMMA",
    yt_channel_title: "Cage Dispatch test connection",
  });
  workspace.connections.youtube = true;
  let role = "owner";
  let verified = 0;
  let disconnected = 0;
  await page.route("**/api/studio/bootstrap", (route) =>
    route.fulfill({
      json: {
        ...bootstrap,
        preview: false,
        user: { ...bootstrap.user, role },
      },
    }),
  );
  await page.route("**/api/studio/workspace", (route) =>
    route.fulfill({ json: workspace }),
  );
  await page.route(
    `**/api/studio/youtube/${channel.id}/verify`,
    async (route) => {
      assert.equal(route.request().method(), "POST");
      assert.equal(route.request().postDataJSON().revision, channel.revision);
      assert.ok(route.request().headers()["x-csrf-token"]);
      verified++;
      await route.fulfill({
        json: {
          channel_title: channel.yt_channel_title,
          channel_id: channel.yt_channel_id,
          checked_at: new Date().toISOString(),
        },
      });
    },
  );
  await page.route(
    `**/api/studio/youtube/${channel.id}/disconnect`,
    async (route) => {
      assert.equal(route.request().method(), "POST");
      assert.equal(route.request().postDataJSON().revision, channel.revision);
      assert.ok(route.request().headers()["x-csrf-token"]);
      disconnected++;
      Object.assign(channel, {
        connected: 0,
        enabled: 0,
        paused: 1,
        revision: channel.revision + 1,
      });
      await route.fulfill({ json: { ok: true } });
    },
  );
  const dialog = () =>
    page.getByRole("dialog", { name: "YouTube · Cage Dispatch", exact: true });
  const button = () =>
    page.getByRole("button", {
      name: "Connexion YouTube de Cage Dispatch",
      exact: true,
    });
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto(url + `/channels?connected=${channel.id}`, {
      waitUntil: "networkidle",
    });
    await dialog().waitFor();
    await dialog().getByText(channel.yt_channel_id, { exact: true }).waitFor();
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    );
    assert.ok(
      await dialog()
        .getByRole("button", { name: "Reconnecter avec Google", exact: true })
        .isEnabled(),
    );
    await dialog().getByRole("button", { name: "Fermer", exact: true }).tap();
    assert.equal(new URL(page.url()).searchParams.has("connected"), false);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await button().tap();
  await dialog()
    .getByRole("button", { name: "Vérifier la connexion", exact: true })
    .tap();
  await dialog()
    .getByRole("status")
    .filter({ hasText: "Connexion vérifiée auprès de YouTube" })
    .waitFor();
  assert.equal(verified, 1);
  await dialog()
    .getByRole("button", { name: "Déconnecter cette chaîne", exact: true })
    .tap();
  assert.equal(disconnected, 0);
  await dialog()
    .getByRole("button", { name: "Garder la connexion", exact: true })
    .tap();
  assert.equal(disconnected, 0);
  await dialog()
    .getByRole("button", { name: "Déconnecter cette chaîne", exact: true })
    .tap();
  await dialog()
    .getByRole("button", { name: "Déconnecter et suspendre", exact: true })
    .tap();
  await dialog().waitFor({ state: "hidden" });
  assert.equal(disconnected, 1);
  assert.ok((await button().textContent()).includes("Connecter YouTube"));
  role = "editor";
  channel.connected = 1;
  await page.reload({ waitUntil: "networkidle" });
  await button().tap();
  await dialog()
    .getByText(/Le propriétaire du studio connecte/)
    .waitFor();
  assert.ok(
    await dialog()
      .getByRole("button", { name: "Reconnecter avec Google", exact: true })
      .isDisabled(),
  );
  assert.ok(
    await dialog()
      .getByRole("button", { name: "Vérifier la connexion", exact: true })
      .isDisabled(),
  );
  assert.equal(
    await dialog()
      .getByRole("button", { name: "Déconnecter cette chaîne", exact: true })
      .count(),
    0,
  );
  assert.deepEqual(errors, []);
  console.log(
    "Simulated Google UI: return identity, four widths, checked result, confirmed disconnect, owner/editor controls and zero JavaScript errors: passed",
  );
} finally {
  await browser.close();
}
