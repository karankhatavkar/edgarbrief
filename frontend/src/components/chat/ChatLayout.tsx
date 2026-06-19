import { useCallback, useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { AppSidebar } from "@/components/chat/AppSidebar";
import { useSession } from "@/lib/auth";
import { listThreads, createThread as createThreadApi, type Thread } from "@/lib/threads";

const SIDEBAR_MIN = 180;
const SIDEBAR_MAX = 400;
const SIDEBAR_DEFAULT = 288;

function getSavedSidebarWidth(): number {
  const saved = localStorage.getItem("sidebar-width");
  if (!saved) return SIDEBAR_DEFAULT;
  const n = parseInt(saved, 10);
  return Number.isFinite(n) ? Math.min(Math.max(n, SIDEBAR_MIN), SIDEBAR_MAX) : SIDEBAR_DEFAULT;
}

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
  const [sidebarWidth, setSidebarWidth] = useState(getSavedSidebarWidth);

  function handleResizeStart(e: React.MouseEvent) {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = sidebarWidth;
    let currentWidth = startWidth;

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    function onMove(ev: MouseEvent) {
      currentWidth = Math.min(Math.max(startWidth + ev.clientX - startX, SIDEBAR_MIN), SIDEBAR_MAX);
      setSidebarWidth(currentWidth);
    }

    function onUp() {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      localStorage.setItem("sidebar-width", String(currentWidth));
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

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
      <aside
        className="relative hidden shrink-0 border-r md:flex"
        style={{ width: sidebarWidth }}
      >
        <AppSidebar
          threads={threads}
          loading={loadingThreads}
          createThread={createThread}
          email={email}
        />
        <div
          onMouseDown={handleResizeStart}
          aria-hidden
          className="absolute inset-y-0 right-0 w-1 cursor-col-resize hover:bg-primary/30 active:bg-primary/50"
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
