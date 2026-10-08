import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AgentPipeline } from "@/components/AgentPipeline";
import { PageHeader, TierBadge } from "@/components/editorial";
import { useAppStore } from "@/store/appStore";
import { useAuthStore } from "@/store/authStore";
import { api, apiErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import type { OutbreakReport } from "@/types";

const EXAMPLE =
  "Jimma zone, Seka Chekorsa woreda: 4 children with fever, rash and cough since 2 days ago. Two siblings in the same kebele also sick. No vaccination records available.";

export default function ProcessReport() {
  const [input, setInput] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isAdmin = useAuthStore((s) => s.user?.role === "admin");
  const {
    pipeline,
    setPipelineProcessing,
    setPipelineResult,
    setPipelineResults,
    setPipelineError,
    resetPipeline,
    addReports,
    addNotification,
    updateReportStatus,
  } = useAppStore();

  const run = async (call: () => Promise<OutbreakReport[]>, label: string) => {
    resetPipeline();
    setPipelineProcessing(true);
    try {
      const results = await call();
      if (results?.length) {
        setPipelineResult(results[0]);
        setPipelineResults(results);
        addReports(results);
        addNotification(`${label}: ${results.length} record${results.length > 1 ? "s" : ""} created`);
        toast.success(`${results.length} record${results.length > 1 ? "s" : ""} created`);
      } else {
        toast.message("No records could be extracted.");
      }
    } catch (e) {
      const msg = apiErrorMessage(e, "Processing failed.");
      setPipelineError(msg);
      toast.error(msg);
    } finally {
      setPipelineProcessing(false);
    }
  };

  const decide = async (approved: boolean) => {
    const r = pipeline.result;
    if (!r) return;
    const status = approved ? "approved" : "rejected";
    try {
      await api.approveReport(r.session_id, approved);
      updateReportStatus(r.session_id, status);
      setPipelineResult({ ...r, status, human_validation_required: false });
      toast.success(approved ? "Record approved" : "Record rejected");
    } catch (e) {
      toast.error(apiErrorMessage(e, "Could not update the record."));
    }
  };

  const result = pipeline.result;
  const busy = pipeline.isProcessing;

  return (
    <div>
      <PageHeader
        kicker="Submit a report"
        title="Turn a field report into records"
        lede="Paste text or upload a file. Each place and condition mentioned becomes its own record, which then waits for review."
      />

      <div className="grid lg:grid-cols-12 gap-x-10 gap-y-10">
        <div className="lg:col-span-7">
          <Tabs defaultValue="text">
            <TabsList>
              <TabsTrigger value="text">Paste text</TabsTrigger>
              <TabsTrigger value="file">Upload a file</TabsTrigger>
            </TabsList>

            <TabsContent value="text" className="mt-6 space-y-4">
              <label htmlFor="report-text" className="label-caps block">
                Report text
              </label>
              <Textarea
                id="report-text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Who reported it, where (region, zone, woreda), how many people, which signs, since when."
                rows={9}
                className="font-serif text-[1.0625rem] leading-relaxed resize-y"
              />
              <div className="flex flex-wrap items-center gap-3">
                <Button onClick={() => run(() => api.processReport(input), "Text report")} disabled={busy || !input.trim()}>
                  {busy ? "Processing…" : "Process report"}
                </Button>
                <Button variant="ghost" onClick={() => setInput(EXAMPLE)} disabled={busy}>
                  Use an example
                </Button>
                {input && (
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setInput("");
                      resetPipeline();
                    }}
                    disabled={busy}
                  >
                    Clear
                  </Button>
                )}
                <span className="ml-auto num text-xs text-muted-foreground">{input.length.toLocaleString()} characters</span>
              </div>
            </TabsContent>

            <TabsContent value="file" className="mt-6 space-y-4">
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  const f = e.dataTransfer.files[0];
                  if (f) setSelectedFile(f);
                }}
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && fileInputRef.current?.click()}
                role="button"
                tabIndex={0}
                className="border border-dashed border-foreground/50 px-6 py-14 text-center cursor-pointer hover:bg-muted/50"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.csv,.jpg,.jpeg,.png,.txt"
                  className="hidden"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                />
                {selectedFile ? (
                  <>
                    <p className="font-serif text-lg">{selectedFile.name}</p>
                    <p className="num text-xs text-muted-foreground mt-1">{(selectedFile.size / 1024).toFixed(0)} KB · click to change</p>
                  </>
                ) : (
                  <>
                    <p className="font-serif text-lg">Drop a file here, or click to choose</p>
                    <p className="text-xs text-muted-foreground mt-1">PDF, CSV, JPEG, PNG or plain text</p>
                  </>
                )}
              </div>
              <Button onClick={() => selectedFile && run(() => api.uploadFile(selectedFile), selectedFile.name)} disabled={busy || !selectedFile}>
                {busy ? "Processing…" : "Process file"}
              </Button>
            </TabsContent>
          </Tabs>

          {pipeline.error && (
            <p className="mt-6 border-l-2 border-tier-red pl-3 text-sm" role="alert">
              {pipeline.error}
            </p>
          )}
        </div>

        <aside className="lg:col-span-5 space-y-10">
          <AgentPipeline isProcessing={busy} />

          {result && !busy && (
            <section aria-labelledby="result-h">
              <div className="flex items-baseline justify-between border-t border-foreground pt-2 mb-4">
                <h2 id="result-h" className="text-lg font-medium">
                  Result
                </h2>
                <span className="label-caps">
                  {pipeline.pipelineResults.length} record{pipeline.pipelineResults.length > 1 ? "s" : ""}
                </span>
              </div>

              {pipeline.pipelineResults.length > 1 && (
                <div className="flex flex-wrap gap-1 mb-4">
                  {pipeline.pipelineResults.map((r) => (
                    <button
                      key={r.session_id}
                      onClick={() => setPipelineResult(r)}
                      className={cn(
                        "px-2 py-1 text-xs border",
                        result.session_id === r.session_id ? "border-foreground bg-foreground text-background" : "border-border hover:border-foreground",
                      )}
                    >
                      {r.extracted_data.location}
                    </button>
                  ))}
                </div>
              )}

              <p className="font-serif text-2xl leading-tight">{result.extracted_data?.location}</p>
              <dl className="grid grid-cols-2 gap-4 mt-4 text-sm">
                <div>
                  <dt className="label-caps">Cases</dt>
                  <dd className="num text-xl mt-1">{result.extracted_data?.cases ?? 0}</dd>
                </div>
                <div>
                  <dt className="label-caps">Level</dt>
                  <dd className="mt-2">
                    <TierBadge level={result.risk_analysis?.risk_level} />
                  </dd>
                </div>
                <div className="col-span-2">
                  <dt className="label-caps">Likely condition</dt>
                  <dd className="mt-1">{result.risk_analysis?.possible_disease || "Unidentified"}</dd>
                </div>
              </dl>

              <div className="mt-6 pt-4 border-t border-border">
                {result.status === "approved" || result.status === "rejected" ? (
                  <p className="label-caps">Marked {result.status}</p>
                ) : isAdmin ? (
                  <div className="flex items-center gap-2">
                    <Button size="sm" onClick={() => decide(true)}>
                      Approve
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => decide(false)}>
                      Reject
                    </Button>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Waiting for an administrator to review it.</p>
                )}
                <Link to={`/vault/details/${result.session_id}`} className="inline-block mt-4 text-sm underline underline-offset-4">
                  Open the full record
                </Link>
              </div>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
