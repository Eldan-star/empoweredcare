import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAppStore } from "@/store/appStore";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { EmptyState, LoadingLine, SectionRule, TierBadge, formatDate } from "@/components/editorial";
import type { OutbreakReport } from "@/types";

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <tr>
      <th scope="row" className="label-caps text-left font-medium w-2/5 py-2 pr-3 border-b border-border align-top">
        {k}
      </th>
      <td className="py-2 border-b border-border">{v}</td>
    </tr>
  );
}

export default function RecordDetailsPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { reports, setReports } = useAppStore();
  const [state, setState] = useState<"loading" | "ready" | "missing">("loading");
  const [copied, setCopied] = useState(false);

  const report: OutbreakReport | undefined = reports.find((r) => r.session_id === sessionId);

  useEffect(() => {
    if (report) {
      setState("ready");
      return;
    }
    api
      .getReports()
      .then((data) => {
        setReports(data);
        setState(data.some((r) => r.session_id === sessionId) ? "ready" : "missing");
      })
      .catch(() => setState("missing"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  if (state === "loading" && !report) return <LoadingLine label="Loading record" />;
  if (!report)
    return (
      <EmptyState
        title="Record not found"
        body="It may have been merged into another record or removed."
        action={
          <Link to="/vault" className="underline underline-offset-4 text-sm">
            Back to records
          </Link>
        }
      />
    );

  const ed = report.extracted_data;
  const exportCSV = () => {
    const rows = [
      ["Field", "Value"],
      ["Record ID", report.session_id],
      ["Location", ed.location],
      ["Cases", ed.cases],
      ["Report date", ed.date || ""],
      ["Signs", ed.symptoms.join(", ")],
      ["Condition", report.risk_analysis?.possible_disease || ""],
      ["Level", report.risk_analysis?.risk_level || ""],
      ["Status", report.status || "pending"],
      ["Raw report", report.raw_report || ""],
    ];
    const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = `record-${report.session_id.slice(0, 8)}.csv`;
    a.click();
  };

  const copyRaw = async () => {
    await navigator.clipboard.writeText(report.raw_report || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  // Prefer the full per-perspective opinions; the stored consensus text is truncated.
  const opinions = report.consensus?.agent_opinions ?? [];
  const reasoning = opinions.length
    ? opinions.map((o) => ({ level: (o.risk_level || "").toUpperCase() as string | null, text: o.reason }))
    : (report.consensus?.final_reasoning || report.risk_analysis?.reason || "")
    .replace(/Consensus reached from multiple perspectives:\s*/i, "")
    .split(" | ")
    .map((s) => {
      const m = s.match(/^(HIGH|MEDIUM|LOW|UNKNOWN):\s*([\s\S]*)/i);
      return m ? { level: m[1].toUpperCase(), text: m[2].trim() } : { level: null as string | null, text: s.trim() };
    })
    .filter((p) => p.text);

  return (
    <div>
      <div className="flex items-center justify-between mb-6 text-sm">
        <Link to="/vault" className="underline underline-offset-4">
          ← Records
        </Link>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={exportCSV}>
            Export CSV
          </Button>
        </div>
      </div>

      <header className="pb-5 mb-8 border-b border-foreground">
        <p className="label-caps mb-2">
          Record <span className="num">{report.session_id.slice(0, 8)}</span> · {report.status || "pending"}
        </p>
        <h1 className="text-[2rem] md:text-[2.5rem] leading-tight font-medium">{ed.location}</h1>
        <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
          <TierBadge level={report.risk_analysis?.risk_level || "UNKNOWN"} className="text-foreground" />
          <span>{report.risk_analysis?.possible_disease || "Unidentified condition"}</span>
          <span>
            <span className="num text-foreground">{ed.cases}</span> cases
          </span>
          <span>Report date: {ed.date || "not stated"}</span>
          <span>Received {formatDate(report.created_at, true)}</span>
        </div>
      </header>

      <div className="grid lg:grid-cols-12 gap-x-10">
        <div className="lg:col-span-8">
          {report.alert?.message && (
            <SectionRule title="Summary">
              <p className="font-serif text-lg leading-snug">{report.alert.title}</p>
              <p className="prose-brief mt-3">{report.alert.message}</p>
              {report.alert.why_urgent && (
                <p className="mt-3 text-sm">
                  <span className="label-caps mr-2">Why flagged</span>
                  {report.alert.why_urgent}
                </p>
              )}
            </SectionRule>
          )}

          <SectionRule title="Model reasoning" meta="Four perspectives · unverified">
            {reasoning.length ? (
              <ol className="space-y-4">
                {reasoning.map((p, i) => (
                  <li key={i} className="grid grid-cols-[6.5rem_1fr] gap-4">
                    {p.level ? <TierBadge level={p.level} className="mt-0.5" /> : <span />}
                    <p className="text-sm leading-relaxed">{p.text}</p>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-sm text-muted-foreground">No reasoning recorded.</p>
            )}
            <p className="text-xs text-muted-foreground mt-4">
              These opinions come from language-model prompts and are not a validated risk estimate.
            </p>
          </SectionRule>

          <SectionRule
            title="Original report"
            meta={
              <button onClick={copyRaw} className="underline underline-offset-4">
                {copied ? "Copied" : "Copy text"}
              </button>
            }
          >
            <pre className="font-mono text-xs leading-relaxed whitespace-pre-wrap border border-border bg-card p-4 max-h-96 overflow-auto">
              {report.raw_report?.trim() || "No original text stored."}
            </pre>
          </SectionRule>
        </div>

        <aside className="lg:col-span-4">
          <SectionRule title="Extracted fields">
            <table className="w-full text-sm">
              <tbody>
                <Row k="Classification" v={ed.classification || "Suspected"} />
                <Row k="Clinical signs" v={ed.symptoms.length ? ed.symptoms.join(", ") : "None"} />
                <Row k="Cases" v={<span className="num">{ed.cases}</span>} />
                <Row k="Report date" v={ed.date || "—"} />
                <Row
                  k="Extraction check"
                  v={
                    report.validation
                      ? `${report.validation.valid ? "Passed" : "Failed"} · ${Math.round((report.validation.confidence || 0) * 100)}%`
                      : "—"
                  }
                />
              </tbody>
            </table>
            {report.validation?.issues?.length ? (
              <ul className="mt-3 list-disc pl-4 text-xs text-muted-foreground space-y-1">
                {report.validation.issues.map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            ) : null}
          </SectionRule>

          {report.alert?.recommendations?.length ? (
            <SectionRule title="Suggested actions">
              <ol className="list-decimal pl-4 text-sm space-y-2">
                {report.alert.recommendations.map((rec, i) => (
                  <li key={i}>{rec}</li>
                ))}
              </ol>
            </SectionRule>
          ) : null}

          {report.context_research && (
            <SectionRule title="Web context" meta="Scraped · unverified">
              <table className="w-full text-sm">
                <tbody>
                  <Row k="Security" v={report.context_research.security_status || "—"} />
                  <Row k="Conflict zone" v={report.context_research.conflict_zone ? "Yes" : "No"} />
                  <Row k="Water" v={report.context_research.water_quality || "—"} />
                  <Row k="Weather" v={report.context_research.temperature || "—"} />
                </tbody>
              </table>
            </SectionRule>
          )}
        </aside>
      </div>
    </div>
  );
}
