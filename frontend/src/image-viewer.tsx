import { useState } from "react";
import { createPortal } from "react-dom";
import { ZoomIn, ZoomOut, Maximize, ArrowUpRight } from "lucide-react";
import { Button, Modal } from "./components";

export function ZoomImage({
  src,
  alt,
  loading = "lazy",
  caption,
}: {
  src: string;
  alt: string;
  loading?: "lazy" | "eager";
  caption?: string;
}) {
  const [open, setOpen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [width, setWidth] = useState(1000);
  return (
    <>
      <button
        type="button"
        className="zoom-image"
        aria-label={"Agrandir : " + alt}
        onClick={() => {
          setZoom(1);
          setOpen(true);
        }}
      >
        <img src={src} alt={alt} loading={loading} />
        {caption && (
          <span>
            {caption}
            <ZoomIn size={14} />
          </span>
        )}
      </button>
      {open &&
        createPortal(
          <Modal
            title={alt}
            subtitle="Agrandis l’image avec +, puis fais défiler pour examiner les détails."
            close={() => setOpen(false)}
            wide
          >
            <div className="image-viewer">
              <div className="image-viewer-toolbar">
                <Button
                  onClick={() => setZoom((z) => Math.max(0.5, z - 0.5))}
                  disabled={zoom <= 0.5}
                >
                  <ZoomOut size={17} />
                  <span>Réduire</span>
                </Button>
                <output aria-live="polite">{Math.round(zoom * 100)} %</output>
                <Button
                  onClick={() => setZoom((z) => Math.min(4, z + 0.5))}
                  disabled={zoom >= 4}
                >
                  <ZoomIn size={17} />
                  <span>Agrandir</span>
                </Button>
                <Button onClick={() => setZoom(1)}>
                  <Maximize size={17} />
                  <span>Ajuster</span>
                </Button>
                <a
                  className="button ghost"
                  href={src}
                  target="_blank"
                  rel="noreferrer"
                >
                  <ArrowUpRight size={16} />
                  <span>Image originale</span>
                </a>
              </div>
              <div
                className="image-viewer-canvas"
                tabIndex={0}
                aria-label="Image agrandie, fais défiler pour voir les détails"
              >
                <img
                  src={src}
                  alt={alt}
                  onLoad={(e) =>
                    setWidth(
                      Math.min(
                        e.currentTarget.naturalWidth,
                        window.innerWidth - 80,
                        990,
                      ),
                    )
                  }
                  style={{
                    width: Math.max(250, width) * zoom,
                    maxWidth: "none",
                  }}
                />
              </div>
            </div>
          </Modal>,
          document.body,
        )}
    </>
  );
}
