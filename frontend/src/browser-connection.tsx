import { useEffect, useRef, useState } from "react";
import { Eye, EyeOff, Monitor, RefreshCw } from "lucide-react";
import { api } from "./api";
import { Button } from "./components";
import type { Channel } from "./types";

type Session = { session_id: string; public_key: string; expires_at: number };
type Frame = { image: string; width: number; height: number };
type Result = Partial<Frame> & {
  error?: string;
  channel_access_observed?: boolean;
  login_required?: boolean;
  browser_blocked?: boolean;
};
const bytes = (value: string) =>
  Uint8Array.from(atob(value), (c) => c.charCodeAt(0));
const encoded = (value: ArrayBuffer | Uint8Array) => {
  const data = value instanceof Uint8Array ? value : new Uint8Array(value);
  let text = "";
  for (const byte of data) text += String.fromCharCode(byte);
  return btoa(text);
};

export function BrowserConnection({
  channel,
  onAvailable,
}: {
  channel: Channel;
  onAvailable: (available: boolean) => void;
}) {
  const [enabled, setEnabled] = useState(false);
  const [active, setActive] = useState<Session | null>(null);
  const [frame, setFrame] = useState<Frame | null>(null);
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [visible, setVisible] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const sessionRef = useRef<Session | null>(null);
  const busyRef = useRef(false);
  const mounted = useRef(true);
  const base = `/youtube-browser/${channel.id}/sessions`;

  useEffect(() => {
    mounted.current = true;
    void api<{ enabled: boolean }>("/youtube-browser/status")
      .then((status) => {
        if (!mounted.current) return;
        setEnabled(status.enabled);
        onAvailable(status.enabled);
      })
      .catch(() => {});
    return () => {
      mounted.current = false;
      const viewer = sessionRef.current;
      if (viewer)
        void api(`${base}/${viewer.session_id}/close`, "POST", {}).catch(
          () => {},
        );
      sessionRef.current = null;
    };
  }, [base, onAvailable]);

  async function command(
    kind: string,
    payload: Record<string, string> = {},
    viewer = sessionRef.current,
  ) {
    if (!viewer) throw new Error("Ouvre d’abord le navigateur.");
    const queued = await api<{ command_id: string }>(
      `${base}/${viewer.session_id}/commands`,
      "POST",
      { kind, ...payload },
    );
    for (let i = 0; i < 85; i++) {
      if (
        !mounted.current ||
        sessionRef.current?.session_id !== viewer.session_id
      )
        throw new Error("Navigateur fermé.");
      const response = await api<{ state: string; result: Result | null }>(
        `${base}/${viewer.session_id}/commands/${queued.command_id}`,
      );
      if (response.state === "done" && response.result) {
        if (response.result.error) throw new Error(response.result.error);
        if (
          response.result.image &&
          response.result.width &&
          response.result.height
        ) {
          setFrame(response.result as Frame);
        }
        return response.result;
      }
      await new Promise((resolve) => setTimeout(resolve, 400));
    }
    throw new Error(
      "Le navigateur n’a pas répondu. L’action ne sera pas renvoyée automatiquement.",
    );
  }

  async function run(action: () => Promise<unknown>, silent = false) {
    if (silent && busyRef.current) return;
    if (!silent) {
      setBusy(true);
      setError("");
    }
    while (busyRef.current && mounted.current) {
      await new Promise((resolve) => setTimeout(resolve, 150));
    }
    if (!mounted.current) return;
    busyRef.current = true;
    if (!silent) {
      setBusy(true);
      setError("");
    }
    try {
      await action();
    } catch (failure) {
      if (mounted.current)
        setError(
          failure instanceof Error
            ? failure.message
            : "Navigateur indisponible.",
        );
    } finally {
      busyRef.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  useEffect(() => {
    if (!active) return;
    const refresh = setInterval(() => {
      if (!busyRef.current && document.visibilityState === "visible") {
        void run(() => command("frame"), true);
      }
    }, 2500);
    return () => clearInterval(refresh);
  }, [active]);

  async function input(value: Record<string, unknown>) {
    const viewer = sessionRef.current;
    if (!viewer) throw new Error("Navigateur fermé.");
    const key = await crypto.subtle.importKey(
      "spki",
      bytes(viewer.public_key),
      { name: "RSA-OAEP", hash: "SHA-256" },
      false,
      ["encrypt"],
    );
    const aes = await crypto.subtle.generateKey(
      { name: "AES-GCM", length: 256 },
      true,
      ["encrypt"],
    );
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const wrapped = await crypto.subtle.encrypt(
      { name: "RSA-OAEP" },
      key,
      await crypto.subtle.exportKey("raw", aes),
    );
    const ciphertext = await crypto.subtle.encrypt(
      {
        name: "AES-GCM",
        iv,
        additionalData: new TextEncoder().encode(viewer.session_id),
      },
      aes,
      new TextEncoder().encode(JSON.stringify(value)),
    );
    await command("input", {
      key: encoded(wrapped),
      iv: encoded(iv),
      ciphertext: encoded(ciphertext),
    });
    await command("frame");
  }

  async function start() {
    setMessage("Ouverture du navigateur du VPS…");
    setFrame(null);
    await api("/youtube-browser/start-service", "POST", {});
    let available = false;
    for (let i = 0; i < 90; i++) {
      if (!mounted.current) return;
      const status = await api<{ available: boolean }>(
        "/youtube-browser/status",
      );
      if (status.available) {
        available = true;
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    if (!available)
      throw new Error(
        "Le navigateur n’a pas démarré. Aucun compte n’a été connecté.",
      );
    const viewer = await api<Session>(base, "POST", {
      revision: channel.revision,
    });
    sessionRef.current = viewer;
    setActive(viewer);
    await command("open", {}, viewer);
    setMessage(
      "Clique dans le champ Google, écris ci-dessous, puis appuie sur Entrée. Termine les vérifications demandées par Google.",
    );
  }

  async function close() {
    const viewer = sessionRef.current;
    if (viewer) await api(`${base}/${viewer.session_id}/close`, "POST", {});
    sessionRef.current = null;
    setActive(null);
    setFrame(null);
    setText("");
    setMessage("");
  }

  if (!enabled) return null;
  return (
    <section
      className="private-browser-connection"
      aria-label="Connexion directe à YouTube Studio"
    >
      <strong>YouTube Studio sur le serveur</strong>
      <p>
        Connexion directe à YouTube, sans application à installer. La session
        Google reste privée sur le VPS.
      </p>
      {!active && (
        <Button
          variant="primary"
          disabled={busy}
          onClick={() => void run(start)}
        >
          <Monitor size={16} />
          Ouvrir YouTube sur le serveur
        </Button>
      )}
      {message && <p role="status">{message}</p>}
      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
      {active && (
        <>
          <div className="private-browser-screen" aria-busy={busy}>
            {frame ? (
              <img
                src={`data:image/jpeg;base64,${frame.image}`}
                alt="Écran privé de connexion Google sur le VPS"
                draggable={false}
                onClick={(event) => {
                  const rect = event.currentTarget.getBoundingClientRect();
                  const x = Math.min(
                    frame.width - 1,
                    Math.max(
                      0,
                      Math.floor(
                        ((event.clientX - rect.left) * frame.width) /
                          rect.width,
                      ),
                    ),
                  );
                  const y = Math.min(
                    frame.height - 1,
                    Math.max(
                      0,
                      Math.floor(
                        ((event.clientY - rect.top) * frame.height) /
                          rect.height,
                      ),
                    ),
                  );
                  void run(() => input({ action: "click", x, y }));
                }}
              />
            ) : (
              <p>Le navigateur démarre…</p>
            )}
          </div>
          <form
            className="private-browser-input"
            onSubmit={(event) => {
              event.preventDefault();
              if (!text) return;
              const value = text;
              setText("");
              void run(() => input({ action: "text", text: value }));
            }}
          >
            <label htmlFor={`browser-input-${channel.id}`}>
              Texte à écrire dans le champ Google sélectionné
            </label>
            <div className="private-browser-type">
              <input
                id={`browser-input-${channel.id}`}
                type={visible ? "text" : "password"}
                value={text}
                onChange={(event) => setText(event.target.value)}
                autoComplete="off"
                autoCorrect="off"
                spellCheck={false}
                autoCapitalize="none"
                maxLength={2000}
              />
              <Button
                aria-label={
                  visible ? "Masquer la saisie" : "Afficher la saisie"
                }
                onClick={() => setVisible(!visible)}
              >
                {visible ? <EyeOff size={18} /> : <Eye size={18} />}
              </Button>
            </div>
            <Button type="submit" disabled={busy || !text}>
              Écrire dans Google
            </Button>
          </form>
          <div className="youtube-actions">
            <Button
              disabled={busy}
              onClick={() =>
                void run(() => input({ action: "key", key: "Return" }))
              }
            >
              Entrée
            </Button>
            <Button
              disabled={busy}
              onClick={() =>
                void run(() => input({ action: "key", key: "Tab" }))
              }
            >
              Champ suivant
            </Button>
            <Button
              disabled={busy}
              onClick={() =>
                void run(() => input({ action: "key", key: "BackSpace" }))
              }
            >
              Effacer
            </Button>
            <Button
              disabled={busy}
              onClick={() => void run(() => command("frame"))}
            >
              <RefreshCw size={16} />
              Actualiser
            </Button>
          </div>
          <Button
            variant="primary"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                setMessage("Vérification de la chaîne ouverte…");
                const result = await command("inspect");
                await command("frame");
                setMessage(
                  result.channel_access_observed
                    ? `Accès à ${channel.name} observé. L’envoi automatique reste à valider par un test.`
                    : result.browser_blocked
                      ? "Google refuse ce navigateur. Aucun contournement de sécurité ne sera appliqué."
                      : "La chaîne attendue n’a pas été confirmée. Termine la connexion Google et choisis la bonne chaîne.",
                );
              })
            }
          >
            J’ai terminé la connexion Google
          </Button>
          <Button disabled={busy} onClick={() => void run(close)}>
            Fermer l’écran privé
          </Button>
          <p className="form-hint">
            Cet écran expire après 20 minutes. Une session ouverte ne valide pas
            encore la publication automatique.
          </p>
        </>
      )}
    </section>
  );
}
