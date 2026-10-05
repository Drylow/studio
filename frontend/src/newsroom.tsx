import { useEffect, useState } from "react";
import {
  Radio,
  RefreshCw,
  ArrowUpRight,
  Plus,
  X,
  Check,
  SlidersHorizontal,
  Clock3,
  FileSearch,
  Trash2,
  AlertTriangle,
} from "lucide-react";
import { api, dateLabel } from "./api";
import {
  Button,
  Tag,
  Empty,
  Modal,
  SectionTitle,
  ChannelMark,
} from "./components";
import type { PageProps } from "./pages";
import type { Source, Workspace } from "./types";

type Signal = {
  id: string;
  channel_id: number;
  title: string;
  url: string;
  published: string;
  summary: string;
  sources: Source[];
  fresh: boolean;
  status: string;
  video_id: string;
  revision: number;
};
type Feed = {
  id: string;
  channel_id: number;
  name: string;
  url: string;
  enabled: number;
  revision: number;
  last_checked: string;
  last_success: string;
  error: string;
};
type Config = {
  channel_id: number;
  enabled: number;
  interval_minutes: number;
  last_run: string;
  next_run: string;
  revision: number;
};
type Radar = { items: Signal[]; feeds: Feed[]; configs: Config[] };

export function Newsroom(p: PageProps) {
  const channels = p.data.channels.filter((c) => c.format === "news");
  const [cid, setCid] = useState(channels[0]?.id || 0);
  const [data, setData] = useState<Radar | null>(null);
  const [tab, setTab] = useState("new");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [settings, setSettings] = useState(false);
  const [feedName, setFeedName] = useState("");
  const [feedUrl, setFeedUrl] = useState("");
  const [interval, setIntervalValue] = useState(60);
  const channel = channels.find((c) => c.id === cid);
  const config = data?.configs.find((c) => c.channel_id === cid);
  const feeds = data?.feeds.filter((f) => f.channel_id === cid) || [];
  const items =
    data?.items.filter(
      (i) =>
        i.channel_id === cid &&
        (tab === "old" ? !i.fresh : i.fresh && i.status === tab),
    ) || [];
  async function load() {
    try {
      setData(await api<Radar>("/news"));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
    const timer = window.setInterval(load, 15000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    setNote("");
    setIntervalValue(config?.interval_minutes || 60);
  }, [cid, config?.interval_minutes]);
  async function change(operation: () => Promise<unknown>, message: string) {
    const ok = await p.mutate(operation, message);
    await load();
    return ok;
  }
  async function refresh() {
    setBusy(true);
    setNote("");
    await change(async () => {
      const result = await api<{
        added: number;
        successful_feeds: number;
        failed_feeds: number;
      }>("/news/scan", "POST", { channel_id: cid });
      setNote(
        `${result.added} nouvelle${result.added !== 1 ? "s" : ""} info${result.added !== 1 ? "s" : ""} · ${result.successful_feeds}/${result.successful_feeds + result.failed_feeds} sources accessibles.`,
      );
    }, "Recherche terminée.");
    setBusy(false);
  }
  async function prepare(item: Signal) {
    setBusy(true);
    await change(async () => {
      const result = await api<{ video_id: string }>(
        `/news/items/${item.id}/prepare`,
        "POST",
        { revision: item.revision },
      );
      const workspace = await api<Workspace>("/workspace");
      const video = workspace.videos.find((v) => v.id === result.video_id);
      if (video) p.openVideo(video);
    }, "Fiche de recherche préparée. Aucun appel payant lancé.");
    setBusy(false);
  }
  return (
    <div className="page news-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">SIGNAL / NIGHT CITY NEWSWIRE</span>
          <h1>
            Radar d’actus<span className="heading-dot">.</span>
          </h1>
          <p>Les bonnes infos, au bon moment. Avec leurs sources.</p>
        </div>
        <Button
          variant="primary"
          onClick={refresh}
          disabled={
            busy ||
            !feeds.some((f) => f.enabled) ||
            !!channel?.paused ||
            !!p.data.settings.paused
          }
        >
          <RefreshCw size={16} className={busy ? "spin" : ""} />
          {busy ? "Recherche en cours…" : "Actualiser les infos"}
        </Button>
      </div>
      <div className="news-channel-tabs">
        {channels.map((c) => (
          <button
            key={c.id}
            onClick={() => setCid(c.id)}
            className={c.id === cid ? "active" : ""}
          >
            <ChannelMark channel={c} />
            <span>{c.name}</span>
          </button>
        ))}
      </div>
      {error && <div className="error-box">{error}</div>}
      {channel && (
        <div className="news-layout">
          <section className="news-results">
            <div className="panel news-intro">
              <Radio size={27} />
              <div>
                <h2>{channel.name} / en direct</h2>
                <p>
                  Infos publiées dans les dernières {channel.freshness_hours}{" "}
                  heures. Les titres servent à repérer un sujet ; les faits
                  restent à vérifier avant le script.
                </p>
              </div>
              <Tag tone={config?.enabled ? "ready" : "muted"}>
                {config?.enabled ? "COLLECTE ACTIVE" : "COLLECTE MANUELLE"}
              </Tag>
            </div>
            <div className="filter-bar">
              <div className="tabs">
                {[
                  ["new", "À explorer"],
                  ["used", "En production"],
                  ["dismissed", "Écartées"],
                  ["old", "Périmées"],
                ].map(([k, label]) => (
                  <button
                    key={k}
                    className={tab === k ? "active" : ""}
                    onClick={() => setTab(k)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <span className="muted small">{items.length} infos</span>
            </div>
            {note && (
              <div className="news-result-note" role="status">
                {note}
              </div>
            )}
            {!data ? (
              <Empty
                icon={<RefreshCw className="spin" />}
                title="Ouverture du radar…"
                text="Les sources et sujets arrivent."
              />
            ) : !items.length ? (
              <Empty
                icon={<Radio size={28} />}
                title={
                  tab === "new"
                    ? "En attente de nouvelles infos"
                    : "Aucune info dans cette vue"
                }
                text={
                  tab === "new"
                    ? "Clique sur Actualiser les infos. Le radar garde les sources datées et rassemble les doublons."
                    : "Les sujets apparaîtront ici lorsqu’ils seront préparés, écartés ou périmés."
                }
              />
            ) : (
              <div className="news-cards">
                {items.map((item) => (
                  <article key={item.id} className="panel news-card">
                    <div className="news-card-meta">
                      <span className="eyebrow">{item.sources[0]?.name}</span>
                      <span>
                        <Clock3 size={12} />
                        {dateLabel(item.published, {
                          day: "numeric",
                          month: "short",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>
                    <h2>{item.title}</h2>
                    <p>
                      {item.summary ||
                        "Ouvre la source pour lire l’information dans son contexte."}
                    </p>
                    <div className="news-source-links">
                      {item.sources.map((s) => (
                        <a
                          key={s.id}
                          href={s.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {s.name}
                          <ArrowUpRight size={13} />
                        </a>
                      ))}
                    </div>
                    <div className="news-card-footer">
                      <Tag tone={item.fresh ? "review" : "muted"}>
                        {item.fresh ? "FAITS À VÉRIFIER" : "PÉRIMÉE"}
                      </Tag>
                      <div>
                        {item.video_id ? (
                          <Button
                            onClick={() => {
                              const v = p.data.videos.find(
                                (v) => v.id === item.video_id,
                              );
                              if (v) p.openVideo(v);
                            }}
                          >
                            <FileSearch size={14} />
                            Ouvrir la vidéo
                          </Button>
                        ) : (
                          item.fresh && (
                            <>
                              <Button
                                disabled={busy}
                                onClick={() =>
                                  change(
                                    () =>
                                      api(`/news/items/${item.id}`, "PATCH", {
                                        revision: item.revision,
                                        status:
                                          tab === "dismissed"
                                            ? "new"
                                            : "dismissed",
                                      }),
                                    tab === "dismissed"
                                      ? "Info rétablie."
                                      : "Info écartée.",
                                  )
                                }
                              >
                                {tab === "dismissed" ? "Rétablir" : "Écarter"}
                              </Button>
                              <Button
                                variant="primary"
                                disabled={busy}
                                onClick={() => prepare(item)}
                              >
                                <Plus size={14} />
                                Préparer une vidéo
                              </Button>
                            </>
                          )
                        )}
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
          <aside className="news-sidebar">
            <section className="panel">
              <SectionTitle
                eyebrow="LA VEILLE"
                title="Sources du radar"
                action={
                  p.user.role === "owner" && (
                    <button
                      className="icon-button"
                      aria-label="Configurer le radar"
                      onClick={() => setSettings(true)}
                    >
                      <SlidersHorizontal size={16} />
                    </button>
                  )
                }
              />
              <div className="news-feeds">
                {feeds.map((f) => (
                  <div key={f.id}>
                    <span
                      className={
                        f.error
                          ? "news-feed-error"
                          : f.enabled
                            ? "live-dot"
                            : "idle-dot"
                      }
                    />
                    <div>
                      <strong>{f.name}</strong>
                      <p>
                        {!f.enabled
                          ? "En pause"
                          : f.error ||
                            (f.last_success
                              ? "Lue le " +
                                dateLabel(f.last_success, {
                                  day: "numeric",
                                  month: "short",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })
                              : "Premier passage à lancer")}
                      </p>
                    </div>
                  </div>
                ))}
                {!feeds.length && (
                  <p className="muted">
                    Aucune source. Ouvre les réglages du radar pour ajouter un
                    flux RSS.
                  </p>
                )}
              </div>
            </section>
            <section className="panel news-rules">
              <span className="eyebrow">LA SUITE, SANS SE PERDRE</span>
              <h2>De l’info à la vidéo.</h2>
              <ol>
                <li>
                  <strong>Ouvrir la source.</strong>
                  <span>Vérifier les faits, la date et les citations.</span>
                </li>
                <li>
                  <strong>Préparer une vidéo.</strong>
                  <span>
                    Le sujet et les liens arrivent dans une fiche partagée.
                  </span>
                </li>
                <li>
                  <strong>Compléter les faits vérifiés.</strong>
                  <span>Puis écrire le script et lancer le montage.</span>
                </li>
              </ol>
              <p>
                Le radar ne télécharge aucun extrait, photo ou musique de ces
                articles.
              </p>
            </section>
            <section className="panel news-cadence">
              <Clock3 size={20} />
              <h3>
                {config?.enabled
                  ? `Un passage toutes les ${config.interval_minutes} minutes`
                  : "À ton rythme pour l’instant"}
              </h3>
              <p>
                {config?.enabled && config.next_run
                  ? "Prochain passage : " +
                    dateLabel(config.next_run, {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "La collecte régulière se règle ici, indépendamment de la publication YouTube."}
              </p>
            </section>
          </aside>
        </div>
      )}
      {settings && channel && (
        <Modal
          title="Régler le radar"
          subtitle={channel.name + " · sources et fréquence de collecte"}
          close={() => setSettings(false)}
          wide
        >
          <div className="news-settings form">
            <div className="inline-note">
              <AlertTriangle size={16} />
              Un flux aide à trouver des sujets. Il n’accorde aucun droit de
              réutilisation des médias.
            </div>
            <h3>Sources de veille</h3>
            <div className="news-feed-settings">
              {feeds.map((f) => (
                <div key={f.id}>
                  <div>
                    <strong>{f.name}</strong>
                    <a href={f.url} target="_blank" rel="noreferrer">
                      {f.url}
                    </a>
                  </div>
                  <button
                    className={"toggle " + (f.enabled ? "on" : "")}
                    aria-label={
                      (f.enabled ? "Désactiver " : "Activer ") + f.name
                    }
                    onClick={() =>
                      change(
                        () =>
                          api(`/news/feeds/${f.id}`, "PATCH", {
                            revision: f.revision,
                            enabled: !f.enabled,
                          }),
                        "Source mise à jour.",
                      )
                    }
                  >
                    <span />
                  </button>
                  <button
                    className="icon-button"
                    aria-label={"Supprimer " + f.name}
                    onClick={() =>
                      change(
                        () =>
                          api(`/news/feeds/${f.id}`, "DELETE", {
                            revision: f.revision,
                          }),
                        "Source supprimée.",
                      )
                    }
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}
            </div>
            <form
              className="news-add-feed"
              onSubmit={async (e) => {
                e.preventDefault();
                if (
                  await change(
                    () =>
                      api("/news/feeds", "POST", {
                        channel_id: cid,
                        name: feedName,
                        url: feedUrl,
                      }),
                    "Source ajoutée.",
                  )
                ) {
                  setFeedName("");
                  setFeedUrl("");
                }
              }}
            >
              <label>
                Nom de la source
                <input
                  required
                  value={feedName}
                  onChange={(e) => setFeedName(e.target.value)}
                  placeholder="Nom du média"
                />
              </label>
              <label>
                Adresse du flux RSS
                <input
                  required
                  type="url"
                  value={feedUrl}
                  onChange={(e) => setFeedUrl(e.target.value)}
                  placeholder="https://…/rss"
                />
              </label>
              <Button type="submit" disabled={feeds.length >= 6}>
                <Plus size={15} />
                Ajouter
              </Button>
            </form>
            {config && (
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  await change(
                    () =>
                      api(`/news/config/${cid}`, "PATCH", {
                        revision: config.revision,
                        enabled: config.enabled,
                        interval_minutes: interval,
                      }),
                    "Fréquence enregistrée.",
                  );
                }}
              >
                <h3>Collecte régulière</h3>
                <div className="form-grid">
                  <label>
                    Intervalle
                    <select
                      value={interval}
                      onChange={(e) => setIntervalValue(Number(e.target.value))}
                    >
                      {[
                        [30, "Toutes les 30 minutes"],
                        [60, "Toutes les heures"],
                        [120, "Toutes les 2 heures"],
                        [360, "Toutes les 6 heures"],
                        [1440, "Chaque jour"],
                      ].map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <Button type="submit">Enregistrer la fréquence</Button>
                </div>
                <div className="news-auto-toggle">
                  <div>
                    <strong>
                      {config.enabled
                        ? "Collecte régulière active"
                        : "Collecte régulière en pause"}
                    </strong>
                    <p>
                      Le serveur doit rester allumé. La pause générale et celle
                      de la chaîne suspendent les prochains passages.
                    </p>
                  </div>
                  <Button
                    variant={config.enabled ? "secondary" : "primary"}
                    onClick={() =>
                      change(
                        () =>
                          api(`/news/config/${cid}`, "PATCH", {
                            revision: config.revision,
                            enabled: !config.enabled,
                            interval_minutes: interval,
                          }),
                        config.enabled
                          ? "Collecte mise en pause."
                          : "Collecte régulière activée.",
                      )
                    }
                  >
                    {config.enabled ? "Mettre en pause" : "Activer la collecte"}
                  </Button>
                </div>
              </form>
            )}
            <div className="modal-footer">
              <Button onClick={() => setSettings(false)}>
                <Check size={15} />
                Terminé
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
