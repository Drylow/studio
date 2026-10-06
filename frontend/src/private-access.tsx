import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  Check,
  Eye,
  EyeOff,
  Fingerprint,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react";
import { api } from "./api";
import type { Boot } from "./types";
import { Button, Skyline } from "./components";

export function Login({
  boot,
  refresh,
}: {
  boot: Boot;
  refresh: () => Promise<void>;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [token, setToken] = useState("");
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <main className="login-page">
      <section className="login-world">
        <div className="brand">
          <span className="brand-icon">
            E<span>/</span>
          </span>
          <div>
            EDGERUNNERS<span>STUDIO</span>
          </div>
        </div>
        <span className="eyebrow">AFTERLIFE / PRIVATE HEADQUARTERS</span>
        <h1>
          Your crew.
          <br />
          <span>Your empire.</span>
        </h1>
        <p>
          Drylow & Kanye. Un studio privé.
          <br />
          Tes chaînes, tes idées, ton territoire.
        </p>
        <Skyline />
        <div className="login-world-footer">
          AUTHORIZED CREW ONLY<span>EST. 2026</span>
        </div>
      </section>
      <section className="login-form">
        <div className="gate-emblem">
          <Fingerprint size={30} />
          <span>CREW / 02</span>
          <LockKeyhole size={16} />
        </div>
        <span className="eyebrow">ACCÈS PRIVÉ / EDGERUNNERS STUDIO</span>
        <h2>
          {boot.setup_required
            ? "Crée ton accès privé."
            : "Bienvenue dans le crew."}
        </h2>
        <p>
          {boot.setup_required
            ? "Le code d’installation réserve la création du premier compte. Kanye sera ajouté depuis les réglages."
            : "Entre ton identifiant et ton mot de passe personnel. Le studio est réservé à vous deux."}
        </p>
        <form
          className="form"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await api(boot.setup_required ? "/setup" : "/login", "POST", {
                name,
                username,
                password,
                token,
              });
              setPassword("");
              await refresh();
            } catch (e) {
              setError((e as Error).message);
            }
            setBusy(false);
          }}
        >
          {boot.setup_required && (
            <>
              <label>
                Code d’installation
                <input
                  required
                  type="password"
                  maxLength={256}
                  autoComplete="off"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                />
              </label>
              <label>
                Ton nom
                <input
                  required
                  maxLength={80}
                  autoComplete="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
            </>
          )}
          <label>
            Identifiant
            <input
              required
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              minLength={3}
              maxLength={40}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </label>
          <label>
            Mot de passe
            <div className="gate-password">
              <input
                required
                type={visible ? "text" : "password"}
                minLength={boot.setup_required ? 16 : 1}
                maxLength={128}
                autoComplete={
                  boot.setup_required ? "new-password" : "current-password"
                }
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                aria-label={
                  visible
                    ? "Masquer le mot de passe"
                    : "Afficher le mot de passe"
                }
                aria-pressed={visible}
                onClick={() => setVisible(!visible)}
              >
                {visible ? <EyeOff size={19} /> : <Eye size={19} />}
              </button>
            </div>
          </label>
          {boot.setup_required && (
            <p className="form-hint">
              16 caractères minimum. Une phrase de plusieurs mots est facile à
              retenir.
            </p>
          )}
          {error && (
            <div role="alert" className="error-box">
              {error}
            </div>
          )}
          <Button variant="primary" type="submit" disabled={busy}>
            {busy
              ? "Vérification…"
              : boot.setup_required
                ? "Créer mon compte"
                : "Entrer dans le studio"}
            <ArrowUpRight size={17} />
          </Button>
        </form>
        <div className="login-security">
          <ShieldCheck size={17} />
          <span>
            Deux comptes privés · mot de passe personnel
            <br />
            Pages, vidéos et outils protégés côté serveur
          </span>
        </div>
        <nav className="login-public-links" aria-label="Informations publiques">
          <a href="/about">Présentation</a>
          <a href="/privacy">Confidentialité</a>
          <a href="/terms">Conditions</a>
        </nav>
      </section>
    </main>
  );
}

export function SecuritySettings({
  refresh,
}: {
  refresh: () => Promise<void>;
}) {
  const [status, setStatus] = useState<{
    preview: boolean;
    sessions: number;
  } | null>(null);
  const [editing, setEditing] = useState(false);
  const [old, setOld] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const load = () =>
    api<NonNullable<typeof status>>("/security").then(setStatus);
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  return (
    <section className="panel settings-card gate-settings">
      <div className="section-title">
        <div>
          <span className="eyebrow">TON ACCÈS PERSONNEL</span>
          <h2>Accès & sécurité</h2>
        </div>
        <ShieldCheck size={25} />
      </div>
      <p className="form-hint">
        Le studio est réservé à Drylow et Kanye. Chacun utilise son mot de passe
        personnel.
      </p>
      {status && (
        <div className="gate-status">
          <span>
            {status.preview ? "Aperçu local" : "Accès privé par mot de passe"}
          </span>
          <span>
            {status.sessions} session{status.sessions > 1 ? "s" : ""} ouverte
            {status.sessions > 1 ? "s" : ""}
          </span>
        </div>
      )}
      {!status?.preview && (
        <div className="gate-actions">
          <Button onClick={() => setEditing(!editing)}>
            Changer mon mot de passe
          </Button>
          <Button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                await api("/security/sessions", "POST", {});
                await load();
                setMessage("Les autres appareils ont été déconnectés.");
              } catch (e) {
                setError((e as Error).message);
              }
              setBusy(false);
            }}
          >
            Déconnecter les autres appareils
          </Button>
        </div>
      )}
      {editing && (
        <form
          className="form"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await api("/security/password", "POST", {
                current_password: old,
                password,
              });
              await refresh();
              await load();
              setEditing(false);
              setOld("");
              setPassword("");
              setMessage(
                "Mot de passe changé. Les anciennes sessions ont été fermées.",
              );
            } catch (e) {
              setError((e as Error).message);
            }
            setBusy(false);
          }}
        >
          <label>
            Mot de passe actuel
            <input
              required
              type="password"
              autoComplete="current-password"
              maxLength={128}
              value={old}
              onChange={(e) => setOld(e.target.value)}
            />
          </label>
          <label>
            Nouveau mot de passe
            <input
              required
              type="password"
              autoComplete="new-password"
              minLength={16}
              maxLength={128}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <Button variant="primary" type="submit" disabled={busy}>
            <Check size={16} />
            Enregistrer mon mot de passe
          </Button>
        </form>
      )}
      {error && (
        <p className="error-box" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="form-hint" role="status">
          {message}
        </p>
      )}
    </section>
  );
}
