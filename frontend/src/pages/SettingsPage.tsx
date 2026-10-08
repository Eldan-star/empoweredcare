import { useState } from "react";
import { useAppStore } from "@/store/appStore";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { PageHeader, SectionRule } from "@/components/editorial";
import { useHealth } from "@/hooks/use-health";
import { toast } from "sonner";

export default function SettingsPage() {
  const { apiBaseUrl, setApiBaseUrl, darkMode, toggleDarkMode } = useAppStore();
  const user = useAuthStore((s) => s.user);
  const health = useHealth();
  const [url, setUrl] = useState(apiBaseUrl);

  const save = () => {
    setApiBaseUrl(url.trim());
    toast.success("Backend address saved");
    health.refetch();
  };

  return (
    <div className="max-w-2xl">
      <PageHeader kicker="Settings" title="This browser" lede="These settings are stored in this browser only." />

      <SectionRule title="Backend">
        <div className="space-y-1.5">
          <Label htmlFor="api-url" className="label-caps">
            API address
          </Label>
          <div className="flex gap-2">
            <Input id="api-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://localhost:8000" className="h-10 font-mono" />
            <Button onClick={save} disabled={url.trim() === apiBaseUrl}>
              Save
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Status:{" "}
            {health.isLoading
              ? "checking…"
              : health.isSuccess
                ? `online, version ${health.data?.version ?? "unknown"}`
                : "unreachable"}
          </p>
        </div>
      </SectionRule>

      <SectionRule title="Appearance">
        <div className="flex items-center justify-between">
          <div>
            <Label htmlFor="dark" className="text-sm">
              Dark theme
            </Label>
            <p className="text-xs text-muted-foreground mt-0.5">Ink background with paper-toned text.</p>
          </div>
          <Switch id="dark" checked={darkMode} onCheckedChange={toggleDarkMode} />
        </div>
      </SectionRule>

      <SectionRule title="Account">
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="label-caps">Signed in as</dt>
            <dd className="mt-1">{user?.email ?? "—"}</dd>
          </div>
          <div>
            <dt className="label-caps">Role</dt>
            <dd className="mt-1">{user?.role === "admin" ? "Administrator" : user?.role === "data_entry" ? "Data entry" : "Viewer"}</dd>
          </div>
        </dl>
      </SectionRule>
    </div>
  );
}
