import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  Check,
  Download,
  Fingerprint,
  LockKeyhole,
  ShieldCheck,
  Smartphone,
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
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState(false);
  const [saved, setSaved] = useState(false);
  const [enrolment, setEnrolment] = useState<{
    secret: string;
    uri: string;
    qr: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const stage = boot.auth?.stage;
  useEffect(() => {
    setError("");
    setCode("");
    setEnrolment(null);
    setSaved(false);
    if (stage === "enrol")
      api<{ secret: string; uri: string; qr: string }>(
        "/auth/enrol",
        "POST",
        {},
      )
        .then(setEnrolment)
        .catch((e) => setError(e.message));
  }, [stage, boot.csrf]);
  const confirm = async () => {
    setBusy(true);
    setError("");
    try {
      if (stage === "recovery") await api("/auth/finish", "POST", { saved });
      else if (stage)
        await api("/auth/verify", "POST", {
          code,
          recovery: stage === "challenge" && recovery,
        });
      else
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
  };
  const downloadCodes = () => {
    const blob = new Blob(
      [
        "Edgerunners Studio — codes de secours personnels\n\n" +
          boot.auth?.codes?.join("\n") +
          "\n\nChaque code ne fonctionne qu’une fois, avec ton mot de passe. Conserve ce fichier en lieu sûr.\n",
      ],
      { type: "text/plain;charset=utf-8" },
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "edgerunners-codes-de-secours.txt";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
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
          {stage === "enrol"
            ? "Sécurise ton accès."
            : stage === "challenge"
              ? "Confirme que c’est toi."
              : stage === "recovery"
                ? "Garde tes codes de secours."
                : boot.setup_required
                  ? "Crée ton accès privé."
                  : "Bienvenue dans le crew."}
        </h2>
        <p>
          {stage === "enrol"
            ? "Une seule installation. Ensuite, ton téléphone affichera un code pour chaque connexion."
            : stage === "challenge"
              ? recovery
                ? "Entre un de tes codes de secours. Tu pourras ensuite relier ton nouveau téléphone."
                : "Ouvre ton application d’authentification et entre le code Edgerunners Studio à 6 chiffres."
              : stage === "recovery"
                ? "Ces 8 codes permettent de récupérer ton accès si tu perds ton téléphone. Chaque code ne fonctionne qu’une fois, avec ton mot de passe."
                : boot.setup_required
                  ? "Le code d’installation réserve la création du premier compte. Kanye sera ajouté depuis les réglages."
                  : "Ton identifiant, ton mot de passe, puis le code sur ton téléphone. Le studio est réservé à vous deux."}
        </p>
        <form
          className="form"
          onSubmit={async (e) => {
            e.preventDefault();
            await confirm();
          }}
        >
          {!stage && (
            <>
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
                <input
                  required
                  type="password"
                  minLength={boot.setup_required ? 16 : 1}
                  maxLength={128}
                  autoComplete={
                    boot.setup_required ? "new-password" : "current-password"
                  }
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              {boot.setup_required && (
                <p className="form-hint">
                  16 caractères minimum. Une phrase de plusieurs mots est facile
                  à retenir.
                </p>
              )}
            </>
          )}
          {stage === "enrol" && (
            <div className="gate-enrol">
              <ol>
                <li>
                  Installe Google Authenticator, Microsoft Authenticator ou 2FAS
                  sur ton téléphone.
                </li>
                <li>
                  Dans l’application, touche <strong>+</strong>, puis{" "}
                  <strong>Scanner un QR code</strong>.
                </li>
                <li>
                  Scanne ce code, puis saisis les 6 chiffres affichés
                  ci-dessous.
                </li>
              </ol>
              {enrolment ? (
                <>
                  <img
                    className="gate-qr"
                    src={enrolment.qr}
                    alt="QR code personnel à scanner dans ton application d’authentification"
                  />
                  <details>
                    <summary>Je suis déjà sur mon téléphone</summary>
                    <p>
                      Dans l’application, choisis{" "}
                      <strong>Saisir une clé</strong>. Nom : Edgerunners Studio.
                      Type : basé sur le temps. Copie cette clé :
                    </p>
                    <code className="gate-secret">{enrolment.secret}</code>
                  </details>
                </>
              ) : (
                <p role="status">Préparation de ton QR code…</p>
              )}
            </div>
          )}
          {(stage === "enrol" || stage === "challenge") && (
            <label>
              {recovery && stage === "challenge"
                ? "Code de secours"
                : "Code de sécurité"}
              <input
                required
                autoFocus
                className="gate-code"
                inputMode={
                  recovery && stage === "challenge" ? "text" : "numeric"
                }
                autoComplete="one-time-code"
                pattern={
                  recovery && stage === "challenge" ? undefined : "[0-9]{6}"
                }
                minLength={recovery && stage === "challenge" ? 20 : 6}
                maxLength={recovery && stage === "challenge" ? 32 : 6}
                placeholder={
                  recovery && stage === "challenge"
                    ? "Ton code de secours"
                    : "000000"
                }
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </label>
          )}
          {stage === "recovery" && (
            <>
              <div className="gate-recovery">
                {boot.auth?.codes?.map((value) => (
                  <code key={value}>{value.match(/.{1,5}/g)?.join("-")}</code>
                ))}
              </div>
              <Button type="button" onClick={downloadCodes}>
                <Download size={16} />
                Télécharger mes codes
              </Button>
              <label className="gate-saved">
                <input
                  type="checkbox"
                  required
                  checked={saved}
                  onChange={(e) => setSaved(e.target.checked)}
                />
                J’ai enregistré mes codes de secours en lieu sûr.
              </label>
            </>
          )}
          {error && (
            <div role="alert" className="error-box">
              {error}
            </div>
          )}
          <Button
            variant="primary"
            type="submit"
            disabled={
              busy ||
              (stage === "enrol" && !enrolment) ||
              (stage === "recovery" && !saved)
            }
          >
            {busy
              ? "Vérification…"
              : stage === "recovery"
                ? "Entrer dans le studio"
                : stage
                  ? "Confirmer mon accès"
                  : boot.setup_required
                    ? "Créer mon compte"
                    : "Se connecter"}
            <ArrowUpRight size={17} />
          </Button>
          {stage === "challenge" && (
            <button
              className="gate-link"
              type="button"
              onClick={() => {
                setRecovery(!recovery);
                setCode("");
                setError("");
              }}
            >
              {recovery
                ? "Utiliser le code sur mon téléphone"
                : "J’ai perdu mon téléphone"}
            </button>
          )}
          {stage && (
            <button
              className="gate-link"
              type="button"
              disabled={busy}
              onClick={async () => {
                try {
                  await api("/logout", "POST", {});
                  setRecovery(false);
                  await refresh();
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              Revenir à la connexion
            </button>
          )}
        </form>
        <div className="login-security">
          <ShieldCheck size={17} />
          <span>
            Deux comptes privés · double authentification
            <br />
            Pages, vidéos et outils protégés côté serveur
          </span>
          <Smartphone size={17} />
        </div>
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
    mfa: boolean;
    preview: boolean;
    sessions: number;
    recovery_remaining: number;
  } | null>(null);
  const [editing, setEditing] = useState(false);
  const [old, setOld] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
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
        Le studio est réservé à Drylow et Kanye. Chacun garde son mot de passe,
        son téléphone et ses codes de secours.
      </p>
      {status && (
        <div className="gate-status">
          <span>
            {status.preview
              ? "Aperçu local"
              : status.mfa
                ? "Double authentification active"
                : "Double authentification à configurer"}
          </span>
          <span>
            {status.sessions} session{status.sessions > 1 ? "s" : ""} ouverte
            {status.sessions > 1 ? "s" : ""}
          </span>
          {status.mfa && (
            <span>{status.recovery_remaining} codes de secours restants</span>
          )}
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
                code,
              });
              await refresh();
              await load();
              setEditing(false);
              setOld("");
              setPassword("");
              setCode("");
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
          <label>
            Nouveau code de sécurité
            <input
              required
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </label>
          <Button variant="primary" disabled={busy}>
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
