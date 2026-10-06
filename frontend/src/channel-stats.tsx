import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  BarChart3,
  Eye,
  RefreshCw,
  Settings,
  Plus,
} from "lucide-react";
import type { Channel } from "./types";
import type { PageProps } from "./pages";
import { api, dateLabel, labels } from "./api";
import { Button, ChannelMark, Modal } from "./components";
import { YouTubeConnection } from "./youtube-connection";
import "./channel-stats.css";

type Counters = {
  views: number | null;
  subscribers: number | null;
  videos: number | null;
};
type Snapshot = Counters & { captured_at: string };
type Report = {
  channel_id: number;
  connected: boolean;
  updated_at: string | null;
  totals: Counters;
  stale: boolean;
  error: string;
  refreshing: boolean;
  gain: number | null;
  since: string | null;
  until: string | null;
  partial: boolean;
  days: number;
  history: Snapshot[];
  recent_videos: {
    id: string;
    title: string;
    published_at: string;
    views: number | null;
  }[];
  videos_updated_at: string | null;
  status?: "updated" | "cached" | "running" | "error";
};
type Ranking = { channels: Report[]; ranking: Report[]; days: number };
const number = (value: number | null | undefined) =>
  value == null ? "—" : value.toLocaleString("fr-FR");
const change = (value: number) => (value >= 0 ? "+" : "") + number(value);
const stamp = (value: string) =>
  dateLabel(value, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

function Period({
  days,
  changeDays,
  disabled = false,
}: {
  days: number;
  changeDays: (days: number) => void;
  disabled?: boolean;
}) {
  return (
    <select
      aria-label="Période des statistiques"
      value={days}
      disabled={disabled}
      onChange={(e) => changeDays(Number(e.target.value))}
    >
      <option value={1}>24 heures</option>
      <option value={7}>7 jours</option>
      <option value={28}>28 jours</option>
    </select>
  );
}

function coverage(stats: Report) {
  return stats.since
    ? `${stats.partial ? "Suivi commencé le" : "Depuis le"} ${stamp(stats.since)}`
    : "La progression apparaîtra après deux relevés.";
}

export function ChannelRanking(p: PageProps & { channels: Channel[] }) {
  const [days, setDays] = useState(7);
  const [data, setData] = useState<Ranking | null>(null);
  const [error, setError] = useState("");
  const connectionKey = p.data.channels
    .map((c) => `${c.id}:${c.connected}:${c.yt_channel_id}`)
    .join(",");
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const value = await api<Ranking>(`/channel-stats?days=${days}`);
        if (active) {
          setData(value);
          setError("");
        }
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    }
    setData(null);
    void load();
    const timer = window.setInterval(() => {
      if (!document.hidden) void load();
    }, 60000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [days, connectionKey]);
  const ranking =
    data?.ranking
      .filter((r) => p.channels.some((c) => c.id === r.channel_id))
      .slice(0, 3) || [];
  const connected = p.channels.some((c) => c.connected);
  return (
    <section
      className="panel channel-ranking"
      aria-label="Progression des chaînes"
    >
      <header>
        <div>
          <span className="eyebrow">VUES RÉCENTES</span>
          <h2>
            <BarChart3 size={19} /> Les chaînes qui progressent
          </h2>
        </div>
        <Period days={days} changeDays={setDays} />
      </header>
      {error ? (
        <p role="alert" className="stats-error">
          {error}
        </p>
      ) : !data ? (
        <p className="muted small" role="status">
          Chargement des statistiques…
        </p>
      ) : ranking.length ? (
        <div className="ranking-list">
          {ranking.map((r, i) => {
            const channel = p.channels.find((c) => c.id === r.channel_id)!;
            return (
              <button
                className="ranking-row"
                key={r.channel_id}
                onClick={() => p.openChannel(channel)}
              >
                <span className="ranking-position">0{i + 1}</span>
                <ChannelMark channel={channel} />
                <span className="ranking-name">
                  <strong>{channel.name}</strong>
                  <small>
                    {coverage(r)} · relevé {stamp(r.updated_at!)}
                  </small>
                </span>
                <span
                  className={`ranking-gain ${r.gain! < 0 ? "negative" : ""}`}
                >
                  {change(r.gain!)}
                  <small>vues</small>
                </span>
                <ArrowUpRight size={16} />
              </button>
            );
          })}
        </div>
      ) : (
        <p className="stats-empty">
          {connected
            ? "Le classement apparaîtra après deux relevés récents et une connexion YouTube valide."
            : "Connecte YouTube pour suivre les vues et comparer tes chaînes. Tu peux déjà ouvrir chaque fiche en cliquant sur son nom."}
        </p>
      )}
      {ranking.length > 0 && (
        <p className="muted small stats-footnote">
          Variation des compteurs YouTube entre les dates affichées. Les
          périodes de suivi peuvent différer ; les chiffres peuvent être
          corrigés par YouTube.
        </p>
      )}
    </section>
  );
}

