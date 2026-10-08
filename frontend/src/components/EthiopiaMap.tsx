import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";
import { useAppStore } from "@/store/appStore";
import type { OutbreakReport } from "@/types";
import { TierBadge, formatDate, toTier, type TierKey } from "@/components/editorial";
import { cn } from "@/lib/utils";
import regionPaths from "./ethiopia-region-paths.json";

/*
 * Interim map. Place names are matched to a small hand-made gazetteer; anything
 * that cannot be matched is listed as "not placed" instead of being drawn at a
 * guessed position. The P-code map with current boundaries replaces this in M5.
 */

interface Place {
  region: string;
  cx: number;
  cy: number;
}

// Longest names first so "Arba Minch" wins over shorter tokens.
const GAZETTEER: Array<[string, Place]> = (
  [
    ["Addis Ababa", { region: "Addis Ababa", cx: 250, cy: 323 }],
    ["Mercato", { region: "Addis Ababa", cx: 246, cy: 320 }],
    ["Bole", { region: "Addis Ababa", cx: 256, cy: 327 }],
    ["Bahir Dar", { region: "Amhara", cx: 200, cy: 150 }],
    ["Lake Tana", { region: "Amhara", cx: 198, cy: 140 }],
    ["Gondar", { region: "Amhara", cx: 220, cy: 120 }],
    ["Dessie", { region: "Amhara", cx: 290, cy: 190 }],
    ["Weldiya", { region: "Amhara", cx: 295, cy: 170 }],
    ["Mekelle", { region: "Tigray", cx: 280, cy: 60 }],
    ["Adigrat", { region: "Tigray", cx: 290, cy: 40 }],
    ["Hawassa", { region: "SNNPR", cx: 240, cy: 370 }],
    ["Arba Minch", { region: "SNNPR", cx: 200, cy: 410 }],
    ["Hosaena", { region: "SNNPR", cx: 220, cy: 360 }],
    ["Wolkite", { region: "SNNPR", cx: 200, cy: 340 }],
    ["Konso", { region: "SNNPR", cx: 215, cy: 440 }],
    ["Jinka", { region: "SNNPR", cx: 165, cy: 430 }],
    ["Turmi", { region: "SNNPR", cx: 160, cy: 465 }],
    ["South Omo", { region: "SNNPR", cx: 160, cy: 450 }],
    ["Jimma", { region: "Oromia", cx: 160, cy: 320 }],
    ["Adama", { region: "Oromia", cx: 280, cy: 340 }],
    ["Zway", { region: "Oromia", cx: 260, cy: 360 }],
    ["Bale", { region: "Oromia", cx: 340, cy: 420 }],
    ["Nekemte", { region: "Oromia", cx: 140, cy: 260 }],
    ["Moyale", { region: "Oromia", cx: 380, cy: 480 }],
    ["Haramaya", { region: "Oromia", cx: 418, cy: 262 }],
    ["Jijiga", { region: "Somali", cx: 460, cy: 250 }],
    ["Gode", { region: "Somali", cx: 550, cy: 380 }],
    ["Dire Dawa", { region: "Dire Dawa", cx: 422, cy: 245 }],
    ["Harar", { region: "Harari People", cx: 428, cy: 258 }],
    ["Semera", { region: "Afar", cx: 370, cy: 160 }],
    ["Assosa", { region: "Benshangul-Gumaz", cx: 100, cy: 200 }],
    ["Gambela", { region: "Gambela Peoples", cx: 58, cy: 327 }],
  ] as Array<[string, Place]>
).sort((a, b) => b[0].length - a[0].length);

export function placeLocation(location?: string | null): (Place & { name: string }) | null {
  if (!location) return null;
  const l = location.toLowerCase();
  for (const [name, place] of GAZETTEER) {
    if (l.includes(name.toLowerCase())) return { ...place, name };
  }
  return null;
}

const RANK: Record<TierKey, number> = { RED: 4, ORANGE: 3, YELLOW: 2, CLEAR: 1, GAP: 0, UNKNOWN: 0 };
const FILL: Partial<Record<TierKey, string>> = {
  RED: "hsl(var(--tier-red))",
  ORANGE: "hsl(var(--tier-orange))",
  YELLOW: "hsl(var(--tier-yellow))",
  CLEAR: "hsl(var(--tier-clear))",
};

interface Group {
  key: string;
  label: string;
  reports: OutbreakReport[];
  cases: number;
  top: TierKey;
  topLevel: string;
}

function group(reports: OutbreakReport[], keyOf: (r: OutbreakReport) => string | null): Record<string, Group> {
  const out: Record<string, Group> = {};
  for (const r of reports) {
    const key = keyOf(r);
    if (!key) continue;
    const level = r.risk_analysis?.risk_level || "UNKNOWN";
    const g = (out[key] ??= { key, label: key, reports: [], cases: 0, top: "UNKNOWN", topLevel: "UNKNOWN" });
    g.reports.push(r);
    g.cases += r.extracted_data?.cases || 0;
    if (RANK[toTier(level)] > RANK[g.top]) {
      g.top = toTier(level);
      g.topLevel = level;
    }
  }
  return out;
}

