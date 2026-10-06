import {
  Plus,
  ArrowUpRight,
  Link2,
  CheckCircle2,
  ListTodo,
  Clapperboard,
  CalendarDays,
} from "lucide-react";
import type { PageProps } from "./pages";
import { Button, Empty, VideoThumb } from "./components";
import { dateLabel, labels } from "./api";

export function DailyHome(p: PageProps) {
  const missing = p.data.channels.filter((c) => !c.connected).length;
  const reviews = p.data.videos.filter((v) => v.status === "review").length;
  const tasks = p.data.tasks
    .filter((t) => !t.done && (!t.assignee || t.assignee === p.user.id))
    .slice(0, 3);
  const recent = [...p.data.videos]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 3);
  return (
    <div className="page daily-home">
      <div className="page-heading">
        <div>
          <h1>
            Accueil<span className="heading-dot">.</span>
          </h1>
          <p>Bonjour {p.user.name}. Voici la suite du travail.</p>
        </div>
        <Button variant="primary" onClick={() => p.newVideo()}>
          <Plus size={17} />
          Nouvelle vidéo
        </Button>
      </div>
      <div className="daily-stats">
        {[
          {
            n: p.data.stats.producing,
            label: "En création",
            icon: <Clapperboard size={19} />,
            page: "production" as const,
          },
          {
            n: p.data.stats.ready,
            label: "Vidéos prêtes",
            icon: <CheckCircle2 size={19} />,
            page: "production" as const,
          },
          {
            n: p.data.stats.scheduled,
            label: "Programmées",
            icon: <CalendarDays size={19} />,
            page: "calendar" as const,
          },
        ].map((s) => (
          <button
            className="panel daily-stat"
            key={s.label}
            onClick={() => p.go(s.page)}
          >
            {s.icon}
            <strong>{s.n}</strong>
            <span>{s.label}</span>
          </button>
        ))}
      </div>
      <div className="daily-columns">
        <section className="panel daily-panel">
          <h2>À faire</h2>
          {missing > 0 && (
            <button className="daily-action" onClick={() => p.go("channels")}>
              <Link2 size={19} />
              <span>
                <strong>Connecter les chaînes YouTube</strong>
                <small>
                  {missing} connexion{missing > 1 ? "s" : ""} à terminer
                </small>
              </span>
              <ArrowUpRight size={16} />
            </button>
          )}
          {reviews > 0 && (
            <button className="daily-action" onClick={() => p.go("production")}>
              <CheckCircle2 size={19} />
              <span>
                <strong>Vérifier les vidéos</strong>
                <small>{reviews} en attente de validation</small>
              </span>
              <ArrowUpRight size={16} />
            </button>
          )}
          {tasks.map((t) => (
            <button
              className="daily-action"
              key={t.id}
              onClick={() => p.editTask(t)}
            >
              <ListTodo size={19} />
              <span>
                <strong>{t.title}</strong>
                <small>
                  {t.due_at ? dateLabel(t.due_at) : "Sans échéance"}
                </small>
              </span>
              <ArrowUpRight size={16} />
            </button>
          ))}
          {!missing && !reviews && !tasks.length && (
            <Empty
              title="Tout est à jour"
              text="Tu peux préparer la prochaine vidéo."
            />
          )}
          <button className="text-button" onClick={() => p.go("tasks")}>
            Toutes les tâches <ArrowUpRight size={15} />
          </button>
        </section>
        <section className="panel daily-panel">
          <h2>Dernières vidéos</h2>
          {recent.map((v) => (
            <button
              className="daily-video"
              key={v.id}
              onClick={() => p.openVideo(v)}
            >
              <VideoThumb video={v} />
              <span>
                <strong>{v.title}</strong>
                <small>
                  {p.data.channels.find((c) => c.id === v.channel_id)?.name} ·{" "}
                  {labels[v.status] || v.status}
                </small>
              </span>
              <ArrowUpRight size={16} />
            </button>
          ))}
          {!recent.length && (
            <Empty
              title="Ta première vidéo"
              text="Choisis une chaîne et ajoute un sujet."
            />
          )}
          <button className="text-button" onClick={() => p.go("production")}>
            Toutes les vidéos <ArrowUpRight size={15} />
          </button>
        </section>
      </div>
      <button className="panel daily-delamain" onClick={() => p.agent()}>
        <span className="daily-agent-mark">D_</span>
        <span>
          <strong>Un coup de main ?</strong>
          <small>Demande à Delamain.</small>
        </span>
        <ArrowUpRight size={19} />
      </button>
    </div>
  );
}
