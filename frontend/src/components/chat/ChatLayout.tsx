import { useCallback, useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { AppSidebar } from "@/components/chat/AppSidebar";
import { useSession } from "@/lib/auth";
import { listThreads, createThread as createThreadApi, type Thread } from "@/lib/threads";

/** Shared state handed to chat routes through React Router's outlet context. */
export interface ChatOutletContext {
  threads: Thread[];
  createThread: (title?: string) => Promise<Thread>;
  refreshThreads: () => Promise<void>;
  openSidebar: () => void;
}

async function loadThreads(): Promise<Thread[]> {
  const rows = await listThreads();
  rows.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  return rows;
}

export function ChatLayout() {
  const { session } = useSession();
  const email = session?.user.email ?? null;

  const [threads, setThreads] = useState<Thread[]>([]);
  const [loadingThreads, setLoadingThreads] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);

  const refreshThreads = useCallback(async () => {
    setThreads(await loadThreads());
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadThreads()
      .then((rows) => {
        if (!cancelled) setThreads(rows);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoadingThreads(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const createThread = useCallback(async (title?: string) => {
    const thread = await createThreadApi(title);
    setThreads((prev) => [thread, ...prev]);
    return thread;
  }, []);

  const context: ChatOutletContext = {
    threads,
    createThread,
    refreshThreads,
    openSidebar: () => setMobileOpen(true),
  };

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      <aside className="hidden w-72 shrink-0 border-r md:flex">
        <AppSidebar
          threads={threads}
          loading={loadingThreads}
          createThread={createThread}
          email={email}
        />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-foreground/20 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 w-72 border-r shadow-xl">
            <AppSidebar
              threads={threads}
              loading={loadingThreads}
              createThread={createThread}
              email={email}
              onClose={() => setMobileOpen(false)}
            />
          </aside>
        </div>
      )}

      <main className="flex min-w-0 flex-1 flex-col">
        <Outlet context={context} />
      </main>
    </div>
  );
}
