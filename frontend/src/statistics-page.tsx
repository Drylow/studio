import { useEffect, useRef, useState } from "react";
import {
  BarChart3,
  ArrowUpRight,
  Plus,
  RefreshCw,
  Eye,
  Users,
  TrendingUp,
  Download,
  Search,
  Settings,
  Trash2,
  Radio,
} from "lucide-react";
import type { PageProps } from "./pages";
import { api, dateLabel } from "./api";
import { Button, Modal, Disclosure } from "./components";
import "./statistics-page.css";

type Point = {
  captured_at: string;
  views: number | null;
  subscribers: number | null;
  videos: number | null;
};
export type PublicChannel = {
  id: string;
  name: string;
  handle: string;
  youtube_id: string;
  studio_id: number | null;
  responsible_id: string | null;
  accent: string;
  totals: {
    views: number | null;
    subscribers: number | null;
    videos: number | null;
  };
  gain: number | null;
  subscriber_gain: number | null;
  since: string | null;
  updated_at: string | null;
  partial: boolean;
  stale: boolean;
  error: string;
  refreshing: boolean;
  queued: boolean;
  videos_at: string;
  has_more: boolean;
  history: Point[];
};
type PublicVideo = {
  video_id: string;
  title: string;
  published_at: string;
  duration: number | null;
  views: number | null;
  likes: number | null;
  comments: number | null;
  gain: number | null;
  since: string | null;
  partial: boolean;
  published_in_period: boolean;
  engagement: number | null;
};
type Data = {
  channels: PublicChannel[];
  hours: number;
  configuration: {
    configured: boolean;
    verified_at: string;
    poll_minutes: number;
    max_channels: number;
    max_videos: number;
    worker_online: boolean;
  };
};
type Detail = PublicChannel & { videos: PublicVideo[] };
const periods = [
  [24, "24 heures"],
  [48, "48 heures"],
  [168, "7 jours"],
  [336, "14 jours"],
  [672, "28 jours"],
] as const;
const format = (value: number | null | undefined) =>
  value == null ? "—" : value.toLocaleString("fr-FR");
const delta = (value: number | null | undefined) =>
  value == null ? "—" : (value >= 0 ? "+" : "") + format(value);
const timestamp = (value: string) =>
  dateLabel(value, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
const sum = (items: (number | null)[]) =>
  items.some((v) => v !== null)
    ? items.reduce<number>((n, v) => n + (v ?? 0), 0)
    : null;
const coverage = (c: PublicChannel) =>
  c.since
    ? `${c.partial ? "Suivi partiel depuis" : "Relevé depuis"} ${timestamp(c.since)}`
    : "Premier relevé en attente";

function KeySetup({ close, done }: { close: () => void; done: () => void }) {
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <Modal
      title="Activer les statistiques publiques"
      subtitle="Une seule clé pour tout le studio. Aucune chaîne à connecter."
      close={close}
    >
      <form
        className="form public-key-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            await api("/statistics/key", "POST", { api_key: key });
            setKey("");
            done();
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <ol>
          <li>
            Ouvre{" "}
            <a
              href="https://console.cloud.google.com/apis/library/youtube.googleapis.com?project=507920096990"
              target="_blank"
              rel="noopener noreferrer"
            >
              YouTube Data API v3
            </a>
            . Clique « Activer » si elle est désactivée.
          </li>
          <li>
            Ouvre{" "}
            <a
              href="https://console.cloud.google.com/apis/credentials?project=507920096990"
              target="_blank"
              rel="noopener noreferrer"
            >
              les identifiants Google
            </a>
            . Clique « Créer des identifiants » → « Clé API », puis copie la
            clé.
          </li>
          <li>
            Colle-la ci-dessous. Le studio la vérifie et la garde sur le
            serveur.
          </li>
        </ol>
        <label>
          Clé API YouTube
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={key}
            onChange={(e) => setKey(e.target.value)}
            required
            maxLength={120}
            placeholder="Colle la clé API ici"
          />
        </label>
        <p className="muted small">
          Cette clé sert à lire les données publiques. Elle ne publie aucune
          vidéo. Dans Google, limite-la à YouTube Data API v3 ; les restrictions
          « sites web » ne conviennent pas aux lectures faites par le serveur.
        </p>
        {error && (
          <p className="statistics-error" role="alert">
            {error}
          </p>
        )}
        <Button variant="primary" type="submit" disabled={busy}>
          {busy ? "Vérification…" : "Vérifier et enregistrer"}
        </Button>
      </form>
    </Modal>
  );
}

