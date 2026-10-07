import { useEffect, useState } from "react";
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
import { BrowserConnection } from "./browser-connection";

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
  const pending = returned ? query.get("youtube_pending") : null;
  const [open, setOpen] = useState(returned);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [checked, setChecked] = useState("");
  const [browserAvailable, setBrowserAvailable] = useState(false);
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
      url.searchParams.delete("youtube_pending");
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
              {pending && owner && <PendingChoice id={pending} close={close} />}
              <Tag tone={channel.connected ? "ready" : "muted"}>
                {channel.connected ? "ACCÈS ENREGISTRÉ" : "À CONNECTER"}
              </Tag>
              {!browserAvailable && (
                <p>
                  Rien à installer sur ton PC. Après l’autorisation Google, le
                  serveur pourra envoyer la vidéo, le titre, la description et
                  la miniature directement sur cette chaîne.
                </p>
              )}
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
              {owner && !preview && (
                <BrowserConnection
                  channel={channel}
                  onAvailable={setBrowserAvailable}
                />
              )}
              <details
                className="youtube-api-alternative"
                open={!browserAvailable}
              >
                <summary>
                  {browserAvailable
                    ? "Autre méthode : API Google"
                    : "Connexion API Google"}
                </summary>
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
                    Choisis ton compte Google, puis un profil. Les profils
                    peuvent garder un ancien nom de chaîne : le site te montre
                    ensuite la vraie chaîne et te laisse choisir sa fiche.
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
                    variant="primary"
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
              </details>
              {!!channel.connected &&
                owner &&
                !preview &&
                (confirm ? (
                  <div className="youtube-disconnect">
                    <p>
                      Déconnecter suspend l’automatisation de cette chaîne. Ses
                      vidéos et son historique sont conservés.
                    </p>
                    <div className="youtube-actions">
                      <Button onClick={() => setConfirm(false)} disabled={busy}>
                        Garder la connexion
                      </Button>
                      <Button
                        variant="danger"
                        disabled={busy}
                        onClick={async () => {
                          setBusy(true);
                          const ok = await mutate(
                            () =>
                              api(`/youtube/${channel.id}/disconnect`, "POST", {
                                revision: channel.revision,
                              }),
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
            </div>
          </Modal>,
          document.body,
        )}
    </>
  );
}

type PendingFiche = {
  id: number;
  name: string;
  revision: number;
  enabled: boolean;
  holds: boolean;
  linked_title: string;
  compatible: boolean;
};
type Pending = {
  title: string;
  yt_channel_id: string;
  handle: string;
  subscribers: string | null;
  thumbnail: string;
  origin: number;
  suggested: number | null;
  fiches: PendingFiche[];
};

// Google profiles can keep a former channel name: show the real channel, then
// let the owner choose which studio fiche receives it.
function PendingChoice({ id, close }: { id: string; close: () => void }) {
  const [data, setData] = useState<Pending | null>(null);
  const [target, setTarget] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api<Pending>(`/youtube/pending/${encodeURIComponent(id)}`)
      .then((d) => {
        setData(d);
        setTarget(d.suggested ?? 0);
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Choix indisponible."),
      );
  }, [id]);
  if (error && !data) return <p className="error-text">{error}</p>;
  if (!data) return <p className="muted small">Lecture de la chaîne choisie…</p>;
  const fiche = data.fiches.find((f) => f.id === target);
  const holder = data.fiches.find((f) => f.holds && f.id !== target);
  async function assign() {
    if (!fiche) return;
    setBusy(true);
    setError("");
    try {
      await api(`/youtube/pending/${encodeURIComponent(id)}/assign`, "POST", {
        channel_id: fiche.id,
        revision: fiche.revision,
      });
      window.location.assign(`/channels?connected=${fiche.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Liaison impossible.");
      setBusy(false);
    }
  }
  async function other() {
    setBusy(true);
    await api(`/youtube/pending/${encodeURIComponent(id)}/cancel`, "POST", {}).catch(
      () => undefined,
    );
    window.location.assign(`/api/studio/youtube/${data!.origin}/connect`);
  }
  return (
    <div className="youtube-pending">
      <p>
        Google t’a donné l’accès à cette chaîne YouTube. Vérifie que c’est la
        bonne, puis choisis la fiche du studio à laquelle la relier.
      </p>
      <div className="youtube-pending-channel">
        {data.thumbnail ? (
          <img src={data.thumbnail} alt="" width={56} height={56} />
        ) : (
          <span className="youtube-pending-avatar">
            {data.title.slice(0, 1).toUpperCase()}
          </span>
        )}
        <div>
          <strong>{data.title}</strong>
          <span>
            {[
              data.handle,
              data.subscribers !== null && data.subscribers !== undefined
                ? `${Number(data.subscribers).toLocaleString("fr-FR")} abonnés`
                : "",
            ]
              .filter(Boolean)
              .join(" · ")}
          </span>
          <a
            className="text-button"
            href={`https://www.youtube.com/channel/${encodeURIComponent(data.yt_channel_id)}`}
            target="_blank"
            rel="noreferrer"
          >
            Voir sur YouTube <ExternalLink size={14} />
          </a>
        </div>
      </div>
      <label>
        Relier à la fiche
        <select
          value={target}
          onChange={(e) => setTarget(Number(e.target.value))}
          disabled={busy}
        >
          {data.suggested === null && (
            <option value={0}>Choisis une fiche…</option>
          )}
          {data.fiches.map((f) => (
            <option key={f.id} value={f.id} disabled={!f.compatible}>
              {f.name}
              {f.id === data.suggested ? " (même nom)" : ""}
              {!f.compatible ? " (connecte depuis cette fiche)" : ""}
            </option>
          ))}
        </select>
      </label>
      {data.suggested === null && (
        <p className="form-hint">
          Aucune fiche du studio ne porte le nom de cette chaîne. Si ce n’est pas
          une chaîne à automatiser, clique « Choisir un autre profil Google ».
        </p>
      )}
      {fiche?.linked_title && (
        <p className="form-hint">
          « {fiche.name} » est reliée à « {fiche.linked_title} » : ce lien sera
          remplacé.
        </p>
      )}
      {holder && (
        <p className="form-hint">
          Cette chaîne est reliée à « {holder.name} » : le lien sera déplacé
          vers « {fiche?.name} ».
        </p>
      )}
      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
      <div className="youtube-actions">
        <Button
          variant="primary"
          onClick={assign}
          disabled={busy || !fiche?.compatible}
        >
          <Link2 size={16} />
          Relier à {fiche?.name || "la fiche"}
        </Button>
        <Button onClick={other} disabled={busy}>
          Choisir un autre profil Google
        </Button>
        <Button variant="ghost" onClick={close} disabled={busy}>
          Annuler
        </Button>
      </div>
    </div>
  );
}
