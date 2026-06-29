import { PageContainer, SectionHeader, EmptyState } from "@/components/ui";
import { Activity } from "lucide-react";

export default function MetricsPage() {
  return (
    <PageContainer>
      <SectionHeader
        title="Metrics"
        description="Platform health and performance monitoring"
      />
      <EmptyState
        icon={<Activity className="w-12 h-12" strokeWidth={1.5} />}
        title="Metrics Dashboard Coming Soon"
        description="Visualize platform health, API usage, and workflow performance metrics."
      />
    </PageContainer>
  );
}
