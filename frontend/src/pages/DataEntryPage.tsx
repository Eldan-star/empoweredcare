import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState, LoadingLine, TierBadge, formatDate, isoWeek } from "@/components/editorial";
import { useAuthStore } from "@/store/authStore";
import { api, apiErrorMessage, type PatientRecordInput, type PatientRecordRow } from "@/lib/api";
import type { OutbreakReport } from "@/types";
import { toast } from "sonner";

interface VitalSigns {
  blood_pressure: string;
  pulse: string;
  temperature: string;
  respiratory_rate: string;
  oxygen_saturation: string;
  weight: string;
  height: string;
}

interface PatientFormData {
  patient_name: string;
  sex: string;
  age: string;
  city: string;
  subcity: string;
  woreda: string;
  mrn: string;
  occupation: string;
  date: string;
  chief_complaint: string;
  history: string;
  physical_exam: string;
  vital_signs: VitalSigns;
  assessment: string;
  past_medical_history: string;
  plan: string;
}

const EMPTY_FORM: PatientFormData = {
  patient_name: "",
  sex: "",
  age: "",
  city: "",
  subcity: "",
  woreda: "",
  mrn: "",
  occupation: "",
  date: "",
  chief_complaint: "",
  history: "",
  physical_exam: "",
  vital_signs: { blood_pressure: "", pulse: "", temperature: "", respiratory_rate: "", oxygen_saturation: "", weight: "", height: "" },
  assessment: "",
  past_medical_history: "",
  plan: "",
};

const VITALS: Array<[keyof VitalSigns, string, string]> = [
  ["blood_pressure", "Blood pressure", "120/80 mmHg"],
  ["pulse", "Pulse", "72 /min"],
  ["temperature", "Temperature", "36.6 °C"],
  ["respiratory_rate", "Respiratory rate", "18 /min"],
  ["oxygen_saturation", "SpO₂", "98 %"],
  ["weight", "Weight", "70 kg"],
  ["height", "Height", "175 cm"],
];

function FormSection({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <fieldset className="border-t border-foreground pt-3 mb-10">
      <legend className="sr-only">{title}</legend>
      <div className="flex items-baseline gap-3 mb-5">
        <span className="num text-xs text-muted-foreground">{String(n).padStart(2, "0")}</span>
        <h2 className="text-xl font-medium">{title}</h2>
      </div>
      {children}
    </fieldset>
  );
}

function TextField({
  id,
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  required,
  className,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  required?: boolean;
  className?: string;
}) {
  return (
    <div className={className}>
      <Label htmlFor={id} className="label-caps">
        {label}
        {required && <span aria-hidden> *</span>}
      </Label>
      <Input id={id} type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} required={required} className="h-10 mt-1.5" />
    </div>
  );
}

function AreaField({ id, label, value, onChange, placeholder }: { id: string; label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div>
      <Label htmlFor={id} className="label-caps">
        {label}
      </Label>
      <Textarea id={id} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} rows={4} className="mt-1.5 resize-y" />
    </div>
  );
}

