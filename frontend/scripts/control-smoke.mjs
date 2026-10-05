import { chromium } from "playwright";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

// Use a dedicated preview database; this scenario adds test research/tasks only.
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
  await page.goto(url + "/tasks", { waitUntil: "networkidle" });
  const fixture = await page.evaluate(async () => {
    const boot = await (await fetch("/api/studio/bootstrap")).json();
    const w = await (await fetch("/api/studio/workspace")).json();
    const cid = w.channels.find((c) => c.key === "mma_en").id;
    const otherChannel = w.channels.find(
      (c) => c.key === "oddly_specific_en",
    ).id;
    const title = "Control smoke " + Date.now();
    const headers = {
      "Content-Type": "application/json",
      "X-CSRF-Token": boot.csrf,
    };
    const response = await fetch("/api/studio/videos", {
      method: "POST",
      headers,
      body: JSON.stringify({ channel_id: cid, title, minutes: 5 }),
    });
    if (!response.ok) throw new Error("Fixture creation failed");
    const v = await response.json();
    const postAt = new Date(Date.parse(w.server_time) + 3600000).toISOString();
    const scheduled = await fetch("/api/studio/videos/" + v.id, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ revision: 1, post_at: postAt }),
    });
    if (!scheduled.ok) throw new Error("Fixture calendar failed");
    return {
      cid,
      otherChannel,
      title,
      vid: v.id,
      postAt,
      user: boot.user.id,
      server: w.server_time,
    };
  });
  await page.reload({ waitUntil: "networkidle" });
  const due = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Europe/Paris",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  })
    .format(new Date(Date.parse(fixture.server) - 86400000))
    .replace(" ", "T");
  async function addRoutine() {
    await page
      .getByRole("button", { name: "Ajouter une routine", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: /Organiser la semaine/ }).click();
    await dialog
      .getByLabel("Chaîne de la routine")
      .selectOption(String(fixture.cid));
    await dialog
      .getByLabel("Vidéo liée à la routine")
      .selectOption(fixture.vid);
    await dialog.getByLabel("Échéance commune · heure belge").fill(due);
    await dialog
      .getByRole("button", { name: "Ajouter les tâches", exact: true })
      .click();
    await dialog.waitFor({ state: "hidden" });
  }
  await addRoutine();
  let w = await page.evaluate(
    async () => await (await fetch("/api/studio/workspace")).json(),
  );
  const first = w.tasks
    .filter((t) => t.video_id === fixture.vid)
    .map((t) => t.id)
    .sort();
  assert.equal(first.length, 4);
  assert.equal(w.jobs.length, 0);
  await addRoutine();
  w = await page.evaluate(
    async () => await (await fetch("/api/studio/workspace")).json(),
  );
  assert.deepEqual(
    w.tasks
      .filter((t) => t.video_id === fixture.vid)
      .map((t) => t.id)
      .sort(),
    first,
  );
  console.log(
    "Shared routine creation, deadline, video binding and duplicate prevention: passed",
  );

  await page.getByLabel("Rechercher une tâche").fill(fixture.title);
  await page.getByRole("button", { name: "En retard", exact: true }).click();
  assert.equal(await page.locator(".task-row").count(), 4);
  await page
    .getByLabel("Filtrer les tâches par chaîne")
    .selectOption(String(fixture.otherChannel));
  assert.equal(await page.locator(".task-row").count(), 0);
  await page
    .getByLabel("Filtrer les tâches par chaîne")
    .selectOption(String(fixture.cid));
  await page
    .getByRole("button", { name: "Ouvrir la vidéo liée" })
    .first()
    .click();
  await page
    .getByRole("dialog")
    .getByRole("heading", { name: fixture.title, exact: true })
    .waitFor();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Fermer", exact: true })
    .click();
  console.log("Task search, channel/overdue filters and linked video: passed");

  await page.goto(url + "/control", { waitUntil: "networkidle" });
  await page.getByLabel("Filtrer les alertes").selectOption("tasks");
  const firstCard = page
    .locator(".control-alert")
    .filter({ hasText: fixture.title })
    .first();
  const readTitle = await firstCard
    .getByRole("heading", { level: 3 })
    .innerText();
  const card = page.locator(".control-alert").filter({
    has: page.getByRole("heading", { name: readTitle, exact: true }),
  });
  await card.getByRole("button", { name: /Marquer comme lue/ }).click();
  await card.getByText("Lu par toi", { exact: true }).waitFor();
  await page.reload({ waitUntil: "networkidle" });
  await page.getByLabel("Filtrer les alertes").selectOption("tasks");
  await page
    .locator(".control-alert")
    .filter({ hasText: fixture.title })
    .getByText("Lu par toi", { exact: true })
    .waitFor();
  const current = await page.evaluate(
    async () => await (await fetch("/api/studio/control")).json(),
  );
  assert.equal(
    current.alerts.filter(
      (a) => a.action.task_id && first.includes(a.action.task_id) && a.read,
    ).length,
    1,
  );
  console.log(
    "Personal alert acknowledgement survives reload without resolving the task: passed",
  );

  await page.goto(url + "/calendar", { waitUntil: "networkidle" });
  await page
    .getByLabel("Filtrer le calendrier par chaîne")
    .selectOption(String(fixture.cid));
  const downloaded = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Exporter le mois", exact: true })
    .click();
  const download = await downloaded;
  assert.match(download.suggestedFilename(), /^edgerunners-\d{4}-\d{2}\.ics$/);
  const content = await readFile(await download.path(), "utf8");
  assert.ok(content.includes(`UID:video-${fixture.vid}@edgerunners.studio`));
  assert.ok(content.includes("BEGIN:VCALENDAR"));
  console.log(
    "Filtered calendar download contains the actual planned video: passed",
  );

  await page.context().setOffline(true);
  await page
    .getByRole("alert")
    .filter({ hasText: "Connexion à vérifier." })
    .waitFor();
  await page.context().setOffline(false);
  await page
    .getByRole("alert")
    .filter({ hasText: "Connexion à vérifier." })
    .waitFor({ state: "hidden" });
  console.log(
    "Connection loss is visible and online recovery refreshes the studio: passed",
  );
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 844 });
    for (const path of ["/control", "/tasks", "/calendar"]) {
      await page.goto(url + path, { waitUntil: "networkidle" });
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
        `${path} overflows at ${width}`,
      );
    }
  }
  assert.deepEqual(errors, []);
  console.log(
    "Control, tasks and calendar at four screen widths; zero JavaScript errors: passed",
  );
} finally {
  await browser.close();
}
