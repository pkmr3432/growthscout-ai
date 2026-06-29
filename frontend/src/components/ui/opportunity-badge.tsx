import { Badge } from "./badge";

interface OpportunityBadgeProps {
  score: number;
  className?: string;
}

export function OpportunityBadge({ score, className = "" }: OpportunityBadgeProps) {
  let variant: "default" | "success" | "warning" | "error" | "info" = "default";

  if (score >= 80) {
    variant = "error"; // High opportunity (red) = High value to pitch
  } else if (score >= 60) {
    variant = "warning"; // Medium opportunity (amber)
  } else {
    variant = "success"; // Low opportunity (green) = Already optimized
  }

  return (
    <Badge variant={variant} className={`font-mono text-[0.8125rem] ${className}`}>
      {score} / 100
    </Badge>
  );
}
