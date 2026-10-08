import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAppStore } from "@/store/appStore";
import { useAuthStore } from "@/store/authStore";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { EmptyState, PageHeader, SectionRule, Stat, StatRow, TierBadge, formatDate } from "@/components/editorial";
import { cn } from "@/lib/utils";

const ORDER: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 };
const FILTERS = [
  { label: "All", value: null },
  { label: "High", value: "HIGH" },
  { label: "Medium", value: "MEDIUM" },
  { label: "Low", value: "LOW" },
] as const;

export default function AlertsPage() {
  const { reports, updateReportStatus, setReports, addNotification } = useAppStore();
  const isAdmin = useAuthStore((s) => s.user?.role === "admin");
  const [filterRisk, setFilterRisk] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [processing, setProcessing] = useState<string | null>(null);

  useEffect(() => {
    api.getReports().then(setReports).catch(() => toast.error("Could not load records."));
  }, [setReports]);

  const isPending = (r: (typeof reports)[number]) => (r.status || "pending") === "pending";
  const queue = reports
    .filter(isPending)
    .filter((r) => !filterRisk || r.risk_analysis?.risk_level === filterRisk)
    .sort((a, b) => (ORDER[b.risk_analysis?.risk_level || ""] || 0) - (ORDER[a.risk_analysis?.risk_level || ""] || 0));
  const resolved = reports.filter((r) => !isPending(r));
  const totalPending = reports.filter(isPending).length;
  const highPending = reports.filter((r) => isPending(r) && r.risk_analysis?.risk_level === "HIGH").length;

  const decide = async (id: string, approved: boolean) => {
    setProcessing(id);
    try {
      await api.approveReport(id, approved);
      updateReportStatus(id, approved ? "approved" : "rejected");
      addNotification(`Record ${id.slice(0, 8)} ${approved ? "approved" : "rejected"}`);
      toast.success(approved ? "Record approved" : "Record rejected");
      setExpandedId(null);
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not update the record."));
    } finally {
      setProcessing(null);
    }
  };

  return (
    <div>
      <PageHeader
        kicker="Alert review"
        title="Records awaiting a decision"
        lede="Each record was extracted and rated by the language-model pipeline. Nothing counts as verified until an officer approves it."
      />

      <StatRow className="mb-10">
        <Stat label="Awaiting review" value={totalPending} />
        <Stat label="Rated high, pending" value={highPending} tone={highPending ? "red" : "default"} />
        <Stat label="Decided" value={resolved.length} />
        <Stat label="Approved" value={resolved.filter((r) => r.status === "approved").length} />
      </StatRow>

      {!isAdmin && (
        <p className="mb-8 border-l-2 border-foreground pl-3 text-sm text-muted-foreground">
          You can read the queue. Approving or rejecting records requires an administrator account.
        </p>
      )}

      <div className="grid lg:grid-cols-12 gap-x-10">
        <SectionRule title="Queue" meta={`${queue.length} records · highest rated first`} className="lg:col-span-8">
          <div className="flex flex-wrap gap-1 mb-4" role="group" aria-label="Filter by level">
            {FILTERS.map((f) => (
              <Button
                key={f.label}
                size="sm"
                variant={filterRisk === f.value ? "default" : "outline"}
                onClick={() => setFilterRisk(f.value)}
                aria-pressed={filterRisk === f.value}
              >
                {f.label}
              </Button>
            ))}
          </div>

          {queue.length === 0 ? (
            <EmptyState
              title="Nothing waiting"
              body={filterRisk ? `No pending records rated ${filterRisk.toLowerCase()}.` : "Every record has been reviewed."}
              action={
                filterRisk ? (
                  <Button variant="outline" size="sm" onClick={() => setFilterRisk(null)}>
                    Show all levels
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <ol className="border-t border-border">
              {queue.map((r) => {
                const open = expandedId === r.session_id;
                const busy = processing === r.session_id;
                return (
                  <li key={r.session_id} className="border-b border-border">
                    <button
                      className="w-full text-left py-4 grid grid-cols-[6.5rem_1fr_auto] gap-4 items-start hover:bg-muted/50 px-1"
                      onClick={() => setExpandedId(open ? null : r.session_id)}
                      aria-expanded={open}
                    >
                      <TierBadge level={r.risk_analysis?.risk_level || "UNKNOWN"} className="mt-1" />
                      <span>
                        <span className="block font-serif text-[1.0625rem] leading-snug">{r.alert?.title || "Untitled report"}</span>
                        <span className="block text-xs text-muted-foreground mt-1">
                          {r.extracted_data?.location || "Unknown location"} · <span className="num">{r.extracted_data?.cases ?? 0}</span> cases ·{" "}
                          {r.risk_analysis?.possible_disease || "Unidentified"} · received {formatDate(r.created_at, true)}
                        </span>
                      </span>
                      <ChevronDown className={cn("h-4 w-4 mt-1 text-muted-foreground transition-transform", open && "rotate-180")} />
                    </button>

                    {open && (
                      <div className="pb-5 pl-1 md:pl-[7.5rem] pr-1 space-y-4 text-sm">
                        {r.alert?.message && <p className="prose-brief text-[0.9375rem]">{r.alert.message}</p>}
                        <dl className="grid sm:grid-cols-3 gap-4">
                          <div>
                            <dt className="label-caps">Classification</dt>
                            <dd className="mt-1">{r.extracted_data?.classification || "Suspected"}</dd>
                          </div>
                          <div className="sm:col-span-2">
                            <dt className="label-caps">Clinical signs</dt>
                            <dd className="mt-1">{r.extracted_data?.symptoms?.length ? r.extracted_data.symptoms.join(", ") : "None extracted"}</dd>
                          </div>
                        </dl>
                        {r.risk_analysis?.reason && (
                          <div>
                            <p className="label-caps">Model reasoning (unverified)</p>
                            <p className="mt-1 text-muted-foreground leading-relaxed">
                              {r.risk_analysis.reason.length > 400 ? r.risk_analysis.reason.slice(0, 400) + "…" : r.risk_analysis.reason}
                            </p>
                          </div>
                        )}
                        <div className="flex flex-wrap items-center gap-2 pt-1">
                          {isAdmin && (
                            <>
                              <Button size="sm" onClick={() => decide(r.session_id, true)} disabled={busy}>
                                {busy ? "Saving…" : "Approve"}
                              </Button>
                              <Button size="sm" variant="outline" onClick={() => decide(r.session_id, false)} disabled={busy}>
                                Reject
                              </Button>
                            </>
                          )}
                          <Link to={`/vault/details/${r.session_id}`} className="text-sm underline underline-offset-4 ml-1">
                            Full record
                          </Link>
                        </div>
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>
          )}
        </SectionRule>

        <SectionRule title="Recently decided" meta={`${resolved.length} total`} className="lg:col-span-4">
          {resolved.length === 0 ? (
            <p className="text-sm text-muted-foreground">No decisions yet.</p>
          ) : (
            <ul>
              {resolved.slice(0, 10).map((r) => (
                <li key={r.session_id} className="py-2.5 border-b border-border">
                  <Link to={`/vault/details/${r.session_id}`} className="block group">
                    <span className="label-caps text-[0.625rem]">{r.status}</span>
                    <span className="block text-sm group-hover:underline underline-offset-2 mt-0.5">{r.alert?.title || "Untitled report"}</span>
                    <span className="block text-xs text-muted-foreground">{r.extracted_data?.location}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </SectionRule>
      </div>
    </div>
  );
}
