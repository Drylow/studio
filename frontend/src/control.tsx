import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Bell,
  Check,
  CheckCircle2,
  Clock3,
  RefreshCw,
  ShieldAlert,
  SlidersHorizontal,
  Workflow,
} from "lucide-react";
import { api, dateLabel } from "./api";
import { Button, ChannelMark, Empty, SectionTitle, Tag } from "./components";
import type { PageProps } from "./pages";
import type { Page } from "./types";

type ControlAlert = {
  key: string;
  fingerprint: string;
  level: string;
  category: string;
  title: string;
  message: string;
  help: string;
  read: boolean;
  read_at: string;
  action: {
    page: Page;
    label: string;
    kind?: string;
    video_id?: string;
    task_id?: string;
    channel_id?: number;
  };
};
type ControlData = {
  alerts: ControlAlert[];
  services: {
    id: string;
    name: string;
    state: string;
    detail: string;
    page: Page;
  }[];
  summary: { total: number; critical: number; unread: number };
  server_time: string;
  preview: boolean;
};
const categories: Record<string, string> = {
  all: "Tout",
  production: "Production",
  calendar: "Planning",
  stock: "Stock",
  tasks: "Tâches",
  news: "Radar",
  connections: "Connexions",
  system: "Moteur",
};
const levels: Record<string, string> = {
  critical: "À traiter en priorité",
  warning: "À préparer",
  info: "À suivre",
};

