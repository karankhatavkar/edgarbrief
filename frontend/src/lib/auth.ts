import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";

/**
 * Subscribe to the Supabase auth session.
 *
 * `loading` is true until the initial session has been read from storage, so
 * guards can avoid flashing the login page for an already-authenticated user.
 * After that, `onAuthStateChange` keeps `session` in sync across sign-in,
 * sign-out, and silent token refreshes.
 */
export function useSession(): { session: Session | null; loading: boolean } {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
    });

    return () => subscription.subscription.unsubscribe();
  }, []);

  return { session, loading };
}
