import React, { useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  LayoutDashboard,
  Radio,
  Clapperboard,
  CalendarDays,
  ListTodo,
  Layers,
  BookOpen,
  Settings as SettingsIcon,
  Bot,
  Search,
  Command,
  Plus,
  ArrowUpRight,
  Pause,
  Play,
  Menu,
  X,
  LogOut,
  Link2,
  AlertTriangle,
  ChevronRight,
  RefreshCw,
  CheckCircle2,
  ShieldCheck,
  Bell,
  ShieldAlert,
} from "lucide-react";
import { api, dateLabel, setCsrf } from "./api";
import type { Boot, Workspace, Page, Video, Channel } from "./types";
import { Button, Tag, Modal, Skyline, ChannelMark } from "./components";
import {
  ChannelForm,
  NewChannel,
  NewVideo,
  NewTask,
  ScheduleForm,
  VideoDetail,
} from "./forms";
import {
  Overview,
  Channels,
  Production,
  Calendar,
  Tasks,
  Studio,
  Library,
  Settings,
  Agent,
} from "./pages";
import type { PageProps } from "./pages";
import { Newsroom } from "./newsroom";
import { Control } from "./control";
import "./style.css";

const nav: { key: Page; path: string; label: string; icon: React.ReactNode }[] =
  [
    {
      key: "overview",
      path: "/",
      label: "Vue d’ensemble",
      icon: <LayoutDashboard size={18} />,
    },
    {
      key: "channels",
      path: "/channels",
      label: "Chaînes",
      icon: <Radio size={18} />,
    },
    {
      key: "control",
      path: "/control",
      label: "Centre de contrôle",
      icon: <ShieldAlert size={18} />,
    },
    {
      key: "news",
      path: "/news",
      label: "Radar d’actus",
      icon: <Radio size={18} />,
    },
    {
      key: "production",
      path: "/production",
      label: "Production",
      icon: <Clapperboard size={18} />,
    },
    {
      key: "calendar",
      path: "/calendar",
      label: "Calendrier",
      icon: <CalendarDays size={18} />,
    },
    {
      key: "tasks",
      path: "/tasks",
      label: "Tâches",
      icon: <ListTodo size={18} />,
    },
    {
      key: "studio",
      path: "/studio",
      label: "Studio vidéo",
      icon: <Layers size={18} />,
    },
    {
      key: "library",
      path: "/library",
      label: "Bibliothèque",
      icon: <BookOpen size={18} />,
    },
    {
      key: "agent",
      path: "/agent",
      label: "Delamain",
      icon: <Bot size={18} />,
    },
    {
      key: "settings",
      path: "/settings",
      label: "Réglages",
      icon: <SettingsIcon size={18} />,
    },
  ];
function currentPage() {
  return (
    nav.find((n) => n.path === window.location.pathname)?.key || "overview"
  );
}

function Login({
  boot,
  refresh,
}: {
  boot: Boot;
  refresh: () => Promise<void>;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <main className="login-page">
      <section className="login-world">
        <div className="brand">
          <span className="brand-icon">
            E<span>/</span>
          </span>
          <div>
            EDGERUNNERS<span>STUDIO</span>
          </div>
        </div>
        <span className="eyebrow">NIGHT CITY / CREATIVE HEADQUARTERS</span>
        <h1>
          Build your
          <br />
          <span>own empire.</span>
        </h1>
        <p>
          Tes chaînes. Ton équipe. Ton studio.
          <br />
          Un seul endroit pour faire avancer tes idées.
        </p>
        <Skyline />
        <div className="login-world-footer">
          AFTERLIFE / CREW ACCESS<span>EST. 2026</span>
        </div>
      </section>
      <section className="login-form">
        <span className="eyebrow">ACCÈS AU STUDIO</span>
        <h2>
          {boot.setup_required
            ? "Bienvenue dans ton studio."
            : "Content de te revoir."}
        </h2>
        <p>
          {boot.setup_required
            ? "Crée ton compte propriétaire. Tu pourras ensuite ajouter ton collègue."
            : "Connecte-toi pour retrouver ton espace partagé."}
        </p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await api(boot.setup_required ? "/setup" : "/login", "POST", {
                name,
                username,
                password,
                token,
              });
              await refresh();
            } catch (e) {
              setError((e as Error).message);
            }
            setBusy(false);
          }}
          className="form"
        >
          {boot.setup_required && (
            <>
              <label>
                Code d’activation
                <input
                  required
                  type="password"
                  autoComplete="off"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                />
              </label>
              <label>
                Ton nom
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
            </>
          )}
          <label>
            Identifiant
            <input
              required
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </label>
          <label>
            Mot de passe
            <input
              type="password"
              required
              minLength={boot.setup_required ? 12 : 1}
              autoComplete={
                boot.setup_required ? "new-password" : "current-password"
              }
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && (
            <div role="alert" className="error-box">
              {error}
            </div>
          )}
          <Button variant="primary" type="submit" disabled={busy}>
            {busy
              ? "Connexion…"
              : boot.setup_required
                ? "Activer le studio"
                : "Entrer dans le studio"}
            <ArrowUpRight size={17} />
          </Button>
        </form>
        <div className="login-security">
          <ShieldCheck size={16} />
          Espace privé · données partagées · clés protégées
        </div>
      </section>
    </main>
  );
}