export function Control(p: PageProps) {
  const [data, setData] = useState<ControlData | null>(null);
  const [error, setError] = useState("");
  const [category, setCategory] = useState("all");
  const [unread, setUnread] = useState(false);
  const [loading, setLoading] = useState(false);
  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setData(await api<ControlData>("/control"));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => clearInterval(timer);
  }, [refresh]);
  const alerts =
    data?.alerts.filter(
      (a) =>
        (category === "all" || a.category === category) && (!unread || !a.read),
    ) || [];
  function act(a: ControlAlert) {
    const v = p.data.videos.find((v) => v.id === a.action.video_id);
    const task = p.data.tasks.find((t) => t.id === a.action.task_id);
    if (v) p.openVideo(v);
    else if (task) p.editTask(task);
    else if (a.action.kind === "new_video") p.newVideo(a.action.channel_id);
    else p.go(a.action.page);
  }
  return (
    <div className="page control-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">NETWATCH / LE POSTE DE COMMANDE</span>
          <h1>
            Centre de contrôle<span className="heading-dot">.</span>
          </h1>
          <p>Ce qui demande ton attention. Et comment le régler.</p>
        </div>
        <Button onClick={refresh} disabled={loading}>
          <RefreshCw size={16} className={loading ? "spin" : ""} />
          Actualiser le contrôle
        </Button>
      </div>
      {error && (
        <div className="error-box" role="alert">
          {error} Les informations ci-dessous peuvent être anciennes. Clique sur
          Actualiser le contrôle pour réessayer.
        </div>
      )}
      <section className="control-command panel">
        <div className="control-grid-art" aria-hidden="true">
          <span />
          <span />
          <span />
          <Activity size={100} />
        </div>
        <div className="control-command-copy">
          <span className="eyebrow">EDGERUNNERS / OPERATION BOARD</span>
          <h2>
            Garde une longueur
            <br />
            <span>d’avance.</span>
          </h2>
          <p>
            Un problème, une prochaine action. Les alertes suivent les données
            du studio et se retirent lorsque leur cause est résolue.
          </p>
          <div className="control-command-state">
            <span className={error ? "idle-dot" : "live-dot"} />
            {data
              ? "Dernière lecture à " +
                dateLabel(data.server_time, {
                  hour: "2-digit",
                  minute: "2-digit",
                }) +
                " · heure belge"
              : "Lecture du studio…"}
          </div>
        </div>
        <div className="control-counters">
          <div>
            <ShieldAlert size={20} />
            <strong>{data?.summary.critical ?? "—"}</strong>
            <span>Prioritaires</span>
          </div>
          <div>
            <Bell size={20} />
            <strong>{data?.summary.unread ?? "—"}</strong>
            <span>Non lues</span>
          </div>
          <div>
            <Workflow size={20} />
            <strong>
              {
                p.data.jobs.filter((j) =>
                  ["queued", "running"].includes(j.status),
                ).length
              }
            </strong>
            <span>Travaux actifs</span>
          </div>
        </div>
      </section>
      <div className="control-layout">
        <section className="panel control-alert-panel">
          <SectionTitle
            eyebrow="LA PROCHAINE ACTION"
            title="À prendre en main"
            action={
              <Tag>
                {alerts.length} {alerts.length > 1 ? "signaux" : "signal"}
              </Tag>
            }
          />
          <div className="control-filters">
            <select
              aria-label="Filtrer les alertes"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {Object.entries(categories).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
            <button
              className={"control-unread " + (unread ? "active" : "")}
              aria-pressed={unread}
              onClick={() => setUnread(!unread)}
            >
              <Bell size={14} />
              Non lues
            </button>
          </div>
          {!data ? (
            <Empty
              icon={<RefreshCw className="spin" />}
              title="Lecture du studio"
              text="Les contrôles arrivent."
            />
          ) : alerts.length ? (
            <div className="control-alerts">
              {alerts.map((a) => (
                <article key={a.key} className={"control-alert " + a.level}>
                  <div className="control-alert-header">
                    <Tag
                      tone={
                        a.level === "critical"
                          ? "danger"
                          : a.level === "warning"
                            ? "warning"
                            : "auto"
                      }
                    >
                      {levels[a.level]}
                    </Tag>
                    <span className="small muted">
                      {categories[a.category]}
                    </span>
                  </div>
                  <h3>{a.title}</h3>
                  <p>{a.message}</p>
                  <div className="control-next">
                    <ArrowUpRight size={16} />
                    <p>{a.help}</p>
                  </div>
                  <div className="control-alert-actions">
                    <Button onClick={() => act(a)}>
                      {a.action.label}
                      <ArrowUpRight size={14} />
                    </Button>
                    {a.read ? (
                      <span className="control-read">
                        <Check size={14} />
                        Lu par toi
                      </span>
                    ) : (
                      <button
                        className="text-button"
                        aria-label={"Marquer comme lue : " + a.title}
                        onClick={async () => {
                          const ok = await p.mutate(
                            () =>
                              api(
                                `/control/alerts/${encodeURIComponent(a.key)}/read`,
                                "POST",
                                { fingerprint: a.fingerprint },
                              ),
                            "Alerte lue. Le contrôle reste nécessaire.",
                          );
                          if (ok) await refresh();
                        }}
                      >
                        <Check size={14} />
                        Marquer comme lue
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <Empty
              icon={<CheckCircle2 />}
              title={
                unread
                  ? "Toutes les alertes de ce filtre sont lues."
                  : "Aucun signal dans ce filtre."
              }
              text="Une alerte lue reste visible dans Tout tant que sa cause n’est pas résolue."
            />
          )}
        </section>
        <aside className="control-side">
          <section className="panel">
            <SectionTitle
              eyebrow="LE SYSTÈME"
              title="Connexions & moteur"
              action={<SlidersHorizontal size={16} />}
            />
            <div className="control-services">
              {data?.services.map((s) => (
                <button
                  key={s.id}
                  onClick={() => p.go(s.page)}
                  className={"control-service " + s.state}
                >
                  <span className="service-light" />
                  <div>
                    <strong>{s.name}</strong>
                    <small>{s.detail}</small>
                  </div>
                  <ArrowUpRight size={14} />
                </button>
              ))}
            </div>
            <p className="control-service-note">
              La présence d’une configuration ne confirme pas qu’un fournisseur
              répond. Aucun appel payant n’est lancé par ce contrôle.
            </p>
          </section>
          <section className="panel">
            <SectionTitle eyebrow="LA FLOTTE" title="Le stock des chaînes" />
            <div className="control-stock">
              {p.data.channels.map((c) => (
                <button key={c.id} onClick={() => p.editChannel(c)}>
                  <ChannelMark channel={c} size="small" />
                  <div>
                    <strong>{c.name}</strong>
                    <small>
                      {c.format === "news"
                        ? `Infos fraîches · ${c.freshness_hours} h`
                        : `${c.days_ahead} jour(s) couvert(s)`}
                    </small>
                    <span className="control-stock-track">
                      <i
                        style={{
                          width:
                            Math.min(
                              100,
                              (c.ready / Math.max(1, c.target_stock)) * 100,
                            ) + "%",
                          background: c.accent,
                        }}
                      />
                    </span>
                  </div>
                  <span>
                    {c.ready}
                    <small>/{c.target_stock}</small>
                  </span>
                </button>
              ))}
            </div>
          </section>
          <section className="panel control-guidance">
            <Clock3 size={22} />
            <h3>Lu ne veut pas dire résolu.</h3>
            <p>
              Ton suivi est personnel. Ton collègue garde ses propres alertes
              non lues. Une modification du problème peut faire réapparaître
              l’alerte.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
