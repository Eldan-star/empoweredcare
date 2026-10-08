import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import EthiopiaMap from "@/components/EthiopiaMap";
import { useAppStore } from "@/store/appStore";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  EmptyState,
  LoadingLine,
  PageHeader,
  SectionRule,
  Stat,
  StatRow,
  TierBadge,
  formatDate,
  parseDate,
} from "@/components/editorial";
import { LevelBars, TrendLine } from "@/components/charts";
import type { OutbreakReport } from "@/types";

type RiskFilter = "all" | "HIGH" | "MEDIUM" | "LOW";

const receivedAt = (r: OutbreakReport) => r.created_at || r.timestamp || null;

export default function Dashboard() {
  const navigate = useNavigate();
  const { reports, setReports } = useAppStore();
  const [loading, setLoading] = useState(reports.length === 0);
  const [error, setError] = useState<string | null>(null);
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("all");
  const [diseaseFilter, setDiseaseFilter] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [last7, setLast7] = useState(false);

  const load = () => {
    setError(null);
    api
      .getReports()
      .then(setReports)
      .catch(() => setError("Could not load records from the backend."))
      .finally(() => setLoading(false));
  };
  useEffect(load, [setReports]);

  const filtered = useMemo(
    () =>
      reports.filter((r) => {
        if (last7) {
          const t = receivedAt(r);
          if (!t || Date.now() - parseDate(t).getTime() > 7 * 86400000) return false;
        }
        if (riskFilter !== "all" && r.risk_analysis?.risk_level !== riskFilter) return false;
        if (diseaseFilter !== "all" && (r.risk_analysis?.possible_disease || "Unidentified") !== diseaseFilter) return false;
        if (searchTerm) {
          const s = searchTerm.toLowerCase();
          if (
            !(r.extracted_data?.location || "").toLowerCase().includes(s) &&
            !(r.risk_analysis?.possible_disease || "").toLowerCase().includes(s)
          )
            return false;
        }
        return true;
      }),
    [reports, last7, riskFilter, diseaseFilter, searchTerm],
  );

  const totalCases = filtered.reduce((a, r) => a + (r.extracted_data?.cases || 0), 0);
  const high = filtered.filter((r) => r.risk_analysis?.risk_level === "HIGH").length;
  const pending = filtered.filter((r) => (r.status || "pending") === "pending").length;
  const diseases = Array.from(new Set(reports.map((r) => r.risk_analysis?.possible_disease || "Unidentified"))).sort();

  const levelCounts = filtered.reduce<Record<string, number>>((acc, r) => {
    const l = r.risk_analysis?.risk_level || "UNKNOWN";
    acc[l] = (acc[l] || 0) + 1;
    return acc;
  }, {});

  // Cases by day received, chronological.
  const timeline = useMemo(() => {
    const byDay = new Map<string, number>();
    for (const r of filtered) {
      const t = receivedAt(r);
      if (!t) continue;
      const day = parseDate(t).toISOString().slice(0, 10);
      byDay.set(day, (byDay.get(day) || 0) + (r.extracted_data?.cases || 0));
    }
    return [...byDay.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([day, cases]) => ({ day: formatDate(day).replace(/ \d{4}$/, ""), cases }));
  }, [filtered]);

  const exportCSV = () => {
    if (!filtered.length) return;
    const header = ["Location", "Cases", "Report date", "Condition", "Level", "Status", "Received"];
    const rows = filtered.map((r) => [
      r.extracted_data?.location,
      r.extracted_data?.cases,
      r.extracted_data?.date || "",
      r.risk_analysis?.possible_disease,
      r.risk_analysis?.risk_level,
      r.status || "pending",
      receivedAt(r) || "",
    ]);
    const csv = [header, ...rows].map((row) => row.map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = `empowered-care-records-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  const filtersActive = riskFilter !== "all" || diseaseFilter !== "all" || searchTerm !== "" || last7;
  const clear = () => {
    setRiskFilter("all");
    setDiseaseFilter("all");
    setSearchTerm("");
    setLast7(false);
  };

  return (
    <div>
      <PageHeader
        kicker="Overview"
        title="The week in brief"
        lede={
          loading
            ? "Loading records…"
            : `${filtered.length} records across ${new Set(filtered.map((r) => r.extracted_data?.location)).size} locations; ${pending} awaiting review.`
        }
        actions={
          <>
            <Button variant="outline" size="sm" onClick={load}>
              Refresh
            </Button>
            <Button size="sm" onClick={exportCSV} disabled={!filtered.length}>
              Export CSV
            </Button>
          </>
        }
      />

      {error && (
        <p className="mb-6 border-l-2 border-tier-red pl-3 text-sm" role="alert">
          {error}
        </p>
      )}

      <StatRow className="mb-10">
        <Stat label="Records" value={filtered.length} note={last7 ? "Received in the last 7 days" : "All time"} />
        <Stat label="Cases reported" value={totalCases.toLocaleString()} note="Sum of extracted case counts" />
        <Stat label="Rated high" value={high} tone={high > 0 ? "red" : "default"} note="Language-model rating, unverified" />
        <Stat label="Awaiting review" value={pending} note={<Link to="/alerts" className="underline underline-offset-2">Open the review queue</Link>} />
      </StatRow>

      {/* Filters: one row above everything they affect */}
      <div className="flex flex-wrap items-center gap-2 mb-10">
        <Input
          type="search"
          placeholder="Search location or condition"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="h-9 w-56"
          aria-label="Search records"
        />
        <Select value={riskFilter} onValueChange={(v) => setRiskFilter(v as RiskFilter)}>
          <SelectTrigger className="h-9 w-36" aria-label="Level">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All levels</SelectItem>
            <SelectItem value="HIGH">High</SelectItem>
            <SelectItem value="MEDIUM">Medium</SelectItem>
            <SelectItem value="LOW">Low</SelectItem>
          </SelectContent>
        </Select>
        <Select value={diseaseFilter} onValueChange={setDiseaseFilter}>
          <SelectTrigger className="h-9 w-56" aria-label="Condition">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All conditions</SelectItem>
            {diseases.map((d) => (
              <SelectItem key={d} value={d}>
                {d}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant={last7 ? "default" : "outline"} size="sm" className="h-9" onClick={() => setLast7((v) => !v)} aria-pressed={last7}>
          Last 7 days
        </Button>
        {filtersActive && (
          <Button variant="ghost" size="sm" className="h-9" onClick={clear}>
            Clear filters
          </Button>
        )}
        <span className="ml-auto num text-xs text-muted-foreground">
          {filtered.length} of {reports.length}
        </span>
      </div>

      <div className="grid lg:grid-cols-12 gap-x-10">
        <SectionRule title="Where reports come from" meta="Regions shaded by highest level" className="lg:col-span-8">
          {loading ? <LoadingLine /> : <EthiopiaMap reports={filtered} />}
        </SectionRule>

        <div className="lg:col-span-4">
          <SectionRule title="Records by level" meta="Click to filter">
            <LevelBars counts={levelCounts} onSelect={(l) => setRiskFilter(l === riskFilter ? "all" : (l as RiskFilter))} selected={riskFilter} />
            <p className="text-xs text-muted-foreground mt-4">
              Levels come from the current language-model pipeline. Threshold-based tiers replace them in Phase 1.
            </p>
          </SectionRule>
          <SectionRule title="Cases by day received">
            {timeline.length < 2 ? (
              <p className="text-sm text-muted-foreground">Not enough dated records to draw a trend.</p>
            ) : (
              <TrendLine data={timeline} xKey="day" yKey="cases" unit="cases" height={180} />
            )}
          </SectionRule>
        </div>
      </div>

      <SectionRule title="Latest records" meta={`${Math.min(filtered.length, 20)} of ${filtered.length}`}>
        {loading ? (
          <LoadingLine />
        ) : filtered.length === 0 ? (
          <EmptyState
            title={reports.length === 0 ? "No records yet" : "No records match these filters"}
            body={reports.length === 0 ? "Submit a field report to see it here." : undefined}
            action={
              reports.length === 0 ? (
                <Button size="sm" onClick={() => navigate("/process")}>
                  Submit a report
                </Button>
              ) : (
                <Button variant="outline" size="sm" onClick={clear}>
                  Clear filters
                </Button>
              )
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Location</th>
                  <th>Condition</th>
                  <th>Classification</th>
                  <th className="text-right">Cases</th>
                  <th>Level</th>
                  <th>Status</th>
                  <th>Received</th>
                </tr>
              </thead>
              <tbody>
                {filtered.slice(0, 20).map((r) => (
                  <tr key={r.session_id} className="cursor-pointer" onClick={() => navigate(`/vault/details/${r.session_id}`)}>
                    <td className="font-medium">
                      <Link to={`/vault/details/${r.session_id}`} className="hover:underline underline-offset-2" onClick={(e) => e.stopPropagation()}>
                        {r.extracted_data?.location}
                      </Link>
                    </td>
                    <td>{r.risk_analysis?.possible_disease || "Unidentified"}</td>
                    <td className="text-muted-foreground">{r.extracted_data?.classification || "Suspected"}</td>
                    <td className="num text-right">{r.extracted_data?.cases}</td>
                    <td>
                      <TierBadge level={r.risk_analysis?.risk_level} />
                    </td>
                    <td className="label-caps">{r.status === "approved" ? "Approved" : r.status === "rejected" ? "Rejected" : "Pending"}</td>
                    <td className="num text-xs whitespace-nowrap">{formatDate(receivedAt(r))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filtered.length > 20 && (
              <p className="mt-4 text-sm">
                <Link to="/vault" className="underline underline-offset-4">
                  All {filtered.length} records
                </Link>
              </p>
            )}
          </div>
        )}
      </SectionRule>
    </div>
  );
}
