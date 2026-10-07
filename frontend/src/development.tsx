import { useState } from "react";
import { Code2, ArrowUpRight, ShieldCheck } from "lucide-react";
import { api, dateLabel } from "./api";
import { Button, Modal, SectionTitle, Tag } from "./components";
import type { Development, Workspace } from "./types";

const steps = ["Préparation", "Code", "Tests", "Mise en ligne"];
const ranks: Record<string, number> = {
  queued: 0,
  preparing: 0,
  coding: 1,
  testing: 2,
  deploying: 3,
  done: 4,
};

export function DevelopmentCard({
  change,
  owner,
}: {
  change: Development;
  owner: boolean;
}) {
  const [detail, setDetail] = useState<Development | null>(null);
  const [error, setError] = useState("");
  const active = [
    "queued",
    "preparing",
    "coding",
    "testing",
    "deploying",
  ].includes(change.status);
  async function open() {
    try {
      setDetail(await api<Development>(`/development/${change.id}`));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Détails indisponibles.");
    }
  }
  return (
    <article className="development-card">
      <div className="development-heading">
        <Code2 size={18} />
        <strong>{change.request}</strong>
        <Tag
          tone={
            change.status === "done"
              ? "ready"
              : change.status === "failed"
                ? "blocked"
                : "muted"
          }
        >
          {change.status === "done"
            ? "EN LIGNE"
            : change.status === "failed"
              ? "ARRÊTÉ"
              : change.status === "cancelled"
                ? "ANNULÉ"
                : "EN COURS"}
        </Tag>
      </div>
      <ol className="development-steps" aria-label="Étapes de la modification">
        {steps.map((step, i) => (
          <li
            key={step}
            className={
              i < (ranks[change.status] || 0)
                ? "complete"
                : active && i === ranks[change.status]
                  ? "current"
                  : ""
            }
          >
            {step}
          </li>
        ))}
      </ol>
      <p>{change.summary || change.message}</p>
      {change.error && <p className="error-text">{change.error}</p>}
      {change.session_url && (
        <a
          className="text-button"
          href={change.session_url}
          target="_blank"
          rel="noreferrer"
        >
          Suivre le travail de Claude <ArrowUpRight size={14} />
        </a>
      )}
      <div className="development-footer">
        <small>
          {dateLabel(change.updated_at, { hour: "2-digit", minute: "2-digit" })}
        </small>
        {owner && (
          <Button onClick={open}>
            Voir le résultat <ArrowUpRight size={14} />
          </Button>
        )}
      </div>
      {error && <p className="error-text">{error}</p>}
      {detail && (
        <Modal
          title="Résultat de la modification"
          close={() => setDetail(null)}
        >
          <p>{detail.summary || detail.message}</p>
          {detail.error && <p className="error-text">{detail.error}</p>}
          {detail.commit_id && (
            <p className="form-hint">
              Version enregistrée : {detail.commit_id.slice(0, 12)}
            </p>
          )}
          <details>
            <summary>Vérifications</summary>
            <pre className="development-log">
              {detail.checks ||
                "Les vérifications n’ont pas encore été terminées."}
            </pre>
          </details>
          <details>
            <summary>Code modifié</summary>
            <pre className="development-log">
              {detail.diff || "Aucun changement enregistré pour le moment."}
            </pre>
          </details>
        </Modal>
      )}
    </article>
  );
}

function ClaudeRoutine({
  routine,
  owner,
}: {
  routine?: { configured: boolean; url: string };
  owner: boolean;
}) {
  const [url, setUrl] = useState(routine?.url || "");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  if (!owner) return null;
  async function save(remove = false) {
    setBusy(true);
    setMessage("");
    try {
      if (remove) await api("/development/routine", "DELETE", {});
      else await api("/development/routine", "POST", { url, token });
      window.location.reload();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Enregistrement impossible.");
      setBusy(false);
    }
  }
  return (
    <div className="inline-note development-routine">
      <Code2 size={18} />
      <div>
        <strong>
          {routine?.configured
            ? "Claude (Sonnet) code tes demandes."
            : "Brancher Claude pour coder tes demandes"}
        </strong>
        {routine?.configured ? (
          <p>
            Chaque demande lance une session Claude que tu peux suivre ; le
            serveur refait les tests et met en ligne tout seul.
          </p>
        ) : (
          <>
            <p>
              Sur claude.ai/code/routines → routine « Delamain » → Modifier →
              déclencheur API : copie l’adresse et génère le jeton, puis colle-les
              ici.
            </p>
            <label>
              Adresse de la routine
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://api.anthropic.com/v1/claude_code/routines/trig_…/fire"
                autoComplete="off"
              />
            </label>
            <label>
              Jeton
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                autoComplete="off"
              />
            </label>
          </>
        )}
        {message && <p className="error-text">{message}</p>}
        <div className="development-actions">
          {routine?.configured ? (
            <Button onClick={() => save(true)} disabled={busy}>
              Retirer le jeton
            </Button>
          ) : (
            <Button
              variant="primary"
              onClick={() => save()}
              disabled={busy || !url || !token}
            >
              Enregistrer
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

export function DevelopmentSettings({
  data,
  owner,
  go,
}: {
  data: Workspace;
  owner: boolean;
  go: () => void;
}) {
  const state = data.development.configuration;
  return (
    <section className="panel development-panel">
      <SectionTitle
        eyebrow="DELAMAIN / CONSTRUCTION"
        title="Modifications du site"
        action={
          <Tag tone={state.ready ? "ready" : "muted"}>
            {state.ready ? "CONNECTÉ" : "À CONNECTER"}
          </Tag>
        }
      />
      <p>
        Demande une nouvelle fonction ou un changement visuel. Delamain prépare
        le code, lance les vérifications et met le site à jour quand elles
        passent.
      </p>
      <ClaudeRoutine routine={state.routine} owner={owner} />
      {!state.ready && (
        <div className="inline-note">
          <ShieldCheck size={18} />
          <div>
            <strong>
              {state.preview
                ? "L’aperçu n’exécute aucun déploiement."
                : state.check_error ||
                  "Le serveur doit être connecté une fois avant de pouvoir modifier le site."}
            </strong>
            {!!state.missing.length && (
              <ul>
                {state.missing.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
            {!state.worker_online && (
              <p>L’exécuteur ne signale pas encore sa présence.</p>
            )}
          </div>
        </div>
      )}
      <div className="development-actions">
        {owner && (
          <Button variant="primary" onClick={go} disabled={!state.ready}>
            <Code2 size={16} />
            Demander à Delamain
          </Button>
        )}
        <a
          className="button secondary"
          href="/api/studio/development/setup-guide"
          target="_blank"
          rel="noreferrer"
        >
          Guide de connexion <ArrowUpRight size={14} />
        </a>
      </div>
      <small className="form-hint">
        {state.scope}. Les données, vidéos et clés restent sur le serveur.
      </small>
      {data.development.changes.length ? (
        <div className="development-list">
          {data.development.changes.map((change) => (
            <DevelopmentCard key={change.id} change={change} owner={owner} />
          ))}
        </div>
      ) : (
        <p className="muted small">
          Les demandes, tests et résultats apparaîtront ici.
        </p>
      )}
    </section>
  );
}
