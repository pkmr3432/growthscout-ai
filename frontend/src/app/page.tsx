import { PageContainer, SectionHeader, Card, CardTitle, Badge } from "@/components/ui";
import { TrendingUp, Users, FileBarChart, Clock } from "lucide-react";

const stats = [
  { label: "Opportunities Discovered", value: "—", trend: null, icon: TrendingUp },
  { label: "Active Sessions", value: "0", trend: null, icon: Clock },
  { label: "Reports Generated", value: "0", trend: null, icon: FileBarChart },
  { label: "Businesses Analyzed", value: "0", trend: null, icon: Users },
];

export default function DashboardPage() {
  return (
    <PageContainer>
      <SectionHeader
        title="Dashboard"
        description="Your growth intelligence overview"
      />

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-[var(--space-4)] mb-[var(--space-8)]">
        {stats.map((stat) => (
          <Card key={stat.label} className="flex items-start gap-[var(--space-4)]">
            <div className="p-[var(--space-2)] bg-[var(--color-primary-muted)] rounded-[var(--radius-md)]">
              <stat.icon className="w-5 h-5 text-[var(--color-primary)]" aria-hidden="true" />
            </div>
            <div>
              <p className="text-[0.75rem] text-[var(--text-muted)] uppercase tracking-wider font-medium">
                {stat.label}
              </p>
              <p className="text-[1.5rem] font-bold text-[var(--text-primary)] mt-[var(--space-1)]">
                {stat.value}
              </p>
            </div>
          </Card>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-[var(--space-4)]">
        <Card>
          <CardTitle>Quick Actions</CardTitle>
          <p className="text-[0.875rem] text-[var(--text-secondary)] mt-[var(--space-2)]">
            Start a new discovery search or resume a pending review session.
          </p>
          <div className="flex items-center gap-[var(--space-2)] mt-[var(--space-4)]">
            <Badge variant="info">Phase 10.4</Badge>
            <span className="text-[0.75rem] text-[var(--text-muted)]">Feature pages coming soon</span>
          </div>
        </Card>

        <Card>
          <CardTitle>Recent Activity</CardTitle>
          <p className="text-[0.875rem] text-[var(--text-secondary)] mt-[var(--space-2)]">
            Your latest session runs and report exports will appear here.
          </p>
          <div className="flex items-center gap-[var(--space-2)] mt-[var(--space-4)]">
            <Badge variant="info">Phase 10.5</Badge>
            <span className="text-[0.75rem] text-[var(--text-muted)]">Session integration coming soon</span>
          </div>
        </Card>
      </div>
    </PageContainer>
  );
}
