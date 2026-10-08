import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/* Dates                                                               */
/* ------------------------------------------------------------------ */

/** ISO-8601 week number and week-year for a date. */
export function isoWeek(d = new Date()): { week: number; year: number } {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((t.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return { week, year: t.getUTCFullYear() };
}

/** Parse backend timestamps such as "2026-05-01 00:08:44.520070" in every browser. */
export function parseDate(value: string): Date {
  const iso = value.trim().replace(" ", "T").replace(/(\.\d{3})\d+/, "$1");
  return new Date(iso);
}

export function formatDate(value?: string | null, withTime = false): string {
  if (!value) return "—";
  const d = parseDate(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

/* ------------------------------------------------------------------ */
/* Page structure                                                      */
/* ------------------------------------------------------------------ */

interface PageHeaderProps {
  kicker?: string;
  title: string;
  lede?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

/** Serif page title over a strong rule, with an optional kicker and lede. */
export function PageHeader({ kicker, title, lede, actions, className }: PageHeaderProps) {
  return (
    <header className={cn("pb-5 mb-8 border-b border-foreground", className)}>
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="max-w-3xl">
          {kicker && <p className="label-caps mb-2">{kicker}</p>}
          <h1 className="text-[2rem] leading-[1.1] md:text-[2.5rem] font-medium">{title}</h1>
          {lede && <p className="mt-3 text-[0.9375rem] text-muted-foreground leading-relaxed max-w-2xl">{lede}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div>}
      </div>
    </header>
  );
}

interface SectionRuleProps {
  title: string;
  meta?: ReactNode;
  className?: string;
  children?: ReactNode;
}

/** Section heading on a hairline rule; `meta` sits right-aligned in small caps. */
export function SectionRule({ title, meta, className, children }: SectionRuleProps) {
  return (
    <section className={cn("mb-10", className)}>
      <div className="flex items-baseline justify-between gap-4 border-t border-foreground pt-2 mb-4">
        <h2 className="text-xl font-medium">{title}</h2>
        {meta && <div className="label-caps text-right">{meta}</div>}
      </div>
      {children}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Numbers                                                             */
/* ------------------------------------------------------------------ */

interface StatProps {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  tone?: "default" | "red" | "orange";
  className?: string;
}

/** A single headline figure: mono number, small-caps label, plain note. */
export function Stat({ label, value, note, tone = "default", className }: StatProps) {
  return (
    <div className={cn("py-3 pr-4", className)}>
      <p className="label-caps">{label}</p>
      <p
        className={cn(
          "num text-[2rem] leading-none mt-2",
          tone === "red" && "text-tier-red",
          tone === "orange" && "text-[hsl(17_60%_45%)] dark:text-tier-orange",
        )}
      >
        {value}
      </p>
      {note && <p className="text-xs text-muted-foreground mt-2">{note}</p>}
    </div>
  );
}

/** A row of stats separated by vertical hairlines. */
export function StatRow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "grid grid-cols-2 md:grid-cols-4 border-y border-border [&>*]:px-4 [&>*]:border-border",
        "[&>*:nth-child(odd)]:border-r md:[&>*]:border-r md:[&>*:last-child]:border-r-0",
        "[&>*:nth-child(-n+2)]:border-b md:[&>*:nth-child(-n+2)]:border-b-0",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Minimal inline sparkline: one 1.5px ink line, no axes. */
export function Sparkline({
  values,
  width = 96,
  height = 24,
  className,
  label,
}: {
  values: number[];
  width?: number;
  height?: number;
  className?: string;
  label?: string;
}) {
  if (values.length < 2 || values.every((v) => v === 0))
    return (
      <span className="text-muted-foreground text-xs" title="No cases in this period">
        —
      </span>
    );
  const max = Math.max(...values, 1);
  const step = width / (values.length - 1);
  const pts = values.map((v, i) => `${(i * step).toFixed(1)},${(height - 2 - (v / max) * (height - 4)).toFixed(1)}`);
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn("text-foreground", className)}
      role="img"
      aria-label={label ?? `Trend of ${values.length} values, latest ${values[values.length - 1]}`}
    >
      <polyline points={pts.join(" ")} fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinejoin="round" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Tiers                                                               */
/* ------------------------------------------------------------------ */

export type TierKey = "RED" | "ORANGE" | "YELLOW" | "CLEAR" | "GAP" | "UNKNOWN";

/** Map legacy LLM risk levels and new tier names onto one key. */
export function toTier(level?: string | null): TierKey {
  const l = (level || "").toUpperCase();
  if (l === "RED" || l === "HIGH") return "RED";
  if (l === "ORANGE" || l === "MEDIUM") return "ORANGE";
  if (l === "YELLOW") return "YELLOW";
  if (l === "LOW" || l === "CLEAR") return "CLEAR";
  if (l === "GAP") return "GAP";
  return "UNKNOWN";
}

const TIER_STYLE: Record<TierKey, { swatch: string; label: string }> = {
  RED: { swatch: "bg-tier-red", label: "Red" },
  ORANGE: { swatch: "bg-tier-orange", label: "Orange" },
  YELLOW: { swatch: "bg-tier-yellow", label: "Yellow" },
  CLEAR: { swatch: "bg-tier-clear", label: "Low" },
  GAP: { swatch: "hatch-gap border border-tier-gap", label: "Data gap" },
  UNKNOWN: { swatch: "border border-muted-foreground", label: "Unrated" },
};

/** Square swatch + text label. Colour never carries the meaning alone. */
export function TierBadge({
  level,
  className,
  showRaw = true,
}: {
  level?: string | null;
  className?: string;
  /** Show the original level word (e.g. HIGH) instead of the tier name. */
  showRaw?: boolean;
}) {
  const tier = toTier(level);
  const style = TIER_STYLE[tier];
  const text = showRaw && level ? level.toUpperCase() : style.label;
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-[0.6875rem] font-medium uppercase tracking-[0.08em] whitespace-nowrap", className)}>
      <span aria-hidden className={cn("inline-block h-2.5 w-2.5 shrink-0", style.swatch)} />
      {text}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* States                                                              */
/* ------------------------------------------------------------------ */

export function EmptyState({
  title,
  body,
  action,
  className,
}: {
  title: string;
  body?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("border border-dashed border-border px-6 py-12 text-center", className)}>
      <p className="font-serif text-lg">{title}</p>
      {body && <p className="text-sm text-muted-foreground mt-2 max-w-md mx-auto">{body}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function LoadingLine({ label = "Loading" }: { label?: string }) {
  return (
    <div className="py-12 text-center label-caps" role="status" aria-live="polite">
      {label}…
    </div>
  );
}

/** Small "In development" marker for features that are specified but not built. */
export function InDevelopment({ className }: { className?: string }) {
  return (
    <span className={cn("label-caps border border-border px-1.5 py-0.5 text-[0.625rem]", className)}>
      In development
    </span>
  );
}
