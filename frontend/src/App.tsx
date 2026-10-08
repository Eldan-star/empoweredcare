import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { DashboardLayout } from "@/components/DashboardLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import Landing from "@/pages/Landing";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import ForgotPasswordPage from "@/pages/ForgotPasswordPage";
import Dashboard from "@/pages/Dashboard";
import ProcessReport from "@/pages/ProcessReport";
import QueryPage from "@/pages/QueryPage";
import AlertsPage from "@/pages/AlertsPage";
import SummaryPage from "@/pages/SummaryPage";
import SettingsPage from "@/pages/SettingsPage";
import AdminPage from "@/pages/AdminPage";
import ProfilePage from "@/pages/ProfilePage";
import DataVault from "@/pages/DataVault";
import RecordDetailsPage from "@/pages/RecordDetailsPage";
import NotFound from "@/pages/NotFound";
import DataEntryPage from "@/pages/DataEntryPage";
import { useEffect } from "react";
import { useAppStore } from "@/store/appStore";

const queryClient = new QueryClient();

function DarkModeInit() {
  const darkMode = useAppStore((s) => s.darkMode);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
  }, [darkMode]);
  return null;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <DarkModeInit />
      <Sonner />
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />

          {/* Protected dashboard routes */}
          <Route
            element={
              <ProtectedRoute>
                <DashboardLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/process" element={<ProcessReport />} />
            <Route path="/query" element={<QueryPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/summary" element={<SummaryPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/vault" element={<DataVault />} />
            <Route path="/vault/details/:sessionId" element={<RecordDetailsPage />} />
            <Route
              path="/admin"
              element={
                <ProtectedRoute requireAdmin>
                  <AdminPage />
                </ProtectedRoute>
              }
            />
          </Route>

          {/* Data entry portal: data_entry and admin roles */}
          <Route
            path="/data-entry"
            element={
              <ProtectedRoute allowedRoles={["data_entry", "admin"]}>
                <DataEntryPage />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
