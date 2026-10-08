import { Fragment, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAppStore } from "@/store/appStore";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState, PageHeader, Stat, StatRow, TierBadge, formatDate, parseDate } from "@/components/editorial";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

type SortField = "date" | "cases" | "risk";
const RISK_ORDER: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1, UNKNOWN: 0 };

export default function DataVault() {
  const { reports, setReports } = useAppStore();
  const [search, setSearch] = useState("");
  const [filterRisk, setFilterRisk] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>("date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  useEffect(() => {
    api.getReports().then(setReports).catch(() => toast.error("Could not load records."));
  }, [setReports]);

  const q = search.toLowerCase();
  const rows = reports
    .filter((r) => {
      const matchSearch =
        (r.extracted_data?.location || "").toLowerCase().includes(q) ||
        (r.risk_analysis?.possible_disease || "").toLowerCase().includes(q);
      const matchRisk = !filterRisk || r.risk_analysis?.risk_level === filterRisk;
      const matchStatus = !filterStatus || (r.status || "pending") === filterStatus;
      return matchSearch && matchRisk && matchStatus;
    })
    .sort((a, b) => {
      let v = 0;
      if (sortField === "cases") v = (a.extracted_data?.cases || 0) - (b.extracted_data?.cases || 0);
      else if (sortField === "risk") v = RISK_ORDER[a.risk_analysis?.risk_level || "UNKNOWN"] - RISK_ORDER[b.risk_analysis?.risk_level || "UNKNOWN"];
      else v = (a.created_at ? parseDate(a.created_at).getTime() : 0) - (b.created_at ? parseDate(b.created_at).getTime() : 0);
      return sortDir === "desc" ? -v : v;
    });

  const totalCases = rows.reduce((s, r) => s + (r.extracted_data?.cases || 0), 0);
  const pendingCount = rows.filter((r) => (r.status || "pending") === "pending").length;
  const approvedCount = rows.filter((r) => r.status === "approved").length;

  const exportJSON = () => {
    if (!rows.length) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(rows, null, 2)], { type: "application/json" }));
    a.download = `empowered-care-records-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
  };

  const sortBy = (f: SortField) => {
    if (sortField === f) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortField(f);
      setSortDir("desc");
    }
  };
  const SortHead = ({ field, label, className }: { field: SortField; label: string; className?: string }) => (
    <th className={className} aria-sort={sortField === field ? (sortDir === "asc" ? "ascending" : "descending") : "none"}>
      <button onClick={() => sortBy(field)} className="label-caps hover:text-foreground">
        {label} {sortField === field ? (sortDir === "desc" ? "↓" : "↑") : ""}
      </button>
    </th>
  );

  const chip = (active: boolean) => (active ? "default" : "outline") as "default" | "outline";

  return (
    <div>
      <PageHeader
        kicker="Records"
        title="Every processed report"
        lede="The complete archive of extracted reports, their ratings and review status."
        actions={
          <Button size="sm" variant="outline" onClick={exportJSON} disabled={!rows.length}>
            Export JSON
          </Button>
        }
      />

      <StatRow className="mb-8">
        <Stat label="Records shown" value={rows.length} />
        <Stat label="Cases" value={totalCases.toLocaleString()} />
        <Stat label="Pending" value={pendingCount} />
        <Stat label="Approved" value={approvedCount} />
      </StatRow>

      <div className="flex flex-wrap items-center gap-2 mb-6">
        <Input type="search" placeholder="Search location or condition" value={search} onChange={(e) => setSearch(e.target.value)} className="h-9 w-64" aria-label="Search records" />
        <div className="flex gap-1" role="group" aria-label="Level">
          {[null, "HIGH", "MEDIUM", "LOW"].map((v) => (
            <Button key={String(v)} size="sm" variant={chip(filterRisk === v)} onClick={() => setFilterRisk(v)} aria-pressed={filterRisk === v}>
              {v ? v[0] + v.slice(1).toLowerCase() : "All levels"}
            </Button>
          ))}
        </div>
        <div className="flex gap-1" role="group" aria-label="Status">
          {[
            [null, "Any status"],
            ["pending", "Pending"],
            ["approved", "Approved"],
            ["rejected", "Rejected"],
          ].map(([v, label]) => (
            <Button key={String(v)} size="sm" variant={chip(filterStatus === v)} onClick={() => setFilterStatus(v)} aria-pressed={filterStatus === v}>
              {label}
            </Button>
          ))}
        </div>
        <span className="ml-auto num text-xs text-muted-foreground">
          {rows.length} of {reports.length}
        </span>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No records match"
          action={
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setSearch("");
                setFilterRisk(null);
                setFilterStatus(null);
              }}
            >
              Clear filters
            </Button>
          }
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <SortHead field="date" label="Received" />
                <th>Location</th>
                <th>Condition</th>
                <SortHead field="cases" label="Cases" className="text-right" />
                <SortHead field="risk" label="Level" />
                <th>Status</th>
                <th className="text-right">Extraction confidence</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const open = expandedId === r.session_id;
                return (
                  <Fragment key={r.session_id}>
                    <tr className={cn("cursor-pointer", open && "[&>td]:bg-muted")} onClick={() => setExpandedId(open ? null : r.session_id)} aria-expanded={open}>
                      <td className="num text-xs whitespace-nowrap">{formatDate(r.created_at, true)}</td>
                      <td className="font-medium">{r.extracted_data?.location}</td>
                      <td>
                        {r.risk_analysis?.possible_disease || "Unidentified"}
                        {r.extracted_data?.symptoms?.length > 0 && (
                          <span className="block text-xs text-muted-foreground mt-0.5">{r.extracted_data.symptoms.slice(0, 3).join(", ")}</span>
                        )}
                      </td>
                      <td className="num text-right">{r.extracted_data?.cases}</td>
                      <td>
                        <TierBadge level={r.risk_analysis?.risk_level || "UNKNOWN"} />
                      </td>
                      <td className="label-caps">{r.status || "pending"}</td>
                      <td className="num text-right text-xs">{r.validation ? `${Math.round((r.validation.confidence || 0) * 100)}%` : "—"}</td>
                    </tr>
                    {open && (
                      <tr>
                        <td colSpan={7} className="!bg-muted/40">
                          <div className="grid md:grid-cols-3 gap-6 py-3">
                            <div className="md:col-span-2">
                              <p className="label-caps">Model reasoning (unverified)</p>
                              <p className="text-sm text-muted-foreground mt-1 leading-relaxed">{r.risk_analysis?.reason || "None recorded."}</p>
                            </div>
                            <div>
                              <p className="label-caps">Suggested actions</p>
                              <ol className="list-decimal pl-4 text-sm mt-1 space-y-1">
                                {(r.alert?.recommendations || []).slice(0, 3).map((rec, i) => (
                                  <li key={i}>{rec}</li>
                                ))}
                              </ol>
                              <Link to={`/vault/details/${r.session_id}`} className="inline-block mt-3 text-sm underline underline-offset-4">
                                Full record
                              </Link>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
