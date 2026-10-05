import { chromium } from "playwright";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

// Dedicated preview database, with a known test password for the colleague.
const url = process.env.STUDIO_SMOKE_URL || "http://127.0.0.1:5002";
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  args: ["--no-sandbox"],
});
const page = await browser.newPage({
  viewport: { width: 1440, height: 1000 },
  acceptDownloads: true,
});
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
try {
  await page.goto(url + "/channels", { waitUntil: "networkidle" });
  const fixture = await page.evaluate(async () => {
    const boot = await (await fetch("/api/studio/bootstrap")).json();
    const w = await (await fetch("/api/studio/workspace")).json();
    const c = w.channels.find((c) => c.key === "mma_en");
    const other = w.channels.find((c) => c.key === "football_en");
    const headers = {
      "Content-Type": "application/json",
      "X-CSRF-Token": boot.csrf,
    };
    for (const channel of [c, other]) {
      const r = await fetch(
        `/api/studio/channels/${channel.id}/responsibility`,
        {
          method: "PATCH",
          headers,
          body: JSON.stringify({
            responsible_id: null,
            revision: channel.revision,
          }),
        },
      );
      if (!r.ok) throw new Error("Could not reset fixture assignment");
    }
    const title = "Team smoke " + Date.now();
    const response = await fetch("/api/studio/videos", {
      method: "POST",
      headers,
      body: JSON.stringify({ channel_id: c.id, title, minutes: 5 }),
    });
    if (!response.ok) throw new Error("Fixture video creation failed");
    const v = await response.json();
    const postAt = new Date(Date.parse(w.server_time) + 3600000).toISOString();
    const reserved = await fetch(`/api/studio/videos/${v.id}`, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ revision: 1, post_at: postAt }),
    });
    if (!reserved.ok) throw new Error("Fixture reservation failed");
    return {
      cid: c.id,
      other: other.id,
      title,
      vid: v.id,
      postAt,
      server: w.server_time,
    };
  });
  await page.reload({ waitUntil: "networkidle" });
  const card = () => page.locator(`[data-channel="${fixture.cid}"]`);
  const ownerLane = page.locator('[data-team="drylow"]');
  const colleagueLane = page.locator('[data-team="collegue"]');
  await card().dragTo(ownerLane);
  await ownerLane.locator(`[data-channel="${fixture.cid}"]`).waitFor();
  await card().dragTo(colleagueLane);
  await colleagueLane.locator(`[data-channel="${fixture.cid}"]`).waitFor();
  await page.reload({ waitUntil: "networkidle" });
  await colleagueLane.locator(`[data-channel="${fixture.cid}"]`).waitFor();
  assert.equal(
    await card().getByLabel("Responsable de Cage Dispatch").inputValue(),
    "collegue",
  );
  console.log(
    "Native drag and drop between owners, persistence after reload: passed",
  );
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
      `Team board overflow at ${width}`,
    );
  }

  await page
    .getByLabel("Filtrer les chaînes par responsable")
    .selectOption("mine");
  assert.equal(await card().count(), 0);
  await page
    .getByLabel("Filtrer les chaînes par responsable")
    .selectOption("all");
  await page.setViewportSize({ width: 390, height: 844 });
  await card()
    .getByLabel("Responsable de Cage Dispatch")
    .selectOption("drylow");
  await ownerLane.locator(`[data-channel="${fixture.cid}"]`).waitFor();
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  );
  console.log("Mobile transfer fallback and personal channel scope: passed");

  await page.goto(url + "/calendar", { waitUntil: "networkidle" });
  await page
    .getByLabel("Filtrer le calendrier par responsable")
    .selectOption("mine");
  await page.getByRole("button", { name: "Qui poste ?", exact: true }).click();
  await page.locator('[data-planning-member="drylow"]').waitFor();
  await page
    .locator(".rhythm-slot.reserved")
    .filter({ hasText: fixture.title })
    .waitFor();
  assert.equal(
    await page.locator('[data-planning-member="collegue"]').count(),
    0,
  );
  assert.ok((await page.locator(".rhythm-slot.suggestion").count()) > 0);
  const suggestion = page.locator(".rhythm-slot.suggestion").first();
  const time = await suggestion
    .locator(".rhythm-slot-info small")
    .textContent();
  await suggestion.getByRole("button", { name: "Prévoir une vidéo" }).click();
  let dialog = page.getByRole("dialog");
  assert.ok(
    (await dialog.getByLabel("Vidéo", { exact: true }).inputValue()).length > 0,
  );
  const selected = await dialog
    .getByLabel("Vidéo", { exact: true })
    .locator("option:checked")
    .textContent();
  assert.ok(selected.includes("Cage Dispatch"));
  assert.ok(
    (await dialog.getByLabel("Date et heure belges").inputValue()).endsWith(
      time.slice(0, 5),
    ),
  );
  await page.keyboard.press("Escape");
  assert.ok(
    await page
      .locator(".rhythm-slot.reserved")
      .filter({ hasText: fixture.title })
      .textContent()
      .then((s) => s.includes("Bloquée") && s.includes("YouTube à connecter")),
  );
  await page
    .locator(".rhythm-slot.reserved")
    .filter({ hasText: fixture.title })
    .getByRole("button", { name: "Ouvrir la fiche" })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("heading", { name: fixture.title })
    .waitFor();
  await page.keyboard.press("Escape");

  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
      `Rhythm overflow at ${width}`,
    );
  }
  await page.getByRole("button", { name: "Agenda", exact: true }).click();
  await page.getByText(fixture.title, { exact: true }).waitFor();
  const downloadEvent = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Exporter le mois", exact: true })
    .click();
  const download = await downloadEvent;
  const calendar = await readFile(await download.path(), "utf8");
  assert.ok(calendar.includes(fixture.title));
  console.log(
    "Personal cadence, blocked reserved video, responsive views and scoped export: passed",
  );

  await page.goto(url + "/channels", { waitUntil: "networkidle" });
  await card()
    .getByLabel("Responsable de Cage Dispatch")
    .selectOption("collegue");
  await colleagueLane.locator(`[data-channel="${fixture.cid}"]`).waitFor();
  await page.goto(url + "/calendar", { waitUntil: "networkidle" });
  await page
    .getByLabel("Filtrer le calendrier par responsable")
    .selectOption("mine");
  await page.getByRole("button", { name: "Qui poste ?", exact: true }).click();
  await page.locator('[data-planning-member="drylow"]').waitFor();
  assert.equal(
    await page
      .locator(".rhythm-slot.reserved")
      .filter({ hasText: fixture.title })
      .count(),
    0,
  );
  await page.evaluate(async () => {
    const boot = await (await fetch("/api/studio/bootstrap")).json();
    const response = await fetch("/api/studio/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": boot.csrf,
      },
      body: JSON.stringify({
        username: "collegue",
        password: "team smoke colleague password",
      }),
    });
    if (!response.ok) throw new Error("Colleague test login failed");
  });
  await page.reload({ waitUntil: "networkidle" });
  await page
    .getByLabel("Filtrer le calendrier par responsable")
    .selectOption("mine");
  await page.getByRole("button", { name: "Qui poste ?", exact: true }).click();
  await page.locator('[data-planning-member="collegue"]').waitFor();
  await page
    .locator(".rhythm-slot.reserved")
    .filter({ hasText: fixture.title })
    .waitFor();
  const w = await page.evaluate(
    async () => await (await fetch("/api/studio/workspace")).json(),
  );
  assert.equal(w.jobs.length, 0);
  assert.deepEqual(errors, []);
  console.log(
    "Calendar follows transfer and logged-in colleague; no publication job or browser error: passed",
  );
} finally {
  await browser.close();
}
