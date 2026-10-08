import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/AuthLayout";
import { PageHeader, SectionRule, formatDate } from "@/components/editorial";
import { useAuthStore } from "@/store/authStore";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";

export default function ProfilePage() {
  const { user, updateUser } = useAuthStore();
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getMe().then(updateUser).catch(() => undefined);
  }, [updateUser]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      toast.error("The new passwords do not match.");
      return;
    }
    if (newPassword.length < 8) {
      toast.error("Use at least 8 characters.");
      return;
    }
    setSaving(true);
    try {
      await api.changePassword(oldPassword, newPassword);
      toast.success("Password changed");
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not change the password."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <PageHeader kicker="Profile" title={user?.full_name || "Your account"} />

      <SectionRule title="Details">
        <dl className="grid sm:grid-cols-3 gap-4 text-sm">
          <div>
            <dt className="label-caps">Email</dt>
            <dd className="mt-1 break-all">{user?.email}</dd>
          </div>
          <div>
            <dt className="label-caps">Role</dt>
            <dd className="mt-1">{user?.role === "admin" ? "Administrator" : user?.role === "data_entry" ? "Data entry" : "Viewer"}</dd>
          </div>
          <div>
            <dt className="label-caps">Member since</dt>
            <dd className="num mt-1">{formatDate(user?.created_at)}</dd>
          </div>
        </dl>
      </SectionRule>

      <SectionRule title="Change password">
        <form onSubmit={submit} className="space-y-5 max-w-md">
          <Field id="old-pw" label="Current password" type="password" value={oldPassword} onChange={setOldPassword} autoComplete="current-password" />
          <Field id="new-pw" label="New password" type="password" value={newPassword} onChange={setNewPassword} autoComplete="new-password" hint="At least 8 characters." />
          <Field
            id="confirm-pw"
            label="Confirm new password"
            type="password"
            value={confirmPassword}
            onChange={setConfirmPassword}
            autoComplete="new-password"
            hint={confirmPassword && newPassword !== confirmPassword ? "Does not match." : undefined}
          />
          <Button type="submit" disabled={saving || !oldPassword || !newPassword || newPassword !== confirmPassword}>
            {saving ? "Saving…" : "Change password"}
          </Button>
        </form>
      </SectionRule>
    </div>
  );
}
