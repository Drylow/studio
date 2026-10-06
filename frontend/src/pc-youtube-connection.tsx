import { useEffect, useState } from "react";
import { Download, Monitor, RefreshCw } from "lucide-react";
import type { Channel } from "./types";
import { api } from "./api";
import { Button, Tag } from "./components";

type LocalConnection = {
  configured: boolean;
  preview: boolean;
  status: "idle" | "awaiting_app" | "waiting" | "ready" | "failed";
  message: string;
  channel_title: string;
  channel_id: string;
  launch_uri?: string;
  installer_href?: string;
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
  const pending =
    state?.status === "awaiting_app" || state?.status === "waiting";
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
              : "Vérification indisponible.",
          );
      } finally {
        checking = false;
      }
    }, 3000);
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
        <strong>Depuis ce PC</strong>
        {state?.status === "ready" && <Tag tone="muted">CHAÎNE VÉRIFIÉE</Tag>}
      </div>
      <p>
        À faire sur le PC Windows qui servira à publier, avec Google Chrome
        installé.
      </p>
      {owner && !preview && (
        <ol className="connection-steps">
          <li>
            Clique sur <strong>Connecter avec mon PC</strong>.
          </li>
          <li>
            Au premier usage, télécharge l’assistant ci-dessous,{" "}
            <strong>extrais le ZIP</strong> puis double-clique sur{" "}
            <strong>Installer.cmd</strong>.
          </li>
          <li>
            Dans la nouvelle fenêtre Chrome, connecte-toi à YouTube et choisis{" "}
            <strong>{channel.name}</strong> : photo → Changer de compte si
            nécessaire.
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
        {pending ? "En attente de l’assistant" : "Connecter avec mon PC"}
      </Button>
      {owner &&
        !preview &&
        pending &&
        state?.installer_href &&
        state.launch_uri && (
          <div className="pc-local-launch">
            <a
              className="button primary"
              href={state.installer_href}
              download="Edgerunners-PC.zip"
            >
              <Download size={16} /> Télécharger l’assistant PC
            </a>
            <p className="form-hint">
              Une seule installation par PC. Le programme ouvre ensuite Chrome
              automatiquement.
            </p>
            <a className="text-button" href={state.launch_uri}>
              Déjà installé ? Ouvrir l’assistant sur ce PC
            </a>
            <p className="form-hint">
              Si Chrome propose « Ouvrir Edgerunners Studio », accepte
              l’ouverture. Si rien ne s’ouvre, installe l’assistant avec le ZIP
              ci-dessus.
            </p>
          </div>
        )}
      <p className="form-hint">
        Cette étape vérifie la bonne chaîne. Aucune vidéo n’est publiée. La
        publication automatique depuis le PC reste à valider.
      </p>
    </section>
  );
}