function History({ stats }: { stats: Report }) {
  const history = stats.history.filter((s) => s.views !== null);
  if (history.length < 2)
    return (
      <p className="stats-empty">
        Le graphique apparaîtra au deuxième relevé. Actualisation automatique
        toutes les 4 heures.
      </p>
    );
  const values = history.map((s) => s.views!);
  const low = Math.min(...values),
    high = Math.max(...values);
  const first = Date.parse(history[0].captured_at),
    last = Date.parse(history[history.length - 1].captured_at);
  const points = history.map((s) => ({
    ...s,
    x:
      12 +
      ((Date.parse(s.captured_at) - first) / Math.max(1, last - first)) * 576,
    y: 105 - ((s.views! - low) / Math.max(1, high - low)) * 84,
  }));
  return (
    <div className="stats-chart">
      <div className="stats-chart-label">
        <span>Vues cumulées</span>
        <span>
          {number(low)} → {number(high)}
        </span>
      </div>
      <svg
        viewBox="0 0 600 120"
        role="img"
        aria-label={`Vues cumulées du ${stamp(history[0].captured_at)} au ${stamp(history[history.length - 1].captured_at)} : ${number(values[0])} à ${number(values[values.length - 1])}`}
      >
        <path d="M12 105H588 M12 63H588 M12 21H588" className="stats-grid" />
        <polyline
          points={points.map((p) => `${p.x},${p.y}`).join(" ")}
          fill="none"
          className="stats-line"
        />
        {points.map((p) => (
          <circle key={p.captured_at} cx={p.x} cy={p.y} r="2.5">
            <title>
              {stamp(p.captured_at)} : {number(p.views)} vues
            </title>
          </circle>
        ))}
      </svg>
      <div className="stats-chart-label">
        <span>{stamp(history[0].captured_at)}</span>
        <span>{stamp(history[history.length - 1].captured_at)}</span>
      </div>
    </div>
  );
}

