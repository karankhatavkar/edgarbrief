import {
  Menu01Icon,
  LegalDocument01Icon,
  ChartLineData02Icon,
  File01Icon,
  SparklesIcon,
} from "@hugeicons/core-free-icons";
import type { IconSvgElement } from "@hugeicons/react";
import { Icon } from "@/components/icon";
import { Composer } from "@/components/chat/Composer";

const EXAMPLES: { icon: IconSvgElement; label: string }[] = [
  { icon: LegalDocument01Icon, label: "Summarize the risk factors in the latest 10-K" },
  { icon: ChartLineData02Icon, label: "What changed in the MD&A quarter over quarter?" },
  { icon: File01Icon, label: "List the related-party transactions disclosed" },
  { icon: SparklesIcon, label: "Flag any going-concern language" },
];

interface EmptyStateProps {
  onStart: (text: string) => void;
  starting: boolean;
  onOpenSidebar: () => void;
}

export function EmptyState({ onStart, starting, onOpenSidebar }: EmptyStateProps) {
  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-2 border-b px-4 py-3 md:hidden">
        <button onClick={onOpenSidebar} aria-label="Open menu" className="rounded-md p-1.5 hover:bg-muted">
          <Icon icon={Menu01Icon} size={20} />
        </button>
        <span className="font-serif text-base">EdgarBrief</span>
      </header>

      <div className="ledger-canvas flex min-h-0 flex-1 items-center overflow-y-auto">
        <div className="mx-auto w-full max-w-2xl px-5 py-10">
          <p
            className="animate-message-in font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground"
            style={{ animationDelay: "0ms" }}
          >
            A new brief
          </p>
          <h1
            className="animate-message-in mt-3 font-serif text-4xl leading-tight tracking-tight text-foreground sm:text-5xl"
            style={{ animationDelay: "60ms" }}
          >
            Interrogate the filing.
          </h1>
          <p
            className="animate-message-in mt-3 max-w-md text-[15px] leading-relaxed text-muted-foreground"
            style={{ animationDelay: "120ms" }}
          >
            Ask a question to open a new conversation. EdgarBrief reads the source documents and
            answers with citations.
          </p>

          <div className="mt-8 grid gap-2.5 sm:grid-cols-2">
            {EXAMPLES.map((example, i) => (
              <button
                key={example.label}
                disabled={starting}
                onClick={() => onStart(example.label)}
                style={{ animationDelay: `${180 + i * 60}ms` }}
                className="animate-message-in group flex items-start gap-3 rounded-xl border bg-card/60 p-3.5 text-left transition hover:border-foreground/30 hover:bg-card disabled:opacity-50"
              >
                <span className="mt-0.5 text-muted-foreground transition group-hover:text-foreground">
                  <Icon icon={example.icon} size={18} />
                </span>
                <span className="text-sm leading-snug text-foreground/90">{example.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <Composer
        onSend={onStart}
        status="idle"
        placeholder="Ask about a filing to start a new brief…"
        autoFocus
        disabled={starting}
      />
    </div>
  );
}
