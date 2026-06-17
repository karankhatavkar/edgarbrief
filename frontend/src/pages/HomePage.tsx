import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { isApiError } from "@/lib/http";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface Me {
  id: string;
  email: string | null;
}

export default function HomePage() {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Me>("/me")
      .then(setMe)
      .catch((err: unknown) => {
        setError(isApiError(err) ? err.message : "Failed to load profile.");
      });
  }, []);

  return (
    <div className="flex min-h-dvh items-center justify-center bg-background px-4 py-10">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="font-heading text-2xl">You're signed in</CardTitle>
          <CardDescription>Verified against the backend via GET /me.</CardDescription>
        </CardHeader>

        <CardContent className="flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          {me && (
            <dl className="text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Email</dt>
                <dd>{me.email ?? "—"}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">User ID</dt>
                <dd className="truncate font-mono text-xs">{me.id}</dd>
              </div>
            </dl>
          )}

          <Button variant="outline" onClick={() => supabase.auth.signOut()}>
            Sign out
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
