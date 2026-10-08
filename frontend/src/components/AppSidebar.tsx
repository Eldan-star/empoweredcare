import { Link, useLocation } from "react-router-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";

interface NavItem {
  to: string;
  label: string;
}

const surveillance: NavItem[] = [
  { to: "/dashboard", label: "Overview" },
  { to: "/alerts", label: "Alert review" },
  { to: "/vault", label: "Records" },
  { to: "/summary", label: "Weekly summary" },
];

const tools: NavItem[] = [
  { to: "/process", label: "Submit a report" },
  { to: "/query", label: "Ask the data" },
];

const account: NavItem[] = [
  { to: "/profile", label: "Profile" },
  { to: "/settings", label: "Settings" },
];

interface Props {
  open: boolean;
  onClose: () => void;
}

function NavGroup({ title, items, pathname, onNavigate }: { title: string; items: NavItem[]; pathname: string; onNavigate: () => void }) {
  return (
    <div>
      <p className="label-caps px-5 mb-2">{title}</p>
      <ul>
        {items.map((item) => {
          const active = pathname === item.to || (item.to !== "/dashboard" && pathname.startsWith(item.to + "/"));
          return (
            <li key={item.to}>
              <Link
                to={item.to}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "block px-5 py-1.5 text-[0.875rem] border-l-2 transition-colors",
                  active
                    ? "border-foreground font-medium text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function AppSidebar({ open, onClose }: Props) {
  const { pathname } = useLocation();
  const { user } = useAuthStore();
  const admin: NavItem[] = user?.role === "admin" ? [{ to: "/admin", label: "Administration" }] : [];

  return (
    <>
      {open && <div className="fixed inset-0 z-40 bg-foreground/30 lg:hidden" onClick={onClose} aria-hidden />}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-60 shrink-0 bg-sidebar border-r border-sidebar-border flex flex-col",
          "transition-transform duration-200 lg:static lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
        aria-label="Main navigation"
      >
        <div className="px-5 pt-6 pb-5 border-b border-sidebar-border flex items-start justify-between">
          <Link to="/dashboard" onClick={onClose} className="block">
            <span className="block font-serif text-[1.375rem] leading-none">Empowered Care</span>
            <span className="label-caps block mt-2 text-[0.625rem]">Outbreak intelligence · Ethiopia</span>
          </Link>
          <button onClick={onClose} className="lg:hidden -mr-2 p-2 text-muted-foreground hover:text-foreground" aria-label="Close navigation">
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-6 space-y-7">
          <NavGroup title="Surveillance" items={surveillance} pathname={pathname} onNavigate={onClose} />
          <NavGroup title="Tools" items={tools} pathname={pathname} onNavigate={onClose} />
          <NavGroup title="Account" items={[...account, ...admin]} pathname={pathname} onNavigate={onClose} />
        </nav>

        <div className="px-5 py-4 border-t border-sidebar-border">
          <p className="text-[0.8125rem] truncate">{user?.full_name || user?.email || "Signed in"}</p>
          <p className="label-caps text-[0.625rem] mt-1">
            {user?.role === "admin" ? "Administrator" : user?.role === "data_entry" ? "Data entry" : "Viewer"}
          </p>
        </div>
      </aside>
    </>
  );
}
