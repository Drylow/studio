import { useEffect, useState } from "react";
import { Monitor, RefreshCw } from "lucide-react";
import type { Channel } from "./types";
import { api } from "./api";
import { Button, Tag } from "./components";

type LocalConnection = {
  configured: boolean;
  preview: boolean;
  status: "idle" | "queued" | "waiting" | "ready" | "failed";
  message: string;
  channel_title: string;
  channel_id: string;
  publication_validated: false;
};

export function PCYouTubeConnection({
  channel,
  owner,
  preview,
}: {
  channel: Channel;
  owner: boolean;
  preview: boolean;
}) {
  const [state, setState] = useState<LocalConnection | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const path = `/youtube/${channel.id}/pc`;
  const pending = state?.status === "queued" || state?.status === "waiting";
  useEffect(() => {
    let alive = true;
    api<LocalConnection>(path)
      .then((value) => {
        if (alive) setState(value);
      })
      .catch((reason) => {
        if (alive) setError(reason.message);
      });
    return () => {
      alive = false;
    };
  }, [path]);
  useEffect(() => {
    if (!pending || !owner || preview) return;
    let alive = true;
    let checking = false;
    const timer = window.setInterval(async () => {
      if (checking) return;
      checking = true;
      try {
        const value = await api<LocalConnection>(path + "/check", "POST", {});
        if (alive) {
          setState(value);
          setError("");
        }
      } catch (reason) {
        if (alive)
          setError(
            reason instanceof Error
              ? reason.message
              : "Relais PC indisponible.",
          );
      } finally {
        checking = false;
      }
    }, 15000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [pending, path, owner, preview]);
  return (
    <section
      className="pc-youtube-connection"
      aria-label="Connexion YouTube depuis ton PC"
    >
      <div className="youtube-actions">
        <Monitor size={20} />
        <strong>Depuis ton PC</strong>
        {state?.status === "ready" && <Tag tone="muted">CHROME VÉRIFIÉ</Tag>}
      </div>
      <p>
        Ton PC servira à envoyer les vidéos préparées par le studio. Une
        notification Windows annonce chaque intervention. Les vidéos attendront
        si le PC est éteint.
      </p>
      {owner && !preview && (
        <ol className="connection-steps">
          <li>
            Allume ton PC, puis clique sur{" "}
            <strong>Connecter avec mon PC</strong>.
          </li>
          <li>
            Chrome s’ouvre sur ton PC. Connecte-toi normalement à YouTube.
          </li>
          <li>
            Choisis <strong>{channel.name}</strong>. Si nécessaire : photo de
            profil → Changer de compte.
          </li>
        </ol>
      )}
      {state?.channel_id && (
        <a
          className="text-button"
          href={`https://www.youtube.com/channel/${state.channel_id}`}
          target="_blank"
          rel="noreferrer"
        >
          Chaîne à sélectionner : {state.channel_title}
        </a>
      )}
      {state && state.status !== "idle" && (
        <p className="youtube-check-result" role="status">
          {state.message}
        </p>
      )}
      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
      <Button
        variant="primary"
        disabled={!owner || preview || !state?.configured || busy || pending}
        onClick={async () => {
          setBusy(true);
          setError("");
          try {
            setState(
              await api<LocalConnection>(path + "/connect", "POST", {
                revision: channel.revision,
              }),
            );
          } catch (reason) {
            setError(
              reason instanceof Error
                ? reason.message
                : "Connexion PC indisponible.",
            );
            // An already pending request stays discoverable after reopening the modal.
            try {
              setState(await api<LocalConnection>(path));
            } catch {
              /* Keep the concrete error. */
            }
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy || pending ? <RefreshCw size={16} /> : <Monitor size={16} />}
        {pending ? "Connexion en cours sur ton PC" : "Connecter avec mon PC"}
      </Button>
      <p className="form-hint">
        Cette étape vérifie l’accès à la bonne chaîne. Elle ne publie aucune
        vidéo. L’envoi automatique et la création entièrement autonome restent à
        valider.
      </p>
    </section>
  );
}
