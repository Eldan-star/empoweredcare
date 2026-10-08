import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { AuthLayout, Field } from "@/components/AuthLayout";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";

export default function ForgotPasswordPage() {
  const [searchParams] = useSearchParams();
  const resetToken = searchParams.get("token");
  return resetToken ? <ResetPasswordForm token={resetToken} /> : <RequestResetForm />;
}

const backToSignIn = (
  <Link to="/login" className="text-foreground underline underline-offset-4">
    Back to sign in
  </Link>
);

function RequestResetForm() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.forgotPassword(email);
      setSent(true);
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not send the reset link."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      kicker="Password reset"
      title={sent ? "Check your email." : "Reset your password."}
      lede={
        sent
          ? `If an account exists for ${email}, a reset link is on its way. The link expires in one hour.`
          : "Enter the email you sign in with and we will send a reset link."
      }
      footer={backToSignIn}
    >
      {sent ? (
        <p className="text-sm text-muted-foreground">You can close this page.</p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          <Field id="email" label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" />
          <div className="flex justify-end pt-2">
            <Button type="submit" disabled={loading} className="h-11 px-6">
              {loading ? "Sending…" : "Send reset link"}
            </Button>
          </div>
        </form>
      )}
    </AuthLayout>
  );
}

function ResetPasswordForm({ token }: { token: string }) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      toast.error("The passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await api.resetPassword(token, password);
      setDone(true);
    } catch (err) {
      toast.error(apiErrorMessage(err, "Reset failed. The link may be invalid or expired."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      kicker="Password reset"
      title={done ? "Password updated." : "Choose a new password."}
      lede={done ? "Sign in with your new password." : undefined}
      footer={backToSignIn}
    >
      {!done && (
        <form onSubmit={handleSubmit} className="space-y-5">
          <Field id="password" label="New password" type="password" value={password} onChange={setPassword} autoComplete="new-password" />
          <Field id="confirm" label="Confirm password" type="password" value={confirmPassword} onChange={setConfirmPassword} autoComplete="new-password" />
          <div className="flex justify-end pt-2">
            <Button type="submit" disabled={loading} className="h-11 px-6">
              {loading ? "Saving…" : "Save password"}
            </Button>
          </div>
        </form>
      )}
    </AuthLayout>
  );
}
