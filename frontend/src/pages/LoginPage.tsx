import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { AuthLayout, Field } from "@/components/AuthLayout";
import { useAuthStore } from "@/store/authStore";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) return;
    setLoading(true);
    try {
      const tokenData = await api.login(email, password);
      useAuthStore.getState().setAuth(tokenData.access_token, {
        email,
        full_name: tokenData.full_name,
        role: tokenData.role,
        created_at: new Date().toISOString(),
      });
      navigate(tokenData.role === "data_entry" ? "/data-entry" : "/dashboard");
    } catch (err) {
      toast.error(apiErrorMessage(err, "Sign-in failed. Check your email and password."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      kicker="Sign in"
      title="The weekly picture, with the evidence behind it."
      lede="Access is by invitation for EPHI and regional health bureau staff. Ask your administrator for an invite."
      footer={
        <>
          Have an invitation code?{" "}
          <Link to="/register" className="text-foreground underline underline-offset-4">
            Create your account
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        <Field id="email" label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" />
        <Field id="password" label="Password" type="password" value={password} onChange={setPassword} autoComplete="current-password" />
        <div className="flex items-center justify-between pt-2">
          <Link to="/forgot-password" className="text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground">
            Forgot password
          </Link>
          <Button type="submit" disabled={loading} className="h-11 px-6">
            {loading ? "Signing in…" : "Sign in"}
          </Button>
        </div>
      </form>
    </AuthLayout>
  );
}