function PatientFormTab({ onSaved }: { onSaved: () => void }) {
  const [form, setForm] = useState<PatientFormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<{ id: string; saved_at: string } | null>(null);

  const set = (field: keyof PatientFormData) => (value: string) => setForm((f) => ({ ...f, [field]: value }));
  const setVital = (field: keyof VitalSigns) => (value: string) => setForm((f) => ({ ...f, vital_signs: { ...f.vital_signs, [field]: value } }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.patient_name.trim()) {
      toast.error("Patient name is required.");
      return;
    }
    setSaving(true);
    setSaved(null);
    try {
      const vitals = Object.fromEntries(Object.entries(form.vital_signs).filter(([, v]) => v.trim() !== ""));
      const { vital_signs: _omit, ...rest } = form;
      const text = Object.fromEntries(Object.entries(rest).filter(([, v]) => v.trim() !== "")) as Partial<PatientRecordInput>;
      const payload: PatientRecordInput = {
        ...text,
        patient_name: form.patient_name.trim(),
        vital_signs: Object.keys(vitals).length ? vitals : undefined,
      };
      const res = await api.savePatientRecord(payload);
      setSaved({ id: res.id, saved_at: res.saved_at });
      toast.success(`Record saved for ${res.patient_name}`);
      setForm(EMPTY_FORM);
      onSaved();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not save the record."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="max-w-3xl">
      <FormSection n={1} title="Patient">
        <div className="grid sm:grid-cols-3 gap-4">
          <TextField id="pf-name" label="Full name" value={form.patient_name} onChange={set("patient_name")} required className="sm:col-span-2" />
          <div>
            <Label htmlFor="pf-sex" className="label-caps">
              Sex
            </Label>
            <select
              id="pf-sex"
              value={form.sex}
              onChange={(e) => set("sex")(e.target.value)}
              className="mt-1.5 w-full h-10 px-3 rounded-sm border border-input bg-card text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="">Not stated</option>
              <option value="Male">Male</option>
              <option value="Female">Female</option>
            </select>
          </div>
          <TextField id="pf-age" label="Age" value={form.age} onChange={set("age")} placeholder="e.g. 4 years" />
          <TextField id="pf-mrn" label="MRN" value={form.mrn} onChange={set("mrn")} placeholder="Medical record number" />
          <TextField id="pf-occupation" label="Occupation" value={form.occupation} onChange={set("occupation")} />
          <TextField id="pf-date" label="Date of visit" type="date" value={form.date} onChange={set("date")} />
        </div>
      </FormSection>

      <FormSection n={2} title="Location">
        <div className="grid sm:grid-cols-3 gap-4">
          <TextField id="pf-city" label="City or zone" value={form.city} onChange={set("city")} placeholder="e.g. Addis Ababa" />
          <TextField id="pf-subcity" label="Sub-city" value={form.subcity} onChange={set("subcity")} placeholder="e.g. Bole" />
          <TextField id="pf-woreda" label="Woreda" value={form.woreda} onChange={set("woreda")} placeholder="e.g. Woreda 03" />
        </div>
      </FormSection>

      <FormSection n={3} title="Presentation">
        <div className="space-y-4">
          <TextField id="pf-cc" label="Chief complaint" value={form.chief_complaint} onChange={set("chief_complaint")} />
          <AreaField id="pf-history" label="History of presenting illness" value={form.history} onChange={set("history")} placeholder="Onset, duration, progression, associated signs" />
          <AreaField id="pf-exam" label="Physical examination" value={form.physical_exam} onChange={set("physical_exam")} />
        </div>
      </FormSection>

      <FormSection n={4} title="Vital signs">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {VITALS.map(([field, label, ph]) => (
            <TextField key={field} id={`pf-vital-${field}`} label={label} value={form.vital_signs[field]} onChange={setVital(field)} placeholder={ph} />
          ))}
        </div>
      </FormSection>

      <FormSection n={5} title="Assessment and plan">
        <div className="space-y-4">
          <AreaField id="pf-assessment" label="Assessment / diagnosis" value={form.assessment} onChange={set("assessment")} />
          <AreaField id="pf-pmh" label="Past medical history" value={form.past_medical_history} onChange={set("past_medical_history")} />
          <AreaField id="pf-plan" label="Plan" value={form.plan} onChange={set("plan")} />
        </div>
      </FormSection>

      <div className="flex flex-wrap items-center gap-3 border-t border-foreground pt-4">
        <Button id="portal-save-record-btn" type="submit" disabled={saving || !form.patient_name.trim()}>
          {saving ? "Saving…" : "Save record"}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setForm(EMPTY_FORM)} disabled={saving}>
          Clear form
        </Button>
        {saved && (
          <p className="text-sm" role="status">
            Saved · <span className="num">{saved.id.slice(0, 8)}</span> · {formatDate(saved.saved_at, true)}
          </p>
        )}
      </div>
    </form>
  );
}

