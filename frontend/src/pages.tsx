import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  Plus,
  Radio,
  ArrowRight,
  Clock3,
  Clapperboard,
  CalendarDays,
  Check,
  CheckCircle2,
  ShieldCheck,
  Pause,
  Play,
  SlidersHorizontal,
  Link2,
  Search,
  ChevronLeft,
  ChevronRight,
  ListTodo,
  Trash2,
  RefreshCw,
  BookOpen,
  Image,
  Layers,
  Send,
  Bot,
  Activity,
  Users,
  Wallet,
  AlertTriangle,
  ExternalLink,
  Sparkles,
  Download,
  ListChecks,
} from "lucide-react";
import type {
  Channel,
  Video,
  Workspace,
  Page,
  User,
  Message,
  Task,
} from "./types";
import { api, dateLabel, dayKey, localTime, parisToIso, labels } from "./api";
import {
  Button,
  Tag,
  SectionTitle,
  Empty,
  ChannelMark,
  VideoThumb,
  VideoRow,
  Skyline,
  Modal,
} from "./components";
import type { Mutate } from "./forms";
import { ZoomImage } from "./image-viewer";
import { RoutinePicker } from "./routines";
import { TeamBoard, TeamScope, matchesScope } from "./team-board";
import { PersonalPlanning } from "./personal-planning";
import { YouTubeConnection } from "./youtube-connection";

export type PageProps = {
  data: Workspace;
  user: User;
  preview: boolean;
  mutate: Mutate;
  go: (page: Page) => void;
  newVideo: (channel?: number) => void;
  newTask: () => void;
  editTask: (task: Task) => void;
  openVideo: (video: Video) => void;
  editChannel: (channel: Channel) => void;
  newChannel: () => void;
  agent: (message?: string) => void;
  schedule: (day: string, channel?: number, postAt?: string) => void;
};

export function Overview(p: PageProps) {
  const { data } = p;
  const today = dateLabel(data.server_time, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  const delivered = data.videos.filter((v) => v.status === "delivered").length;
  const recent = [...data.videos]
    .sort((a, b) => Number(!!b.engine_ref.brief) - Number(!!a.engine_ref.brief))
    .slice(0, 3);
  return (
    <div className="page overview-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">TON CENTRE DE COMMANDE</span>
          <h1>
            Vue d’ensemble<span className="heading-dot">.</span>
          </h1>
          <p>Tout le studio, une longueur d’avance.</p>
        </div>
        <Button variant="primary" onClick={() => p.newVideo()}>
          <Plus size={17} />
          Nouvelle vidéo
        </Button>
      </div>
      <div className="hero-grid">
        <section className="hero panel">
          <Skyline />
          <div className="hero-label">
            <span className="live-dot" />
            NIGHT CITY / STUDIO OPÉRATIONNEL
          </div>
          <h2>
            De bonnes idées.
            <br />
            <span>De grandes chaînes.</span>
          </h2>
          <p>
            Crée, organise et fais grandir ton univers.
            <br />
            Delamain s’occupe du reste, selon tes règles.
          </p>
          <div className="hero-actions">
            <Button variant="primary" onClick={() => p.go("studio")}>
              Entrer dans le studio
              <ArrowUpRight size={17} />
            </Button>
            <button className="text-button" onClick={() => p.go("calendar")}>
              <CalendarDays size={15} />
              Voir le planning
            </button>
          </div>
          <div className="hero-footer">
            <span>ESPACE PARTAGÉ / {data.users.length} MEMBRES</span>
            <span>{today.toUpperCase()}</span>
          </div>
        </section>
        <section className="agent-summary panel">
          <div className="agent-summary-top">
            <div className="agent-orb">
              <Bot size={26} />
            </div>
            <Tag tone={data.connections.ai ? "ready" : "muted"}>
              <span className="live-dot" />
              {data.connections.ai ? "IA CONFIGURÉE" : "À CONNECTER"}
            </Tag>
          </div>
          <span className="eyebrow">TON COPILOTE</span>
          <h2>
            Delamain<span>_</span>
          </h2>
          <p>
            Un sujet à trouver ? Une semaine à préparer ? Donne-moi la mission.
          </p>
          <button
            className="agent-prompt"
            onClick={() =>
              p.agent(
                "Fais le point sur mes chaînes et propose les prochaines priorités.",
              )
            }
          >
            <Sparkles size={15} />
            <span>Fais le point sur le studio</span>
            <ArrowUpRight size={16} />
          </button>
          <button
            className="agent-prompt"
            onClick={() =>
              p.agent(
                "Crée les tâches prioritaires pour organiser les chaînes cette semaine.",
              )
            }
          >
            <ListTodo size={15} />
            <span>Prépare les tâches de la semaine</span>
            <ArrowUpRight size={16} />
          </button>
        </section>
      </div>
      <div className="stats-grid">
        {[
          {
            n: data.stats.ready,
            label: "Vidéos prêtes",
            sub: "Contrôlées et éligibles",
            icon: <CheckCircle2 size={18} />,
            accent: "yellow",
          },
          {
            n: data.stats.producing,
            label: "En production",
            sub: "Du script au montage",
            icon: <Clapperboard size={18} />,
            accent: "cyan",
          },
          {
            n: data.stats.scheduled,
            label: "Programmées",
            sub: "Prêtes avec un créneau",
            icon: <CalendarDays size={18} />,
            accent: "pink",
          },
          {
            n: delivered,
            label: "Livrées sur Discord",
            sub: "Publication à confirmer",
            icon: <Send size={18} />,
            accent: "violet",
          },
        ].map((s) => (
          <div key={s.label} className={"stat-card panel " + s.accent}>
            <div className="stat-top">
              <span>{s.label}</span>
              {s.icon}
            </div>
            <strong>{String(s.n).padStart(2, "0")}</strong>
            <small>{s.sub}</small>
            <div className="stat-lines" />
          </div>
        ))}
      </div>
      <div className="overview-bottom">
        <section className="panel channels-overview">
          <SectionTitle
            eyebrow="LA FLOTTE"
            title="Tes chaînes"
            action={
              <button className="text-button" onClick={() => p.go("channels")}>
                Tout voir
                <ArrowUpRight size={16} />
              </button>
            }
          />
          <div className="channel-table-head">
            <span>CHAÎNE</span>
            <span>STOCK PRÊT</span>
            <span>PROCHAIN POST</span>
            <span>MODE</span>
          </div>
          {data.channels.slice(0, 5).map((c) => (
            <button
              className="channel-table-row"
              key={c.id}
              onClick={() => p.editChannel(c)}
            >
              <div className="channel-table-name">
                <ChannelMark channel={c} size="small" />
                <div>
                  <strong>{c.name}</strong>
                  <small>{c.niche}</small>
                </div>
              </div>
              <div className="stock-meter">
                <span>
                  <strong>{c.ready}</strong>
                  <small> / {c.target_stock}</small>
                </span>
                <div>
                  <i
                    style={{
                      width: `${Math.min(100, (c.ready / Math.max(c.target_stock, 1)) * 100)}%`,
                      background: c.accent,
                    }}
                  />
                </div>
              </div>
              <span className="next-post">
                {c.next_post
                  ? dateLabel(c.next_post, {
                      day: "numeric",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "À planifier"}
              </span>
              <Tag tone={c.autonomy === "auto" ? "auto" : "muted"}>
                {c.paused
                  ? "PAUSE"
                  : c.autonomy === "auto"
                    ? "AUTO"
                    : "VALIDATION"}
              </Tag>
            </button>
          ))}
          <div className="panel-bottom">
            <span>{data.stats.channels} chaînes dans le studio</span>
            <button onClick={p.newChannel}>
              Ajouter une chaîne
              <Plus size={14} />
            </button>
          </div>
        </section>
        <section className="panel priorities">
          <SectionTitle eyebrow="RESTER EN AVANCE" title="À faire ensuite" />
          <div
            className="priority-card"
            onClick={() => p.go("channels")}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter") p.go("channels");
            }}
          >
            <div className="priority-icon cyan">
              <Link2 size={18} />
            </div>
            <div>
              <strong>Connecter les chaînes</strong>
              <p>
                {data.channels.filter((c) => !c.connected).length} connexions
                YouTube à terminer
              </p>
            </div>
            <ArrowUpRight size={17} />
          </div>
          <div
            className="priority-card"
            onClick={() => p.go("production")}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter") p.go("production");
            }}
          >
            <div className="priority-icon yellow">
              <ShieldCheck size={18} />
            </div>
            <div>
              <strong>Contrôler les prochaines vidéos</strong>
              <p>{data.stats.review} vidéos à relire avant publication</p>
            </div>
            <ArrowUpRight size={17} />
          </div>
          <div
            className="priority-card"
            onClick={() => p.go("calendar")}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter") p.go("calendar");
            }}
          >
            <div className="priority-icon pink">
              <CalendarDays size={18} />
            </div>
            <div>
              <strong>Remplir le calendrier</strong>
              <p>Des créneaux clairs pour chaque chaîne</p>
            </div>
            <ArrowUpRight size={17} />
          </div>
          <div className="today-note">
            <span className="eyebrow">AUJOURD’HUI</span>
            <strong>
              {data.today.length
                ? `${data.today.length} publication${data.today.length > 1 ? "s" : ""} prévue${data.today.length > 1 ? "s" : ""}`
                : "Le calendrier est ouvert."}
            </strong>
            <p>
              {data.today.length
                ? "Les contrôles déterminent ce qui pourra sortir."
                : "Choisis le prochain sujet et réserve son créneau."}
            </p>
            <Button onClick={() => p.go("calendar")}>
              Organiser la journée
              <ArrowRight size={15} />
            </Button>
          </div>
        </section>
      </div>
      <section className="panel recent-videos">
        <SectionTitle
          eyebrow="LES DERNIÈRES PRODUCTIONS"
          title="Dans le studio"
          action={
            <button className="text-button" onClick={() => p.go("production")}>
              Toute la production
              <ArrowUpRight size={16} />
            </button>
          }
        />
        {recent.length ? (
          recent.map((v) => (
            <VideoRow
              key={v.id}
              video={v}
              channel={data.channels.find((c) => c.id === v.channel_id)}
              onClick={() => p.openVideo(v)}
            />
          ))
        ) : (
          <Empty
            title="Le prochain projet commence ici"
            text="Ajoute un sujet pour préparer ta première vidéo."
            action={
              <Button onClick={() => p.newVideo()}>Nouvelle vidéo</Button>
            }
          />
        )}
      </section>
    </div>
  );
}

