import { useState } from "react";
import { createPortal } from "react-dom";
import {
  Link2,
  ExternalLink,
  RefreshCw,
  Unplug,
  ShieldCheck,
} from "lucide-react";
import type { Channel, User } from "./types";
import type { Mutate } from "./forms";
import { api } from "./api";
import { Button, Modal, Tag } from "./components";
import { PCYouTubeConnection } from "./pc-youtube-connection";

export function YouTubeConnection({
  channel,
  configured,
  preview,
  user,
  mutate,
  onDisconnected,
}: {
  channel: Channel;
  configured: boolean;
  preview: boolean;
  user: User;
  mutate: Mutate;
  onDisconnected?: () => void;
}) {
  const query = new URLSearchParams(window.location.search);
  const returned =
    query.get("connected") === String(channel.id) ||
    query.get("channel") === String(channel.id);
  const returnedError = returned ? query.get("youtube_error") : null;
  const [open, setOpen] = useState(returned);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [checked, setChecked] = useState("");
  const owner = user.role === "owner";
  const canConnect = owner && configured && !preview;
  function close() {
    setOpen(false);
    setConfirm(false);
    if (returned) {
      const url = new URL(window.location.href);
      url.searchParams.delete("connected");
      url.searchParams.delete("channel");
      url.searchParams.delete("youtube_error");
      window.history.replaceState({}, "", url.pathname + url.search);
    }
  }
  return (
    <>
      <button
        type="button"
        className={
          "youtube-connect-button " + (channel.connected ? "linked" : "")
        }
        aria-label={`Connexion YouTube de ${channel.name}`}
        onClick={() => setOpen(true)}
      >
        <Link2 size={16} />
        <span>
          {channel.connected ? "YouTube connecté" : "Connecter YouTube"}
        </span>
        <ExternalLink size={14} />
      </button>
      {open &&
        createPortal(
          <Modal title={`YouTube · ${channel.name}`} close={close}>
            <div className="form youtube-connection">
              {returnedError && (
                <p className="error-text" role="alert">
                  {returnedError}
                </p>
              )}
              <Tag tone={channel.connected ? "ready" : "muted"}>
                {channel.connected ? "ACCÈS ENREGISTRÉ" : "À CONNECTER"}
              </Tag>
              <p>Relie la bonne chaîne avant de demander une publication.</p>
              <PCYouTubeConnection
                channel={channel}
                owner={owner}
                preview={preview}
              />
              <details
                className="youtube-google-option"
                open={!!channel.connected}
              >
                <summary>Connexion par l’API Google</summary>
                {!!channel.connected && (
                  <div className="youtube-identity">
                    <strong>{channel.yt_channel_title || channel.name}</strong>
                    <span>{channel.yt_channel_id}</span>
                    {channel.yt_channel_id && (
                      <a
                        className="text-button"
                        href={`https://www.youtube.com/channel/${encodeURIComponent(channel.yt_channel_id)}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Voir la chaîne YouTube <ExternalLink size={14} />
                      </a>
                    )}
                  </div>
                )}
                {preview ? (
                  <div className="inline-note">
                    <ShieldCheck size={18} />
                    Aperçu : les connexions Google et les publications réelles
                    sont désactivées. Tu pourras connecter la chaîne sur le site
                    en service.
                  </div>
                ) : !owner ? (
                  <div className="inline-note">
                    <ShieldCheck size={18} />
                    Le propriétaire du studio connecte les comptes Google.
                    Ensuite, vous pouvez tous les deux préparer et demander les
                    publications.
                  </div>
                ) : !configured ? (
                  <div className="inline-note">
                    <Link2 size={18} />
                    L’accès Google doit être configuré une seule fois pour le
                    studio : Réglages → Connexions → Comment connecter.
                  </div>
                ) : null}
                <ol className="connection-steps">
                  <li>
                    Clique sur{" "}
                    <strong>
                      {channel.connected
                        ? "Reconnecter avec Google"
                        : "Connecter avec Google"}
                    </strong>
                    .
                  </li>
                  <li>
                    Choisis le compte Google puis la chaîne{" "}
                    <strong>{channel.name}</strong>.
                  </li>
                  <li>
                    Accepte les autorisations : tu reviens au studio avec le nom
                    de la chaîne reliée.
                  </li>
                </ol>
                <p className="form-hint">
                  La connexion n’active pas les publications automatiques. Les
                  contrôles des fichiers, des droits et la validation prévue
                  pour cette chaîne restent obligatoires. Un accès enregistré
                  n’est pas un test de connexion réussi.
                </p>
                {checked && (
                  <p className="youtube-check-result" role="status">
                    {checked}
                  </p>
                )}
                <div className="youtube-actions">
                  <Button
                    disabled={!canConnect || busy}
                    onClick={() =>
                      window.location.assign(
                        `/api/studio/youtube/${channel.id}/connect`,
                      )
                    }
                  >
                    <Link2 size={16} />
                    {channel.connected
                      ? "Reconnecter avec Google"
                      : "Connecter avec Google"}
                  </Button>
                  {!!channel.connected && (
                    <Button
                      disabled={!canConnect || busy}
                      onClick={async () => {
                        setBusy(true);
                        setChecked("");
                        await mutate(async () => {
                          const result = await api<{ channel_title: string }>(
                            `/youtube/${channel.id}/verify`,
                            "POST",
                            { revision: channel.revision },
                          );
                          setChecked(
                            `Connexion vérifiée auprès de YouTube : ${result.channel_title}.`,
                          );
                        }, "Connexion YouTube vérifiée.");
                        setBusy(false);
                      }}
                    >
                      <RefreshCw size={16} />
                      Vérifier la connexion
                    </Button>
                  )}
                </div>
                {!!channel.connected &&
                  owner &&
                  !preview &&
                  (confirm ? (
                    <div className="youtube-disconnect">
                      <p>
                        Déconnecter suspend l’automatisation de cette chaîne.
                        Ses vidéos et son historique sont conservés.
                      </p>
                      <div className="youtube-actions">
                        <Button
                          onClick={() => setConfirm(false)}
                          disabled={busy}
                        >
                          Garder la connexion
                        </Button>
                        <Button
                          variant="danger"
                          disabled={busy}
                          onClick={async () => {
                            setBusy(true);
                            const ok = await mutate(
                              () =>
                                api(
                                  `/youtube/${channel.id}/disconnect`,
                                  "POST",
                                  {
                                    revision: channel.revision,
                                  },
                                ),
                              "YouTube déconnecté ; automatisation suspendue.",
                            );
                            setBusy(false);
                            if (ok) {
                              close();
                              onDisconnected?.();
                            }
                          }}
                        >
                          Déconnecter et suspendre
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <Button variant="ghost" onClick={() => setConfirm(true)}>
                      <Unplug size={16} />
                      Déconnecter cette chaîne
                    </Button>
                  ))}
              </details>
            </div>
          </Modal>,
          document.body,
        )}
    </>
  );
}
