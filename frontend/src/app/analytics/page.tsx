"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartNoAxesColumn, Inbox, MailCheck, Signal } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api } from "@/lib/api-client";

type Dashboard = {
  overview: {
    total_leads: number;
    enriched_leads: number;
    active_signals: number;
    inbound_events_30d: number;
    active_sequences: number;
    reply_rate: number;
    bounce_rate: number;
  };
  funnel: {
    stages: { stage: string; count: number }[];
  };
  signals: {
    total_active: number;
    by_type: Record<string, number>;
    average_strength: number | null;
  };
  inbound: {
    total_events: number;
    created_leads: number;
    conversion_rate: number;
    by_source: Record<string, number>;
  };
  sequence_summaries: {
    sequence_id: string;
    enrollments: number;
    active: number;
    completed: number;
    replied: number;
    bounced: number;
  }[];
  personalization: {
    total_drafts: number;
    approved_drafts: number;
    sent_drafts: number;
    average_critique_score: number | null;
  };
};

type TamSummary = {
  captured_leads: number;
  industries: number;
  average_icp_score: number | null;
};

type Lead = {
  id: string;
  icp_score: number | null;
};

type Draft = {
  id: string;
  critique_score: number | null;
  token_usage: {
    prompt_tokens?: number;
    completion_tokens?: number;
  } | null;
  created_at: string;
};

const COLORS = ["#0f766e", "#ea580c", "#2563eb", "#9333ea", "#475569"];

