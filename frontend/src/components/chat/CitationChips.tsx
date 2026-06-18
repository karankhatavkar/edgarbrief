import { badgeVariants } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { filingLabel, locationLabel, type SourcePassage } from "@/lib/citations";

interface CitationChipsProps {
  passages: SourcePassage[];
  onSelect: (passage: SourcePassage) => void;
}

/**
 * The source ledger under a grounded answer: one numbered pill per cited
 * passage. Clicking a pill opens its filing excerpt for verification.
 */
export function CitationChips({ passages, onSelect }: CitationChipsProps) {
  if (passages.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
        Sources
      </span>
      <TooltipProvider delayDuration={150}>
        <ul className="flex flex-wrap gap-1.5">
          {passages.map((passage, i) => {
            const where = locationLabel(passage);
            return (
              <li key={passage.chunk_id}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      onClick={() => onSelect(passage)}
                      className={cn(
                        badgeVariants({ variant: "outline" }),
                        "h-6 cursor-pointer gap-1.5 px-2 hover:bg-muted focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50",
                      )}
                    >
                      <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                        {i + 1}
                      </span>
                      <span className="font-medium">{passage.ticker}</span>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {filingLabel(passage)}
                    {where && ` · ${where}`}
                  </TooltipContent>
                </Tooltip>
              </li>
            );
          })}
        </ul>
      </TooltipProvider>
    </div>
  );
}
