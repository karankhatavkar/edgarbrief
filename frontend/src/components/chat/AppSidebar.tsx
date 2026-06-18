import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  PencilEdit02Icon,
  Logout03Icon,
  LegalDocument01Icon,
  Cancel01Icon,
} from "@hugeicons/core-free-icons";
import { Icon } from "@/components/icon";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { supabase } from "@/lib/supabase";
import { shortAgo } from "@/lib/format";
import type { Thread } from "@/lib/threads";

interface AppSidebarProps {
  threads: Thread[];
  loading: boolean;
  createThread: (title?: string) => Promise<Thread>;
  email: string | null;
  /** Present only inside the mobile drawer; renders a close control. */
  onClose?: () => void;
}

export function AppSidebar({ threads, loading, createThread, email, onClose }: AppSidebarProps) {
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);

  async function newBrief() {
    if (creating) return;
    setCreating(true);
    try {
      const thread = await createThread();
      onClose?.();
      navigate(`/c/${thread.id}`);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="flex h-full w-full flex-col bg-sidebar text-sidebar-foreground">
      {/* Wordmark */}
      <div className="flex items-center gap-2.5 px-4 pb-3 pt-4">
        <div className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Icon icon={LegalDocument01Icon} size={17} />
        </div>
        <div className="min-w-0 leading-tight">
          <div className="font-serif text-[17px] tracking-tight">EdgarBrief</div>
          <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground">
            Filings, distilled
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            aria-label="Close menu"
            className="ml-auto rounded-md p-1.5 text-muted-foreground hover:bg-sidebar-accent md:hidden"
          >
            <Icon icon={Cancel01Icon} size={18} />
          </button>
        )}
      </div>

      <div className="px-3 pb-2">
        <Button onClick={newBrief} disabled={creating} className="w-full justify-start gap-2">
          <Icon icon={PencilEdit02Icon} size={16} />
          {creating ? "Starting…" : "New brief"}
        </Button>
      </div>

      <div className="px-4 pb-1 pt-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
          Conversations
        </span>
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        {loading ? (
          <div className="flex flex-col gap-1 px-1">
            {[70, 55, 64].map((w, i) => (
              <Skeleton key={i} className="h-8 rounded-md" style={{ width: `${w}%` }} />
            ))}
          </div>
        ) : threads.length === 0 ? (
          <p className="px-2 py-6 text-center text-sm text-muted-foreground">No briefs yet.</p>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {threads.map((thread) => (
              <li key={thread.id}>
                <NavLink
                  to={`/c/${thread.id}`}
                  onClick={onClose}
                  className={({ isActive }) =>
                    cn(
                      "group flex items-center gap-2 rounded-md border-l-2 px-2.5 py-2 text-sm transition-colors",
                      isActive
                        ? "border-l-foreground bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                        : "border-transparent text-sidebar-foreground/80 hover:bg-sidebar-accent/60",
                    )
                  }
                >
                  <span className="min-w-0 flex-1 truncate">{thread.title || "Untitled brief"}</span>
                  <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                    {shortAgo(thread.updated_at)}
                  </span>
                </NavLink>
              </li>
            ))}
          </ul>
        )}
      </nav>

      <div className="mt-auto flex items-center gap-2 border-t px-3 py-3">
        <div className="flex size-7 items-center justify-center rounded-full bg-muted font-mono text-[11px] uppercase text-muted-foreground">
          {(email ?? "?").slice(0, 1)}
        </div>
        <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground">
          {email ?? "Signed in"}
        </span>
        <button
          onClick={() => supabase.auth.signOut()}
          aria-label="Sign out"
          title="Sign out"
          className="rounded-md p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
        >
          <Icon icon={Logout03Icon} size={17} />
        </button>
      </div>
    </div>
  );
}
