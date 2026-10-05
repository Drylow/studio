import type { ReactNode } from "react";
import { useEffect, useRef } from "react";
import {
  X,
  ArrowUpRight,
  Radio,
  CheckCircle2,
  AlertTriangle,
  Clock3,
  Clapperboard,
} from "lucide-react";
import type { Channel, Video } from "./types";
import { dateLabel, labels } from "./api";

export function Button({
  children,
  onClick,
  variant = "secondary",
  disabled = false,
  type = "button",
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
}) {
  return (
    <button
      className={`button ${variant} ${className}`}
      type={type}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
export function Tag({
  children,
  tone = "muted",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`tag ${tone}`}>{children}</span>;
}
export function SectionTitle({
  eyebrow,
  title,
  action,
}: {
  eyebrow?: string;
  title: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-title">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h2>{title}</h2>
      </div>
      {action}
    </div>
  );
}
export function Empty({
  icon,
  title,
  text,
  action,
}: {
  icon?: ReactNode;
  title: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon || <Clapperboard size={26} />}</div>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}
export function Modal({
  title,
  subtitle,
  children,
  close,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  close: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(close);
  closeRef.current = close;
  useEffect(() => {
    const active = document.activeElement as HTMLElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    ref.current
      ?.querySelector<HTMLElement>("button,input,select,textarea")
      ?.focus();
    function handle(e: KeyboardEvent) {
      if (e.key === "Escape") closeRef.current();
      if (e.key === "Tab") {
        const items = ref.current?.querySelectorAll<HTMLElement>(
          "button:not([disabled]),input:not([disabled]),select,textarea,a[href]",
        );
        if (!items?.length) return;
        const first = items[0],
          last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", handle);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", handle);
      active?.focus();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={"modal " + (wide ? "wide" : "")}
      >
        <header className="modal-head">
          <div>
            <span className="eyebrow">DRYLOW / STUDIO</span>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="icon-button" onClick={close} aria-label="Fermer">
            <X size={20} />
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}
export function ChannelMark({
  channel,
  size = "normal",
}: {
  channel: Channel;
  size?: string;
}) {
  return (
    <div
      className={`channel-mark ${size}`}
      style={{ "--channel": channel.accent } as React.CSSProperties}
    >
      <span>{channel.initials}</span>
    </div>
  );
}
export function VideoThumb({
  video,
  channel,
}: {
  video: Video;
  channel?: Channel;
}) {
  return video.thumb_path ? (
    <img
      className="video-thumb"
      src={`/media/${video.id}/thumbnail`}
      alt={`Miniature : ${video.title}`}
      loading="lazy"
    />
  ) : (
    <div
      className="video-thumb abstract-thumb"
      style={
        { "--channel": channel?.accent || "#00d8ef" } as React.CSSProperties
      }
    >
      <span>{channel?.initials || "DL"}</span>
      <Clapperboard size={22} />
      <small>{channel?.niche || "PRODUCTION"}</small>
    </div>
  );
}
export function VideoRow({
  video,
  channel,
  onClick,
}: {
  video: Video;
  channel?: Channel;
  onClick: () => void;
}) {
  return (
    <button className="video-row" onClick={onClick}>
      <VideoThumb video={video} channel={channel} />
      <div className="video-row-info">
        <span className="eyebrow" style={{ color: channel?.accent }}>
          {channel?.name}
        </span>
        <strong>{video.title}</strong>
        <small>
          {Number(video.minutes).toFixed(0)} min <span>·</span>{" "}
          {video.post_at
            ? dateLabel(video.post_at, {
                day: "numeric",
                month: "short",
                hour: "2-digit",
                minute: "2-digit",
              })
            : "Créneau libre"}
        </small>
      </div>
      <Tag tone={video.status}>{labels[video.status]}</Tag>
      <ArrowUpRight size={18} />
    </button>
  );
}
export function StatusIcon({ status }: { status: string }) {
  return status === "published" || status === "ready" ? (
    <CheckCircle2 size={15} />
  ) : status === "blocked" ? (
    <AlertTriangle size={15} />
  ) : status === "creating" ? (
    <Radio size={15} />
  ) : (
    <Clock3 size={15} />
  );
}
export function Skyline() {
  return (
    <svg
      className="skyline"
      viewBox="0 0 850 320"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient
          id="city-fade"
          x1="400"
          y1="60"
          x2="400"
          y2="340"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#18403f" />
          <stop offset="1" stopColor="#081314" />
        </linearGradient>
        <linearGradient id="road-fade" x1="450" y1="200" x2="350" y2="310">
          <stop stopColor="#08efe0" stopOpacity=".55" />
          <stop offset="1" stopColor="#08efe0" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d="M0 300V211h40v-30h45v30h28V98h43v42h20V75h53v70h32V120h35v32h30V77h40V22h20v55h20v93h30v-28h34V97h38v-47h9v47h21v95h40V125h44v33h28v-84h42v74h30v60h22V112h59v29h32v77h38v-45h27V300Z"
        fill="url(#city-fade)"
      />
      <path
        d="M366 77V22h20v55m-61 75V78h41m102 65V97h38v-47m96 108v-33h44m-47-37h32m118 121v-96h59"
        stroke="#0be9d5"
        strokeOpacity=".28"
      />
      <path
        d="M390 310l120-95h60l-64 95m-110 0l95-80"
        stroke="url(#road-fade)"
        strokeWidth="2"
      />
      <g stroke="#55b8ae" strokeOpacity=".21" strokeWidth="3">
        <path d="M126 163h20m-20 13h20m-20 13h20m40-51h21m-21 15h21m-21 15h21m123-68h14m-14 14h14m-14 14h14m42-52h12m-12 13h12m-12 13h12m114 27h20m-20 12h20m-20 12h20m46 36h24m-24 13h24m-24 13h24m71-64h21m-21 13h21m-21 13h21m62 6h24m-24 13h24m-24 13h24" />
      </g>
      <path
        d="M304 208h88v29h-88z"
        fill="#c8ef3e"
        fillOpacity=".05"
        stroke="#c8ef3e"
        strokeOpacity=".3"
      />
      <text
        x="348"
        y="227"
        fontSize="10"
        fill="#c8ef3e"
        fillOpacity=".6"
        textAnchor="middle"
        fontFamily="monospace"
      >
        AFTERLIFE
      </text>
      <circle cx="592" cy="62" r="36" stroke="#c8ef3e" strokeOpacity=".10" />
      <path
        d="M22 265h95m485-28h125M450 30h63"
        stroke="#09bba9"
        strokeOpacity=".2"
      />
      <path d="M670 169h46v18h-46z" fill="#df60a2" fillOpacity=".18" />
      <text
        x="693"
        y="181"
        fontSize="7"
        fill="#eb79b7"
        fillOpacity=".6"
        textAnchor="middle"
      >
        NIGHT CITY
      </text>
    </svg>
  );
}
