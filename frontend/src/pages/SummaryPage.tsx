import { useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { useAppStore } from "@/store/appStore";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { EmptyState, PageHeader, SectionRule, Sparkline, Stat, StatRow, TierBadge, isoWeek, parseDate } from "@/components/editorial";
import { LevelBars } from "@/components/charts";
import type { OutbreakReport } from "@/types";
import { toast } from "sonner";

const RANK: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1, UNKNOWN: 0 };
const weekKey = (d: Date) => {
  const { week, year } = isoWeek(d);
  return year * 100 + week;
};

interface LocationRow {
  location: string;
  count: number;
  cases: number;
  maxRisk: string;
  weekly: number[];
}

export default function SummaryPage() {
  const { reports, setReports } = useAppStore();

  useEffect(() => {
    api.getReports().then(setReports).catch(() => toast.error("Could not load records."));
  }, [setReports]);

  const now = new Date();
  const thisWeek = weekKey(now);
  const lastWeek = weekKey(new Date(now.getTime() - 7 * 86400000));
  // The last eight ISO weeks, oldest first, for sparklines.
  const weeks = Array.from({ length: 8 }, (_, i) => weekKey(new Date(now.getTime() - (7 - i) * 7 * 86400000)));

  const receivedWeek = (r: OutbreakReport) => (r.created_at ? weekKey(parseDate(r.created_at)) : null);
  const inWeek = (w: number) => reports.filter((r) => receivedWeek(r) === w);
  const casesIn = (rs: OutbreakReport[]) => rs.reduce((a, r) => a + (r.extracted_data?.cases || 0), 0);

  const byLocation: LocationRow[] = useMemo(() => {
    const m = new Map<string, LocationRow>();
    for (const r of reports) {
      const loc = r.extracted_data?.location || "Unknown";
      const row = m.get(loc) ?? { location: loc, count: 0, cases: 0, maxRisk: "UNKNOWN", weekly: weeks.map(() => 0) };
      row.count++;
      row.cases += r.extracted_data?.cases || 0;
      const lvl = r.risk_analysis?.risk_level || "UNKNOWN";
      if ((RANK[lvl] || 0) > (RANK[row.maxRisk] || 0)) row.maxRisk = lvl;
      const w = receivedWeek(r);
      const idx = w === null ? -1 : weeks.indexOf(w);
      if (idx >= 0) row.weekly[idx] += r.extracted_data?.cases || 0;
      m.set(loc, row);
    }
    return [...m.values()].sort((a, b) => b.cases - a.cases);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reports]);

  const conditions = Object.entries(
    reports.reduce<Record<string, number>>((acc, r) => {
      const d = r.risk_analysis?.possible_disease || "Unidentified";
      acc[d] = (acc[d] || 0) + 1;
      return acc;
    }, {}),
  )
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);
  const maxCondition = Math.max(1, ...conditions.map(([, v]) => v));

  const levelCounts = reports.reduce<Record<string, number>>((acc, r) => {
    const l = r.risk_analysis?.risk_level || "UNKNOWN";
    acc[l] = (acc[l] || 0) + 1;
    return acc;
  }, {});

  const thisWeekRecords = inWeek(thisWeek);
  const lastWeekRecords = inWeek(lastWeek);
  const { week, year } = isoWeek(now);

  const exportCSV = () => {
    const rows = [["Location", "Records", "Cases", "Highest level"], ...byLocation.map((l) => [l.location, l.count, l.cases, l.maxRisk])];
    const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = `summary-week-${year}-${week}.csv`;
    a.click();
  };

  const delta = thisWeekRecords.length - lastWeekRecords.length;

  return (
    <div>
      <PageHeader
        kicker={`Weekly summary · week ${week}, ${year}`}
        title="Where the reports are coming from"
        lede={`This week: ${thisWeekRecords.length} records and ${casesIn(thisWeekRecords)} cases, ${
          delta === 0 ? "the same number of records as" : `${Math.abs(delta)} ${delta > 0 ? "more" : "fewer"} records than`
        } last week.`}
        actions={
          <Button size="sm" variant="outline" onClick={exportCSV} disabled={!byLocation.length}>
            Export CSV
          </Button>
        }
      />

      <StatRow className="mb-10">
        <Stat label="Records this week" value={thisWeekRecords.length} note={`${lastWeekRecords.length} last week`} />
        <Stat label="Cases this week" value={casesIn(thisWeekRecords)} note={`${casesIn(lastWeekRecords)} last week`} />
        <Stat label="Locations, all time" value={byLocation.length} />
        <Stat label="Awaiting review" value={reports.filter((r) => (r.status || "pending") === "pending").length} />
      </StatRow>

      {reports.length === 0 ? (
        <EmptyState title="No records yet" body="The summary fills in as reports are processed." />
      ) : (
        <div className="grid lg:grid-cols-12 gap-x-10">
          <SectionRule title="By location" meta="Sorted by cases · last 8 weeks" className="lg:col-span-8">
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Location</th>
                    <th className="text-right">Records</th>
                    <th className="text-right">Cases</th>
                    <th>Cases by week</th>
                    <th>Highest level</th>
                  </tr>
                </thead>
                <tbody>
                  {byLocation.map((l) => (
                    <tr key={l.location}>
                      <td className="font-medium">{l.location}</td>
                      <td className="num text-right">{l.count}</td>
                      <td className="num text-right">{l.cases}</td>
                      <td>
                        <Sparkline values={l.weekly} label={`${l.location}: cases over the last 8 weeks`} />
                      </td>
                      <td>
                        <TierBadge level={l.maxRisk} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionRule>

          <div className="lg:col-span-4">
            <SectionRule title="Most frequent conditions" meta="Records">
              <ul className="space-y-2.5">
                {conditions.map(([name, n]) => (
                  <li key={name} title={`${name}: ${n}`}>
                    <div className="flex justify-between gap-3 text-sm">
                      <span className="truncate">{name}</span>
                      <span className="num">{n}</span>
                    </div>
                    <div className="h-1 mt-1 border-l border-foreground">
                      <div className="h-full bg-foreground/60" style={{ width: `${(n / maxCondition) * 100}%` }} />
                    </div>
                  </li>
                ))}
              </ul>
            </SectionRule>

            <SectionRule title="Records by level">
              <LevelBars counts={levelCounts} />
              <p className="text-xs text-muted-foreground mt-4">
                Language-model ratings, not verified tiers. <Link to="/alerts" className="underline underline-offset-2">Review queue</Link>
              </p>
            </SectionRule>
          </div>
        </div>
      )}
    </div>
  );
}
