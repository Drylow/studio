import { chromium } from "playwright";
import assert from "node:assert/strict";

// Exercise real touch layouts on a dedicated preview database, never production.
const url = process.env.STUDIO_SMOKE_URL || "http://127.0.0.1:5002";
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  args: ["--no-sandbox"],
});
const paths = [
  "/",
  "/channels",
  "/control",
  "/news",
  "/production",
  "/calendar",
  "/tasks",
  "/studio",
  "/library",
  "/agent",
  "/settings",
];
const errors = [];
try {
  for (const [width, height] of [
    [320, 844],
    [375, 812],
    [390, 844],
    [430, 932],
    [768, 1024],
    [844, 390],
  ]) {
    const context = await browser.newContext({
      viewport: { width, height },
      isMobile: true,
      hasTouch: true,
    });
    const page = await context.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    for (const path of paths) {
      await page.goto(url + path, { waitUntil: "networkidle" });
      await page.locator("main h1").waitFor();
      assert.ok(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
        `Overflow on ${path}, ${width}×${height}`,
      );
    }
    console.log(`Eleven touch pages ${width}×${height}: passed`);
    await context.close();
  }
  const context = await browser.newContext({
    viewport: { width: 375, height: 812 },
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(url + "/channels", { waitUntil: "networkidle" });
  assert.equal(
    await page.getByText("Ring Dispatch", { exact: true }).count(),
    0,
  );
  const colors = await page.evaluate(() => {
    const lane = document.querySelector('[data-team="drylow"]');
    return {
      line: getComputedStyle(lane).borderTopColor,
      letter: getComputedStyle(lane.querySelector(".team-avatar")).color,
      width: getComputedStyle(lane).borderTopWidth,
    };
  });
  assert.equal(colors.line, colors.letter);
  assert.equal(colors.width, "2px");
  const connection = page.getByRole("button", {
    name: "Connexion YouTube de Cage Dispatch",
    exact: true,
  });
  assert.ok((await connection.boundingBox()).height >= 44);
  await connection.tap();
  let youtube = page.getByRole("dialog", {
    name: "YouTube · Cage Dispatch",
    exact: true,
  });
  await youtube.waitFor();
  assert.ok(
    await youtube
      .getByRole("button", { name: "Connecter avec Google", exact: true })
      .isDisabled(),
  );
  await youtube.getByText(/Aperçu : les connexions Google/).waitFor();
  await youtube.getByRole("button", { name: "Fermer", exact: true }).tap();
  await page
    .getByRole("button", { name: "Fiches des chaînes", exact: true })
    .tap();
  await connection.tap();
  await youtube.waitFor();
  await youtube.getByRole("button", { name: "Fermer", exact: true }).tap();
  await page.getByRole("button", { name: "Répartition", exact: true }).tap();
  await page
    .locator(".team-channel-name")
    .filter({ hasText: "Cage Dispatch" })
    .tap();
  const settingsDialog = page.getByRole("dialog", {
    name: "Cage Dispatch",
    exact: true,
  });
  await settingsDialog
    .getByRole("button", {
      name: "Connexion YouTube de Cage Dispatch",
      exact: true,
    })
    .tap();
  await youtube.waitFor();
  await youtube.getByRole("button", { name: "Fermer", exact: true }).tap();
  await settingsDialog.getByText("Identité et style", { exact: true }).tap();
  await settingsDialog.getByLabel("Nom de la chaîne").waitFor();
  await settingsDialog
    .getByRole("button", { name: "Annuler", exact: true })
    .tap();
  console.log(
    "Touch YouTube buttons in team, channel cards and settings, preview guards and nested dialog: passed",
  );
  await page.getByRole("button", { name: "Ouvrir le menu", exact: true }).tap();
  await page.locator("nav button").filter({ hasText: "Tâches" }).tap();
  await page.getByRole("button", { name: "Nouvelle tâche", exact: true }).tap();
  let dialog = page.getByRole("dialog");
  assert.ok(
    await dialog
      .getByLabel("À faire", { exact: true })
      .evaluate((e) => parseFloat(getComputedStyle(e).fontSize) >= 16),
  );
  await dialog
    .getByLabel("À faire", { exact: true })
    .fill("Mobile touch task " + Date.now());
  await dialog.getByLabel("Responsable").selectOption("collegue");
  const save = dialog.getByRole("button", {
    name: "Créer la tâche",
    exact: true,
  });
  assert.ok((await save.boundingBox()).height >= 44);
  await save.tap();
  await dialog.waitFor({ state: "hidden" });
  console.log(
    "Turquoise team accent, retired channel absence, touch navigation and task editing: passed",
  );

  await page.goto(url + "/calendar", { waitUntil: "networkidle" });
  assert.ok(
    (
      await page
        .getByRole("button", { name: "Agenda", exact: true })
        .getAttribute("class")
    ).includes("active"),
  );
  await page.getByRole("button", { name: "Mois", exact: true }).tap();
  const scroll = page.locator(".month-scroll");
  assert.ok(await scroll.evaluate((e) => e.scrollWidth > e.clientWidth));
  await scroll.evaluate((e) => (e.scrollLeft = 180));
  assert.ok(await scroll.evaluate((e) => e.scrollLeft > 0));
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  );
  await page
    .getByRole("button", { name: "Prévoir une publication", exact: true })
    .tap();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Date et heure belges").waitFor();
  assert.ok(
    await dialog
      .getByLabel("Date et heure belges")
      .evaluate((e) => parseFloat(getComputedStyle(e).fontSize) >= 16),
  );
  await dialog.getByRole("button", { name: "Annuler", exact: true }).tap();
  await page.goto(url + "/production", { waitUntil: "networkidle" });
  assert.ok(
    (
      await page
        .getByRole("button", { name: "Liste", exact: true })
        .getAttribute("class")
    ).includes("active"),
  );
  console.log(
    "Readable phone agenda, internally scrollable month, scheduling form and production list: passed",
  );

  await page.goto(url + "/agent", { waitUntil: "networkidle" });
  const card = page
    .locator(".chat-attachment")
    .filter({ hasText: "Mobile Delamain thumbnail fixture" });
  await card
    .getByRole("button", { name: "Ouvrir la fiche vidéo", exact: true })
    .waitFor();
  await card.locator("img").scrollIntoViewIfNeeded();
  await page.waitForFunction(() =>
    Array.from(document.querySelectorAll(".chat-attachment img")).some(
      (e) => e.complete && e.naturalWidth > 0,
    ),
  );
  await card
    .getByRole("button", {
      name: "Agrandir : Miniature : Mobile Delamain thumbnail fixture",
      exact: true,
    })
    .tap();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Agrandir", exact: true })
    .tap();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Fermer", exact: true })
    .tap();
  await card
    .getByRole("button", { name: "Ouvrir la fiche vidéo", exact: true })
    .tap();
  await page
    .getByRole("dialog")
    .getByRole("heading", {
      name: "Mobile Delamain thumbnail fixture",
      exact: true,
    })
    .waitFor();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Fermer", exact: true })
    .tap();
  console.log(
    "Delamain real thumbnail card, touch zoom and linked video sheet: passed",
  );

  await page.goto(url + "/", { waitUntil: "networkidle" });
  await page.locator(".daily-delamain").tap();
  const drawer = page.getByRole("complementary", {
    name: "Assistant Delamain",
  });
  await drawer.waitFor();
  const input = drawer.getByLabel("Message à Delamain");
  await input.fill("Une mission sur téléphone");
  await input.press("Enter");
  assert.ok((await input.inputValue()).endsWith("\n"));
  await page.evaluate(() =>
    document.documentElement.style.setProperty("--visible-height", "480px"),
  );
  await page.waitForTimeout(100);
  const rect = await drawer
    .getByRole("button", { name: "Envoyer à Delamain", exact: true })
    .boundingBox();
  assert.ok(
    rect.y + rect.height <= 480,
    `Composer hidden below keyboard: ${JSON.stringify(rect)}`,
  );
  await drawer
    .getByRole("button", { name: "Fermer Delamain", exact: true })
    .tap();
  assert.deepEqual(errors, []);
  console.log(
    "Phone Enter inserts a newline, reduced keyboard viewport keeps composer accessible, zero JavaScript errors: passed",
  );
  await context.close();
} finally {
  await browser.close();
}