function App() {
  const [boot, setBoot] = useState<Boot | null>(null);
  const [data, setData] = useState<Workspace | null>(null);
  const [fatal, setFatal] = useState("");
  const [syncError, setSyncError] = useState("");
  const [page, setPage] = useState<Page>(currentPage());
  const [toast, setToast] = useState<{ text: string; error: boolean } | null>(
    null,
  );
  const [mobile, setMobile] = useState(false);
  const [agentOpen, setAgentOpen] = useState(false);
  const [agentText, setAgentText] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [newVideoChannel, setNewVideoChannel] = useState<number | undefined>(
    undefined,
  );
  const [creatingVideo, setCreatingVideo] = useState(false);
  const [creatingTask, setCreatingTask] = useState(false);
  const [editingTask, setEditingTask] = useState<string | null>(null);
  const [creatingChannel, setCreatingChannel] = useState(false);
  const [editingChannel, setEditingChannel] = useState<number | null>(null);
  const [openedVideo, setOpenedVideo] = useState<string | null>(null);
  const [scheduleDay, setScheduleDay] = useState<{
    day: string;
    channel?: number;
    postAt?: string;
  } | null>(null);
  const refresh = useCallback(async () => {
    const b = await api<Boot>("/bootstrap");
    setCsrf(b.csrf);
    setBoot(b);
    if (b.user) {
      const w = await api<Workspace>("/workspace");
      setData(w);
    } else setData(null);
    setSyncError("");
  }, []);
  useEffect(() => {
    const viewport = window.visualViewport;
    const update = () =>
      document.documentElement.style.setProperty(
        "--visible-height",
        `${viewport?.height || window.innerHeight}px`,
      );
    update();
    viewport?.addEventListener("resize", update);
    window.addEventListener("resize", update);
    return () => {
      viewport?.removeEventListener("resize", update);
      window.removeEventListener("resize", update);
    };
  }, []);
  useEffect(() => {
    refresh().catch((e) => setFatal(e.message));
  }, [refresh]);
  useEffect(() => {
    if (!boot?.user) return;
    const timer = setInterval(
      () =>
        api<Workspace>("/workspace")
          .then((w) => {
            setData(w);
            setSyncError("");
          })
          .catch((e) => setSyncError(e.message)),
      15000,
    );
    const offline = () =>
      setSyncError("La connexion au studio est interrompue.");
    const online = () => refresh().catch((e) => setSyncError(e.message));
    window.addEventListener("offline", offline);
    window.addEventListener("online", online);
    return () => {
      clearInterval(timer);
      window.removeEventListener("offline", offline);
      window.removeEventListener("online", online);
    };
  }, [boot?.user?.id]);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 6500);
    return () => clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    const handler = () => setPage(currentPage());
    window.addEventListener("popstate", handler);
    const key = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen((s) => !s);
      }
      if (e.key === "Escape") {
        setMobile(false);
        setAgentOpen(false);
      }
    };
    window.addEventListener("keydown", key);
    return () => {
      window.removeEventListener("popstate", handler);
      window.removeEventListener("keydown", key);
    };
  }, []);
  function go(next: Page) {
    setPage(next);
    setMobile(false);
    window.history.pushState(
      {},
      "",
      nav.find((n) => n.key === next)?.path || "/",
    );
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  async function mutate(operation: () => Promise<unknown>, success: string) {
    try {
      await operation();
      await refresh();
      setToast({ text: success, error: false });
      return true;
    } catch (e) {
      setToast({ text: (e as Error).message, error: true });
      return false;
    }
  }
  function newVideo(channel?: number) {
    setNewVideoChannel(channel);
    setCreatingVideo(true);
  }
  function agent(message = "") {
    setAgentText(message);
    if (page !== "agent") setAgentOpen(true);
  }
  if (fatal)
    return (
      <div className="startup-error">
        <AlertTriangle size={32} />
        <h1>Le studio n’a pas répondu.</h1>
        <p>{fatal}</p>
        <Button
          onClick={() => {
            setFatal("");
            refresh().catch((e) => setFatal(e.message));
          }}
        >
          Réessayer
        </Button>
      </div>
    );
  if (!boot)
    return (
      <div className="startup-loader">
        <span className="brand-icon">
          E<span>/</span>
        </span>
        <p>
          CONNEXION AU STUDIO<span className="blinking">_</span>
        </p>
      </div>
    );
  if (!boot.user) return <Login boot={boot} refresh={refresh} />;
  if (!data)
    return (
      <div className="startup-loader">
        <RefreshCw className="spin" />
        <p>Ouverture de l’espace partagé…</p>
      </div>
    );
  const p: PageProps = {
    data,
    user: boot.user,
    mutate,
    go,
    newVideo,
    newTask: () => {
      setEditingTask(null);
      setCreatingTask(true);
    },
    editTask: (task) => {
      setEditingTask(task.id);
      setCreatingTask(true);
    },
    openVideo: (v) => setOpenedVideo(v.id),
    editChannel: (c) => setEditingChannel(c.id),
    newChannel: () => setCreatingChannel(true),
    agent,
    schedule: (day, channel, postAt) =>
      setScheduleDay({ day, channel, postAt }),
  };
  const selectedVideo = data.videos.find((v) => v.id === openedVideo);
  const selectedChannel = data.channels.find((c) => c.id === editingChannel);
  const query = search.toLowerCase();
  const searchVideos = query
    ? data.videos
        .filter((v) => v.title.toLowerCase().includes(query))
        .slice(0, 5)
    : [];
  const searchChannels = query
    ? data.channels.filter((c) => c.name.toLowerCase().includes(query))
    : [];
  const workerOnline =
    data.worker.heartbeat &&
    Date.now() - new Date(data.worker.heartbeat).getTime() < 120000;
  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Aller au contenu
      </a>
      {mobile && (
        <div className="sidebar-scrim" onClick={() => setMobile(false)} />
      )}
      <aside className={"sidebar " + (mobile ? "mobile-open" : "")}>
        <button
          className="brand"
          onClick={() => go("overview")}
          aria-label="Edgerunners Studio, accueil"
        >
          <span className="brand-icon">
            E<span>/</span>
          </span>
          <div>
            EDGERUNNERS<span>STUDIO</span>
          </div>
          <i>2077</i>
        </button>
        <div className="sidebar-section-label">
          LE STUDIO<span>01—11</span>
        </div>
        <nav aria-label="Navigation principale">
          {nav.map((n, i) => (
            <button
              key={n.key}
              className={
                "nav-item " +
                (page === n.key ? "active" : "") +
                (n.key === "settings" ? " settings-nav" : "")
              }
              onClick={() => go(n.key)}
              aria-current={page === n.key ? "page" : undefined}
            >
              {n.icon}
              <span>{n.label}</span>
              {n.key === "channels" ? (
                <small>{data.channels.length}</small>
              ) : n.key === "tasks" &&
                data.tasks.filter((t) => !t.done).length > 0 ? (
                <small>{data.tasks.filter((t) => !t.done).length}</small>
              ) : n.key === "agent" ? (
                <i className="live-dot" />
              ) : (
                <em>{String(i + 1).padStart(2, "0")}</em>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button className="sidebar-agent" onClick={() => agent()}>
            <Bot size={21} />
            <div>
              <strong>DELAMAIN</strong>
              <span>Ton copilote de studio</span>
            </div>
            <ArrowUpRight size={15} />
          </button>
          <div className="system-state">
            <span className={workerOnline ? "live-dot" : "idle-dot"} />
            <span>
              {boot.preview
                ? "APERÇU LOCAL"
                : workerOnline
                  ? "MOTEUR DISPONIBLE"
                  : "MOTEUR AU REPOS"}
            </span>
          </div>
          <div className="sidebar-user">
            <span className="avatar">{boot.user.name.slice(0, 1)}</span>
            <div>
              <strong>{boot.user.name}</strong>
              <span>
                {boot.user.role === "owner" ? "Propriétaire" : "Collaborateur"}{" "}
                / NIGHT CITY
              </span>
            </div>
            <button
              className="icon-button"
              aria-label="Déconnexion"
              onClick={() =>
                mutate(() => api("/logout", "POST", {}), "Déconnecté.")
              }
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-menu"
              onClick={() => setMobile(!mobile)}
              aria-label="Ouvrir le menu"
            >
              <Menu size={20} />
            </button>
            <span className="topbar-brand">NIGHT CITY</span>
            <ChevronRight size={12} />
            <span>{nav.find((n) => n.key === page)?.label}</span>
          </div>
          <div className="topbar-right">
            <button
              className={
                "control-trigger " + (data.control.critical ? "attention" : "")
              }
              onClick={() => go("control")}
              aria-label={`Centre de contrôle, ${data.control.unread} alertes non lues`}
            >
              <Bell size={16} />
              {data.control.unread > 0 && <span>{data.control.unread}</span>}
            </button>
            <button
              className="search-trigger"
              onClick={() => setSearchOpen(true)}
            >
              <Search size={15} />
              <span>Rechercher</span>
              <kbd>
                <Command size={11} />K
              </kbd>
            </button>
            <button
              className={
                "pause-control " + (data.settings.paused ? "paused" : "")
              }
              onClick={() =>
                mutate(
                  () =>
                    api("/settings", "PATCH", {
                      revision: data.settings.revision,
                      paused: !data.settings.paused,
                    }),
                  data.settings.paused
                    ? "Le studio reprend."
                    : "Le studio est en pause.",
                )
              }
              aria-label={
                data.settings.paused
                  ? "Reprendre le studio"
                  : "Mettre le studio en pause"
              }
            >
              {data.settings.paused ? <Play size={14} /> : <Pause size={14} />}
              <span>{data.settings.paused ? "Reprendre" : "Pause"}</span>
            </button>
            <button className="agent-topbar" onClick={() => agent()}>
              <Bot size={17} />
              <span>Delamain</span>
              <i className="live-dot" />
            </button>
          </div>
        </header>
        {boot.preview && (
          <div className="preview-banner">
            <span>APERÇU LOCAL</span>Organisation active · générations payantes
            et publications désactivées.
          </div>
        )}
        {syncError && (
          <div className="connection-banner" role="alert">
            <AlertTriangle size={20} />
            <div>
              <strong>Connexion à vérifier.</strong>
              <span>
                {syncError} Dernière lecture :{" "}
                {dateLabel(data.server_time, {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
                , heure belge. Les données peuvent être anciennes.
              </span>
            </div>
            <Button
              onClick={() => refresh().catch((e) => setSyncError(e.message))}
            >
              Réessayer la connexion
            </Button>
          </div>
        )}
        <main id="main" tabIndex={-1}>
          {page === "overview" ? (
            <Overview {...p} />
          ) : page === "news" ? (
            <Newsroom {...p} />
          ) : page === "control" ? (
            <Control {...p} />
          ) : page === "channels" ? (
            <Channels {...p} />
          ) : page === "production" ? (
            <Production {...p} />
          ) : page === "calendar" ? (
            <Calendar {...p} />
          ) : page === "tasks" ? (
            <Tasks {...p} />
          ) : page === "studio" ? (
            <Studio {...p} />
          ) : page === "library" ? (
            <Library {...p} />
          ) : page === "settings" ? (
            <Settings {...p} />
          ) : (
            <div className="page agent-page">
              <div className="page-heading">
                <div>
                  <span className="eyebrow">LE COPILOTE DU STUDIO</span>
                  <h1>
                    Delamain<span className="heading-dot">.</span>
                  </h1>
                  <p>Donne la mission. Suis les actions. Garde le contrôle.</p>
                </div>
                <Tag tone="auto">ESPACE PARTAGÉ</Tag>
              </div>
              <div className="panel full-chat">
                <Agent
                  data={data}
                  initial={agentText}
                  mutate={mutate}
                  openVideo={p.openVideo}
                  editChannel={p.editChannel}
                  go={p.go}
                />
              </div>
            </div>
          )}
        </main>
        <footer className="app-footer">
          <span>
            EDGERUNNERS STUDIO <i>/</i> BUILT FOR YOUR NEXT MOVE
          </span>
          <span>
            NIGHT CITY ·{" "}
            {dateLabel(data.server_time, {
              hour: "2-digit",
              minute: "2-digit",
            })}{" "}
            HEURE BELGE
          </span>
        </footer>
      </div>
      {agentOpen && (
        <>
          <div
            className="agent-drawer-backdrop"
            onClick={() => setAgentOpen(false)}
          />
          <aside className="agent-drawer" aria-label="Assistant Delamain">
            <div className="drawer-head">
              <span className="eyebrow">CANAL / DELAMAIN</span>
              <button
                className="icon-button"
                onClick={() => setAgentOpen(false)}
                aria-label="Fermer Delamain"
              >
                <X size={20} />
              </button>
            </div>
            <Agent
              data={data}
              initial={agentText}
              mutate={mutate}
              compact
              openVideo={(v) => {
                setAgentOpen(false);
                p.openVideo(v);
              }}
              editChannel={(c) => {
                setAgentOpen(false);
                p.editChannel(c);
              }}
              go={(page) => {
                setAgentOpen(false);
                p.go(page);
              }}
            />
          </aside>
        </>
      )}
      {creatingVideo && (
        <NewVideo
          data={data}
          initialChannel={newVideoChannel}
          close={() => setCreatingVideo(false)}
          mutate={mutate}
          onCreated={(id) => {
            setOpenedVideo(id);
            go("production");
          }}
        />
      )}
      {creatingTask && (
        <NewTask
          data={data}
          initial={data.tasks.find((t) => t.id === editingTask)}
          close={() => setCreatingTask(false)}
          mutate={mutate}
        />
      )}{" "}
      {creatingChannel && (
        <NewChannel close={() => setCreatingChannel(false)} mutate={mutate} />
      )}{" "}
      {selectedChannel && (
        <ChannelForm
          channel={selectedChannel}
          close={() => setEditingChannel(null)}
          mutate={mutate}
        />
      )}{" "}
      {selectedVideo && (
        <VideoDetail
          video={selectedVideo}
          channel={
            data.channels.find((c) => c.id === selectedVideo.channel_id)!
          }
          data={data}
          close={() => setOpenedVideo(null)}
          mutate={mutate}
        />
      )}{" "}
      {scheduleDay && (
        <ScheduleForm
          data={data}
          day={scheduleDay.day}
          channelId={scheduleDay.channel}
          postAt={scheduleDay.postAt}
          createVideo={() => {
            setScheduleDay(null);
            p.newVideo(scheduleDay.channel);
          }}
          close={() => setScheduleDay(null)}
          mutate={mutate}
        />
      )}
      {searchOpen && (
        <Modal
          title="Retrouver quelque chose"
          close={() => setSearchOpen(false)}
        >
          <div className="search-palette">
            <div className="input-with-icon">
              <Search size={19} />
              <input
                autoFocus
                placeholder="Une chaîne, une vidéo, une page…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            {searchChannels.map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  setSearchOpen(false);
                  go("channels");
                  setEditingChannel(c.id);
                }}
              >
                <ChannelMark channel={c} size="small" />
                <span>{c.name}</span>
                <ArrowUpRight size={16} />
              </button>
            ))}
            {searchVideos.map((v) => (
              <button
                key={v.id}
                onClick={() => {
                  setSearchOpen(false);
                  setOpenedVideo(v.id);
                }}
              >
                <Clapperboard size={18} />
                <span>{v.title}</span>
                <ArrowUpRight size={16} />
              </button>
            ))}
            {nav
              .filter((n) => !query || n.label.toLowerCase().includes(query))
              .map((n) => (
                <button
                  key={n.key}
                  onClick={() => {
                    setSearchOpen(false);
                    go(n.key);
                  }}
                >
                  {n.icon}
                  <span>{n.label}</span>
                  <ArrowUpRight size={16} />
                </button>
              ))}
          </div>
        </Modal>
      )}
      {toast && (
        <div
          className={"toast " + (toast.error ? "error" : "success")}
          role="status"
        >
          {toast.error ? (
            <AlertTriangle size={19} />
          ) : (
            <CheckCircle2 size={19} />
          )}
          <span>{toast.text}</span>
          <button aria-label="Fermer le message" onClick={() => setToast(null)}>
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
