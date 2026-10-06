import { chromium } from "playwright";
import assert from "node:assert/strict";
const url = process.env.STUDIO_SMOKE_URL || "http://127.0.0.1:5002";
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
try {
  await page.goto(url + "/news", { waitUntil: "networkidle" });
  await page
    .locator(".news-channel-tabs button")
    .filter({ hasText: "Pitch Dispatch" })
    .click();
  await page.locator(".news-card").first().waitFor();
  const title = await page.locator(".news-card h2").first().innerText();
  await page
    .locator(".news-card")
    .first()
    .getByRole("button", { name: "Préparer une vidéo", exact: true })
    .click();
  let dialog = page.getByRole("dialog");
  await dialog.getByRole("heading", { name: title, exact: true }).waitFor();
  await dialog
    .getByRole("button", { name: "Publication", exact: true })
    .click();
  await dialog
    .getByRole("heading", {
      name: "Les étapes avant publication.",
      exact: true,
    })
    .waitFor();
  await dialog
    .getByRole("button", {
      name: "Aller à : Faits et sources renseignés",
      exact: true,
    })
    .click();
  await dialog.getByLabel("Faits vérifiés et consignes").waitFor();
  assert.equal(
    await dialog.getByLabel("Faits vérifiés et consignes").inputValue(),
    "",
  );
  await dialog.getByRole("button", { name: "Fermer", exact: true }).click();
  const w = await page.evaluate(
    async () => await (await fetch("/api/studio/workspace")).json(),
  );
  assert.equal(w.videos.filter((v) => v.title === title).length, 1);
  assert.equal(
    w.jobs.filter((j) => ["script", "render", "publish"].includes(j.kind))
      .length,
    0,
  );
  console.log(
    "News preparation creates one research draft, exact next steps and no paid jobs: passed",
  );
  await page.getByText("Sources et réglages du radar", { exact: true }).click();
  await page.getByRole("button", { name: "Configurer le radar" }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Nom de la source").fill("Browser temporary feed");
  await dialog
    .getByLabel("Adresse du flux RSS")
    .fill("https://example.org/temporary-rss");
  await dialog.getByRole("button", { name: "Ajouter", exact: true }).click();
  await dialog
    .getByRole("button", { name: "Désactiver Browser temporary feed" })
    .click();
  await dialog
    .getByRole("button", {
      name: "Activer Browser temporary feed",
      exact: true,
    })
    .waitFor();
  await dialog
    .getByRole("button", { name: "Supprimer Browser temporary feed" })
    .click();
  await dialog
    .getByText("Browser temporary feed", { exact: true })
    .waitFor({ state: "hidden" });
  await dialog.getByRole("button", { name: "Terminé", exact: true }).click();
  console.log("Feed creation, pause and removal persist: passed");
  await page.goto(url + "/library", { waitUntil: "networkidle" });
  await page.locator(".reference-card").first().getByRole("button").click();
  dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Agrandir", exact: true }).click();
  await dialog.locator("output").filter({ hasText: "150 %" }).waitFor();
  await dialog.getByRole("button", { name: "Ajuster", exact: true }).click();
  await dialog.locator("output").filter({ hasText: "100 %" }).waitFor();
  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "hidden" });
  console.log("Media viewer zoom, fit and keyboard close: passed");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(url + "/news", { waitUntil: "networkidle" });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  assert.deepEqual(errors, []);
  console.log("Radar mobile layout and JavaScript errors: passed");
} finally {
  await browser.close();
}
