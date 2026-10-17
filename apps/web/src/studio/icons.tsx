/** Inline stroke icons for the studio shell; decorative unless a label is given. */
import type { ReactNode } from "react";

const paths: Record<string, ReactNode> = {
  home: <path d="M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3z" />,
  globe: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></>,
  list: <path d="M4 6h16M4 12h10M4 18h13" />,
  pitch: <><rect x="3" y="5" width="18" height="14" rx="1.5" /><path d="M12 5v14" /><circle cx="12" cy="12" r="2.5" /></>,
  shield: <><path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z" /><path d="m9 12 2 2 4-4" /></>,
  monitor: <><rect x="3" y="4" width="18" height="12" rx="1.5" /><path d="M8 20h8M12 16v4" /></>,
  phone: <><rect x="7" y="2.5" width="10" height="19" rx="2.2" /><path d="M11 18.5h2" /></>,
  pulse: <path d="M3 12h4l3-8 4 16 3-8h4" />,
  pen: <path d="M4 20h4L19 9l-4-4L4 16z" />,
  search: <><circle cx="11" cy="11" r="6" /><path d="m20 20-4-4" /></>,
  sparkle: <path d="M12 3l1.8 4.6L18 9.4l-4.2 1.8L12 16l-1.8-4.8L6 9.4l4.2-1.8z" />,
  inbox: <path d="M4 4h16v12h-5l-1 3h-4l-1-3H4z" />,
  ball: <><circle cx="12" cy="12" r="9" /><path d="m12 7 4 3-1.5 4.5h-5L8 10z" /></>,
  flag: <path d="M5 21V4h11l-2 4 2 4H5" />,
  swap: <path d="M7 7h12l-3-3M17 17H5l3 3" />,
  card: <rect x="7" y="4" width="10" height="16" rx="1.5" />,
  lock: <><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
  wave: <path d="M3 12v0M6 9v6M9 6v12M12 9v6M15 4v16M18 8v8M21 11v2" />,
  grid: <><rect x="4" y="4" width="7" height="7" rx="1.5" /><rect x="13" y="4" width="7" height="7" rx="1.5" /><rect x="4" y="13" width="7" height="7" rx="1.5" /><rect x="13" y="13" width="7" height="7" rx="1.5" /></>,
  pause: <><path d="M9 5v14M15 5v14" /></>,
  play: <path d="M7 4.5v15l12-7.5z" />,
  prev: <path d="M18 6v12l-9-6zM6 6v12" />,
  next: <path d="M6 6v12l9-6zM18 6v12" />,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8v.5" /></>,
};

export type IconName = keyof typeof paths;

/** Render an icon; pass `label` only when the icon carries meaning on its own. */
export function Icon({ name, size = 18, label, className }: { name: IconName; size?: number; label?: string; className?: string }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      {paths[name]}
    </svg>
  );
}
