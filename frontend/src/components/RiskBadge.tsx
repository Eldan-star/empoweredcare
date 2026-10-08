import { TierBadge } from "@/components/editorial";

/** Legacy wrapper: renders the editorial tier badge for an LLM risk level. */
export function RiskBadge({ level, className }: { level: string; className?: string }) {
  return <TierBadge level={level} className={className} />;
}
