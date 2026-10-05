import { useEffect, useState } from "react";
import { Check, ListChecks, RefreshCw } from "lucide-react";
import { api, parisToIso } from "./api";
import { Button, Modal, Tag } from "./components";
import type { PageProps } from "./pages";

type Routine = {
  id: string;
  name: string;
  description: string;
  steps: string[];
};
export function RoutinePicker({
  p,
  close,
}: {
  p: PageProps;
  close: () => void;
}) {
  const [templates, setTemplates] = useState<Routine[]>([]);
  const [selected, setSelected] = useState("research");
  const [cid, setCid] = useState(p.data.channels[0]?.id || 0);
  const [vid, setVid] = useState("");
  const [assignee, setAssignee] = useState(p.user.id);
  const [due, setDue] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [requestKey] = useState(() => crypto.randomUUID());
  useEffect(() => {
    let active = true;
    api<{ templates: Routine[] }>("/routines")
      .then((r) => {
        if (active) setTemplates(r.templates);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  const routine = templates.find((t) => t.id === selected);
  return (
    <Modal
      title="Ajouter une routine"
      subtitle="Une liste de travail commune, sans lancer de production."
      close={close}
      wide
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          let dueAt = "";
          try {
            dueAt = parisToIso(due);
          } catch (e) {
            setError((e as Error).message);
            setBusy(false);
            return;
          }
          const ok = await p.mutate(async () => {
            await api<{ created: boolean; task_ids: string[] }>(
              "/routines",
              "POST",
              {
                template: selected,
                channel_id: cid,
                video_id: vid,
                assignee,
                due_at: dueAt,
                request_key: requestKey,
              },
            );
          }, "Routine disponible dans les tâches partagées.");
          setBusy(false);
          if (ok) close();
        }}
        className="form"
      >
        {error && <div className="error-box">{error}</div>}
        <div className="routine-options">
          {templates.map((t) => (
            <button
              type="button"
              key={t.id}
              className={selected === t.id ? "selected" : ""}
              aria-pressed={selected === t.id}
              onClick={() => setSelected(t.id)}
            >
              <ListChecks size={22} />
              <strong>{t.name}</strong>
              <p>{t.description}</p>
              <Tag>{t.steps.length} étapes</Tag>
            </button>
          ))}
        </div>
        {!templates.length && !error && (
          <p className="muted">
            <RefreshCw size={16} className="spin" />
            Chargement des routines…
          </p>
        )}
        <div className="form-grid">
          <label>
            Chaîne
            <select
              aria-label="Chaîne de la routine"
              value={cid}
              onChange={(e) => {
                setCid(Number(e.target.value));
                setVid("");
              }}
            >
              {p.data.channels.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Vidéo liée
            <select
              aria-label="Vidéo liée à la routine"
              value={vid}
              onChange={(e) => setVid(e.target.value)}
            >
              <option value="">Routine pour la chaîne</option>
              {p.data.videos
                .filter(
                  (v) =>
                    v.channel_id === cid &&
                    !["published", "reported"].includes(v.status),
                )
                .map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.title}
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
              <option value="">À répartir</option>
              {p.data.users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Échéance commune · heure belge
            <input
              type="datetime-local"
              value={due}
              onChange={(e) => setDue(e.target.value)}
            />
          </label>
        </div>
        {routine && (
          <div className="routine-steps">
            <h3>Ce qui sera ajouté</h3>
            {routine.steps.map((step, i) => (
              <p key={step}>
                <span>{String(i + 1).padStart(2, "0")}</span>
                {step}
              </p>
            ))}
          </div>
        )}
        <p className="small muted">
          Une routine déjà ouverte garde ses responsables et échéances ; tu peux
          les modifier dans les tâches. Cocher les tâches ne valide pas les
          droits ou le rendu : les contrôles restent dans la fiche vidéo.
        </p>
        <div className="modal-footer">
          <Button onClick={close}>Annuler</Button>
          <Button
            type="submit"
            variant="primary"
            disabled={busy || !routine || !cid}
          >
            <Check size={16} />
            {busy ? "Ajout en cours…" : "Ajouter les tâches"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