function AddChannel({
  p,
  initialStudio,
  close,
  done,
}: {
  p: PageProps;
  initialStudio: number | null;
  close: () => void;
  done: (id: string) => void;
}) {
  const linked = p.data.channels.find((c) => c.id === initialStudio);
  const [handle, setHandle] = useState(
    linked?.handle.startsWith("@") ? linked.handle : "",
  );
  const [studio, setStudio] = useState(initialStudio?.toString() || "");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <Modal
      title="Suivre une chaîne YouTube"
      subtitle="Colle son @pseudo ou le lien de sa page. Pas besoin de connexion Google."
      close={close}
    >
      <form
        className="form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            const result = await api<{ id: string; created: boolean }>(
              "/statistics/channels",
              "POST",
              { handle, studio_id: studio ? Number(studio) : null },
            );
            done(result.id);
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          @pseudo ou lien YouTube
          <input
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
            required
            maxLength={300}
            placeholder="@NomDeTaChaine"
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
          />
        </label>
        <label>
          Associer à une chaîne du studio · facultatif
          <select value={studio} onChange={(e) => setStudio(e.target.value)}>
            <option value="">Suivi indépendant</option>
            {p.data.channels.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <p className="muted small">
          Le suivi commence au premier relevé. Les périodes de 48 heures et 7
          jours se rempliront ensuite automatiquement, sans donner accès à la
          chaîne.
        </p>
        {error && (
          <p role="alert" className="statistics-error">
            {error}
          </p>
        )}
        <Button variant="primary" type="submit" disabled={busy}>
          {busy ? "Recherche sur YouTube…" : "Suivre cette chaîne"}
        </Button>
      </form>
    </Modal>
  );
}

function Evolution({
  channels,
  metric,
}: {
  channels: PublicChannel[];
  metric: "views" | "subscribers";
}) {
  const series = channels.filter(
    (c) => c.history.filter((h) => h[metric] !== null).length >= 2,
  );
  if (!series.length)
    return (
      <div className="statistics-chart-empty">
        <Radio size={24} />
        <strong>Le suivi est prêt à démarrer</strong>
        <p>
          Les compteurs actuels s’affichent au premier relevé. La courbe et les
          variations commencent au deuxième, puis se remplissent chaque heure.
        </p>
      </div>
    );
  const points = series.flatMap((c) =>
    c.history.filter((h) => h[metric] !== null),
  );
  const start = Math.min(...points.map((p) => Date.parse(p.captured_at))),
    end = Math.max(...points.map((p) => Date.parse(p.captured_at)));
  const values = series.flatMap((c) => {
    const h = c.history.filter((p) => p[metric] !== null);
    return h.map((p) => p[metric]! - h[0][metric]!);
  });
  const min = Math.min(0, ...values),
    max = Math.max(1, ...values),
    span = Math.max(1, max - min);
  return (
    <div className="public-evolution">
      <div className="public-chart-scale">
        <span>{format(max)}</span>
        <span>{format(min)}</span>
      </div>
      <svg
        viewBox="0 0 800 230"
        role="img"
        aria-label={`Progression observée des ${metric === "views" ? "vues" : "abonnés"} de ${series.length} chaîne(s), du ${timestamp(new Date(start).toISOString())} au ${timestamp(new Date(end).toISOString())}`}
      >
        <path
          d="M20 20H780 M20 70H780 M20 120H780 M20 170H780 M20 220H780"
          className="public-chart-grid"
        />
        {series.map((c) => {
          const h = c.history.filter((p) => p[metric] !== null);
          const mapped = h.map((p) => ({
            ...p,
            gain: p[metric]! - h[0][metric]!,
            x:
              20 +
              ((Date.parse(p.captured_at) - start) / Math.max(1, end - start)) *
                760,
            y: 220 - ((p[metric]! - h[0][metric]! - min) / span) * 200,
          }));
          return (
            <g key={c.id} style={{ color: c.accent }}>
              <polyline
                fill="none"
                points={mapped.map((p) => `${p.x},${p.y}`).join(" ")}
              />
              <circle
                cx={mapped[mapped.length - 1].x}
                cy={mapped[mapped.length - 1].y}
                r="4"
              >
                <title>
                  {c.name} · {delta(mapped[mapped.length - 1].gain)} ·{" "}
                  {timestamp(mapped[mapped.length - 1].captured_at)}
                </title>
              </circle>
            </g>
          );
        })}
      </svg>
      <div className="public-chart-dates">
        <span>{timestamp(new Date(start).toISOString())}</span>
        <span>{timestamp(new Date(end).toISOString())}</span>
      </div>
      <div className="public-chart-legend">
        {series.map((c) => (
          <span key={c.id}>
            <i style={{ background: c.accent }} />
            {c.name}
          </span>
        ))}
      </div>
    </div>
  );
}

