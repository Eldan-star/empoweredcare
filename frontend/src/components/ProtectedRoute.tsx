import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';

interface Props {
  children: React.ReactNode;
  requireAdmin?: boolean;
  /** If set, only these roles may access this route; others are redirected. */
  allowedRoles?: Array<'admin' | 'vw' | 'data_entry'>;
}

export function ProtectedRoute({ children, requireAdmin = false, allowedRoles }: Props) {
  const { isAuthenticated, user } = useAuthStore();
  const location = useLocation();

  // Not logged in → go to login
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // data_entry users should never reach dashboard routes
  if (user?.role === 'data_entry' && !allowedRoles?.includes('data_entry')) {
    return <Navigate to="/data-entry" replace />;
  }

  // requireAdmin check (existing behaviour)
  if (requireAdmin && user?.role !== 'admin') {
    return <Navigate to="/dashboard" replace />;
  }

  // allowedRoles check
  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
