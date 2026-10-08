import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { AuthLayout, Field } from "@/components/AuthLayout";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [token, setToken] = useState(searchParams.get("token") || "");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      toast.error("The passwords do not match.");
      return;
    }
    if (password.length < 8) {
      toast.error("Use at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      await api.register({ token, password, full_name: fullName });
      toast.success("Account created. Sign in to continue.");
      navigate("/login");
    } catch (err) {
      toast.error(apiErrorMessage(err, "Registration failed. The invitation may be invalid or expired."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      kicker="Create account"
      title="Accept your invitation."
      lede="Invitations are valid for 48 hours. If yours has expired, ask your administrator to send a new one."
      footer={
        <>
          Already registered?{" "}
          <Link to="/login" className="text-foreground underline underline-offset-4">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {!searchParams.get("token") && (
          <Field id="token" label="Invitation code" value={token} onChange={setToken} hint="The code from your invitation email." />
        )}
        <Field id="name" label="Full name" value={fullName} onChange={setFullName} autoComplete="name" />
        <Field id="password" label="Password" type="password" value={password} onChange={setPassword} autoComplete="new-password" hint="At least 8 characters." />
        <Field id="confirm" label="Confirm password" type="password" value={confirmPassword} onChange={setConfirmPassword} autoComplete="new-password" />
        <div className="flex justify-end pt-2">
          <Button type="submit" disabled={loading} className="h-11 px-6">
            {loading ? "Creating account…" : "Create account"}
          </Button>
        </div>
      </form>
    </AuthLayout>
  );
}
