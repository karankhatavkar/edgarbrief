import { useEffect, useRef, useState } from "react";
import { SentIcon, StopCircleIcon } from "@hugeicons/core-free-icons";
import { Icon } from "@/components/icon";
import { Textarea } from "@/components/ui/textarea";
import type { ChatStatus } from "@/hooks/use-chat";

interface ComposerProps {
  onSend: (text: string) => void;
  status: ChatStatus;
  onStop?: () => void;
  placeholder?: string;
  autoFocus?: boolean;
  /** Blocks input while a thread is being created (home screen). */
  disabled?: boolean;
}

export function Composer({ onSend, status, onStop, placeholder, autoFocus, disabled }: ComposerProps) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  const streaming = status === "streaming";

  // Grow with content up to a cap (fallback for browsers without field-sizing).
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  function submit() {
    const text = value.trim();
    if (!text || streaming || disabled) return;
    onSend(text);
    setValue("");
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="border-t bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto w-full max-w-3xl px-4 py-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          className="rounded-2xl border bg-background shadow-sm transition focus-within:ring-2 focus-within:ring-ring/60"
        >
          <Textarea
            ref={ref}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={placeholder ?? "Ask about the filing…"}
            autoFocus={autoFocus}
            disabled={disabled}
            rows={1}
            className="min-h-[46px] resize-none rounded-none border-0 bg-transparent px-4 py-3 text-[15px] shadow-none focus-visible:border-transparent focus-visible:ring-0 dark:bg-transparent"
          />
          <div className="flex items-center justify-between gap-3 px-3 pb-2.5 pt-0.5">
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              <kbd className="font-sans">⏎</kbd> send · <kbd className="font-sans">⇧⏎</kbd> new line
            </span>
            {streaming ? (
              <button
                type="button"
                onClick={onStop}
                className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium text-foreground transition hover:bg-muted"
              >
                <Icon icon={StopCircleIcon} size={16} /> Stop
              </button>
            ) : (
              <button
                type="submit"
                disabled={!value.trim() || disabled}
                aria-label="Send"
                className="inline-flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground transition hover:opacity-90 disabled:opacity-40"
              >
                <Icon icon={SentIcon} size={17} />
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
