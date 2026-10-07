import { useState } from "react";
import { ReviewForm } from "./review";
import { Readiness } from "./readiness";
import {
  Plus,
  Save,
  Check,
  Link2,
  Play,
  ArrowUpRight,
  AlertTriangle,
  Clock3,
  Download,
  Send,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { api, localTime, parisToIso, labels, dateLabel } from "./api";
import type { Channel, Video, Workspace, Task, User } from "./types";
import { Modal, Button, Tag, VideoThumb, Disclosure } from "./components";
import { YouTubeConnection } from "./youtube-connection";

export type Mutate = (
  operation: () => Promise<unknown>,
  success: string,
) => Promise<boolean>;

export function ChannelForm({
  channel,
  close,
  mutate,
  user,
  configured,
  preview,
}: {
  channel: Channel;
  close: () => void;
  mutate: Mutate;
  user: User;
  configured: boolean;
  preview: boolean;
}) {
  const [form, setForm] = useState({ ...channel });
  const [busy, setBusy] = useState(false);
  const [removing, setRemoving] = useState(false);
  async function remove() {
    setBusy(true);
    const ok = await mutate(
      () =>
        api(`/channels/${channel.id}`, "DELETE", {
          revision: channel.revision,
        }),
      `« ${channel.name} » supprimée du studio.`,
    );
    setBusy(false);
    if (ok) close();
  }
  const templates =
    channel.format === "news"
      ? [
          ["mma_en", "Actualités MMA"],
          ["football_en", "Actualités football"],
          ["boxing_en", "Actualités boxe"],
        ]
      : channel.format === "pov"
        ? [
            ["oddly_specific_en", "Oddly Specific Lives"],
            ["oddly_expensive_en", "Oddly Expensive Lives"],
            ["oddly_things_en", "Oddly Specific Things"],
          ]
        : [
            ["survivors_account", "The Survivor’s Account"],
            ["frontier_blood", "Frontier Blood"],
          ];
  const change = (key: string, value: unknown) =>
    setForm((f) => ({ ...f, [key]: value }));
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    const ok = await mutate(
      () =>
        api(`/channels/${channel.id}`, "PATCH", {
          ...form,
          revision: channel.revision,
        }),
      "Réglages de la chaîne enregistrés.",
    );
    setBusy(false);
    if (ok) close();
  }
  return (
    <Modal
      title={channel.name}
      subtitle="Les règles de cette chaîne, au même endroit."
      close={close}
    >
      <form onSubmit={save} className="form">
        <YouTubeConnection
          channel={channel}
          configured={configured}
          preview={preview}
          user={user}
          mutate={mutate}
          onDisconnected={close}
        />
        <Disclosure title="Identité et style">
          <div className="form-grid">
            <label>
              Nom de la chaîne
              <input
                required
                value={form.name}
                onChange={(e) => change("name", e.target.value)}
              />
            </label>
            <label>
              Identifiant YouTube
              <input
                value={form.handle}
                onChange={(e) => change("handle", e.target.value)}
              />
            </label>
          </div>
          <label>
            Modèle de production
            <select
              value={form.template_key}
              onChange={(e) => change("template_key", e.target.value)}
            >
              <option value="">Choisir un modèle…</option>
              {templates.map(([key, name]) => (
                <option key={key} value={key}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        </Disclosure>
        <label>
          Autonomie
          <div className="mode-selector">
            {[
              ["manual", "Avec validation", "Tu contrôles avant publication."],
              ["auto", "Automatique", "L’agent suit les règles de la chaîne."],
            ].map(([key, title, desc]) => (
              <button
                key={key}
                type="button"
                className={form.autonomy === key ? "selected" : ""}
                onClick={() => change("autonomy", key)}
              >
                <span>
                  {title}
                  {form.autonomy === key && <Check size={15} />}
                </span>
                <small>{desc}</small>
              </button>
            ))}
          </div>
        </label>
        {channel.format === "news" && (
          <div className="form" role="group" aria-label="Rythme de publication">
            <span>Rythme de publication</span>
            <div className="mode-selector">
              {[
                [
                  "news",
                  "Selon l’actualité",
                  "Aucune heure fixe ni cadence quotidienne.",
                ],
                [
                  "scheduled",
                  "Rythme fixe",
                  "Des créneaux suggérés dans le calendrier.",
                ],
              ].map(([key, title, desc]) => (
                <button
                  key={key}
                  type="button"
                  className={form.publication_mode === key ? "selected" : ""}
                  onClick={() => change("publication_mode", key)}
                >
                  <span>
                    {title}
                    {form.publication_mode === key && <Check size={15} />}
                  </span>
                  <small>{desc}</small>
                </button>
              ))}
            </div>
          </div>
        )}
        {form.publication_mode === "news" ? (
          <p className="inline-note">
            Selon les actualités pertinentes, après les contrôles. Ce réglage
            n’active pas la production automatique.
          </p>
        ) : (
          <>
            <div className="form-grid three">
              <label>
                Un post tous les…
                <select
                  value={form.cadence_days}
                  onChange={(e) => change("cadence_days", e.target.value)}
                >
                  <option value="0.5">12 heures</option>
                  <option value="1">1 jour</option>
                  <option value="2">2 jours</option>
                  <option value="3">3 jours</option>
                  <option value="7">7 jours</option>
                </select>
              </label>
              <label>
                Heure belge
                <input
                  type="time"
                  value={form.post_time}
                  required
                  onChange={(e) => change("post_time", e.target.value)}
                />
              </label>
              <label>
                Stock cible
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={form.target_stock}
                  onChange={(e) =>
                    change("target_stock", Number(e.target.value))
                  }
                />
              </label>
            </div>
            <label>
              Premier jour du rythme
              <input
                type="date"
                required
                value={form.cadence_anchor}
                onChange={(e) => change("cadence_anchor", e.target.value)}
              />
              <small className="muted">
                Le calendrier suggère des créneaux à partir de cette date. Il
                faut ensuite y programmer une vidéo.
              </small>
            </label>
          </>
        )}
        <Disclosure title="Budget et consignes">
          <div className="form-grid">
            <label>
              Budget autorisé / vidéo ($)
              <input
                type="number"
                min="0"
                max="1000"
                step="0.5"
                value={form.budget}
                onChange={(e) => change("budget", Number(e.target.value))}
              />
            </label>
            {channel.format === "news" ? (
              <label>
                Fraîcheur maximum (heures)
                <input
                  type="number"
                  min="1"
                  max="168"
                  value={form.freshness_hours}
                  onChange={(e) =>
                    change("freshness_hours", Number(e.target.value))
                  }
                />
              </label>
            ) : (
              <label>
                Langue des vidéos
                <select
                  value={form.lang}
                  onChange={(e) => change("lang", e.target.value)}
                >
                  <option value="en">Anglais</option>
                  <option value="fr">Français</option>
                </select>
              </label>
            )}
          </div>
          <label>
            Instructions pour l’agent
            <textarea
              rows={4}
              value={form.instructions}
              placeholder="Ton, sujets à privilégier, sujets à éviter…"
              onChange={(e) => change("instructions", e.target.value)}
            />
          </label>
        </Disclosure>
        <div className="form-switches">
          <label>
            <input
              type="checkbox"
              checked={!!form.paused}
              onChange={(e) => change("paused", e.target.checked ? 1 : 0)}
            />
            Mettre cette chaîne en pause
          </label>
          <label>
            <input
              type="checkbox"
              checked={!!form.enabled}
              onChange={(e) => change("enabled", e.target.checked ? 1 : 0)}
            />
            Activer l’automatisation
          </label>
        </div>
        {!channel.connected && (
          <div className="inline-note">
            <Link2 size={16} />
            La connexion YouTube est nécessaire pour activer les publications
            automatiques.
          </div>
        )}
        {user.role === "owner" &&
          (removing ? (
            <div className="youtube-disconnect channel-remove">
              <p>
                <strong>Supprimer « {channel.name} » du studio ?</strong> Son
                automatisation s’arrête et sa connexion YouTube est effacée. Ses
                vidéos et son historique restent archivés.{" "}
                <strong>Rien n’est supprimé sur YouTube.</strong>
              </p>
              <div className="youtube-actions">
                <Button onClick={() => setRemoving(false)} disabled={busy}>
                  Garder la chaîne
                </Button>
                <Button variant="danger" onClick={remove} disabled={busy}>
                  <Trash2 size={16} />
                  Supprimer la chaîne
                </Button>
              </div>
            </div>
          ) : (
            <Button variant="ghost" onClick={() => setRemoving(true)}>
              <Trash2 size={16} />
              Supprimer cette chaîne du studio
            </Button>
          ))}
        <div className="modal-footer">
          <Button onClick={close}>Annuler</Button>
          <Button variant="primary" type="submit" disabled={busy}>
            <Save size={16} />
            Enregistrer
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function NewChannel({
  close,
  mutate,
}: {
  close: () => void;
  mutate: Mutate;
}) {
  const [name, setName] = useState("");
  const [format, setFormat] = useState("news");
  return (
    <Modal title="Ajouter une chaîne" close={close}>
      <form
        className="form"
        onSubmit={async (e) => {
          e.preventDefault();
          if (
            await mutate(
              () => api("/channels", "POST", { name, format }),
              "Chaîne ajoutée.",
            )
          )
            close();
        }}
      >
        <label>
          Nom
          <input
            required
            minLength={3}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Le nom de ta chaîne"
          />
        </label>
        <label>
          Format
          <select value={format} onChange={(e) => setFormat(e.target.value)}>
            <option value="news">Actualités sportives</option>
            <option value="pov">Animation Oddly</option>
            <option value="history">Documentaire historique</option>
          </select>
        </label>
        <p className="form-hint">
          La chaîne démarre avec validation. Son modèle de production se règle
          ensuite.
        </p>
        <div className="modal-footer">
          <Button onClick={close}>Annuler</Button>
          <Button type="submit" variant="primary">
            <Plus size={16} />
            Créer la chaîne
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function NewVideo({
  data,
  initialChannel,
  close,
  mutate,
  onCreated,
}: {
  data: Workspace;
  initialChannel?: number;
  close: () => void;
  mutate: Mutate;
  onCreated: (id: string) => void;
}) {
  const [cid, setCid] = useState(initialChannel || data.channels[0]?.id || 0);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [minutes, setMinutes] = useState(5);
  const [sources, setSources] = useState("");
  const [eventAt, setEventAt] = useState("");
  const [busy, setBusy] = useState(false);
  const ch = data.channels.find((c) => c.id === cid);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    let vid = "";
    const ok = await mutate(async () => {
      const urls = sources
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
      const response = await api<{ id: string }>("/videos", "POST", {
        channel_id: cid,
        title,
        notes,
        minutes,
        event_at: parisToIso(eventAt),
        sources: urls.map((url, i) => ({
          id: "source" + (i + 1),
          url,
          name: new URL(url).hostname,
          published: eventAt ? parisToIso(eventAt) : undefined,
        })),
      });
      vid = response.id;
    }, "Vidéo ajoutée à la production.");
    setBusy(false);
    if (ok) {
      close();
      onCreated(vid);
    }
  }
  return (
    <Modal
      title="Nouvelle vidéo"
      subtitle="Une idée. Une chaîne. Un nouveau départ."
      close={close}
    >
      <form onSubmit={save} className="form">
        <label>
          Chaîne
          <select
            value={cid}
            onChange={(e) => {
              setCid(Number(e.target.value));
              setMinutes(
                data.channels.find((c) => c.id === Number(e.target.value))
                  ?.format === "news"
                  ? 5
                  : 14,
              );
            }}
          >
            {data.channels.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Sujet ou titre
          <input
            required
            minLength={4}
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={
              ch?.format === "news"
                ? "L’actualité que tu veux raconter…"
                : "Le titre de ta prochaine vidéo…"
            }
          />
        </label>
        <Disclosure title="Durée de la vidéo">
          <label>
            Durée souhaitée (minutes)
            <input
              type="number"
              min="1"
              max="60"
              value={minutes}
              onChange={(e) => setMinutes(Number(e.target.value))}
            />
          </label>
        </Disclosure>
        {ch?.format === "news" && (
          <label>
            Date des faits · heure belge
            <input
              type="datetime-local"
              value={eventAt}
              onChange={(e) => setEventAt(e.target.value)}
            />
          </label>
        )}
        <label>
          {ch?.format === "news"
            ? "Faits vérifiés et angle de l’analyse"
            : "Notes et consignes"}
          <textarea
            rows={4}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Les éléments à raconter, les précautions, l’angle…"
          />
        </label>
        {ch?.format === "news" && (
          <label>
            Sources · une adresse HTTPS par ligne
            <textarea
              rows={3}
              value={sources}
              onChange={(e) => setSources(e.target.value)}
              placeholder="https://…"
            />
          </label>
        )}
        <div className="inline-note">
          <ShieldCheck size={16} />
          La création de cette fiche ne lance aucune génération payante.
        </div>
        <div className="modal-footer">
          <Button onClick={close}>Annuler</Button>
          <Button type="submit" variant="primary" disabled={busy}>
            <Plus size={16} />
            Ajouter à la production
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function NewTask({
  data,
  close,
  mutate,
  initial,
}: {
  data: Workspace;
  close: () => void;
  mutate: Mutate;
  initial?: Task;
}) {
  const [title, setTitle] = useState(initial?.title || "");
  const [cid, setCid] = useState(initial?.channel_id?.toString() || "");
  const [assignee, setAssignee] = useState(initial?.assignee || "");
  const [priority, setPriority] = useState(initial?.priority || "normal");
  const [due, setDue] = useState(localTime(initial?.due_at || ""));
  return (
    <Modal
      title={initial ? "Modifier la tâche" : "Nouvelle tâche"}
      close={close}
    >
      <form
        className="form"
        onSubmit={async (e) => {
          e.preventDefault();
          if (
            await mutate(
              () =>
                api(
                  initial ? "/tasks/" + initial.id : "/tasks",
                  initial ? "PATCH" : "POST",
                  {
                    title,
                    channel_id: cid ? Number(cid) : null,
                    assignee,
                    priority,
                    due_at: parisToIso(due),
                    revision: initial?.revision,
                  },
                ),
              "Tâche ajoutée.",
            )
          )
            close();
        }}
      >
        <label>
          À faire
          <input
            required
            maxLength={300}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Que doit-on faire ?"
          />
        </label>
        <div className="form-grid">
          <label>
            Chaîne
            <select value={cid} onChange={(e) => setCid(e.target.value)}>
              <option value="">Tout le studio</option>
              {data.channels.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Responsable
            <select
              value={assignee}
              onChange={(e) => setAssignee(e.target.value)}
            >
              <option value="">Non attribuée</option>
              {data.users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <Disclosure
          title="Échéance et priorité"
          open={
            !!initial?.due_at || (!!initial && initial.priority !== "normal")
          }
        >
          <div className="form-grid">
            <label>
              Priorité
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
              >
                <option value="normal">Normale</option>
                <option value="high">Haute</option>
                <option value="low">Basse</option>
              </select>
            </label>
            <label>
              Échéance · heure belge
              <input
                type="datetime-local"
                value={due}
                onChange={(e) => setDue(e.target.value)}
              />
            </label>
          </div>
        </Disclosure>
        <div className="modal-footer">
          <Button onClick={close}>Annuler</Button>
          <Button type="submit" variant="primary">
            <Plus size={16} />
            {initial ? "Enregistrer" : "Créer la tâche"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function ScheduleForm({
  data,
  day,
  channelId,
  postAt,
  createVideo,
  close,
  mutate,
}: {
  data: Workspace;
  day: string;
  channelId?: number;
  postAt?: string;
  createVideo: () => void;
  close: () => void;
  mutate: Mutate;
}) {
  const available = data.videos.filter(
    (v) =>
      !["published", "reported"].includes(v.status) &&
      (!channelId || v.channel_id === channelId),
  );
  const [vid, setVid] = useState(available[0]?.id || "");
  const video = data.videos.find((v) => v.id === vid);
  const channel = data.channels.find((c) => c.id === video?.channel_id);
  const [at, setAt] = useState(postAt ? localTime(postAt) : day + "T18:00");
  return (
    <Modal
      title="Prévoir une publication"
      subtitle="Le créneau reste une intention tant que la vidéo n’a pas passé les contrôles."
      close={close}
    >
      <form
        className="form"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!video) return;
          if (
            await mutate(
              () =>
                api(`/videos/${video.id}`, "PATCH", {
                  revision: video.revision,
                  post_at: parisToIso(at),
                }),
              "Créneau enregistré.",
            )
          )
            close();
        }}
      >
        {channelId && (
          <p className="inline-note">
            Créneau pour {data.channels.find((c) => c.id === channelId)?.name}
          </p>
        )}
        {!available.length && (
          <div className="inline-note">
            <p>
              Aucune vidéo à programmer{channelId ? " sur cette chaîne" : ""}.
              Crée d’abord sa fiche.
            </p>
            <Button onClick={createVideo}>Créer une vidéo</Button>
          </div>
        )}
        <label>
          Vidéo
          <select
            aria-label="Vidéo"
            required
            value={vid}
            onChange={(e) => setVid(e.target.value)}
          >
            {available.map((v) => (
              <option key={v.id} value={v.id}>
                {data.channels.find((c) => c.id === v.channel_id)?.name} —{" "}
                {v.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          Date et heure belges
          <input
            type="datetime-local"
            required
            value={at}
            onChange={(e) => setAt(e.target.value)}
          />
        </label>
        {channel && (
          <div className="inline-note">
            <Clock3 size={16} />
            {channel.name} ·{" "}
            {channel.autonomy === "auto"
              ? "Automatique après contrôles"
              : "Validation avant publication"}
          </div>
        )}
        <div className="modal-footer">
          <Button onClick={close}>Annuler</Button>
          <Button type="submit" variant="primary" disabled={!video}>
            Enregistrer le créneau
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function VideoDetail({
  video,
  channel,
  data,
  close,
  mutate,
}: {
  video: Video;
  channel: Channel;
  data: Workspace;
  close: () => void;
  mutate: Mutate;
}) {
  const [tab, setTab] = useState("preview");
  const [script, setScript] = useState(video.script);
  const [notes, setNotes] = useState(video.notes);
  const [title, setTitle] = useState(video.title);
  const [description, setDescription] = useState(video.description);
  const [at, setAt] = useState(localTime(video.post_at));
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const jobs = data.jobs.filter((j) => j.video_id === video.id);
  const active = jobs.find((j) => ["queued", "running"].includes(j.status));
  async function action(name: string) {
    setBusy(true);
    await mutate(
      () =>
        api(`/videos/${video.id}/action`, "POST", {
          action: name,
          revision: video.revision,
        }),
      "Opération enregistrée.",
    );
    setBusy(false);
  }
  const frozen = ["published", "reported"].includes(video.status);
  return (
    <Modal
      title={video.title}
      subtitle={
        channel.name + " · " + Number(video.minutes).toFixed(0) + " minutes"
      }
      close={close}
      wide
    >
      <div className="video-detail">
        <div className="detail-status">
          <Tag tone={video.status}>{labels[video.status]}</Tag>
          <span>
            Modifiée{" "}
            {dateLabel(video.updated_at, {
              day: "numeric",
              month: "short",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>
        <div className="tabs">
          {[
            ["preview", "Aperçu"],
            ["script", "Script & notes"],
            ["sources", "Sources & contrôles"],
            ["publish", "Publication"],
          ].map(([key, label]) => (
            <button
              key={key}
              className={tab === key ? "active" : ""}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </div>
        {video.error && (
          <div className="error-box">
            <AlertTriangle size={18} />
            {video.error}
          </div>
        )}
        {tab === "preview" && (
          <>
            <div className="detail-preview">
              {video.video_path ? (
                <video
                  controls
                  preload="metadata"
                  src={`/media/${video.id}/video`}
                />
              ) : (
                <VideoThumb video={video} channel={channel} />
              )}
            </div>
            <div className="check-strip">
              <span>
                <ShieldCheck size={17} />
                {video.quality_status === "verified"
                  ? "Rendu contrôlé"
                  : video.quality_status === "technical"
                    ? "Intégrité vérifiée · relecture requise"
                    : "Rendu à contrôler"}
              </span>
              <span>
                <ShieldCheck size={17} />
                {video.rights_status === "verified"
                  ? "Droits documentés"
                  : "Droits à vérifier"}
              </span>
            </div>
            {active && (
              <div className="job-progress">
                <div>
                  <span>{active.message}</span>
                  <button
                    onClick={() =>
                      mutate(
                        () => api(`/jobs/${active.id}/cancel`, "POST", {}),
                        "Annulation demandée.",
                      )
                    }
                  >
                    Annuler
                  </button>
                </div>
                <div className="progress-track">
                  <span style={{ width: `${active.progress * 100}%` }} />
                </div>
              </div>
            )}
            <div className="detail-actions">
              <Button
                onClick={() => action("script")}
                disabled={busy || !!active || frozen}
              >
                <Play size={15} />
                Préparer le script
              </Button>
              <Button
                onClick={() => action("render")}
                variant="primary"
                disabled={busy || !!active || frozen}
              >
                <Play size={15} />
                Créer la vidéo
              </Button>
              {video.video_path && (
                <Button
                  onClick={() => action("verify")}
                  disabled={busy || !!active}
                >
                  <ShieldCheck size={15} />
                  Contrôler le fichier
                </Button>
              )}
            </div>
            {video.external_url && (
              <a
                className="text-link"
                href={video.external_url}
                target="_blank"
                rel="noreferrer"
              >
                Ouvrir le paquet vidéo <ArrowUpRight size={15} />
              </a>
            )}
          </>
        )}
        {tab === "script" && (
          <form
            className="form"
            onSubmit={async (e) => {
              e.preventDefault();
              await mutate(
                () =>
                  api(`/videos/${video.id}`, "PATCH", {
                    revision: video.revision,
                    script,
                    notes,
                  }),
                "Script et notes enregistrés.",
              );
            }}
          >
            <label>
              Script
              <textarea
                rows={14}
                value={script}
                onChange={(e) => setScript(e.target.value)}
                placeholder="Le script apparaîtra ici après sa préparation."
                disabled={frozen}
              />
            </label>
            <label>
              Faits vérifiés et consignes
              <textarea
                rows={5}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                disabled={frozen}
              />
            </label>
            <div className="inline-note">
              <AlertTriangle size={15} />
              Modifier le script remet les contrôles du rendu à faire.
            </div>
            <Button
              type="submit"
              variant="primary"
              disabled={frozen || !!active}
            >
              <Save size={16} />
              Enregistrer
            </Button>
          </form>
        )}
        {tab === "sources" && (
          <div className="source-list">
            <div className="rights-banner">
              <ShieldCheck size={24} />
              <div>
                <h3>Des sources traçables. Des droits établis.</h3>
                <p>
                  Une source justifie un fait. La réutilisation de sa photo ou
                  de sa vidéo exige une autorisation distincte.
                </p>
              </div>
            </div>
            {video.sources.length ? (
              video.sources.map((s, i) => (
                <a
                  className="source-item"
                  href={s.url}
                  target="_blank"
                  rel="noreferrer"
                  key={s.id || i}
                >
                  <span className="source-number">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <strong>{s.name}</strong>
                    <small>{s.url}</small>
                  </div>
                  <ArrowUpRight size={17} />
                </a>
              ))
            ) : (
              <p className="muted">
                Aucune source enregistrée. Ajoute les références avant la
                production d’actualité.
              </p>
            )}
            <div className="control-list">
              <div>
                <span>Fichier vidéo</span>
                <Tag tone={video.video_path ? "ready" : "muted"}>
                  {video.video_path ? "Présent" : "Absent"}
                </Tag>
              </div>
              <div>
                <span>Miniature sélectionnée</span>
                <Tag tone={video.thumb_path ? "ready" : "muted"}>
                  {video.thumb_path ? "Présente" : "À choisir"}
                </Tag>
              </div>
              <div>
                <span>Contrôle technique et visuel</span>
                <Tag
                  tone={video.quality_status === "verified" ? "ready" : "muted"}
                >
                  {video.quality_status === "verified"
                    ? "Vérifié"
                    : "À terminer"}
                </Tag>
              </div>
              <div>
                <span>Droits des médias et de la voix</span>
                <Tag
                  tone={
                    video.rights_status === "verified" ? "ready" : "blocked"
                  }
                >
                  {video.rights_status === "verified"
                    ? "Documentés"
                    : "Non établis"}
                </Tag>
              </div>
            </div>
            <p className="form-hint">
              Les contrôles concernent le rendu actuel. Une modification du
              contenu nécessite une nouvelle vérification.
            </p>
            <ReviewForm video={video} mutate={mutate} />
          </div>
        )}
        {tab === "publish" && (
          <div className="form">
            <Readiness video={video} select={setTab} />
            <form
              className="form"
              onSubmit={async (e) => {
                e.preventDefault();
                await mutate(
                  () =>
                    api(`/videos/${video.id}`, "PATCH", {
                      revision: video.revision,
                      title,
                      description,
                      post_at: parisToIso(at),
                    }),
                  "Publication préparée.",
                );
              }}
            >
              <label>
                Titre YouTube
                <input
                  value={title}
                  maxLength={100}
                  onChange={(e) => setTitle(e.target.value)}
                  disabled={frozen}
                />
              </label>
              <label>
                Description
                <textarea
                  value={description}
                  rows={5}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={frozen}
                />
              </label>
              <label>
                Date et heure belges
                <input
                  type="datetime-local"
                  value={at}
                  onChange={(e) => setAt(e.target.value)}
                  disabled={frozen}
                />
              </label>
              <Button type="submit" disabled={frozen || !!active}>
                <Save size={15} />
                Enregistrer
              </Button>
            </form>
            <div className="divider" />
            <div className="detail-actions">
              <Button
                onClick={() => action("approve")}
                disabled={busy || frozen}
              >
                <Check size={15} />
                Valider
              </Button>
              <Button
                variant="primary"
                onClick={() => action("publish")}
                disabled={busy || !!active || frozen}
              >
                <ArrowUpRight size={15} />
                Publier sur YouTube
              </Button>
              <Button
                onClick={() => action("discord")}
                disabled={busy || !!active}
              >
                <Send size={15} />
                Envoyer sur Discord
              </Button>
              {video.video_path && (
                <a
                  className="button secondary"
                  href={`/media/${video.id}/video?download=1`}
                >
                  <Download size={15} />
                  Télécharger
                </a>
              )}
            </div>
            {!channel.connected && (
              <div className="inline-note">
                <Link2 size={16} />
                Connecte {channel.name} à YouTube depuis sa fiche pour publier
                ici.
              </div>
            )}
            {video.youtube_id ? (
              <a
                className="text-link"
                href={`https://www.youtube.com/watch?v=${video.youtube_id}`}
                target="_blank"
                rel="noreferrer"
              >
                Voir la publication{" "}
                {video.status === "reported" ? "rapportée" : ""}
                <ArrowUpRight size={15} />
              </a>
            ) : (
              <form
                className="form"
                onSubmit={async (e) => {
                  e.preventDefault();
                  await mutate(
                    () =>
                      api(`/videos/${video.id}/action`, "POST", {
                        action: "report",
                        url,
                        revision: video.revision,
                      }),
                    "Publication manuelle enregistrée.",
                  );
                }}
              >
                <label>
                  Déjà postée manuellement ?
                  <input
                    type="url"
                    required
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="Colle le lien YouTube"
                  />
                </label>
                <Button type="submit">
                  <Link2 size={15} />
                  Enregistrer le lien
                </Button>
              </form>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
