import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, RefreshCw, Clock3 } from "lucide-react";
import type { PageProps } from "./pages";
import { api, dateLabel, dayKey } from "./api";
import { Button, ChannelMark, Tag } from "./components";
import { matchesScope } from "./team-board";

type Slot = {
  channel_id: number;
  responsible_id: string | null;
  post_at: string;
  kind: string;
  video_id: string | null;
  title: string;
  state: string;
  blockers: string[];
};
type Planning = { start: string; days: number; slots: Slot[] };
function shift(day: string, days: number) {
  const d = new Date(day + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function PersonalPlanning(
  p: PageProps & { scope: string; channelFilter: string },
) {
  const today = dayKey(p.data.server_time);
  const [start, setStart] = useState(today);
  const [data, setData] = useState<Planning | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    api<Planning>(
      "/planning?" + new URLSearchParams({ start, days: "7", scope: p.scope }),
    )
      .then((result) => {
        if (active) {
          setData(result);
          setError("");
        }
      })
      .catch((e) => {
        if (active) {
          setError(e.message);
          setData(null);
        }
      });
    return () => {
      active = false;
    };
  }, [start, p.scope, p.data, retry]);
  const channels = p.data.channels.filter(
    (c) =>
      matchesScope(c, p.scope, p.user) &&
      (p.channelFilter === "all" || c.id === Number(p.channelFilter)),
  );
  const groups = [
    ...p.data.users.map((u) => ({ id: u.id, name: u.name })),
    { id: "unassigned", name: "À répartir" },
  ].filter(
    (g) =>
      p.scope === "all" || g.id === (p.scope === "mine" ? p.user.id : p.scope),
  );
  return (
    <div className="personal-planning">
      <div className="rhythm-intro">
        <Clock3 size={19} />
        <p>
          <strong>Qui poste cette semaine ?</strong> Les créneaux du rythme sont
          des suggestions. Une vidéo réservée affiche les contrôles encore
          nécessaires ; ouvre sa fiche avant de publier.
        </p>
      </div>
      <div className="rhythm-toolbar">
        <Button
          onClick={() => setStart(shift(start, -7))}
          aria-label="Semaine précédente"
        >
          <ChevronLeft size={16} />
        </Button>
        <h2>
          {dateLabel(start + "T12:00:00Z", { day: "numeric", month: "long" })} –{" "}
          {dateLabel(shift(start, 6) + "T12:00:00Z", {
            day: "numeric",
            month: "long",
          })}
        </h2>
        <Button
          onClick={() => setStart(shift(start, 7))}
          aria-label="Semaine suivante"
        >
          <ChevronRight size={16} />
        </Button>
        <Button onClick={() => setStart(today)}>Cette semaine</Button>
      </div>
      {error ? (
        <div role="alert" className="rhythm-error">
          <p>{error}</p>
          <Button onClick={() => setRetry((n) => n + 1)}>
            <RefreshCw size={15} />
            Réessayer
          </Button>
        </div>
      ) : !data ? (
        <p role="status">Chargement du planning…</p>
      ) : (
        <div className="personal-agendas">
          {groups.map((group) => (
            <section
              className="personal-agenda"
              key={group.id}
              data-planning-member={group.id}
            >
              <header>
                <h2>{group.name}</h2>
                <span className="muted small">
                  {
                    channels.filter(
                      (c) => (c.responsible_id || "unassigned") === group.id,
                    ).length
                  }{" "}
                  chaînes
                </span>
              </header>
              {group.id === "unassigned" && p.scope === "all" ? (
                <div className="rhythm-day">
                  <p className="muted small">
                    Attribue ces chaînes pour les retrouver dans votre planning
                    personnel. Tu peux aussi consulter leur rythme avec le
                    filtre « À répartir ».
                  </p>
                  <Button onClick={() => p.go("channels")}>
                    Répartir les chaînes
                  </Button>
                </div>
              ) : (
                Array.from({ length: 7 }, (_, i) => shift(start, i)).map(
                  (day) => {
                    const slots = data.slots.filter(
                      (s) =>
                        dayKey(s.post_at) === day &&
                        (s.responsible_id || "unassigned") === group.id &&
                        channels.some((c) => c.id === s.channel_id),
                    );
                    return (
                      <div
                        className={`rhythm-day ${day === today ? "today" : ""}`}
                        key={day}
                      >
                        <h3>
                          {dateLabel(day + "T12:00:00Z", {
                            weekday: "short",
                            day: "numeric",
                            month: "short",
                          })}
                          {day === today && <span>Aujourd’hui</span>}
                        </h3>
                        {slots.length ? (
                          slots.map((s) => {
                            const c = channels.find(
                              (c) => c.id === s.channel_id,
                            )!;
                            const v = p.data.videos.find(
                              (v) => v.id === s.video_id,
                            );
                            return (
                              <article
                                className={`rhythm-slot ${s.kind}`}
                                key={`${s.channel_id}-${s.post_at}-${s.video_id || "suggestion"}`}
                              >
                                <div className="rhythm-slot-head">
                                  <ChannelMark channel={c} />
                                  <div className="rhythm-slot-info">
                                    <strong>{c.name}</strong>
                                    <small>
                                      {dateLabel(s.post_at, {
                                        hour: "2-digit",
                                        minute: "2-digit",
                                      })}{" "}
                                      ·{" "}
                                      {s.kind === "suggestion"
                                        ? "Rythme proposé"
                                        : "Vidéo réservée"}
                                    </small>
                                  </div>
                                  <Tag
                                    tone={
                                      s.state === "Bloquée" ||
                                      s.state === "En pause"
                                        ? "blocked"
                                        : "muted"
                                    }
                                  >
                                    {s.state}
                                  </Tag>
                                </div>
                                {s.kind === "reserved" && <p>{s.title}</p>}
                                {s.blockers.length > 0 && (
                                  <ul>
                                    {s.blockers.map((reason) => (
                                      <li key={reason}>{reason}</li>
                                    ))}
                                  </ul>
                                )}
                                <Button
                                  onClick={() =>
                                    v
                                      ? p.openVideo(v)
                                      : p.schedule(day, s.channel_id, s.post_at)
                                  }
                                >
                                  {v ? "Ouvrir la fiche" : "Prévoir une vidéo"}
                                </Button>
                              </article>
                            );
                          })
                        ) : (
                          <p className="rhythm-empty">Aucun créneau prévu</p>
                        )}
                      </div>
                    );
                  },
                )
              )}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
