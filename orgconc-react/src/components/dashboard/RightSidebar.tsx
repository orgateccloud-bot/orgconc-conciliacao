import type { ActivityFeedItem, TrustScore } from "@/lib/api";
import { ActivityFeed } from "./ActivityFeed";
import { IndicadoresGoals } from "./IndicadoresGoals";

interface Props {
  activity: ActivityFeedItem[];
  trust: TrustScore | null;
}

/** Sidebar direita do dashboard — feed de atividade auditada + indicadores. */
export function RightSidebar({ activity, trust }: Props) {
  return (
    <>
      <ActivityFeed data={activity} />
      <IndicadoresGoals trust={trust} />
    </>
  );
}