export function ChannelDetail(
  p: PageProps & { channel: Channel; close: () => void },
) {
  const c = p.channel;
  const [days, setDays] = useState(7);
  const [stats, setStats] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const result = await api<Report>(
          `/channels/${c.id}/stats?days=${days}`,
        );
        if (active) {
          setStats(result);
          setError("");
        }
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    }
    setStats(null);
    setNotice("");
    void load();
    const timer = window.setInterval(() => {
      if (!document.hidden) void load();
    }, 60000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [c.id, c.connected, c.yt_channel_id, days]);
  async function refreshStats() {
    setBusy(true);
    setNotice("");
    try {
      const value = await api<Report>(
        `/channels/${c.id}/stats/refresh?days=${days}`,
        "POST",
        {},
      );
      setStats(value);
      setError("");
      setNotice(
        value.status === "cached"
          ? "Le dernier essai est récent. Un nouvel essai sera possible 15 minutes après celui-ci."
          : value.status === "running"
            ? "Une actualisation est déjà en cours."
            : value.status === "error"
              ? ""
              : "Statistiques mises à jour.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const videos = p.data.videos.filter((v) => v.channel_id === c.id);
  const pending = videos.filter(
    (v) => !["published", "reported", "delivered"].includes(v.status),
  );
  return (
    <Modal
      title={c.name}
      subtitle={`Fiche de chaîne · ${p.data.users.find((u) => u.id === c.responsible_id)?.name || "À répartir"}`}
      close={p.close}
      wide
    >
      <div className="channel-detail">
        <div className="channel-detail-actions">
          <Button
            onClick={() => {
              p.close();
              p.editChannel(c);
            }}
          >
            <Settings size={15} /> Réglages
          </Button>
          <Button
            variant="primary"
            onClick={() => {
              p.close();
              p.newVideo(c.id);
            }}
          >
            <Plus size={15} /> Créer une vidéo
          </Button>
        </div>
        <section aria-label="Statistiques YouTube">
          <div className="stats-section-heading">
            <h3>
              <Eye size={18} /> Statistiques YouTube
            </h3>
            <div>
              <Period days={days} changeDays={setDays} disabled={busy} />
              <Button
                disabled={
                  !c.connected || p.preview || busy || stats?.refreshing
                }
                onClick={() => void refreshStats()}
              >
                <RefreshCw size={15} className={busy ? "spin" : ""} />
                {busy ? "Actualisation…" : "Actualiser"}
              </Button>
            </div>
          </div>
          {error && (
            <p className="stats-error" role="alert">
              {error}
            </p>
          )}
          {notice && (
            <p className="muted small" role="status">
              {notice}
            </p>
          )}
          {stats?.error && (
            <p className="stats-error" role="alert">
              {stats.error} Les chiffres conservés restent datés ci-dessous.
            </p>
          )}
          {!c.connected ? (
            <p className="stats-empty">
              Connecte cette chaîne à YouTube pour afficher ses statistiques.
              Son stock et ses projets sont disponibles ci-dessous.
            </p>
          ) : !stats ? (
            <p className="muted small" role="status">
              Chargement des statistiques…
            </p>
          ) : !stats.updated_at ? (
            <p className="stats-empty">
              Aucun relevé YouTube disponible. Clique « Actualiser » pour
              vérifier l’accès et récupérer les premiers chiffres.
            </p>
          ) : (
            <>
              <div className="youtube-metrics">
                <div>
                  <strong>{number(stats.totals.views)}</strong>
                  <span>Vues cumulées</span>
                </div>
                <div>
                  <strong>{number(stats.totals.subscribers)}</strong>
                  <span>Abonnés · arrondis par YouTube</span>
                </div>
                <div>
                  <strong>{number(stats.totals.videos)}</strong>
                  <span>Vidéos publiques</span>
                </div>
              </div>
              <div className="stats-growth">
                <span>Progression observée</span>
                <strong
                  className={
                    stats.gain !== null && stats.gain < 0 ? "negative" : ""
                  }
                >
                  {stats.gain === null ? "—" : change(stats.gain)}
                  {stats.gain !== null && " vues"}
                </strong>
                <small>{coverage(stats)}</small>
              </div>
              <History stats={stats} />
              <p className="muted small stats-footnote">
                Relevé YouTube : {stamp(stats.updated_at)}
                {stats.stale && " · données anciennes"}. Variation des
                compteurs, avec les éventuelles corrections de YouTube. Ce suivi
                commence à la connexion, sans historique antérieur.
              </p>
              {stats.recent_videos.length > 0 && (
                <div className="stats-recent">
                  <h3>Dernières vidéos sur YouTube</h3>
                  <p className="muted small">
                    Vues cumulées des 8 dernières publications maximum.
                    {stats.videos_updated_at &&
                      ` Relevé : ${stamp(stats.videos_updated_at)}.`}
                  </p>
                  {stats.recent_videos.map((v) => (
                    <a
                      key={v.id}
                      href={`https://www.youtube.com/watch?v=${v.id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <span>
                        <strong>{v.title}</strong>
                        <small>{dateLabel(v.published_at)}</small>
                      </span>
                      <span>
                        {number(v.views)}
                        <small>vues</small>
                      </span>
                      <ArrowUpRight size={16} />
                    </a>
                  ))}
                </div>
              )}
            </>
          )}
          <YouTubeConnection
            channel={c}
            configured={p.data.connections.youtube}
            preview={p.preview}
            user={p.user}
            mutate={p.mutate}
          />
        </section>
        <section aria-label="Stock et projets de la chaîne">
          <h3>Prêtes à poster & en préparation</h3>
          <div className="channel-stock-summary">
            <span>
              <strong>{c.ready}</strong> prêtes
            </span>
            <span>
              <strong>{c.producing}</strong> en création
            </span>
            <span>
              <strong>{c.awaiting_review}</strong> à valider
            </span>
          </div>
          <p className="muted small">
            {c.next_post
              ? `Prochaine publication : ${stamp(c.next_post)}`
              : c.publication_mode === "news"
                ? "Publication selon l’actualité · sans heure fixe"
                : "Prochaine publication à planifier"}
          </p>
          {pending.length ? (
            <div className="stats-projects">
              {pending.slice(0, 5).map((v) => (
                <button
                  key={v.id}
                  onClick={() => {
                    p.close();
                    p.openVideo(v);
                  }}
                >
                  <span>{v.title}</span>
                  <small>{labels[v.status] || v.status}</small>
                  <ArrowUpRight size={15} />
                </button>
              ))}
            </div>
          ) : (
            <p className="muted small">
              Aucun projet en attente pour cette chaîne.
            </p>
          )}
        </section>
      </div>
    </Modal>
  );
}
