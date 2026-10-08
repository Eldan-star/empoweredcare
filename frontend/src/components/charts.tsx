import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipProps,
} from "recharts";
import { TierBadge, toTier, type TierKey } from "@/components/editorial";
import { cn } from "@/lib/utils";

const axisTick = { fontSize: 11, fill: "hsl(var(--muted-foreground))", fontFamily: "IBM Plex Mono" };

function InkTooltip({ active, payload, label, unit }: TooltipProps<number, string> & { unit: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border border-foreground bg-popover px-3 py-2 text-xs">
      <p className="label-caps">{label}</p>
      <p className="num text-sm mt-1">
        {payload[0].value?.toLocaleString()} {unit}
      </p>
    </div>
  );
}

/** Single-series line over time. One series → no legend; the section title names it. */
export function TrendLine({
  data,
  xKey,
  yKey,
  unit,
  height = 200,
}: {
  data: Record<string, string | number>[];
  xKey: string;
  yKey: string;
  unit: string;
  height?: number;
}) {
  return (
    <div style={{ height }} role="img" aria-label={`${yKey} by ${xKey}, ${data.length} points`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
          <CartesianGrid vertical={false} stroke="hsl(var(--border))" strokeDasharray="0" />
          <XAxis dataKey={xKey} tick={axisTick} tickLine={false} axisLine={{ stroke: "hsl(var(--foreground))" }} interval="preserveStartEnd" />
          <YAxis tick={axisTick} tickLine={false} axisLine={false} allowDecimals={false} width={44} />
          <Tooltip content={<InkTooltip unit={unit} />} cursor={{ stroke: "hsl(var(--foreground))", strokeWidth: 1 }} />
          <Line
            type="linear"
            dataKey={yKey}
            stroke="hsl(var(--foreground))"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, stroke: "hsl(var(--background))", strokeWidth: 2, fill: "hsl(var(--foreground))" }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

const TIER_BAR: Record<TierKey, string> = {
  RED: "bg-tier-red",
  ORANGE: "bg-tier-orange",
  YELLOW: "bg-tier-yellow",
  CLEAR: "bg-tier-clear",
  GAP: "hatch-gap",
  UNKNOWN: "bg-muted-foreground/40",
};

/**
 * Horizontal bars of counts per level. Every bar is directly labelled with its
 * level word and count, so colour is never the only cue.
 */
export function LevelBars({
  counts,
  order = ["HIGH", "MEDIUM", "LOW", "UNKNOWN"],
  onSelect,
  selected,
}: {
  counts: Record<string, number>;
  order?: string[];
  onSelect?: (level: string) => void;
  selected?: string;
}) {
  const max = Math.max(1, ...Object.values(counts));
  const rows = order.filter((k) => counts[k] !== undefined);
  if (!rows.length) return <p className="text-sm text-muted-foreground">No records.</p>;
  return (
    <ul className="space-y-2.5">
      {rows.map((level) => {
        const value = counts[level] ?? 0;
        const Comp = onSelect ? "button" : "div";
        return (
          <li key={level}>
            <Comp
              {...(onSelect ? { type: "button", onClick: () => onSelect(level) } : {})}
              className={cn(
                "w-full grid grid-cols-[7rem_1fr_3rem] items-center gap-3 text-left",
                onSelect && "hover:bg-muted/60 -mx-2 px-2 py-1",
                selected === level && "bg-muted",
              )}
              title={`${level}: ${value}`}
            >
              <TierBadge level={level} />
              <span className="h-3 bg-transparent border-l border-foreground">
                <span className={cn("block h-full", TIER_BAR[toTier(level)])} style={{ width: `${(value / max) * 100}%` }} />
              </span>
              <span className="num text-sm text-right">{value}</span>
            </Comp>
          </li>
        );
      })}
    </ul>
  );
}
