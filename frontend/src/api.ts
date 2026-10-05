let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export async function upload(path: string, file: File) {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/studio" + path, {
    method: "POST",
    body,
    headers: { "X-CSRF-Token": csrf },
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Import impossible.");
  return result;
}
export async function api<T = Record<string, unknown>>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api/studio" + path, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response
    .json()
    .catch(() => ({ error: "Réponse du serveur indisponible." }));
  if (!response.ok) throw new Error(data.error || "L’opération a échoué.");
  return data as T;
}
const tz = "Europe/Paris";
export function dateLabel(
  value: string,
  options: Intl.DateTimeFormatOptions = { day: "numeric", month: "short" },
) {
  return value
    ? new Intl.DateTimeFormat("fr-FR", { timeZone: tz, ...options }).format(
        new Date(value),
      )
    : "À programmer";
}
export function dayKey(value: string | Date) {
  const d = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat("sv-SE", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(d);
}
export function localTime(value: string) {
  if (!value) return "";
  const date = new Date(value);
  return (
    dayKey(date) +
    "T" +
    new Intl.DateTimeFormat("fr-FR", {
      timeZone: tz,
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(date)
  );
}
export function parisToIso(value: string) {
  if (!value) return "";
  const rough = new Date(value + "Z");
  const offsetLabel =
    new Intl.DateTimeFormat("en-GB", {
      timeZone: tz,
      timeZoneName: "shortOffset",
    })
      .formatToParts(rough)
      .find((p) => p.type === "timeZoneName")?.value || "GMT+1";
  const match = offsetLabel.match(/GMT([+-])(\d+)(?::(\d+))?/);
  const offset = match
    ? (match[1] === "+" ? 1 : -1) *
      (Number(match[2]) * 60 + Number(match[3] || 0))
    : 0;
  const result = new Date(rough.getTime() - offset * 60000).toISOString();
  if (localTime(result) !== value.slice(0, 16))
    throw new Error(
      "Cette heure n’existe pas lors du changement d’heure. Choisis un autre créneau.",
    );
  return result;
}
export const labels: Record<string, string> = {
  idea: "Idée",
  research: "Recherche",
  script: "Script",
  creating: "En création",
  review: "À contrôler",
  ready: "Prête",
  scheduled: "Programmée",
  published: "Publiée",
  reported: "Publication rapportée",
  blocked: "Bloquée",
  delivered: "Livrée sur Discord",
};
