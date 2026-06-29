import { PageContainer, SectionHeader, EmptyState } from "@/components/ui";
import { Code2 } from "lucide-react";

export default function DeveloperPage() {
  return (
    <PageContainer>
      <SectionHeader
        title="Developer Hub"
        description="API reference, SDK documentation, and integration guides"
      />
      <EmptyState
        icon={<Code2 className="w-12 h-12" strokeWidth={1.5} />}
        title="Developer Hub Coming Soon"
        description="Access API documentation, SDK installation guides, and integration examples."
      />
    </PageContainer>
  );
}
