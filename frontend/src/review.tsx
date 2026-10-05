import { useEffect, useState } from "react";
import { Check, Upload, ShieldCheck, ArrowUpRight } from "lucide-react";
import { api, upload } from "./api";
import { Button } from "./components";
import type { Video } from "./types";
import type { Mutate } from "./forms";

const licenses: Record<string, string> = {
  CC0: "https://creativecommons.org/publicdomain/zero/1.0",
  "CC BY 3.0": "https://creativecommons.org/licenses/by/3.0",
  "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0",
  "CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0",
  "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0",
  "Public domain": "",
};
type Proof = { license: string; author: string; evidence_url: string };
function Evidence({
  value,
  onChange,
  label,
}: {
  value: Proof;
  onChange: (p: Proof) => void;
  label: string;
}) {
  return (
    <fieldset className="evidence">
      <legend>{label}</legend>
      <div className="form-grid">
        <label>
          Licence
          <select
            required
            value={value.license}
            onChange={(e) => onChange({ ...value, license: e.target.value })}
          >
            <option value="">Choisir la licence…</option>
            {Object.keys(licenses).map((l) => (
              <option key={l}>{l}</option>
            ))}
          </select>
        </label>
        <label>
          Auteur
          <input
            required
            value={value.author}
            onChange={(e) => onChange({ ...value, author: e.target.value })}
          />
        </label>
      </div>
      <label>
        Page qui établit les droits
        <input
          type="url"
          required
          placeholder="https://…"
          value={value.evidence_url}
          onChange={(e) => onChange({ ...value, evidence_url: e.target.value })}
        />
      </label>
    </fieldset>
  );
}
function complete(p: Proof) {
  return {
    ...p,
    license_url: licenses[p.license],
    adaptation_license: p.license.includes("BY-SA") ? p.license : undefined,
  };
}
export function ReviewForm({
  video,
  mutate,
}: {
  video: Video;
  mutate: Mutate;
}) {
  const [controls, setControls] = useState<{
    images: { url: string; credit: string }[];
    sheets: string[];
  } | null>(null);
  const [error, setError] = useState("");
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [voiceEvidence, setVoiceEvidence] = useState("");
  const [commercial, setCommercial] = useState(false);
  const [automated, setAutomated] = useState(false);
  const [thumb, setThumb] = useState<Proof>({
    license: "",
    author: "",
    evidence_url: "",
  });
  const [visuals, setVisuals] = useState<Record<string, Proof>>({});
  const [rightsOpen, setRightsOpen] = useState(false);
  useEffect(() => {
    api<{ images: { url: string; credit: string }[]; sheets: string[] }>(
      `/videos/${video.id}/controls`,
    )
      .then(setControls)
      .catch((e) => setError(e.message));
  }, [video.id, video.revision]);
  return (
    <div className="review-forms">
      {error && <p className="error-text">{error}</p>}
      <div className="review-title">
        <h3>Miniature de cette vidéo</h3>
        <label className="button secondary upload-button">
          <Upload size={15} />
          Importer une miniature
          <input
            type="file"
            accept="image/png,image/jpeg"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file)
                mutate(
                  () => upload(`/videos/${video.id}/thumbnail`, file),
                  "Miniature importée ; droits à vérifier.",
                );
            }}
          />
        </label>
      </div>
      <p className="form-hint">
        JPEG ou PNG · 16:9 · 2 Mo maximum. Les références approuvées restent
        dans la bibliothèque.
      </p>
      {!!controls?.sheets.length && (
        <>
          <h3 className="review-title">Planches de contrôle</h3>
          <div className="review-sheets">
            {controls.sheets.map((name) => (
              <a
                key={name}
                href={`/media/${video.id}/check/${name}`}
                target="_blank"
                rel="noreferrer"
              >
                <img
                  src={`/media/${video.id}/check/${name}`}
                  alt={"Planche de contrôle " + name}
                  loading="lazy"
                />
                <span>
                  Ouvrir la planche
                  <ArrowUpRight size={12} />
                </span>
              </a>
            ))}
          </div>
        </>
      )}
      <form
        className="form visual-review"
        onSubmit={async (e) => {
          e.preventDefault();
          await mutate(
            () =>
              api(`/videos/${video.id}/review`, "POST", {
                ...checks,
                revision: video.revision,
              }),
            "Relecture du rendu enregistrée.",
          );
        }}
      >
        <h3>Relecture du rendu</h3>
        {[
          ["watched", "J’ai regardé toutes les images du montage."],
          ["audio_checked", "J’ai contrôlé la voix, les noms et le son."],
          [
            "facts_checked",
            "Les faits et les citations correspondent aux sources.",
          ],
          [
            "captions_checked",
            "Les textes et sous-titres sont corrects et lisibles.",
          ],
        ].map(([key, label]) => (
          <label className="review-check" key={key}>
            <input
              type="checkbox"
              checked={!!checks[key]}
              onChange={(e) =>
                setChecks((c) => ({ ...c, [key]: e.target.checked }))
              }
            />
            {label}
          </label>
        ))}
        <Button
          type="submit"
          disabled={
            !video.video_path ||
            !["technical", "verified"].includes(video.quality_status) ||
            Object.values(checks).filter(Boolean).length !== 4
          }
        >
          <Check size={15} />
          Confirmer la relecture
        </Button>
        {!video.video_path && (
          <p className="form-hint">
            Le fichier local doit être disponible pour enregistrer une relecture
            liée au rendu.
          </p>
        )}
      </form>
      <Button onClick={() => setRightsOpen(!rightsOpen)}>
        <ShieldCheck size={15} />
        {rightsOpen
          ? "Fermer les preuves de droits"
          : "Renseigner les preuves de droits"}
      </Button>
      {rightsOpen && (
        <form
          className="form rights-form"
          onSubmit={async (e) => {
            e.preventDefault();
            await mutate(
              () =>
                api(`/videos/${video.id}/rights`, "POST", {
                  revision: video.revision,
                  voice: {
                    commercial_use: commercial,
                    automated_access: automated,
                    evidence_url: voiceEvidence,
                  },
                  thumbnail: complete(thumb),
                  visuals: (controls?.images || []).map((i) => ({
                    url: i.url,
                    rights: complete(
                      visuals[i.url] || {
                        license: "",
                        author: "",
                        evidence_url: "",
                      },
                    ),
                  })),
                }),
              "Preuves de droits enregistrées pour les fichiers actuels.",
            );
          }}
        >
          <div className="inline-note">
            <ShieldCheck size={18} />
            Réservé au propriétaire. Ces preuves doivent établir la
            réutilisation réelle des médias et de la voix, y compris l’accès
            automatisé.
          </div>
          <label>
            Autorisation du fournisseur de voix
            <input
              type="url"
              required
              value={voiceEvidence}
              onChange={(e) => setVoiceEvidence(e.target.value)}
              placeholder="Lien vers le contrat ou la permission applicable"
            />
          </label>
          <label className="review-check">
            <input
              type="checkbox"
              required
              checked={commercial}
              onChange={(e) => setCommercial(e.target.checked)}
            />
            L’autorisation couvre l’usage commercial de la voix.
          </label>
          <label className="review-check">
            <input
              type="checkbox"
              required
              checked={automated}
              onChange={(e) => setAutomated(e.target.checked)}
            />
            L’autorisation couvre explicitement l’accès automatisé.
          </label>
          <Evidence
            label="Droits de la miniature"
            value={thumb}
            onChange={setThumb}
          />
          {controls?.images.map((i, n) => (
            <div key={i.url}>
              <a
                href={i.url}
                target="_blank"
                rel="noreferrer"
                className="text-link"
              >
                Visuel {n + 1} · {i.credit}
                <ArrowUpRight size={13} />
              </a>
              <Evidence
                label={"Droits du visuel " + (n + 1)}
                value={
                  visuals[i.url] || {
                    license: "",
                    author: "",
                    evidence_url: "",
                  }
                }
                onChange={(p) => setVisuals((s) => ({ ...s, [i.url]: p }))}
              />
            </div>
          ))}
          <p className="form-hint">
            Un crédit ou une absence de réclamation YouTube ne remplace pas une
            licence. Les adaptations sous licence BY-SA conservent la même
            licence.
          </p>
          <Button
            variant="primary"
            type="submit"
            disabled={!video.video_path || !video.thumb_path}
          >
            <ShieldCheck size={15} />
            Enregistrer les preuves
          </Button>
        </form>
      )}
    </div>
  );
}
