import { useNavigate } from "react-router-dom";
import { LegalDocument01Icon } from "@hugeicons/core-free-icons";
import { Icon } from "@/components/icon";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="grid min-h-dvh grid-cols-1 md:grid-cols-2">
      {/* Hero image */}
      <div className="h-[52vw] md:h-auto">
        <img
          src="/hero.jpg"
          alt="Professional working at a laptop"
          className="h-full w-full object-cover"
        />
      </div>

      {/* Content panel */}
      <div className="flex flex-col justify-center gap-8 bg-secondary px-10 py-12 md:px-16">
        {/* Wordmark */}
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Icon icon={LegalDocument01Icon} size={22} />
          </div>
          <span className="font-serif text-2xl tracking-tight">EdgarBrief</span>
        </div>

        {/* Tagline */}
        <p className="text-4xl leading-snug text-muted-foreground md:text-5xl">
          Ask SEC filings anything. Get a cited answer back.
        </p>

        {/* CTA */}
        <Button
          size="lg"
          className="w-fit rounded-full bg-brand px-8 text-brand-foreground hover:bg-brand/90"
          onClick={() => navigate("/app")}
        >
          Try EdgarBrief
        </Button>
      </div>
    </div>
  );
}
