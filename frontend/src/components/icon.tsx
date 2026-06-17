import { HugeiconsIcon } from "@hugeicons/react";
import type { IconSvgElement } from "@hugeicons/react";
import { cn } from "@/lib/utils";

/**
 * App-wide icon wrapper. Centralises stroke weight and default size so every
 * glyph reads consistently; pass any icon from `@hugeicons/core-free-icons`.
 */
export function Icon({
  icon,
  size = 18,
  strokeWidth = 1.8,
  className,
}: {
  icon: IconSvgElement;
  size?: number;
  strokeWidth?: number;
  className?: string;
}) {
  return (
    <HugeiconsIcon
      icon={icon}
      size={size}
      strokeWidth={strokeWidth}
      className={cn("shrink-0", className)}
    />
  );
}
