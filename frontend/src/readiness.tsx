import { useEffect, useState } from "react";
import { CheckCircle2, Circle, ArrowUpRight, RefreshCw } from "lucide-react";
import { api } from "./api";
import type { Video } from "./types";

type Checklist = {
  checks: {
    key: string;
    label: string;
    complete: boolean;
    help: string;
    tab: string;
  }[];
  complete: number;
  total: number;
  ready: boolean;
};
export function Readiness({
  video,
  select,
}: {
  video: Video;
  select: (tab: string) => void;
}) {
  const [data, setData] = useState<Checklist | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setError("");
    api<Checklist>(`/videos/${video.id}/readiness`)
      .then((r) => {
        if (active) setData(r);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [video.id, video.revision]);
  return (
    <section className="readiness">
      <div className="readiness-heading">
        <div>
          <span className="eyebrow">AVANT LE DÉPART</span>
          <h3>
            {data?.ready
              ? "Cette vidéo est prête."
              : "Les étapes avant publication."}
          </h3>
        </div>
        <span>
          {data ? (
            `${data.complete} / ${data.total}`
          ) : (
            <RefreshCw size={16} className="spin" />
          )}
        </span>
      </div>
      {error && <p className="error-text">{error}</p>}
      {data && (
        <>
          <div className="readiness-progress">
            <span style={{ width: `${(data.complete / data.total) * 100}%` }} />
          </div>
          <div className="readiness-checks">
            {data.checks.map((check) => (
              <div
                key={check.key}
                className={check.complete ? "complete" : "pending"}
              >
                {check.complete ? (
                  <CheckCircle2 size={17} />
                ) : (
                  <Circle size={17} />
                )}
                <div>
                  <strong>{check.label}</strong>
                  {!check.complete && <p>{check.help}</p>}
                </div>
                {!check.complete && (
                  <button
                    className="icon-button"
                    aria-label={"Aller à : " + check.label}
                    onClick={() => select(check.tab)}
                  >
                    <ArrowUpRight size={16} />
                  </button>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
