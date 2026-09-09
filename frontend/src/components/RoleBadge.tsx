/** Badge ruolo stile Fantacalcio/FIFA — cerchio colorato con lettera. */

const ROLE_CONFIG: Record<string, { letter: string; bg: string; text: string }> = {
  "Portiere":       { letter: "P", bg: "#f9ab0f", text: "#ffffff" },
  "Difensore":      { letter: "D", bg: "#66c723", text: "#ffffff" },
  "Centrocampista": { letter: "C", bg: "#136dfa", text: "#ffffff" },
  "Attaccante":     { letter: "A", bg: "#ee1d41", text: "#ffffff" },
};

type BadgeSize = "xs" | "sm" | "md" | "lg";

const SIZE_CLS: Record<BadgeSize, string> = {
  xs: "w-5 h-5 text-[9px]",
  sm: "w-7 h-7 text-xs",
  md: "w-9 h-9 text-sm",
  lg: "w-11 h-11 text-base",
};

interface Props {
  position: string | null | undefined;
  size?: BadgeSize;
  className?: string;
}

export function RoleBadge({ position, size = "md", className = "" }: Props) {
  if (!position) return null;
  const cfg = ROLE_CONFIG[position];
  if (!cfg) return <span className={`text-xs text-grass ${className}`}>{position}</span>;

  return (
    <span
      className={`inline-flex items-center justify-center rounded-full font-display font-bold flex-shrink-0 select-none ${SIZE_CLS[size]} ${className}`}
      style={{ background: cfg.bg, color: cfg.text }}
      title={position}
    >
      {cfg.letter}
    </span>
  );
}
