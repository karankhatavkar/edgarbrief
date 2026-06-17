import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useSession } from "@/lib/auth";

/**
 * Gate routes that require a signed-in user. Renders nothing while the initial
 * session check is in flight, redirects to /auth when there is no session, and
 * otherwise renders the protected page.
 */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { session, loading } = useSession();

  if (loading) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-muted-foreground">
        Loading…
      </div>
    );
  }

  if (!session) {
    return <Navigate to="/auth" replace />;
  }

  return <>{children}</>;
}
