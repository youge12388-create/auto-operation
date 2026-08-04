import type { ReactNode } from "react";

export type IconName =
  | "alert"
  | "article"
  | "bell"
  | "chart"
  | "check"
  | "chevron"
  | "clock"
  | "close"
  | "copy"
  | "database"
  | "edit"
  | "external"
  | "eye"
  | "folder"
  | "help"
  | "home"
  | "image"
  | "link"
  | "lock"
  | "mail"
  | "magic"
  | "menu"
  | "more"
  | "play"
  | "refresh"
  | "review"
  | "robot"
  | "search"
  | "send"
  | "settings"
  | "shield"
  | "spark"
  | "topic"
  | "upload"
  | "user";

export function Icon({ name, size = 18, className = "" }: { name: IconName; size?: number; className?: string }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  const shapes: Record<IconName, ReactNode> = {
    alert: <><path {...common} d="M12 4 3.8 19h16.4z" /><path {...common} d="M12 9v4M12 16h.01" /></>,
    article: <><path {...common} d="M6 3.5h8l4 4V20H6zM14 3.5v4h4M9 12h6M9 16h6" /></>,
    bell: <><path {...common} d="M6 16.5h12l-1.4-2.1V10a4.6 4.6 0 0 0-9.2 0v4.4zM10 19h4" /></>,
    chart: <><path {...common} d="M4 19h16M6 16V9M11 16V5M16 16v-6" /></>,
    check: <><circle {...common} cx="12" cy="12" r="8" /><path {...common} d="m8.5 12 2.2 2.2 4.8-5" /></>,
    chevron: <path {...common} d="m8 10 4 4 4-4" />,
    clock: <><circle {...common} cx="12" cy="12" r="8" /><path {...common} d="M12 7v5l3 2" /></>,
    close: <path {...common} d="m7 7 10 10M17 7 7 17" />,
    copy: <><rect {...common} x="8" y="8" width="10" height="11" rx="2" /><path {...common} d="M6 16H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></>,
    database: <><ellipse {...common} cx="12" cy="6" rx="7" ry="3" /><path {...common} d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" /></>,
    edit: <><path {...common} d="m5 16.5-.8 3.3 3.3-.8L18 8.5 15.5 6zM14.5 7l2.5 2.5" /></>,
    external: <><path {...common} d="M13 5h6v6M19 5l-8 8" /><path {...common} d="M17 14v5H5V7h5" /></>,
    eye: <><path {...common} d="M3.5 12s3-5 8.5-5 8.5 5 8.5 5-3 5-8.5 5-8.5-5-8.5-5z" /><circle {...common} cx="12" cy="12" r="2" /></>,
    folder: <path {...common} d="M3.5 7h6l2-2h9v14h-17z" />,
    help: <><circle {...common} cx="12" cy="12" r="8" /><path {...common} d="M9.8 9.3a2.4 2.4 0 1 1 3.8 2c-1.1.7-1.6 1.2-1.6 2.2M12 16.5h.01" /></>,
    home: <><path {...common} d="m4 10 8-6 8 6v10H4z" /><path {...common} d="M9 20v-6h6v6" /></>,
    image: <><rect {...common} x="3.5" y="4" width="17" height="16" rx="2" /><circle {...common} cx="9" cy="9" r="1.5" /><path {...common} d="m5.5 17 4.5-4 3 2 2.5-3 3 5" /></>,
    link: <><path {...common} d="M10 13a4 4 0 0 0 5.7 0l2-2a4 4 0 0 0-5.7-5.7l-1.2 1.2M14 11a4 4 0 0 0-5.7 0l-2 2A4 4 0 0 0 12 18.7l1.2-1.2" /></>,
    lock: <><rect {...common} x="5" y="10" width="14" height="10" rx="2" /><path {...common} d="M8 10V7a4 4 0 0 1 8 0v3M12 14v2" /></>,
    mail: <><rect {...common} x="3.5" y="5" width="17" height="14" rx="2" /><path {...common} d="m4 7 8 6 8-6" /></>,
    magic: <><path {...common} d="m4 20 11-11M13 5l1-2 1 2 2 1-2 1-1 2-1-2-2-1zM18 13l.8-1.6.8 1.6 1.6.8-1.6.8-.8 1.6-.8-1.6-1.6-.8z" /><path {...common} d="m7 17 3 3" /></>,
    menu: <path {...common} d="M4 7h16M4 12h16M4 17h16" />,
    more: <><circle cx="6" cy="12" r="1" fill="currentColor" /><circle cx="12" cy="12" r="1" fill="currentColor" /><circle cx="18" cy="12" r="1" fill="currentColor" /></>,
    play: <><circle {...common} cx="12" cy="12" r="8" /><path {...common} d="m10 8 5 4-5 4z" /></>,
    refresh: <><path {...common} d="M19 8a7 7 0 1 0 1 6M19 4v4h-4" /></>,
    review: <><path {...common} d="M6 4h12v16H6zM9 9l1.5 1.5L14 7M9 15h6" /></>,
    robot: <><rect {...common} x="5" y="7" width="14" height="11" rx="3" /><path {...common} d="M12 4v3M8.5 12h.01M15.5 12h.01M9 15h6" /></>,
    search: <><circle {...common} cx="11" cy="11" r="6" /><path {...common} d="m16 16 4 4" /></>,
    send: <><path {...common} d="m4 5 16 7-16 7 3-7zM7 12h13" /></>,
    settings: <><path {...common} d="M12 4.5l1.1 1.8 2.1.4.8 2 1.8 1.2-.7 2 1 1.9-1.6 1.4-.2 2.2-2.1.5-1.1 1.8-2.1-.5-1.8.9-1.5-1.6-2.1-.4-.2-2.2-1.5-1.4 1-1.9-.7-2 1.8-1.2.8-2 2.1-.4z" /><circle {...common} cx="12" cy="12" r="2.5" /></>,
    shield: <><path {...common} d="M12 3.5 19 6v5c0 4.4-2.7 7.5-7 9.5C7.7 18.5 5 15.4 5 11V6z" /><path {...common} d="m9 12 2 2 4-5" /></>,
    spark: <><path {...common} d="m12 3 1.4 5.6L19 10l-5.6 1.4L12 17l-1.4-5.6L5 10l5.6-1.4zM18 16l.6 2.4L21 19l-2.4.6L18 22l-.6-2.4L15 19l2.4-.6z" /></>,
    topic: <><rect {...common} x="4" y="4" width="16" height="16" rx="3" /><path {...common} d="M8 8h8M8 12h5M8 16h7" /></>,
    upload: <><path {...common} d="M5 16v3h14v-3M12 4v11M8.5 7.5 12 4l3.5 3.5" /></>,
    user: <><circle {...common} cx="12" cy="8" r="3" /><path {...common} d="M5.5 20a6.5 6.5 0 0 1 13 0" /></>,
  };
  return <svg className={`ui-icon ${className}`} width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">{shapes[name]}</svg>;
}

export function StatusPill({ tone = "neutral", children }: { tone?: "blue" | "green" | "orange" | "purple" | "red" | "neutral"; children: ReactNode }) {
  return <span className={`status-pill status-pill--${tone}`}>{children}</span>;
}

export function EmptyState({ icon = "folder", title, description }: { icon?: IconName; title: string; description: string }) {
  return (
    <div className="empty-state">
      <span className="empty-state-icon"><Icon name={icon} size={22} /></span>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}