function FileUploadTab() {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<OutbreakReport[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLInputElement>(null);

  const upload = async () => {
    if (!file) return;
    setBusy(true);
    setResults(null);
    setError(null);
    try {
      const res = await api.uploadFile(file);
      setResults(res);
      toast.success(`${res.length} record${res.length === 1 ? "" : "s"} created from ${file.name}`);
    } catch (err) {
      const msg = apiErrorMessage(err, "Upload failed.");
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const f = e.dataTransfer.files[0];
          if (f) {
            setFile(f);
            setResults(null);
          }
        }}
        onClick={() => ref.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && ref.current?.click()}
        role="button"
        tabIndex={0}
        className="border border-dashed border-foreground/50 px-6 py-14 text-center cursor-pointer hover:bg-muted/50"
      >
        <input
          ref={ref}
          id="portal-file-input"
          type="file"
          className="hidden"
          accept=".pdf,.csv,.jpg,.jpeg,.png,.txt"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) {
              setFile(f);
              setResults(null);
            }
          }}
        />
        {file ? (
          <>
            <p className="font-serif text-lg">{file.name}</p>
            <p className="num text-xs text-muted-foreground mt-1">{(file.size / 1024).toFixed(0)} KB · click to change</p>
          </>
        ) : (
          <>
            <p className="font-serif text-lg">Drop a file here, or click to choose</p>
            <p className="text-xs text-muted-foreground mt-1">PDF, CSV, JPEG, PNG or plain text</p>
          </>
        )}
      </div>

      <div className="flex gap-2 mt-4">
        <Button id="portal-upload-btn" onClick={upload} disabled={!file || busy}>
          {busy ? "Processing…" : "Process file"}
        </Button>
        {file && (
          <Button variant="ghost" onClick={() => setFile(null)} disabled={busy}>
            Remove
          </Button>
        )}
      </div>

      {error && (
        <p className="mt-6 border-l-2 border-tier-red pl-3 text-sm" role="alert">
          {error}
        </p>
      )}

      {results && (
        <div className="mt-8">
          <p className="label-caps mb-2">
            {results.length} record{results.length === 1 ? "" : "s"} created
          </p>
          <table className="data-table">
            <thead>
              <tr>
                <th>Location</th>
                <th>Condition</th>
                <th className="text-right">Cases</th>
                <th>Level</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.session_id}>
                  <td>{r.extracted_data?.location}</td>
                  <td>{r.risk_analysis?.possible_disease || "Unidentified"}</td>
                  <td className="num text-right">{r.extracted_data?.cases}</td>
                  <td>
                    <TierBadge level={r.risk_analysis?.risk_level} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function MyRecordsTab({ refreshKey }: { refreshKey: number }) {
  const [records, setRecords] = useState<PatientRecordRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .getPatientRecords()
      .then((res) => setRecords(res.records))
      .catch(() => toast.error("Could not load your records."))
      .finally(() => setLoading(false));
  }, [refreshKey]);

  if (loading) return <LoadingLine label="Loading your records" />;
  if (!records.length) return <EmptyState title="No records yet" body="Records you save appear here." />;

  return (
    <div className="max-w-3xl">
      <p className="label-caps mb-3">
        {records.length} record{records.length === 1 ? "" : "s"}
      </p>
      <ul className="border-t border-border">
        {records.map((r) => (
          <li key={r.id} className="border-b border-border">
            <button
              type="button"
              onClick={() => setOpen(open === r.id ? null : r.id)}
              aria-expanded={open === r.id}
              className="w-full text-left py-3 flex items-baseline justify-between gap-4 hover:bg-muted/50 px-1"
            >
              <span>
                <span className="font-medium">{r.patient_name}</span>
                <span className="text-xs text-muted-foreground ml-3">
                  {[r.mrn && `MRN ${r.mrn}`, r.date, r.city].filter(Boolean).join(" · ")}
                </span>
              </span>
              <span className="num text-xs text-muted-foreground whitespace-nowrap">{formatDate(r.saved_at, true)}</span>
            </button>
            {open === r.id && (
              <dl className="pb-4 px-1 grid sm:grid-cols-3 gap-x-6 gap-y-3 text-sm">
                {(
                  [
                    ["Sex", r.sex],
                    ["Age", r.age],
                    ["Occupation", r.occupation],
                    ["Sub-city", r.subcity],
                    ["Woreda", r.woreda],
                    ["Chief complaint", r.chief_complaint],
                    ["Assessment", r.assessment],
                    ["Plan", r.plan],
                  ] as Array<[string, string | null | undefined]>
                )
                  .filter(([, v]) => v)
                  .map(([k, v]) => (
                    <div key={k}>
                      <dt className="label-caps">{k}</dt>
                      <dd className="mt-0.5">{v}</dd>
                    </div>
                  ))}
                {r.vital_signs && Object.keys(r.vital_signs).length > 0 && (
                  <div className="sm:col-span-3">
                    <dt className="label-caps">Vital signs</dt>
                    <dd className="mt-0.5 num text-xs">
                      {Object.entries(r.vital_signs)
                        .map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`)
                        .join(" · ")}
                    </dd>
                  </div>
                )}
              </dl>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function DataEntryPage() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const [refreshKey, setRefreshKey] = useState(0);
  const { week, year } = isoWeek();

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-foreground">
        <div className="mx-auto max-w-5xl px-4 md:px-8 h-12 flex items-center justify-between text-[0.8125rem]">
          <span className="font-serif text-lg">Empowered Care</span>
          <div className="flex items-center gap-4">
            <span className="num text-muted-foreground hidden sm:inline">
              Week {week} · {year}
            </span>
            {user?.role === "admin" && (
              <Link to="/dashboard" className="underline underline-offset-4">
                Console
              </Link>
            )}
            <span className="text-muted-foreground truncate max-w-[12rem]">{user?.full_name || user?.email}</span>
            <button
              onClick={() => {
                logout();
                navigate("/login");
              }}
              className="underline underline-offset-4"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 md:px-8 py-10">
        <div className="pb-5 mb-8 border-b border-foreground">
          <p className="label-caps mb-2">Data entry</p>
          <h1 className="text-[2rem] md:text-[2.5rem] leading-tight font-medium">Patient records</h1>
          <p className="mt-3 text-[0.9375rem] text-muted-foreground max-w-2xl">
            Enter a record by hand, upload a report file, or review what you have entered.
          </p>
        </div>

        <Tabs defaultValue="form">
          <TabsList>
            <TabsTrigger value="form">New record</TabsTrigger>
            <TabsTrigger value="upload">Upload a file</TabsTrigger>
            <TabsTrigger value="history">My records</TabsTrigger>
          </TabsList>
          <TabsContent value="form" className="mt-8">
            <PatientFormTab onSaved={() => setRefreshKey((k) => k + 1)} />
          </TabsContent>
          <TabsContent value="upload" className="mt-8">
            <FileUploadTab />
          </TabsContent>
          <TabsContent value="history" className="mt-8">
            <MyRecordsTab refreshKey={refreshKey} />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
