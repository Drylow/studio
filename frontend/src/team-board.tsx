import { useState } from "react";
import { GripVertical, ArrowLeftRight, Users } from "lucide-react";
import type { Channel, User } from "./types";
import type { PageProps } from "./pages";
import { api } from "./api";
import { Button, ChannelMark, Empty, Tag } from "./components";
import { YouTubeConnection } from "./youtube-connection";

const DRAG_TYPE = "application/x-edgerunners-channel";

export function matchesScope(channel: Channel, scope: string, user: User) {
  return (
    scope === "all" ||
    (scope === "unassigned"
      ? !channel.responsible_id
      : channel.responsible_id === (scope === "mine" ? user.id : scope))
  );
}

export function TeamScope({
  users,
  value,
  onChange,
  label,
}: {
  users: User[];
  value: string;
  onChange: (scope: string) => void;
  label: string;
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="all">Toute l’équipe</option>
      <option value="mine">Mes chaînes</option>
      {users.map((u) => (
        <option key={u.id} value={u.id}>
          {u.name}
        </option>
      ))}
      <option value="unassigned">À répartir</option>
    </select>
  );
}

export function TeamBoard(p: PageProps & { channels: Channel[] }) {
  const [over, setOver] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const members = [...p.data.users].sort(
    (a, b) => Number(b.role === "owner") - Number(a.role === "owner"),
  );
  async function move(channel: Channel, member: string | null) {
    setOver(null);
    if (busy !== null || channel.responsible_id === member) return;
    setBusy(channel.id);
    await p.mutate(
      () =>
        api(`/channels/${channel.id}/responsibility`, "PATCH", {
          responsible_id: member,
          revision: channel.revision,
        }),
      `${channel.name} → ${members.find((u) => u.id === member)?.name || "À répartir"}.`,
    );
    setBusy(null);
  }
  const lanes = [
    ...members.map((u) => ({ id: u.id, name: u.name })),
    { id: "unassigned", name: "À répartir" },
  ];
  return (
    <>
      <div className="team-intro">
        <ArrowLeftRight size={18} />
        <p>
          Glisse une chaîne vers son responsable. Sur téléphone, utilise «
          Déplacer vers… ». Vous gardez tous les deux accès au studio.
        </p>
      </div>
      {members.length < 2 && (
        <div className="team-intro">
          <Users size={18} />
          <p>
            Pour ajouter Kanye : Réglages → Équipe → Ajouter, puis renseigne son
            nom, son identifiant et son mot de passe.
          </p>
          <Button onClick={() => p.go("settings")}>Ouvrir les réglages</Button>
        </div>
      )}
      <div className="team-board">
        {lanes.map((lane, index) => {
          const cards = p.channels.filter((c) =>
            lane.id === "unassigned"
              ? !c.responsible_id
              : c.responsible_id === lane.id,
          );
          return (
            <section
              key={lane.id}
              data-team={lane.id}
              aria-label={`Chaînes de ${lane.name}`}
              className={`panel team-lane ${lane.id === "unassigned" ? "team-pool" : ""} ${over === lane.id ? "drop-active" : ""}`}
              onDragOver={(e) => {
                if (e.dataTransfer.types.includes(DRAG_TYPE) && busy === null) {
                  e.preventDefault();
                  e.dataTransfer.dropEffect = "move";
                  setOver(lane.id);
                }
              }}
              onDragLeave={(e) => {
                if (!e.currentTarget.contains(e.relatedTarget as Node))
                  setOver(null);
              }}
              onDrop={(e) => {
                e.preventDefault();
                const id = Number(e.dataTransfer.getData(DRAG_TYPE));
                const c = p.data.channels.find((c) => c.id === id);
                if (c) void move(c, lane.id === "unassigned" ? null : lane.id);
                else setOver(null);
              }}
            >
              <header className="team-lane-heading">
                <span className={`team-avatar member-${index % 2}`}>
                  {lane.id === "unassigned"
                    ? "+"
                    : lane.name.slice(0, 1).toUpperCase()}
                </span>
                <div>
                  <span className="eyebrow">
                    {lane.id === "unassigned" ? "ESPACE COMMUN" : "RESPONSABLE"}
                  </span>
                  <h2>{lane.name}</h2>
                </div>
                <span className="team-count">{cards.length}</span>
              </header>
              <div className="team-cards">
                {cards.map((c) => (
                  <article
                    key={c.id}
                    data-channel={c.id}
                    className={`team-channel ${busy === c.id ? "saving" : ""}`}
                    style={{ "--channel": c.accent } as React.CSSProperties}
                    draggable={busy === null}
                    onDragStart={(e) => {
                      e.dataTransfer.setData(DRAG_TYPE, String(c.id));
                      e.dataTransfer.effectAllowed = "move";
                    }}
                    onDragEnd={() => setOver(null)}
                  >
                    <div className="team-channel-top">
                      <GripVertical size={17} className="drag-handle" />
                      <ChannelMark channel={c} />
                      <button
                        className="team-channel-name"
                        onClick={() => p.editChannel(c)}
                      >
                        <strong>{c.name}</strong>
                        <small>
                          {c.ready} / {c.target_stock} vidéos prêtes
                        </small>
                      </button>
                    </div>
                    <div className="team-channel-meta">
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
                            ? "MODE AUTO"
                            : "VALIDATION"}
                      </Tag>
                      <span className="muted small">
                        {c.post_time} ·{" "}
                        {Number(c.cadence_days) < 1
                          ? "2 / jour"
                          : `tous les ${c.cadence_days} j`}
                      </span>
                    </div>
                    <YouTubeConnection
                      channel={c}
                      configured={p.data.connections.youtube}
                      preview={p.preview}
                      user={p.user}
                      mutate={p.mutate}
                    />
                    <label className="team-move">
                      Déplacer vers…
                      <select
                        aria-label={`Responsable de ${c.name}`}
                        disabled={busy !== null}
                        value={c.responsible_id || "unassigned"}
                        onChange={(e) =>
                          void move(
                            c,
                            e.target.value === "unassigned"
                              ? null
                              : e.target.value,
                          )
                        }
                      >
                        <option value="unassigned">À répartir</option>
                        {members.map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </article>
                ))}
                {!cards.length && (
                  <Empty
                    icon={<Users size={24} />}
                    title="Dépose une chaîne ici"
                    text="Le planning suivra son attribution."
                  />
                )}
              </div>
            </section>
          );
        })}
      </div>
    </>
  );
}
