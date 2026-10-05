import { chromium } from "playwright";
import assert from "node:assert/strict";

// Run against a dedicated preview database, never the shared production workspace.
const url = process.env.STUDIO_SMOKE_URL || "http://127.0.0.1:5001";
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  headless: true,
  args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const stamp = "UI smoke " + Date.now();
try {
  await page.goto(url, { waitUntil: "networkidle" });
  await page
    .getByRole("heading", { level: 1, name: "Vue d’ensemble." })
    .waitFor();
  await page.locator("nav button").filter({ hasText: "Tâches" }).click();
  await page
    .getByRole("button", { name: "Nouvelle tâche", exact: true })
    .click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("À faire", { exact: true }).fill(stamp);
  await dialog.getByLabel("Responsable").selectOption("collegue");
  await dialog.getByRole("button", { name: "Créer la tâche" }).click();
  await page.getByRole("button", { name: stamp, exact: true }).waitFor();
  await page.getByRole("button", { name: stamp, exact: true }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("À faire", { exact: true }).fill(stamp + " edited");
  await dialog
    .getByRole("button", { name: "Enregistrer", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Terminer " + stamp + " edited", exact: true })
    .click();
  await page.getByRole("button", { name: "Terminées", exact: true }).click();
  await page
    .getByRole("button", { name: stamp + " edited", exact: true })
    .waitFor();
  await page.reload({ waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Terminées", exact: true }).click();
  await page
    .getByRole("button", { name: stamp + " edited", exact: true })
    .waitFor();
  console.log(
    "Task creation, editing, completion and reload persistence: passed",
  );

  await page.locator("nav button").filter({ hasText: "Studio vidéo" }).click();
  await page
    .locator(".studio-channel-list button")
    .filter({ hasText: "Cage Dispatch" })
    .click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Sujet ou titre").fill(stamp + " video");
  await dialog.getByRole("button", { name: "Ajouter à la production" }).click();
  await page
    .getByRole("dialog")
    .getByRole("heading", { name: stamp + " video", exact: true })
    .waitFor();
  await page
    .getByRole("button", { name: "Créer la vidéo", exact: true })
    .click();
  await page
    .getByRole("status")
    .filter({ hasText: "L’aperçu permet d’organiser" })
    .waitFor();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Fermer", exact: true })
    .click();
  console.log(
    "Creation workflow and preview spending/publication block: passed",
  );

  await page.locator("nav button").filter({ hasText: "Calendrier" }).click();
  await page.getByRole("button", { name: "Prévoir une publication" }).click();
  dialog = page.getByRole("dialog");
  const workspace = await page.evaluate(
    async () => await (await fetch("/api/studio/workspace")).json(),
  );
  const video = workspace.videos.find((v) => v.title === stamp + " video");
  const dateFormat = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Europe/Paris",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  let offset = 1;
  let date = dateFormat.format(new Date(Date.now() + offset * 86400000));
  while (
    workspace.videos.some(
      (v) =>
        v.channel_id === video.channel_id &&
        v.post_at &&
        dateFormat.format(new Date(v.post_at)) === date,
    )
  ) {
    date = dateFormat.format(new Date(Date.now() + ++offset * 86400000));
  }
  await dialog.getByLabel(/^Vidéo/).selectOption(video.id);
  await dialog.getByLabel("Date et heure belges").fill(date + "T18:30");
  await dialog.getByRole("button", { name: "Enregistrer le créneau" }).click();
  await dialog.waitFor({ state: "hidden" });
  await page.getByRole("button", { name: "Agenda", exact: true }).click();
  await page
    .locator(".agenda-list")
    .getByText(stamp + " video", { exact: true })
    .waitFor();
  const saved = await page.evaluate(async (id) => {
    const w = await (await fetch("/api/studio/workspace")).json();
    return w.videos.find((v) => v.id === id);
  }, video.id);
  assert.equal(
    new Intl.DateTimeFormat("fr-FR", {
      timeZone: "Europe/Paris",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(saved.post_at)),
    "18:30",
  );
  console.log("Calendar scheduling and Paris timezone conversion: passed");

  await page.locator("nav button").filter({ hasText: "Chaînes" }).click();
  await page
    .getByRole("button", { name: "Fiches des chaînes", exact: true })
    .click();
  await page
    .locator(".channel-card")
    .filter({
      has: page.getByRole("heading", { name: "Cage Dispatch", exact: true }),
    })
    .getByRole("button", { name: "Réglages" })
    .click();
  dialog = page.getByRole("dialog");
  assert.equal(
    await dialog.getByLabel("Modèle de production").inputValue(),
    "mma_en",
  );
  await dialog
    .getByLabel("Instructions pour l’agent")
    .fill("UI smoke instructions");
  await dialog
    .getByRole("button", { name: "Enregistrer", exact: true })
    .click();
  const channel = await page.evaluate(async () => {
    const w = await (await fetch("/api/studio/workspace")).json();
    return w.channels.find((c) => c.key === "mma_en");
  });
  assert.equal(channel.instructions, "UI smoke instructions");
  console.log("Channel preset and persistent settings: passed");

  const pages = [
    ["/", "Vue d’ensemble."],
    ["/channels", "Tes chaînes."],
    ["/control", "Centre de contrôle."],
    ["/news", "Radar d’actus."],
    ["/production", "Production."],
    ["/calendar", "Calendrier."],
    ["/tasks", "Tâches."],
    ["/studio", "Studio vidéo."],
    ["/library", "Bibliothèque."],
    ["/settings", "Réglages."],
    ["/agent", "Delamain."],
  ];
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    for (const [path, heading] of pages) {
      await page.goto(url + path, { waitUntil: "networkidle" });
      await page.getByRole("heading", { level: 1, name: heading }).waitFor();
      await page.waitForTimeout(250);
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > window.innerWidth,
        ),
        false,
        "Overflow on " + path + " at " + viewport.width,
      );
      if (path === "/library") {
        await page.locator(".reference-card img").evaluateAll((imgs) =>
          imgs.forEach((i) => {
            i.loading = "eager";
          }),
        );
        await page.waitForFunction(() => {
          const imgs = [...document.querySelectorAll(".reference-card img")];
          return (
            imgs.length === 8 &&
            imgs.every((i) => i.complete && i.naturalWidth > 0)
          );
        });
      }
    }
  }
  assert.deepEqual(errors, []);
  console.log(
    "Eleven pages, desktop/mobile, reference images and JavaScript errors: passed",
  );
} finally {
  await browser.close();
}