export function StatisticsPage(
  p: PageProps & { initialStudio?: number | null },
) {
  const [hours, setHours] = useState(48),
    [selected, setSelected] = useState("all"),
    [scope, setScope] = useState("all");
  const [data, setData] = useState<Data | null>(null),
    [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [query, setQuery] = useState("");
  const [keyOpen, setKeyOpen] = useState(false),
    [addOpen, setAddOpen] = useState(false),
    [busy, setBusy] = useState(false);
  const [remove, setRemove] = useState<PublicChannel | null>(null),
    [metric, setMetric] = useState<"views" | "subscribers">("views");
  const [sort, setSort] = useState("gain"),
    [publishedOnly, setPublishedOnly] = useState(false),
    [videoSort, setVideoSort] = useState("gain");
  const [revision, setRevision] = useState(0);
  const initializedStudio = useRef<number | null | undefined>(undefined);
  const [removeError, setRemoveError] = useState("");
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const result = await api<Data>(`/statistics?hours=${hours}`);
        if (active) {
          setData(result);
          setError("");
        }
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    }
    void load();
    const timer = window.setInterval(() => {
      if (!document.hidden) void load();
    }, 15000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [hours, revision]);
  useEffect(() => {
    if (!data || initializedStudio.current === p.initialStudio) return;
    initializedStudio.current = p.initialStudio;
    const target = data.channels.find((c) => c.studio_id === p.initialStudio);
    setSelected(target?.id || "all");
  }, [p.initialStudio, data]);
  useEffect(() => {
    let active = true;
    setDetail(null);
    if (selected === "all") return;
    async function load() {
      try {
        const result = await api<Detail>(
          `/statistics/channels/${selected}?hours=${hours}`,
        );
        if (active) setDetail(result);
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    }
    void load();
    const timer = window.setInterval(() => {
      if (!document.hidden) void load();
    }, 15000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [selected, hours, revision]);
  const all = data?.channels || [];
  const channels = all.filter(
    (c) =>
      (selected === "all" || c.id === selected) &&
      (scope === "all" || c.responsible_id === scope) &&
      (!query ||
        `${c.name} ${c.handle}`.toLowerCase().includes(query.toLowerCase())),
  );
  const available = channels.filter((c) => !c.stale && !c.error);
  const views = sum(channels.map((c) => c.totals.views)),
    subscribers = sum(channels.map((c) => c.totals.subscribers));
  const growth = sum(available.map((c) => c.gain)),
    growthCount = available.filter((c) => c.gain !== null).length;
  const ranked = [...channels].sort((a, b) => {
    const key = sort as "gain" | "subscriber_gain";
    const value = (c: PublicChannel) =>
      sort === "views" || sort === "subscribers" ? c.totals[sort] : c[key];
    return (value(b) ?? -Infinity) - (value(a) ?? -Infinity);
  });
  const videos = [...(detail?.videos || [])]
    .filter(
      (v) =>
        (!publishedOnly || v.published_in_period) &&
        (!query || v.title.toLowerCase().includes(query.toLowerCase())),
    )
    .sort((a, b) =>
      videoSort === "date"
        ? Date.parse(b.published_at) - Date.parse(a.published_at)
        : (b[videoSort as "gain" | "views" | "likes" | "comments"] ??
            -Infinity) -
          (a[videoSort as "gain" | "views" | "likes" | "comments"] ??
            -Infinity),
    );
  async function refresh(c: PublicChannel) {
    setBusy(true);
    setNotice("");
    try {
      const r = await api<{ status: string }>(
        `/statistics/channels/${c.id}/refresh`,
        "POST",
        {},
      );
      setNotice(
        r.status === "cached"
          ? "Le dernier essai est récent : attends 15 minutes entre deux actualisations."
          : r.status === "running"
            ? "Le relevé est déjà en cours."
            : "Actualisation demandée. Le worker relève les compteurs en arrière-plan.",
      );
      setRevision((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const targetStudio = p.data.channels.find((c) => c.id === p.initialStudio);
  return (
    <div className="page statistics-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">PUBLIC / YOUTUBE</span>
          <h1>
            Statistiques<span className="heading-dot">.</span>
          </h1>
          <p>
            Ajoute un @pseudo. Suis tes chaînes et compare leurs performances.
          </p>
        </div>
        <div className="statistics-heading-actions">
          {p.user.role === "owner" && (
            <Button
              onClick={() => setKeyOpen(true)}
              aria-label="Configurer la clé de lecture publique"
            >
              <Settings size={16} />
              {data?.configuration.configured
                ? "Clé de lecture"
                : "Configurer la clé"}
            </Button>
          )}
          <Button
            variant="primary"
            onClick={() => setAddOpen(true)}
            disabled={!data?.configuration.configured}
          >
            <Plus size={16} />
            Ajouter une chaîne
          </Button>
        </div>
      </div>
      {error && (
        <div className="statistics-error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="inline-note" role="status">
          {notice}
        </div>
      )}
      {data && !data.configuration.configured && (
        <section className="panel public-statistics-setup">
          <BarChart3 size={26} />
          <div>
            <h2>Des statistiques sans connecter tes comptes</h2>
            <p>
              Une seule clé de lecture pour tout le studio. Ensuite, le @pseudo
              suffit pour chaque chaîne.
            </p>
            {p.user.role === "owner" ? (
              <Button variant="primary" onClick={() => setKeyOpen(true)}>
                Configurer la clé · une seule fois
              </Button>
            ) : (
              <p className="muted small">
                Drylow peut activer la lecture publique depuis cette page.
              </p>
            )}
          </div>
        </section>
      )}
      {!data ? (
        <p role="status" className="muted">
          Chargement des statistiques…
        </p>
      ) : (
        <>
          <div className="statistics-filters">
            <label>
              Chaîne
              <select
                aria-label="Chaîne suivie"
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
              >
                <option value="all">Toutes les chaînes suivies</option>
                {all.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Période
              <select
                aria-label="Période des statistiques publiques"
                value={hours}
                onChange={(e) => {
                  setHours(Number(e.target.value));
                  setNotice("");
                }}
              >
                {periods.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Responsable
              <select
                aria-label="Responsable des statistiques"
                value={scope}
                onChange={(e) => setScope(e.target.value)}
              >
                <option value="all">Toute l’équipe</option>
                {p.data.users.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name}
                  </option>
                ))}
              </select>
            </label>
            <a
              className="button"
              href={`/api/studio/statistics/export?hours=${hours}`}
              download
            >
              <Download size={16} />
              Exporter CSV
            </a>
          </div>
          {targetStudio &&
            !all.some((c) => c.studio_id === targetStudio.id) && (
              <div className="inline-note">
                <span>
                  Pour suivre {targetStudio.name}, ajoute son @pseudo et
                  associe-le à cette chaîne.
                </span>
                <Button
                  onClick={() => setAddOpen(true)}
                  disabled={!data.configuration.configured}
                >
                  Ajouter son @pseudo
                </Button>
              </div>
            )}
          <div className="public-stats-summary">
            <article className="panel">
              <Eye size={20} />
              <div>
                <strong>{format(views)}</strong>
                <span>Vues cumulées · {channels.length} chaîne(s)</span>
              </div>
            </article>
            <article className="panel">
              <Users size={20} />
              <div>
                <strong>{format(subscribers)}</strong>
                <span>
                  Abonnés · arrondis par YouTube
                  {channels.some((c) => c.totals.subscribers === null) &&
                    " · certains masqués"}
                </span>
              </div>
            </article>
            <article className="panel">
              <TrendingUp size={20} />
              <div>
                <strong
                  className={growth !== null && growth < 0 ? "negative" : ""}
                >
                  {delta(growth)}
                </strong>
                <span>
                  Vues gagnées observées · {growthCount}/{channels.length}{" "}
                  suivies
                </span>
              </div>
            </article>
          </div>
          <section className="panel public-chart-panel">
            <header>
              <div>
                <h2>Évolution des chaînes</h2>
                <p className="muted small">
                  Relevés horaires. Les périodes incomplètes commencent au
                  premier relevé disponible.
                </p>
              </div>
              <div className="segmented">
                <button
                  className={metric === "views" ? "active" : ""}
                  onClick={() => setMetric("views")}
                >
                  Vues
                </button>
                <button
                  className={metric === "subscribers" ? "active" : ""}
                  onClick={() => setMetric("subscribers")}
                >
                  Abonnés
                </button>
              </div>
            </header>
            <Evolution channels={channels} metric={metric} />
          </section>
          <section className="panel public-ranking-panel">
            <header>
              <div>
                <h2>Classement des chaînes</h2>
                <p className="muted small">
                  Compteurs actuels et variations réellement observées entre les
                  dates affichées.
                </p>
              </div>
              <select
                aria-label="Trier les chaînes suivies"
                value={sort}
                onChange={(e) => setSort(e.target.value)}
              >
                <option value="gain">Vues gagnées</option>
                <option value="views">Vues cumulées</option>
                <option value="subscribers">Abonnés</option>
                <option value="subscriber_gain">Abonnés gagnés</option>
              </select>
            </header>
            <div className="statistics-search">
              <Search size={16} />
              <input
                aria-label="Rechercher dans les statistiques"
                placeholder="Rechercher une chaîne ou une vidéo…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            {channels.length ? (
              <div className="statistics-table-scroll">
                <table className="public-channel-table">
                  <thead>
                    <tr>
                      <th>Chaîne</th>
                      <th>Vues cumulées</th>
                      <th>Vues gagnées</th>
                      <th>Abonnés</th>
                      <th>Variation abonnés</th>
                      <th>Vidéos publiques</th>
                      <th>Relevé</th>
                      <th>
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {ranked.map((c, i) => (
                      <tr key={c.id}>
                        <td>
                          <button
                            className="statistics-channel-name"
                            onClick={() => setSelected(c.id)}
                          >
                            <span className="statistics-rank">
                              {String(i + 1).padStart(2, "0")}
                            </span>
                            <i style={{ background: c.accent }} />
                            <span>
                              <strong>{c.name}</strong>
                              <small>{c.handle}</small>
                            </span>
                          </button>
                        </td>
                        <td>{format(c.totals.views)}</td>
                        <td
                          className={
                            c.gain !== null && c.gain < 0
                              ? "negative"
                              : "statistics-growth"
                          }
                        >
                          {delta(c.gain)}
                          <small>
                            {c.gain === null ? "Suivi en cours" : coverage(c)}
                          </small>
                        </td>
                        <td>{format(c.totals.subscribers)}</td>
                        <td>{delta(c.subscriber_gain)}</td>
                        <td>{format(c.totals.videos)}</td>
                        <td>
                          <span
                            className={
                              c.stale || c.error ? "statistics-error" : "muted"
                            }
                          >
                            {c.updated_at
                              ? timestamp(c.updated_at)
                              : "En attente"}
                          </span>
                          <small>
                            {c.refreshing
                              ? "Relevé en cours"
                              : c.queued
                                ? "Actualisation en attente"
                                : c.error ||
                                  (c.stale
                                    ? "Données anciennes"
                                    : "Relevé public")}
                          </small>
                        </td>
                        <td>
                          <div className="statistics-row-actions">
                            <button
                              className="icon-button"
                              aria-label={`Actualiser ${c.name}`}
                              onClick={() => void refresh(c)}
                              disabled={busy || c.refreshing || p.preview}
                            >
                              <RefreshCw size={16} />
                            </button>
                            <a
                              className="icon-button"
                              aria-label={`Ouvrir ${c.name} sur YouTube`}
                              href={`https://www.youtube.com/channel/${c.youtube_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <ArrowUpRight size={16} />
                            </a>
                            <button
                              className="icon-button"
                              aria-label={`Retirer le suivi de ${c.name}`}
                              onClick={() => {
                                setRemoveError("");
                                setRemove(c);
                              }}
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="statistics-no-channels">
                <strong>
                  {all.length
                    ? "Aucun résultat avec ces filtres"
                    : "Ta première chaîne commence avec son @pseudo"}
                </strong>
                <p>
                  {all.length
                    ? "Change le responsable ou efface la recherche."
                    : "Le studio peut suivre tes chaînes et celles que tu veux comparer, sans autorisation de leurs comptes."}
                </p>
                {!all.length && (
                  <Button
                    onClick={() => setAddOpen(true)}
                    disabled={!data.configuration.configured}
                  >
                    <Plus size={16} />
                    Ajouter une chaîne
                  </Button>
                )}
              </div>
            )}
          </section>
          {selected !== "all" && (
            <section className="panel public-videos-panel">
              <header>
                <div>
                  <h2>
                    Vidéos de{" "}
                    {detail?.name || all.find((c) => c.id === selected)?.name}
                  </h2>
                  <p className="muted small">
                    {detail?.videos_at
                      ? `Compteurs relevés le ${timestamp(detail.videos_at)}. `
                      : "La première collecte des vidéos est en attente. "}
                    {detail?.has_more
                      ? `Les ${data.configuration.max_videos} dernières publications sont suivies.`
                      : "Publications publiques disponibles dans le suivi."}
                  </p>
                </div>
                <select
                  aria-label="Trier les vidéos suivies"
                  value={videoSort}
                  onChange={(e) => setVideoSort(e.target.value)}
                >
                  <option value="gain">Vues gagnées</option>
                  <option value="views">Vues cumulées</option>
                  <option value="likes">Likes</option>
                  <option value="comments">Commentaires</option>
                  <option value="date">Plus récentes</option>
                </select>
              </header>
              <label className="statistics-checkbox">
                <input
                  type="checkbox"
                  checked={publishedOnly}
                  onChange={(e) => setPublishedOnly(e.target.checked)}
                />
                Seulement les vidéos publiées sur la période choisie
              </label>
              {detail?.error && (
                <p role="alert" className="statistics-error">
                  {detail.error}
                </p>
              )}
              {!detail ? (
                <p role="status" className="muted">
                  Chargement des vidéos…
                </p>
              ) : videos.length ? (
                <div className="statistics-table-scroll">
                  <table className="public-video-table">
                    <thead>
                      <tr>
                        <th>Vidéo</th>
                        <th>Vues cumulées</th>
                        <th>Vues gagnées</th>
                        <th>Likes</th>
                        <th>Commentaires</th>
                        <th>Interactions / vues</th>
                      </tr>
                    </thead>
                    <tbody>
                      {videos.map((v) => (
                        <tr key={v.video_id}>
                          <td>
                            <a
                              href={`https://www.youtube.com/watch?v=${v.video_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <strong>{v.title}</strong>
                              <small>
                                {dateLabel(v.published_at)} ·{" "}
                                {v.duration === null
                                  ? "Durée indisponible"
                                  : `${Math.floor(v.duration / 60)}:${String(v.duration % 60).padStart(2, "0")}`}
                              </small>
                            </a>
                          </td>
                          <td>{format(v.views)}</td>
                          <td>
                            {delta(v.gain)}
                            <small>
                              {v.gain === null
                                ? "Deux relevés nécessaires"
                                : v.partial
                                  ? "Suivi partiel"
                                  : "Variation observée"}
                            </small>
                          </td>
                          <td>{format(v.likes)}</td>
                          <td>{format(v.comments)}</td>
                          <td>
                            {v.engagement === null
                              ? "—"
                              : `${format(v.engagement)} %`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted statistics-no-videos">
                  {detail.videos_at
                    ? "Aucune vidéo ne correspond à ces filtres."
                    : "Les compteurs de la chaîne sont déjà disponibles. Les vidéos arriveront à la collecte du worker."}
                </p>
              )}
            </section>
          )}
          <Disclosure title="Comprendre les chiffres">
            <div className="statistics-explanation">
              <p>
                Les vues et abonnés cumulés viennent de YouTube Data API v3,
                avec le @pseudo. Les gains sur 48 heures ou 7 jours sont la
                différence entre nos relevés : ils commencent au début du suivi
                et peuvent inclure les corrections de YouTube.
              </p>
              <p>
                Les vues cumulées d’une vidéo récente ne sont pas les vues de
                toute la chaîne sur la période. L’API publique ne donne pas la
                durée de visionnage, les revenus, le taux de clics ou
                l’historique privé de YouTube Analytics.
              </p>
              <p>
                Les abonnés sont arrondis par YouTube. « — » signifie que la
                donnée est masquée ou indisponible. Les relevés sont conservés
                29 jours. Le ratio d’interactions utilise uniquement les likes
                et commentaires publics de la vidéo.
              </p>
              {!data.configuration.worker_online && (
                <p className="statistics-error">
                  Le worker n’a pas signalé de présence récente. Les relevés
                  conservés restent consultables.
                </p>
              )}
            </div>
          </Disclosure>
        </>
      )}
      {keyOpen && (
        <KeySetup
          close={() => setKeyOpen(false)}
          done={() => {
            setKeyOpen(false);
            setNotice(
              "La lecture publique est activée. Ajoute maintenant le @pseudo d’une chaîne.",
            );
            setRevision((n) => n + 1);
          }}
        />
      )}
      {addOpen && (
        <AddChannel
          p={p}
          initialStudio={p.initialStudio || null}
          close={() => setAddOpen(false)}
          done={(id) => {
            setAddOpen(false);
            setSelected(id);
            setScope("all");
            setQuery("");
            setNotice(
              "Chaîne suivie : les compteurs sont disponibles, le suivi horaire démarre.",
            );
            setRevision((n) => n + 1);
          }}
        />
      )}
      {remove && (
        <Modal
          title={`Retirer le suivi de ${remove.name} ?`}
          subtitle="Cela supprime ses relevés statistiques. Sa chaîne et ses projets dans le studio restent disponibles."
          close={() => setRemove(null)}
        >
          <div className="form">
            {removeError && (
              <p role="alert" className="statistics-error">
                {removeError}
              </p>
            )}
            <Button
              variant="danger"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await api(`/statistics/channels/${remove.id}`, "DELETE");
                  if (selected === remove.id) setSelected("all");
                  setRemove(null);
                  setRevision((n) => n + 1);
                } catch (e) {
                  setRemoveError((e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              Retirer le suivi
            </Button>
            <Button onClick={() => setRemove(null)}>Annuler</Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
