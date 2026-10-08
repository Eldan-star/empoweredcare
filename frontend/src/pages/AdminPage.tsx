import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useAuthStore, type AuthUser } from "@/store/authStore";
import { api, apiErrorMessage, type AnalysisStatus, type TeamMember } from "@/lib/api";
import { LoadingLine, PageHeader, SectionRule, formatDate } from "@/components/editorial";
import { toast } from "sonner";

const CRON_PRESETS = [
  { label: "Every 6 hours", value: "0 */6 * * *" },
  { label: "Daily at 06:00", value: "0 6 * * *" },
  { label: "Daily at midnight", value: "0 0 * * *" },
  { label: "Weekly, Monday 06:00", value: "0 6 * * 1" },
];

interface LastResult {
  error?: unknown;
  comparison_summary?: string;
  anomalies_detected?: string[];
}

const ROLE_LABEL: Record<AuthUser["role"], string> = {
  admin: "Administrator",
  vw: "Viewer",
  data_entry: "Data entry",
};

export default function AdminPage() {
  const currentUser = useAuthStore((s) => s.user);
  const [status, setStatus] = useState<AnalysisStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [running, setRunning] = useState(false);
  const [saving, setSaving] = useState(false);
  const [cron, setCron] = useState("");

  const [users, setUsers] = useState<TeamMember[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<AuthUser["role"]>("vw");
  const [inviting, setInviting] = useState(false);
  const [search, setSearch] = useState("");
  const [toDelete, setToDelete] = useState<TeamMember | null>(null);

  const fetchStatus = async () => {
    try {
      const s = await api.getAnalysisStatus();
      setStatus(s);
      setCron(s.status.schedule || "");
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not load the analysis status."));
    } finally {
      setLoadingStatus(false);
    }
  };

  const fetchUsers = async () => {
    setLoadingUsers(true);
    try {
      setUsers(await api.getUsers());
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not load the team."));
    } finally {
      setLoadingUsers(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchUsers();
  }, []);

  const runNow = async () => {
    setRunning(true);
    try {
      const res = await api.triggerAnalysis();
      toast.success(res.message || "Analysis complete");
      fetchStatus();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Analysis failed."));
    } finally {
      setRunning(false);
    }
  };

  const saveSchedule = async () => {
    if (!cron.trim()) return;
    setSaving(true);
    try {
      await api.updateCronSchedule(cron.trim());
      toast.success("Schedule saved");
      fetchStatus();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Invalid schedule."));
    } finally {
      setSaving(false);
    }
  };

  const invite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true);
    try {
      await api.inviteUser(inviteEmail.trim(), inviteRole, window.location.origin);
      toast.success(`Invitation sent to ${inviteEmail}`);
      setInviteEmail("");
      fetchUsers();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not send the invitation."));
    } finally {
      setInviting(false);
    }
  };

  const remove = async () => {
    if (!toDelete) return;
    try {
      await api.deleteUser(toDelete.id);
      setUsers((u) => u.filter((x) => x.id !== toDelete.id));
      toast.success("Access removed");
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not remove the user."));
    } finally {
      setToDelete(null);
    }
  };

  const q = search.toLowerCase();
  const shown = users.filter((u) => u.email.toLowerCase().includes(q) || (u.full_name || "").toLowerCase().includes(q));
  const last = status?.status.last_result as LastResult | null | undefined;

  return (
    <div>
      <PageHeader kicker="Administration" title="Team and scheduled analysis" />

      <div className="grid lg:grid-cols-12 gap-x-10">
        <SectionRule title="Scheduled analysis" meta="Language-model comparison of recent vs older records" className="lg:col-span-7">
          {loadingStatus ? (
            <LoadingLine />
          ) : (
            <>
              <dl className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm mb-6">
                <div>
                  <dt className="label-caps">Last run</dt>
                  <dd className="num mt-1">{status?.status.last_run ? formatDate(status.status.last_run, true) : "Never"}</dd>
                </div>
                <div>
                  <dt className="label-caps">Next run</dt>
                  <dd className="num mt-1">{status?.status.next_run && status.status.next_run !== "None" ? formatDate(status.status.next_run, true) : "Not scheduled"}</dd>
                </div>
                <div>
                  <dt className="label-caps">Scheduler</dt>
                  <dd className="mt-1">{status?.is_scheduler_running ? "Running" : "Stopped"}</dd>
                </div>
              </dl>

              <div className="flex flex-wrap items-end gap-2 mb-2">
                <div className="space-y-1.5">
                  <Label htmlFor="cron" className="label-caps">
                    Schedule (cron)
                  </Label>
                  <Input id="cron" value={cron} onChange={(e) => setCron(e.target.value)} placeholder="0 6 * * *" className="h-9 w-44 font-mono" />
                </div>
                <Button size="sm" variant="outline" className="h-9" onClick={saveSchedule} disabled={saving || !cron.trim()}>
                  {saving ? "Saving…" : "Save schedule"}
                </Button>
                <Button size="sm" className="h-9" onClick={runNow} disabled={running}>
                  {running ? "Running…" : "Run now"}
                </Button>
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs mb-6">
                {CRON_PRESETS.map((p) => (
                  <button key={p.value} onClick={() => setCron(p.value)} className="underline underline-offset-2 text-muted-foreground hover:text-foreground">
                    {p.label}
                  </button>
                ))}
              </div>

              {last && !last.error && (
                <div className="border-t border-border pt-4">
                  <p className="label-caps mb-2">Last result · unverified</p>
                  {last.comparison_summary && <p className="prose-brief text-[0.9375rem]">{last.comparison_summary}</p>}
                  {Array.isArray(last.anomalies_detected) && last.anomalies_detected.length > 0 && (
                    <>
                      <p className="label-caps mt-4 mb-1">Anomalies noted</p>
                      <ul className="list-disc pl-5 text-sm space-y-1">
                        {last.anomalies_detected.map((a: string, i: number) => (
                          <li key={i}>{a}</li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              )}
              {last?.error && <p className="text-sm border-l-2 border-tier-red pl-3">Last run failed: {String(last.error)}</p>}
            </>
          )}
        </SectionRule>

        <SectionRule title="Invite a colleague" className="lg:col-span-5">
          <form onSubmit={invite} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="invite-email" className="label-caps">
                Email
              </Label>
              <Input id="invite-email" type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} required className="h-10" />
            </div>
            <div className="space-y-1.5">
              <Label className="label-caps">Role</Label>
              <Select value={inviteRole} onValueChange={(v) => setInviteRole(v as AuthUser["role"])}>
                <SelectTrigger className="h-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="vw">Viewer — reads everything, cannot approve</SelectItem>
                  <SelectItem value="data_entry">Data entry — submits records only</SelectItem>
                  <SelectItem value="admin">Administrator — approves and manages</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" disabled={inviting}>
              {inviting ? "Sending…" : "Send invitation"}
            </Button>
          </form>
        </SectionRule>
      </div>

      <SectionRule title="Team" meta={`${users.length} accounts`}>
        <Input type="search" placeholder="Search name or email" value={search} onChange={(e) => setSearch(e.target.value)} className="h-9 w-64 mb-4" aria-label="Search team" />
        {loadingUsers ? (
          <LoadingLine />
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Joined</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {shown.map((u) => {
                  const self = u.email === currentUser?.email;
                  return (
                    <tr key={u.id}>
                      <td className="font-medium">
                        {u.full_name || "—"}
                        {self && <span className="label-caps ml-2 text-[0.625rem]">You</span>}
                      </td>
                      <td>{u.email}</td>
                      <td>{ROLE_LABEL[u.role] || u.role}</td>
                      <td className="num text-xs">{formatDate(u.created_at)}</td>
                      <td className="text-right">
                        {!self && (
                          <button onClick={() => setToDelete(u)} className="text-xs underline underline-offset-2 text-muted-foreground hover:text-destructive">
                            Remove
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </SectionRule>

      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-serif font-medium">Remove {toDelete?.full_name || toDelete?.email}?</AlertDialogTitle>
            <AlertDialogDescription>They lose access immediately. Records they submitted stay in the archive.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={remove} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Remove access
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