export function Channels(p: PageProps) {
  const [filter, setFilter] = useState("all");
  const [scope, setScope] = useState("all");
  const [view, setView] = useState("team");
  const list = p.data.channels.filter(
    (c) =>
      (filter === "all" || c.autonomy === filter) &&
      matchesScope(c, scope, p.user),
  );
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            LA FLOTTE / {p.data.channels.length} CHAÎNES
          </span>
          <h1>
            Tes chaînes<span className="heading-dot">.</span>
          </h1>
          <p>
            Drylow & Kanye. Des chaînes partagées, un responsable pour chacune.
          </p>
        </div>
        <Button variant="primary" onClick={p.newChannel}>
          <Plus size={17} />
          Ajouter une chaîne
        </Button>
      </div>
      <div className="filter-bar channels-filters">
        <div className="segmented">
          <button
            className={view === "team" ? "active" : ""}
            onClick={() => setView("team")}
          >
            Répartition
          </button>
          <button
            className={view === "details" ? "active" : ""}
            onClick={() => setView("details")}
          >
            Fiches des chaînes
          </button>
        </div>
        <TeamScope
          users={p.data.users}
          value={scope}
          onChange={setScope}
          label="Filtrer les chaînes par responsable"
        />
        <div className="tabs">
          {[
            ["all", "Toutes"],
            ["auto", "Automatiques"],
            ["manual", "Avec validation"],
          ].map(([k, label]) => (
            <button
              key={k}
              className={filter === k ? "active" : ""}
              onClick={() => setFilter(k)}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="muted small">{list.length} chaînes</span>
      </div>
      {view === "team" ? (
        <TeamBoard {...p} channels={list} />
      ) : (
        <div className="channel-grid">
          {list.map((c) => (
            <article
              className="panel channel-card"
              key={c.id}
              style={{ "--channel": c.accent } as React.CSSProperties}
            >
              <div className="channel-card-head">
                <ChannelMark channel={c} />
                <div className="channel-card-tags">
                  <Tag
                    tone={
                      c.paused
                        ? "blocked"
                        : c.autonomy === "auto"
                          ? "auto"
                          : "muted"
                    }
                  >
                    {c.paused
                      ? "EN PAUSE"
                      : c.autonomy === "auto"
                        ? "AUTOMATIQUE"
                        : "VALIDATION"}
                  </Tag>
                  <span className="channel-connect">
                    <i className={c.connected ? "connected" : ""} />
                    {c.connected ? "YouTube connecté" : "YouTube à connecter"}
                  </span>
                </div>
              </div>
              <h2>{c.name}</h2>
              <p className="channel-handle">
                {c.handle || "Identifiant à renseigner"} <span>·</span>{" "}
                {c.niche}
              </p>
              <p className="muted small">
                Responsable :{" "}
                {p.data.users.find((u) => u.id === c.responsible_id)?.name ||
                  "À répartir"}
              </p>
              <div className="channel-metrics">
                <div>
                  <strong>
                    {c.ready}
                    <small> / {c.target_stock}</small>
                  </strong>
                  <span>Vidéos prêtes</span>
                </div>
                <div>
                  <strong>
                    {c.format === "news"
                      ? `${c.freshness_hours}h`
                      : c.days_ahead.toString()}
                    <small>{c.format === "news" ? "" : " jours"}</small>
                  </strong>
                  <span>
                    {c.format === "news"
                      ? "Fraîcheur maximum"
                      : "Calendrier couvert"}
                  </span>
                </div>
              </div>
              <div className="channel-progress">
                <span
                  style={{
                    width: `${Math.min(100, (c.ready / Math.max(1, c.target_stock)) * 100)}%`,
                  }}
                />
              </div>
              <div className="channel-next">
                <Clock3 size={15} />
                <span>
                  {c.next_post
                    ? dateLabel(c.next_post, {
                        day: "numeric",
                        month: "long",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : "Prochaine publication à planifier"}
                </span>
              </div>
              <div className="channel-card-bottom">
                <Button onClick={() => p.editChannel(c)}>
                  <SlidersHorizontal size={15} />
                  Réglages
                </Button>
                <Button variant="ghost" onClick={() => p.newVideo(c.id)}>
                  <Plus size={16} />
                  Créer
                </Button>
              </div>
              <YouTubeConnection
                channel={c}
                configured={p.data.connections.youtube}
                preview={p.preview}
                user={p.user}
                mutate={p.mutate}
              />
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

const columns = [
  {
    key: "ideas",
    label: "Idées",
    statuses: ["idea", "research", "script"],
    tone: "muted",
  },
  {
    key: "creating",
    label: "En création",
    statuses: ["creating"],
    tone: "auto",
  },
  {
    key: "review",
    label: "À contrôler",
    statuses: ["review", "blocked"],
    tone: "blocked",
  },
  {
    key: "ready",
    label: "Prêtes & prévues",
    statuses: ["ready", "scheduled"],
    tone: "ready",
  },
  {
    key: "delivered",
    label: "Livrées & publiées",
    statuses: ["delivered", "published", "reported"],
    tone: "muted",
  },
];
export function Production(p: PageProps) {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [view, setView] = useState(() =>
    window.matchMedia("(max-width: 600px)").matches ? "list" : "board",
  );
  const vs = p.data.videos.filter(
    (v) =>
      (filter === "all" || v.channel_id === Number(filter)) &&
      v.title.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <div className="page production-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">DE L’IDÉE À LA PUBLICATION</span>
          <h1>
            Production<span className="heading-dot">.</span>
          </h1>
          <p>Le bon projet, au bon stade. Rien ne se perd.</p>
        </div>
        <Button variant="primary" onClick={() => p.newVideo()}>
          <Plus size={17} />
          Nouvelle vidéo
        </Button>
      </div>
      <div className="filter-bar">
        <div className="filters">
          <div className="input-with-icon">
            <Search size={16} />
            <input
              aria-label="Rechercher une vidéo"
              placeholder="Rechercher une vidéo…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <select
            aria-label="Filtrer les vidéos par chaîne"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">Toutes les chaînes</option>
            {p.data.channels.map((c) => (
              <option value={c.id} key={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div className="segmented">
          <button
            className={view === "board" ? "active" : ""}
            onClick={() => setView("board")}
          >
            <Layers size={15} />
            Tableau
          </button>
          <button
            className={view === "list" ? "active" : ""}
            onClick={() => setView("list")}
          >
            <ListTodo size={15} />
            Liste
          </button>
        </div>
      </div>
      {view === "board" ? (
        <div className="kanban">
          {columns.map((col) => {
            const list = vs.filter((v) => col.statuses.includes(v.status));
            return (
              <section className="kanban-column" key={col.key}>
                <div className="kanban-head">
                  <span>
                    <i className={col.tone} />
                    {col.label}
                  </span>
                  <small>{list.length}</small>
                </div>
                <div className="kanban-cards">
                  {list.map((v) => {
                    const c = p.data.channels.find(
                      (c) => c.id === v.channel_id,
                    );
                    const job = p.data.jobs.find(
                      (j) =>
                        j.video_id === v.id &&
                        ["running", "queued"].includes(j.status),
                    );
                    return (
                      <button
                        className="kanban-card panel"
                        key={v.id}
                        onClick={() => p.openVideo(v)}
                      >
                        <VideoThumb video={v} channel={c} />
                        <div className="kanban-card-body">
                          <span
                            className="eyebrow"
                            style={{ color: c?.accent }}
                          >
                            {c?.name}
                          </span>
                          <h3>{v.title}</h3>
                          <div className="kanban-meta">
                            <span>
                              <Clock3 size={13} />
                              {Number(v.minutes).toFixed(0)} min
                            </span>
                            <Tag tone={v.status}>{labels[v.status]}</Tag>
                          </div>
                          {v.post_at && (
                            <div className="kanban-date">
                              <CalendarDays size={13} />
                              {dateLabel(v.post_at, {
                                day: "numeric",
                                month: "short",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </div>
                          )}
                          {job && (
                            <div className="progress-track">
                              <span
                                style={{ width: `${job.progress * 100}%` }}
                              />
                            </div>
                          )}
                        </div>
                      </button>
                    );
                  })}
                  {!list.length && (
                    <div className="column-empty">Aucune vidéo à ce stade.</div>
                  )}
                </div>
                {col.key === "ideas" && (
                  <button className="kanban-add" onClick={() => p.newVideo()}>
                    <Plus size={15} />
                    Ajouter une idée
                  </button>
                )}
              </section>
            );
          })}
        </div>
      ) : (
        <section className="panel">
          {vs.length ? (
            vs.map((v) => (
              <VideoRow
                key={v.id}
                video={v}
                channel={p.data.channels.find((c) => c.id === v.channel_id)}
                onClick={() => p.openVideo(v)}
              />
            ))
          ) : (
            <Empty
              title="Aucune vidéo ici"
              text="Change le filtre ou ajoute un nouveau sujet."
            />
          )}
        </section>
      )}
    </div>
  );
}

export function Calendar(p: PageProps) {
  const today = dayKey(p.data.server_time);
  const [month, setMonth] = useState(today.slice(0, 7));
  const [filter, setFilter] = useState("all");
  const [scope, setScope] = useState("all");
  const [view, setView] = useState(() =>
    window.matchMedia("(max-width: 600px)").matches ? "agenda" : "month",
  );
  const [exporting, setExporting] = useState(false);
  const [year, m] = month.split("-").map(Number);
  const start = new Date(Date.UTC(year, m - 1, 1, 12));
  const pad = (start.getUTCDay() + 6) % 7;
  const count = new Date(Date.UTC(year, m, 0)).getUTCDate();
  const dayList = Array.from(
    { length: Math.ceil((pad + count) / 7) * 7 },
    (_, i) => {
      const d = new Date(Date.UTC(year, m - 1, i - pad + 1, 12));
      return {
        key: d.toISOString().slice(0, 10),
        number: d.getUTCDate(),
        current: d.getUTCMonth() === m - 1,
      };
    },
  );
  const personalChannels = p.data.channels.filter((c) =>
    matchesScope(c, scope, p.user),
  );
  const events = p.data.videos
    .filter(
      (v) => v.post_at && (filter === "all" || v.channel_id === Number(filter)),
    )
    .filter((v) => personalChannels.some((c) => c.id === v.channel_id));
  const personalTasks = p.data.tasks.filter((t) => {
    const member = scope === "mine" ? p.user.id : scope;
    const channelMatches = filter === "all" || t.channel_id === Number(filter);
    return (
      channelMatches &&
      (scope === "all" ||
        (scope === "unassigned" ? !t.assignee : t.assignee === member))
    );
  });
  function move(n: number) {
    setMonth(
      new Date(Date.UTC(year, m - 1 + n, 1, 12)).toISOString().slice(0, 7),
    );
  }
  async function exportMonth() {
    setExporting(true);
    await p.mutate(async () => {
      const query = new URLSearchParams({ month, scope });
      if (filter !== "all") query.set("channel_id", filter);
      const response = await fetch("/api/studio/calendar.ics?" + query, {
        credentials: "same-origin",
      });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(result.error || "Export indisponible.");
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = `edgerunners-${month}.ics`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    }, "Calendrier téléchargé. Ouvre ton agenda → Importer → sélectionne le fichier .ics. C’est une copie, sans synchronisation.");
    setExporting(false);
  }
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">LE RYTHME DU STUDIO</span>
          <h1>
            Calendrier<span className="heading-dot">.</span>
          </h1>
          <p>Tes publications, à l’heure. Fuseau : Belgique / Paris.</p>
        </div>
        <div className="heading-actions">
          <Button
            onClick={exportMonth}
            disabled={exporting || view === "rhythm"}
          >
            <Download size={16} />
            {exporting ? "Export en cours…" : "Exporter le mois"}
          </Button>
          <Button variant="primary" onClick={() => p.schedule(today)}>
            <Plus size={17} />
            Prévoir une publication
          </Button>
        </div>
      </div>
      <section className="panel calendar-panel">
        <div className="calendar-toolbar">
          {view !== "rhythm" && (
            <div className="month-nav">
              <button
                className="icon-button"
                onClick={() => move(-1)}
                aria-label="Mois précédent"
              >
                <ChevronLeft size={18} />
              </button>
              <h2>
                {dateLabel(start.toISOString(), {
                  month: "long",
                  year: "numeric",
                })}
              </h2>
              <button
                className="icon-button"
                onClick={() => move(1)}
                aria-label="Mois suivant"
              >
                <ChevronRight size={18} />
              </button>
              <Button onClick={() => setMonth(today.slice(0, 7))}>
                Aujourd’hui
              </Button>
            </div>
          )}
          <div className="filters">
            <TeamScope
              users={p.data.users}
              value={scope}
              onChange={(value) => {
                setScope(value);
                setFilter("all");
              }}
              label="Filtrer le calendrier par responsable"
            />
            <select
              aria-label="Filtrer le calendrier par chaîne"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="all">Toutes les chaînes</option>
              {personalChannels.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <div className="segmented">
              <button
                className={view === "month" ? "active" : ""}
                onClick={() => setView("month")}
              >
                Mois
              </button>
              <button
                className={view === "agenda" ? "active" : ""}
                onClick={() => setView("agenda")}
              >
                Agenda
              </button>
              <button
                className={view === "rhythm" ? "active" : ""}
                onClick={() => setView("rhythm")}
              >
                Qui poste ?
              </button>
            </div>
          </div>
        </div>
        {view === "rhythm" ? (
          <PersonalPlanning {...p} scope={scope} channelFilter={filter} />
        ) : view === "month" ? (
          <div className="month-scroll">
            <div className="week-head">
              {["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"].map((s) => (
                <span key={s}>{s}</span>
              ))}
            </div>
            <div className="month-grid">
              {dayList.map((d) => (
                <div
                  key={d.key}
                  className={`calendar-day ${d.current ? "" : "outside"} ${d.key === today ? "today" : ""}`}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const vid = e.dataTransfer.getData("text/plain");
                    const v = p.data.videos.find((v) => v.id === vid);
                    if (v) {
                      const c = p.data.channels.find(
                        (c) => c.id === v.channel_id,
                      );
                      p.mutate(
                        () =>
                          api(`/videos/${v.id}`, "PATCH", {
                            revision: v.revision,
                            post_at: parisToIso(
                              d.key + "T" + (c?.post_time || "18:00"),
                            ),
                          }),
                        "Créneau déplacé.",
                      );
                    }
                  }}
                >
                  <button
                    className="day-number"
                    onClick={() => p.schedule(d.key)}
                    aria-label={`Ajouter une publication le ${d.key}`}
                  >
                    {d.number}
                    <Plus size={12} />
                  </button>
                  {events
                    .filter((v) => dayKey(v.post_at) === d.key)
                    .map((v) => {
                      const c = p.data.channels.find(
                        (c) => c.id === v.channel_id,
                      );
                      return (
                        <button
                          className="calendar-event"
                          key={v.id}
                          style={
                            { "--channel": c?.accent } as React.CSSProperties
                          }
                          draggable
                          onDragStart={(e) =>
                            e.dataTransfer.setData("text/plain", v.id)
                          }
                          onClick={() => p.openVideo(v)}
                        >
                          <small>
                            {dateLabel(v.post_at, {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}{" "}
                            · {c?.initials}
                          </small>
                          <strong>{v.title}</strong>
                          <span>{labels[v.status]}</span>
                        </button>
                      );
                    })}
                  {personalTasks
                    .filter(
                      (t) => !t.done && t.due_at && dayKey(t.due_at) === d.key,
                    )
                    .map((t) => (
                      <button
                        key={t.id}
                        className="calendar-task"
                        onClick={() => p.go("tasks")}
                      >
                        <ListTodo size={12} />
                        {t.title}
                      </button>
                    ))}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="agenda-list">
            {events.filter((v) => dayKey(v.post_at).startsWith(month))
              .length ? (
              events
                .filter((v) => dayKey(v.post_at).startsWith(month))
                .sort((a, b) => a.post_at.localeCompare(b.post_at))
                .map((v) => (
                  <VideoRow
                    key={v.id}
                    video={v}
                    channel={p.data.channels.find((c) => c.id === v.channel_id)}
                    onClick={() => p.openVideo(v)}
                  />
                ))
            ) : (
              <Empty
                icon={<CalendarDays size={26} />}
                title="Un mois à organiser"
                text="Réserve un créneau pour tes prochaines vidéos."
                action={
                  <Button onClick={() => p.schedule(today)}>
                    Ajouter un créneau
                  </Button>
                }
              />
            )}
          </div>
        )}
        <footer className="calendar-footer">
          <span>
            <i />
            Aujourd’hui
          </span>
          <span>
            Déplace une vidéo pour changer son jour. Les contrôles restent
            obligatoires.
          </span>
        </footer>
      </section>
    </div>
  );
}

export function Tasks(p: PageProps) {
  const [filter, setFilter] = useState("open");
  const [routineOpen, setRoutineOpen] = useState(false);
  const [channelFilter, setChannelFilter] = useState("all");
  const [taskSearch, setTaskSearch] = useState("");
  const tasks = p.data.tasks.filter(
    (t) =>
      (channelFilter === "all" || t.channel_id === Number(channelFilter)) &&
      t.title.toLowerCase().includes(taskSearch.toLowerCase()) &&
      (filter === "all" ||
        (filter === "done" && t.done) ||
        (filter === "open" && !t.done) ||
        (filter === "mine" && t.assignee === p.user.id && !t.done) ||
        (filter === "overdue" &&
          !t.done &&
          t.due_at &&
          new Date(t.due_at) < new Date(p.data.server_time))),
  );
  const done = p.data.tasks.filter((t) => t.done).length;
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">CHAQUE ACTION COMPTE</span>
          <h1>
            Tâches<span className="heading-dot">.</span>
          </h1>
          <p>Toi, ton collègue, et un plan commun.</p>
        </div>
        <div className="heading-actions">
          <Button onClick={() => setRoutineOpen(true)}>
            <ListChecks size={16} />
            Ajouter une routine
          </Button>
          <Button variant="primary" onClick={p.newTask}>
            <Plus size={17} />
            Nouvelle tâche
          </Button>
        </div>
      </div>
      {routineOpen && (
        <RoutinePicker p={p} close={() => setRoutineOpen(false)} />
      )}
      <div className="task-summary">
        <div className="panel">
          <ListTodo size={20} />
          <strong>{p.data.tasks.length - done}</strong>
          <span>À faire</span>
        </div>
        <div className="panel">
          <CheckCircle2 size={20} />
          <strong>{done}</strong>
          <span>Terminées</span>
        </div>
        <div className="panel">
          <Users size={20} />
          <strong>{p.data.users.length}</strong>
          <span>Dans l’équipe</span>
        </div>
      </div>
      <section className="panel task-panel">
        <div className="filter-bar">
          <div className="tabs">
            {[
              ["open", "À faire"],
              ["mine", "Mes tâches"],
              ["overdue", "En retard"],
              ["all", "Toutes"],
              ["done", "Terminées"],
            ].map(([key, label]) => (
              <button
                key={key}
                className={filter === key ? "active" : ""}
                onClick={() => setFilter(key)}
              >
                {label}
              </button>
            ))}
          </div>
          <span className="small muted">{tasks.length} tâches</span>
        </div>
        <div className="task-tools">
          <div className="search-field">
            <Search size={15} />
            <input
              aria-label="Rechercher une tâche"
              placeholder="Trouver une tâche…"
              value={taskSearch}
              onChange={(e) => setTaskSearch(e.target.value)}
            />
          </div>
          <select
            aria-label="Filtrer les tâches par chaîne"
            value={channelFilter}
            onChange={(e) => setChannelFilter(e.target.value)}
          >
            <option value="all">Toutes les chaînes</option>
            {p.data.channels.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        {tasks.length ? (
          tasks.map((t) => {
            const c = p.data.channels.find((c) => c.id === t.channel_id);
            const u = p.data.users.find((u) => u.id === t.assignee);
            return (
              <div className={"task-row " + (t.done ? "done" : "")} key={t.id}>
                <button
                  className={"task-check " + (t.done ? "checked" : "")}
                  aria-label={
                    t.done ? `Rouvrir ${t.title}` : `Terminer ${t.title}`
                  }
                  onClick={() =>
                    p.mutate(
                      () =>
                        api(`/tasks/${t.id}`, "PATCH", {
                          revision: t.revision,
                          done: !t.done,
                        }),
                      "Tâche mise à jour.",
                    )
                  }
                >
                  {!!t.done && <Check size={15} />}
                </button>
                <div className="task-row-title">
                  <button
                    className="task-edit-title"
                    onClick={() => p.editTask(t)}
                  >
                    {t.title}
                  </button>
                  <small>
                    {c?.name || "Tout le studio"}
                    {t.due_at &&
                      " · " +
                        dateLabel(t.due_at, {
                          day: "numeric",
                          month: "short",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                  </small>
                  {t.video_id &&
                    p.data.videos.find((v) => v.id === t.video_id) && (
                      <button
                        className="task-video-link"
                        onClick={() =>
                          p.openVideo(
                            p.data.videos.find((v) => v.id === t.video_id)!,
                          )
                        }
                      >
                        <Clapperboard size={12} />
                        Ouvrir la vidéo liée
                        <ArrowUpRight size={12} />
                      </button>
                    )}
                </div>
                <Tag tone={t.priority === "high" ? "blocked" : "muted"}>
                  {t.priority === "high"
                    ? "HAUTE"
                    : t.priority === "low"
                      ? "BASSE"
                      : "NORMALE"}
                </Tag>
                <span className="assignee">
                  {u && (
                    <span className="avatar small-avatar">
                      {u.name.slice(0, 1)}
                    </span>
                  )}
                  {u?.name || "Non attribuée"}
                </span>
                <button
                  className="icon-button"
                  aria-label={`Supprimer ${t.title}`}
                  onClick={() =>
                    p.mutate(
                      () =>
                        api(`/tasks/${t.id}`, "DELETE", {
                          revision: t.revision,
                        }),
                      "Tâche supprimée.",
                    )
                  }
                >
                  <Trash2 size={15} />
                </button>
              </div>
            );
          })
        ) : (
          <Empty
            icon={<ListTodo size={30} />}
            title={
              filter === "done"
                ? "Les premières victoires arrivent"
                : "De la place pour les prochaines missions"
            }
            text="Ajoute une tâche, attribue-la et retrouve-la ici à la prochaine connexion."
            action={
              <Button onClick={p.newTask}>
                <Plus size={16} />
                Ajouter une tâche
              </Button>
            }
          />
        )}
      </section>
    </div>
  );
}

export function Studio(p: PageProps) {
  const formats = [
    {
      key: "news",
      name: "Actualités sportives",
      sub: "MMA · Football · Boxe",
      text: "Des faits sourcés, une analyse de 4–6 minutes et les miniatures du thème approuvé.",
      icon: <Radio size={32} />,
      tone: "cyan",
      mark: "DISPATCH / 01",
    },
    {
      key: "pov",
      name: "L’univers Oddly",
      sub: "Vies · Économie · Objets",
      text: "Tes styles 2D, leurs voix et leurs règles. Du sujet au montage animé.",
      icon: <Layers size={32} />,
      tone: "yellow",
      mark: "ODDLY / 02",
    },
    {
      key: "history",
      name: "Documentaires",
      sub: "Témoignages · Frontière",
      text: "Des récits historiques, des sources réelles et un montage immersif.",
      icon: <BookOpen size={32} />,
      tone: "pink",
      mark: "HISTORY / 03",
    },
  ];
  const [chosen, setChosen] = useState("news");
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">LA CRÉATION COMMENCE ICI</span>
          <h1>
            Studio vidéo<span className="heading-dot">.</span>
          </h1>
          <p>Les outils qui font tes vidéos, dans un seul espace.</p>
        </div>
        <Button
          onClick={() =>
            p.mutate(
              () => api("/import", "POST", {}),
              "Productions existantes synchronisées.",
            )
          }
        >
          <RefreshCw size={16} />
          Synchroniser
        </Button>
      </div>
      <section className="studio-intro panel">
        <span className="eyebrow">CHOISIS TON UNIVERS</span>
        <h2>
          La prochaine vidéo
          <br />
          commence avec <span>une idée.</span>
        </h2>
        <p>
          Choisis le format, puis la chaîne.
          <br />
          On garde le style et les réglages qui font son identité.
        </p>
        <div className="studio-reel">
          <Clapperboard size={76} />
          <span>CREATE / BUILD / PUBLISH</span>
        </div>
      </section>
      <div className="format-grid">
        {formats.map((f) => (
          <button
            className={
              "format-card panel " +
              f.tone +
              (chosen === f.key ? " selected" : "")
            }
            key={f.key}
            onClick={() => setChosen(f.key)}
          >
            <div className="format-top">
              <span>{f.mark}</span>
              {chosen === f.key ? (
                <CheckCircle2 size={19} />
              ) : (
                <ArrowUpRight size={19} />
              )}
            </div>
            <div className="format-icon">{f.icon}</div>
            <h2>{f.name}</h2>
            <span className="format-sub">{f.sub}</span>
            <p>{f.text}</p>
          </button>
        ))}
      </div>
      <section className="panel choose-channel">
        <SectionTitle
          eyebrow="POUR QUELLE CHAÎNE ?"
          title="Garder son identité"
        />
        <div className="studio-channel-list">
          {p.data.channels
            .filter((c) => c.format === chosen)
            .map((c) => (
              <button key={c.id} onClick={() => p.newVideo(c.id)}>
                <ChannelMark channel={c} size="small" />
                <span>
                  <strong>{c.name}</strong>
                  <small>
                    {c.autonomy === "auto"
                      ? "Automatique après contrôles"
                      : "Avec ta validation"}
                  </small>
                </span>
                <ArrowUpRight size={18} />
              </button>
            ))}
        </div>
      </section>
      <section className="panel jobs-panel">
        <SectionTitle
          eyebrow="CE QUI SE PASSE EN COULISSES"
          title="Travaux de création"
        />
        {p.data.jobs.length ? (
          p.data.jobs.slice(0, 8).map((j) => (
            <div className="job-row" key={j.id}>
              <Activity size={17} />
              <div>
                <strong>
                  {p.data.videos.find((v) => v.id === j.video_id)?.title ||
                    "Delamain"}
                </strong>
                <small>{j.error || j.message}</small>
              </div>
              <Tag
                tone={
                  j.status === "failed"
                    ? "blocked"
                    : j.status === "done"
                      ? "ready"
                      : "auto"
                }
              >
                {j.status === "done"
                  ? "TERMINÉ"
                  : j.status === "running"
                    ? "EN COURS"
                    : j.status === "queued"
                      ? "EN ATTENTE"
                      : j.status === "cancelled"
                        ? "ANNULÉ"
                        : "À REPRENDRE"}
              </Tag>
              {["running", "queued"].includes(j.status) && (
                <button
                  className="text-button"
                  onClick={() =>
                    p.mutate(
                      () => api(`/jobs/${j.id}/cancel`, "POST", {}),
                      "Annulation demandée.",
                    )
                  }
                >
                  Annuler
                </button>
              )}
            </div>
          ))
        ) : (
          <Empty
            title="Les moteurs sont au repos"
            text="Les étapes et leur progression apparaîtront ici lorsque tu lanceras une création."
          />
        )}
      </section>
    </div>
  );
}

export function Library(p: PageProps) {
  const [tab, setTab] = useState("styles");
  const [refs, setRefs] = useState<{ name: string; path: string }[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    api<{ references: { name: string; path: string }[] }>("/library")
      .then((r) => setRefs(r.references))
      .catch((e) => setError(e.message));
  }, []);
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">L’IDENTITÉ DU STUDIO</span>
          <h1>
            Bibliothèque<span className="heading-dot">.</span>
          </h1>
          <p>Des références solides pour une qualité constante.</p>
        </div>
        <Tag tone="ready">
          <ShieldCheck size={14} />
          STYLES APPROUVÉS
        </Tag>
      </div>
      <div className="tabs library-tabs">
        {[
          ["styles", "Styles & miniatures"],
          ["videos", "Productions"],
          ["sources", "Sources"],
        ].map(([key, label]) => (
          <button
            className={tab === key ? "active" : ""}
            key={key}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>
      {error && <div className="error-box">{error}</div>}
      {tab === "styles" && (
        <>
          <div className="library-note panel">
            <Image size={25} />
            <div>
              <h3>La même direction, à chaque vidéo.</h3>
              <p>
                Ces références sont conservées. Les prochaines miniatures
                sportives suivront le thème que tu as validé.
              </p>
            </div>
          </div>
          <div className="reference-grid">
            {refs.map((r) => (
              <article className="panel reference-card" key={r.path}>
                <ZoomImage
                  src={"/media/reference/" + r.path}
                  alt={"Référence approuvée : " + r.name}
                  loading="lazy"
                />
                <div>
                  <span className="eyebrow">RÉFÉRENCE DE CHAÎNE</span>
                  <h3>
                    {r.path.includes("approved")
                      ? "Miniature sportive · " +
                        (r.path.includes("01") ? "01" : "02")
                      : r.name.replace(/_/g, " ")}
                  </h3>
                  <Tag tone="ready">CONSERVÉE</Tag>
                </div>
              </article>
            ))}
          </div>
        </>
      )}
      {tab === "videos" && (
        <div className="panel">
          {p.data.videos.map((v) => (
            <VideoRow
              key={v.id}
              video={v}
              channel={p.data.channels.find((c) => c.id === v.channel_id)}
              onClick={() => p.openVideo(v)}
            />
          ))}
        </div>
      )}
      {tab === "sources" && (
        <div className="panel source-library">
          <SectionTitle title="Les sources des productions" />
          {p.data.videos
            .filter((v) => v.sources.length)
            .map((v) => (
              <div className="source-group" key={v.id}>
                <h3>{v.title}</h3>
                {v.sources.map((s, i) => (
                  <a
                    key={s.id || i}
                    className="source-item"
                    href={s.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Link2 size={16} />
                    <div>
                      <strong>{s.name}</strong>
                      <small>{s.url}</small>
                    </div>
                    <ExternalLink size={15} />
                  </a>
                ))}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

export function Agent({
  data,
  initial = "",
  mutate,
  compact = false,
  openVideo,
  editChannel,
  go,
}: {
  data: Workspace;
  initial?: string;
  mutate: Mutate;
  compact?: boolean;
  openVideo: (video: Video) => void;
  editChannel: (channel: Channel) => void;
  go: (page: Page) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState(initial);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    setText(initial);
  }, [initial]);
  useEffect(() => {
    const get = () =>
      api<{ messages: Message[] }>("/chat")
        .then((r) => {
          setMessages(r.messages);
          setError("");
        })
        .catch((e) => setError(e.message));
    get();
    const timer = setInterval(get, 7000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (data.jobs.some((j) => j.kind === "agent")) {
      api<{ messages: Message[] }>("/chat")
        .then((r) => setMessages(r.messages))
        .catch((e) => setError(e.message));
    }
  }, [data.jobs]);
  const active = data.jobs.some(
    (j) => j.kind === "agent" && ["queued", "running"].includes(j.status),
  );
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSending(true);
    const ok = await mutate(
      () => api("/chat", "POST", { message: text }),
      "Demande transmise à Delamain.",
    );
    setSending(false);
    if (ok) {
      setText("");
      const r = await api<{ messages: Message[] }>("/chat");
      setMessages(r.messages);
    }
  }
  return (
    <div className={"agent-chat " + (compact ? "compact" : "")}>
      <div className="chat-profile">
        <div className="agent-orb">
          <Bot size={28} />
        </div>
        <div>
          <span className="eyebrow">INTELLIGENCE DU STUDIO</span>
          <h2>Delamain</h2>
          <small>
            <i className="live-dot" />
            {data.connections.ai
              ? "Service IA configuré"
              : "Connexion IA à terminer"}
          </small>
        </div>
      </div>
      <div className="chat-messages" aria-live="polite">
        {!messages.length && (
          <div className="chat-welcome">
            <span className="chat-welcome-symbol">
              D<span>_</span>
            </span>
            <h3>Quelle est la mission ?</h3>
            <p>
              Chaînes, tâches, planning, vidéos et miniatures : donne-moi une
              mission précise.
            </p>
            <div className="chat-suggestions">
              {[
                "Fais le point sur le studio.",
                "Propose des idées pour Cage Dispatch.",
                "Crée les tâches pour préparer la semaine.",
                "Montre-moi les miniatures des dernières vidéos.",
              ].map((s) => (
                <button key={s} onClick={() => setText(s)}>
                  {s}
                  <ArrowUpRight size={14} />
                </button>
              ))}
            </div>
            <span className="form-hint">
              Les actions utilisent tes permissions et les contrôles du studio.
              Les connexions et la relecture humaine se font dans les fiches et
              Réglages.
            </span>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={"chat-message " + m.role}>
            <span className="eyebrow">
              {m.role === "assistant" ? "DELAMAIN" : m.actor}
            </span>
            <p>{m.content}</p>
            {(m.attachments || []).map((link, index) => {
              const v =
                link.kind === "video"
                  ? data.videos.find((v) => v.id === link.id)
                  : undefined;
              const c =
                link.kind === "channel"
                  ? data.channels.find((c) => c.id === Number(link.id))
                  : undefined;
              if (v)
                return (
                  <article className="chat-attachment" key={index}>
                    {v.thumb_path ? (
                      <ZoomImage
                        src={`/media/${v.id}/thumbnail`}
                        alt={`Miniature : ${v.title}`}
                        caption="Agrandir la miniature"
                      />
                    ) : (
                      <p className="muted small">Miniature à choisir</p>
                    )}
                    <strong>{v.title}</strong>
                    <Button onClick={() => openVideo(v)}>
                      Ouvrir la fiche vidéo
                    </Button>
                  </article>
                );
              if (c)
                return (
                  <article className="chat-attachment channel" key={index}>
                    <ChannelMark channel={c} />
                    <strong>{c.name}</strong>
                    <Button onClick={() => editChannel(c)}>
                      Réglages de la chaîne
                    </Button>
                  </article>
                );
              if (
                link.kind === "page" &&
                [
                  "overview",
                  "channels",
                  "production",
                  "calendar",
                  "tasks",
                  "studio",
                  "library",
                  "settings",
                  "news",
                  "control",
                ].includes(String(link.id))
              )
                return (
                  <Button key={index} onClick={() => go(link.id as Page)}>
                    {link.title}
                  </Button>
                );
              return null;
            })}
            <small>
              {dateLabel(m.created_at, { hour: "2-digit", minute: "2-digit" })}
            </small>
          </div>
        ))}
        {active && (
          <div className="agent-thinking">
            <span />
            <span />
            <span />
            Delamain travaille…
          </div>
        )}
        {error && <p className="error-text">{error}</p>}
      </div>
      <form className="chat-input" onSubmit={submit}>
        <textarea
          value={text}
          rows={2}
          placeholder="Donne une mission à Delamain…"
          aria-label="Message à Delamain"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              if (
                window.matchMedia("(hover: hover) and (pointer: fine)").matches
              ) {
                e.preventDefault();
                e.currentTarget.form?.requestSubmit();
              }
            }
          }}
        />
        <button
          type="submit"
          disabled={sending || active || !text.trim()}
          aria-label="Envoyer à Delamain"
        >
          <ArrowUpRight size={20} />
        </button>
      </form>
      <p className="chat-footnote">
        Mise en file ≠ publication confirmée · les contrôles restent
        obligatoires
      </p>
    </div>
  );
}

export function Settings(p: PageProps) {
  const [budget, setBudget] = useState(p.data.settings.daily_budget);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [guide, setGuide] = useState(false);
  const labelsConnections = [
    ["ai", "Agent & création IA", "Recherche, scripts et visuels"],
    [
      "voice",
      "Voix des chaînes Oddly / sport",
      "Fournisseur de voix configuré",
    ],
    [
      "voice_history",
      "Voix des documentaires",
      "Fournisseur de narration configuré",
    ],
    ["render", "Rendu distant", "Relais du VPS de production"],
    ["discord_mma", "Discord · Cage Dispatch", "Paquets des vidéos MMA"],
    ["discord_football", "Discord · Pitch Dispatch", "Paquets des vidéos foot"],
    ["youtube", "Publication YouTube", "Connexion Google du studio"],
  ];
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">TON STUDIO, TES RÈGLES</span>
          <h1>
            Réglages<span className="heading-dot">.</span>
          </h1>
          <p>Les connexions, l’équipe et les limites de production.</p>
        </div>
        <Tag tone="muted">HEURE BELGE / PARIS</Tag>
      </div>
      <div className="settings-grid">
        <section className="panel settings-card">
          <SectionTitle
            eyebrow="GARDE LE CONTRÔLE"
            title="Production & budget"
          />
          <div className="pause-box">
            <div className="priority-icon yellow">
              {p.data.settings.paused ? (
                <Pause size={20} />
              ) : (
                <Play size={20} />
              )}
            </div>
            <div>
              <strong>
                {p.data.settings.paused
                  ? "Le studio est en pause"
                  : "Le studio peut travailler"}
              </strong>
              <p>Une pause bloque les nouveaux lancements et publications.</p>
            </div>
            <button
              className={"toggle " + (!p.data.settings.paused ? "on" : "")}
              aria-label={
                p.data.settings.paused
                  ? "Reprendre le studio"
                  : "Mettre le studio en pause"
              }
              aria-pressed={!p.data.settings.paused}
              onClick={() =>
                p.mutate(
                  () =>
                    api("/settings", "PATCH", {
                      revision: p.data.settings.revision,
                      paused: !p.data.settings.paused,
                    }),
                  "État du studio mis à jour.",
                )
              }
            >
              <i />
            </button>
          </div>
          <form
            className="form"
            onSubmit={async (e) => {
              e.preventDefault();
              await p.mutate(
                () =>
                  api("/settings", "PATCH", {
                    revision: p.data.settings.revision,
                    daily_budget: budget,
                  }),
                "Budget enregistré.",
              );
            }}
          >
            <label>
              Budget quotidien autorisé ($)
              <div className="budget-input">
                <Wallet size={19} />
                <input
                  type="number"
                  step="1"
                  min="0"
                  max="1000"
                  value={budget}
                  onChange={(e) => setBudget(Number(e.target.value))}
                />
              </div>
            </label>
            <p className="form-hint">
              Chaque lancement réserve le budget de sa vidéo. Les factures
              réelles des fournisseurs restent distinctes ; aucun coût fictif
              n’est affiché.
            </p>
            <Button type="submit">
              <Check size={15} />
              Enregistrer le budget
            </Button>
          </form>
          <div className="settings-detail">
            <Clock3 size={17} />
            <div>
              <strong>Europe/Paris</strong>
              <span>
                Calendrier en heure belge, changements d’heure inclus.
              </span>
            </div>
          </div>
        </section>
        <section className="panel settings-card">
          <SectionTitle
            eyebrow="L’ESPACE PARTAGÉ"
            title="Ton équipe"
            action={
              <Button onClick={() => setAdding(true)}>
                <Plus size={15} />
                Ajouter
              </Button>
            }
          />
          {p.data.users.map((u) => (
            <div className="user-row" key={u.id}>
              <span className="avatar">{u.name.slice(0, 1)}</span>
              <div>
                <strong>{u.name}</strong>
                <small>@{u.username}</small>
              </div>
              <Tag>{u.role === "owner" ? "PROPRIÉTAIRE" : "COLLABORATEUR"}</Tag>
            </div>
          ))}
          <div className="inline-note">
            <Users size={16} />
            Les vidéos, tâches et créneaux sont partagés. Les réglages sensibles
            sont réservés au propriétaire.
          </div>
          <div className="team-decoration">
            <span>EDGERUNNERS</span>
            <span>CREW</span>
            <small>BETTER TOGETHER / NIGHT CITY</small>
          </div>
        </section>
      </div>
      <section className="panel connections-panel">
        <SectionTitle eyebrow="LES SERVICES DU STUDIO" title="Connexions" />
        {labelsConnections.map(([key, label, desc]) => (
          <div className="connection-row" key={key}>
            <div className="connection-icon">
              {key === "youtube" ? (
                <Clapperboard size={20} />
              ) : key.includes("discord") ? (
                <Send size={20} />
              ) : key === "ai" ? (
                <Bot size={20} />
              ) : (
                <Link2 size={20} />
              )}
            </div>
            <div>
              <strong>{label}</strong>
              <small>{desc}</small>
            </div>
            <Tag tone={p.data.connections[key] ? "ready" : "muted"}>
              {p.data.connections[key] ? "CONFIGURÉ" : "À CONFIGURER"}
            </Tag>
            {key === "youtube" && (
              <Button onClick={() => setGuide(true)}>
                Comment connecter
                <ArrowUpRight size={14} />
              </Button>
            )}
          </div>
        ))}
        <div className="panel-bottom">
          <ShieldCheck size={15} />
          <span>
            Les clés sont conservées sur le serveur. Elles ne sont jamais
            affichées ici.
          </span>
        </div>
      </section>
      <section className="panel activity-panel">
        <SectionTitle eyebrow="CE QUI A CHANGÉ" title="Journal du studio" />
        {p.data.activity.length ? (
          p.data.activity.slice(0, 15).map((a) => (
            <div className="activity-row" key={a.id}>
              <span className="activity-dot" />
              <div>
                <strong>{a.message}</strong>
                <small>{a.actor}</small>
              </div>
              <time>
                {dateLabel(a.created_at, {
                  day: "numeric",
                  month: "short",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </time>
            </div>
          ))
        ) : (
          <Empty
            icon={<Activity size={24} />}
            title="Un historique commun"
            text="Les créations, modifications et publications apparaîtront ici."
          />
        )}
      </section>
      {adding && (
        <Modal title="Ajouter ton collègue" close={() => setAdding(false)}>
          <form
            className="form"
            onSubmit={async (e) => {
              e.preventDefault();
              if (
                await p.mutate(
                  () => api("/users", "POST", { name, username, password }),
                  "Compte créé.",
                )
              )
                setAdding(false);
            }}
          >
            <label>
              Prénom ou nom
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label>
              Identifiant
              <input
                required
                minLength={3}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="off"
              />
            </label>
            <label>
              Mot de passe initial
              <input
                required
                minLength={12}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
              />
            </label>
            <Button variant="primary" type="submit">
              <Plus size={16} />
              Créer le compte
            </Button>
          </form>
        </Modal>
      )}
      {guide && (
        <Modal title="Connecter YouTube" close={() => setGuide(false)}>
          <div className="form">
            <div className="inline-note">
              <Link2 size={20} />
              {p.data.connections.youtube
                ? "L’accès Google du studio est configuré."
                : "L’accès Google du studio doit être configuré sur le serveur avant la première connexion."}
            </div>
            <ol className="connection-steps">
              <li>
                Ouvre <strong>Chaînes</strong> et clique sur{" "}
                <strong>Connecter YouTube</strong> sur la chaîne à relier.
              </li>
              <li>
                Choisis son compte Google, puis la chaîne YouTube
                correspondante.
              </li>
              <li>
                Accepte les autorisations. Tu reviens au studio avec la chaîne
                connectée.
              </li>
            </ol>
            <p className="form-hint">
              Avant la première connexion, le propriétaire configure un client
              Google pour le studio. Les étapes, le serveur o2switch et
              l’adresse de retour sont décrits dans le guide ci-dessous.
            </p>
            <a
              className="button secondary"
              href="/api/studio/youtube/setup-guide"
              target="_blank"
              rel="noreferrer"
            >
              Ouvrir le guide de configuration <ExternalLink size={16} />
            </a>
            <Button
              variant="primary"
              onClick={() => {
                setGuide(false);
                p.go("channels");
              }}
            >
              Voir mes chaînes
              <ArrowRight size={16} />
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
