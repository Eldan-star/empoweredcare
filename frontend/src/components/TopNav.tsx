import { useNavigate } from "react-router-dom";
import { Menu, Moon, Sun } from "lucide-react";
import { useAppStore } from "@/store/appStore";
import { useAuthStore } from "@/store/authStore";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { isoWeek } from "@/components/editorial";
import { useHealth } from "@/hooks/use-health";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface Props {
  onMenuClick: () => void;
}

/** Masthead: week, scope, backend status, and account controls. */
export function TopNav({ onMenuClick }: Props) {
  const { darkMode, toggleDarkMode, notifications, markAllRead } = useAppStore();
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const health = useHealth();
  const unread = notifications.filter((n) => !n.read);
  const { week, year } = isoWeek();

  const handleLogout = () => {
    logout();
    toast.success("Signed out");
    navigate("/login");
  };

  const online = health.isSuccess;
  const statusText = health.isLoading ? "Checking backend" : online ? "Backend online" : "Backend unreachable";

  return (
    <header className="sticky top-0 z-30 bg-background border-b border-border">
      <div className="h-12 flex items-center gap-4 px-4 md:px-8">
        <button onClick={onMenuClick} className="lg:hidden -ml-1 p-1.5 text-muted-foreground hover:text-foreground" aria-label="Open navigation">
          <Menu className="h-5 w-5" />
        </button>

        <div className="flex items-center gap-3 min-w-0 text-[0.8125rem]">
          <span className="num whitespace-nowrap">
            Week {week} · {year}
          </span>
          <span className="hidden sm:inline text-border">|</span>
          <span className="hidden sm:inline text-muted-foreground whitespace-nowrap">National view</span>
        </div>

        <div className="ml-auto flex items-center gap-1">
          <span className="hidden md:inline-flex items-center gap-2 mr-3 text-[0.75rem] text-muted-foreground" role="status">
            <span
              aria-hidden
              className={cn(
                "h-1.5 w-1.5",
                health.isLoading ? "bg-muted-foreground" : online ? "bg-tier-clear" : "bg-tier-red",
              )}
            />
            {statusText}
          </span>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="relative hidden sm:inline-block px-2 py-1 text-[0.8125rem] text-muted-foreground hover:text-foreground" aria-label={`Notifications, ${unread.length} unread`}>
                Notices
                {unread.length > 0 && <span className="num ml-1.5 text-foreground">{unread.length}</span>}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-80">
              <DropdownMenuLabel className="label-caps">This session</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {notifications.length === 0 ? (
                <p className="px-2 py-3 text-sm text-muted-foreground">No notices yet.</p>
              ) : (
                notifications.slice(0, 8).map((n) => (
                  <p key={n.id} className={cn("px-2 py-2 text-sm border-b border-border last:border-0", !n.read && "font-medium")}>
                    {n.message}
                  </p>
                ))
              )}
              {unread.length > 0 && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={markAllRead}>Mark all as read</DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>

          <button
            onClick={toggleDarkMode}
            className="p-2 text-muted-foreground hover:text-foreground"
            aria-label={darkMode ? "Switch to light theme" : "Switch to dark theme"}
          >
            {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="ml-1 pl-3 border-l border-border text-[0.8125rem] hover:underline underline-offset-4 max-w-[7rem] sm:max-w-[10rem] truncate">
                {user?.full_name || user?.email || "Account"}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="font-normal">
                <p className="text-sm">{user?.full_name || "Signed in"}</p>
                <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => navigate("/profile")}>Profile</DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate("/settings")}>Settings</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout} className="text-destructive focus:text-destructive">
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