export default function AnalyticsPage() {
  const [isMounted, setIsMounted] = useState(false);
  const dashboardQuery = useQuery({
    queryKey: ["analytics-dashboard"],
    queryFn: () => api.get<Dashboard>("/analytics/dashboard"),
  });
  const tamQuery = useQuery({
    queryKey: ["analytics-tam"],
    queryFn: () => api.get<TamSummary>("/analytics/tam"),
  });
  const leadsQuery = useQuery({
    queryKey: ["analytics-leads"],
    queryFn: () => api.get<Lead[]>("/leads", { limit: 200 }),
  });
  const draftsQuery = useQuery({
    queryKey: ["analytics-drafts"],
    queryFn: () => api.get<Draft[]>("/personalization/drafts"),
  });

  const dashboard = dashboardQuery.data;
  const tam = tamQuery.data;
  const leads = leadsQuery.data ?? [];
  const drafts = draftsQuery.data ?? [];
  const signalData = Object.entries(dashboard?.signals.by_type ?? {}).map(
    ([name, value]) => ({ name, value }),
  );
  const inboundData = Object.entries(dashboard?.inbound.by_source ?? {}).map(
    ([name, value]) => ({ name, value }),
  );
  const icpHistogram = buildIcpHistogram(leads);
  const tokenUsage = drafts.reduce(
    (acc, draft) =>
      acc +
      (draft.token_usage?.prompt_tokens ?? 0) +
      (draft.token_usage?.completion_tokens ?? 0),
    0,
  );
  const estimatedCost = (tokenUsage / 1_000_000) * 1.5;
  const qualityTrend = drafts
    .slice(0, 10)
    .reverse()
    .map((draft, index) => ({
      name: `${index + 1}`,
      score: draft.critique_score ?? 0,
    }));

  useEffect(() => {
    setIsMounted(true);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium text-muted-foreground">Phase 6</p>
        <h2 className="text-3xl font-bold tracking-tight">Analytics</h2>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          End-to-end GTM dashboard covering TAM, signals, inbound conversion,
          sequence execution, and personalization quality.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Metric
          icon={<ChartNoAxesColumn className="size-4" />}
          label="Total Leads"
          value={dashboard?.overview.total_leads ?? 0}
        />
        <Metric
          icon={<Signal className="size-4" />}
          label="Active Signals"
          value={dashboard?.overview.active_signals ?? 0}
        />
        <Metric
          icon={<Inbox className="size-4" />}
          label="Inbound 30d"
          value={dashboard?.overview.inbound_events_30d ?? 0}
        />
        <Metric
          icon={<MailCheck className="size-4" />}
          label="Reply Rate"
          value={`${Math.round((dashboard?.overview.reply_rate ?? 0) * 100)}%`}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Metric
          icon={<ChartNoAxesColumn className="size-4" />}
          label="TAM Captured"
          value={tam?.captured_leads ?? 0}
        />
        <Metric
          icon={<ChartNoAxesColumn className="size-4" />}
          label="Industries"
          value={tam?.industries ?? 0}
        />
        <Metric
          icon={<PenCostIcon />}
          label="Tokens Used"
          value={tokenUsage}
        />
        <Metric
          icon={<PenCostIcon />}
          label="Est. Cost"
          value={`$${estimatedCost.toFixed(3)}`}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Funnel</CardTitle>
            <CardDescription>
              Lead progression through the outbound pipeline.
            </CardDescription>
          </CardHeader>
          <CardContent className="h-80">
            {isMounted && (
              <ResponsiveContainer width="100%" height="100%" minHeight={260}>
                <BarChart data={dashboard?.funnel.stages ?? []}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="stage" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#0f766e" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Signal Mix</CardTitle>
            <CardDescription>
              Active signal distribution by type.
            </CardDescription>
          </CardHeader>
          <CardContent className="h-80">
            {isMounted && (
              <ResponsiveContainer width="100%" height="100%" minHeight={260}>
                <PieChart>
                  <Pie
                    data={signalData}
                    dataKey="value"
                    nameKey="name"
                    outerRadius={105}
                    label
                  >
                    {signalData.map((entry, index) => (
                      <Cell
                        key={entry.name}
                        fill={COLORS[index % COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_1fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Inbound Sources</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            {isMounted && (
              <ResponsiveContainer width="100%" height="100%" minHeight={220}>
                <BarChart data={inboundData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#ea580c" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sequences</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(dashboard?.sequence_summaries ?? []).map(sequence => (
              <div key={sequence.sequence_id} className="rounded-lg border p-3">
                <p className="font-medium">
                  {sequence.sequence_id.slice(0, 8)}
                </p>
                <div className="mt-2 grid grid-cols-5 gap-2 text-center text-xs">
                  <Stat label="All" value={sequence.enrollments} />
                  <Stat label="Active" value={sequence.active} />
                  <Stat label="Done" value={sequence.completed} />
                  <Stat label="Reply" value={sequence.replied} />
                  <Stat label="Bounce" value={sequence.bounced} />
                </div>
              </div>
            ))}
            {!dashboard?.sequence_summaries.length && (
              <p className="text-sm text-muted-foreground">
                No sequence activity yet.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Personalization</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Stat
              label="Drafts"
              value={dashboard?.personalization.total_drafts ?? 0}
            />
            <Stat
              label="Approved"
              value={dashboard?.personalization.approved_drafts ?? 0}
            />
            <Stat
              label="Sent"
              value={dashboard?.personalization.sent_drafts ?? 0}
            />
            <Stat
              label="Avg critique"
              value={
                dashboard?.personalization.average_critique_score?.toFixed(1) ??
                "n/a"
              }
            />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>ICP Score Histogram</CardTitle>
            <CardDescription>
              Distribution of account fit across the visible lead pool.
            </CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {isMounted && (
              <ResponsiveContainer width="100%" height="100%" minHeight={220}>
                <BarChart data={icpHistogram}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="bucket" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#2563eb" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Personalization Quality</CardTitle>
            <CardDescription>
              Recent critique score trend from generated drafts.
            </CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {isMounted && (
              <ResponsiveContainer width="100%" height="100%" minHeight={220}>
                <BarChart data={qualityTrend}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis domain={[0, 10]} />
                  <Tooltip />
                  <Bar dataKey="score" fill="#9333ea" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function buildIcpHistogram(leads: Lead[]) {
  const buckets = [
    { bucket: "0-20", count: 0 },
    { bucket: "21-40", count: 0 },
    { bucket: "41-60", count: 0 },
    { bucket: "61-80", count: 0 },
    { bucket: "81-100", count: 0 },
  ];
  for (const lead of leads) {
    const score = lead.icp_score ?? 0;
    const index = Math.min(Math.floor(score / 20), 4);
    buckets[index].count += 1;
  }
  return buckets;
}

function PenCostIcon() {
  return <MailCheck className="size-4" />;
}

function Metric({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: number | string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between pt-0">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-3xl font-bold">{value}</p>
        </div>
        <div className="rounded-full bg-primary/10 p-3 text-primary">
          {icon}
        </div>
      </CardContent>
    </Card>
  );
}

function Stat({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  );
}