export default function EthiopiaMap({ reports: given }: { reports?: OutbreakReport[] }) {
  const stored = useAppStore((s) => s.reports);
  const reports = given ?? stored;
  const [hover, setHover] = useState<string | null>(null);
  const [selected, setSelected] = useState<Group | null>(null);

  const { regions, pins, unplaced } = useMemo(() => {
    const placed = reports.map((r) => ({ r, p: placeLocation(r.extracted_data?.location) }));
    const regions = group(
      placed.filter((x) => x.p).map((x) => x.r),
      (r) => placeLocation(r.extracted_data?.location)?.region ?? null,
    );
    const pinGroups = group(
      placed.filter((x) => x.p).map((x) => x.r),
      (r) => placeLocation(r.extracted_data?.location)?.name ?? null,
    );
    const pins = Object.values(pinGroups).map((g) => ({ ...g, place: placeLocation(g.key)! }));
    const unplaced = placed.filter((x) => !x.p).map((x) => x.r);
    return { regions, pins, unplaced };
  }, [reports]);

  const hovered = hover ? regions[hover] ?? pins.find((p) => p.key === hover) : null;

  return (
    <div className="grid lg:grid-cols-[1fr_16rem] gap-6">
      <div className="relative">
        <svg viewBox="90 20 720 556" className="w-full h-auto" role="img" aria-label="Map of Ethiopia's regions shaded by the highest risk level reported">
          <g transform="translate(100, 30)">
            {Object.entries(regionPaths).map(([name, d]) => {
              const g = regions[name];
              const fill = g ? FILL[g.top] : undefined;
              return (
                <path
                  key={name}
                  d={d as string}
                  fill={fill ?? "hsl(var(--card))"}
                  fillOpacity={fill ? 0.8 : 1}
                  stroke="hsl(var(--foreground))"
                  strokeOpacity={hover === name ? 1 : 0.55}
                  strokeWidth={hover === name ? 1.5 : 0.75}
                  className={cn(g && "cursor-pointer")}
                  onMouseEnter={() => setHover(name)}
                  onMouseLeave={() => setHover(null)}
                  onClick={() => g && setSelected(g)}
                >
                  <title>{g ? `${name}: ${g.reports.length} reports, ${g.cases} cases` : `${name}: no reports`}</title>
                </path>
              );
            })}
            {pins.map((p) => (
              <g
                key={p.key}
                className="cursor-pointer"
                onMouseEnter={() => setHover(p.key)}
                onMouseLeave={() => setHover(null)}
                onClick={() => setSelected(p)}
              >
                <circle cx={p.place.cx} cy={p.place.cy} r={10} fill="transparent" />
                <rect
                  x={p.place.cx - 4}
                  y={p.place.cy - 4}
                  width={8}
                  height={8}
                  fill={FILL[p.top] ?? "hsl(var(--background))"}
                  stroke="hsl(var(--foreground))"
                  strokeWidth={1.25}
                />
                <title>{`${p.key}: ${p.reports.length} reports, ${p.cases} cases`}</title>
              </g>
            ))}
          </g>
        </svg>

        <div className="text-[0.8125rem] min-h-[2.5rem] mt-2" aria-live="polite">
          {hovered ? (
            <div>
              <p className="font-serif text-base">{hovered.key}</p>
              <p className="num text-xs text-muted-foreground">
                {hovered.reports.length} reports · {hovered.cases} cases
              </p>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">Hover a region or marker; click for records.</p>
          )}
        </div>
      </div>

      <aside className="text-sm">
        <p className="label-caps mb-2">Key · highest level reported</p>
        <ul className="space-y-1.5 mb-5">
          {["HIGH", "MEDIUM", "LOW"].map((l) => (
            <li key={l}>
              <TierBadge level={l} />
            </li>
          ))}
          <li className="flex items-center gap-1.5 text-[0.6875rem] uppercase tracking-[0.08em]">
            <span className="h-2.5 w-2.5 border border-foreground bg-card" aria-hidden /> No reports
          </li>
        </ul>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Levels are assigned by the current language-model pipeline and are not verified outbreak tiers. Boundaries
          predate the 2020–2023 regional changes.
        </p>

        {unplaced.length > 0 && (
          <div className="mt-5">
            <p className="label-caps mb-2">Not placed on the map · {unplaced.length}</p>
            <ul className="space-y-1 max-h-40 overflow-y-auto">
              {unplaced.map((r) => (
                <li key={r.session_id} className="text-xs">
                  <Link to={`/vault/details/${r.session_id}`} className="underline underline-offset-2">
                    {r.extracted_data?.location || "Unknown location"}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </aside>

      {selected && (
        <div className="lg:col-span-2 border-t border-foreground pt-3">
          <div className="flex items-baseline justify-between mb-3">
            <h3 className="text-lg font-medium">
              {selected.key} <span className="num text-sm text-muted-foreground">· {selected.reports.length} reports · {selected.cases} cases</span>
            </h3>
            <button onClick={() => setSelected(null)} className="p-1 text-muted-foreground hover:text-foreground" aria-label="Close">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Location</th>
                  <th>Condition</th>
                  <th className="text-right">Cases</th>
                  <th>Level</th>
                  <th>Received</th>
                </tr>
              </thead>
              <tbody>
                {selected.reports.map((r) => (
                  <tr key={r.session_id}>
                    <td>
                      <Link to={`/vault/details/${r.session_id}`} className="underline underline-offset-2">
                        {r.extracted_data?.location}
                      </Link>
                    </td>
                    <td>{r.risk_analysis?.possible_disease || "Unidentified"}</td>
                    <td className="num text-right">{r.extracted_data?.cases}</td>
                    <td>
                      <TierBadge level={r.risk_analysis?.risk_level} />
                    </td>
                    <td className="num text-xs">{formatDate(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
