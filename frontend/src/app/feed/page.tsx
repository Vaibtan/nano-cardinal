"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, BellRing, Rss, Trash2, Zap } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api } from "@/lib/api-client";
import { subscribeToEvents } from "@/lib/events/event-source";

type Lead = {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  company_name: string | null;
  company_domain: string | null;
  title: string | null;
  icp_score: number | null;
};

type Signal = {
  id: string;
  lead_id: string;
  signal_type: string;
  signal_title: string;
  signal_body: string | null;
  signal_strength: number | null;
  detected_at: string;
  expires_at: string;
  lead: Lead | null;
};

type InboundEvent = {
  id: string;
  source: string;
  event_type: string;
  email: string | null;
  processed: boolean;
  processing_error: string | null;
  created_lead_id: string | null;
  received_at: string;
};

export default function FeedPage() {
  const queryClient = useQueryClient();
  const [topic, setTopic] = useState<"all" | "signals" | "inbound">("all");
  const [liveEvents, setLiveEvents] = useState<string[]>([]);

  const signalsQuery = useQuery({
    queryKey: ["signals"],
    queryFn: () => api.get<Signal[]>("/signals"),
  });

  const inboundQuery = useQuery({
    queryKey: ["inbound-events"],
    queryFn: () => api.get<InboundEvent[]>("/inbound/events", { limit: 20 }),
  });

  const dismissMutation = useMutation({
    mutationFn: (signalId: string) => api.delete(`/signals/${signalId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["signals"] });
    },
  });

  const scanMutation = useMutation({
    mutationFn: () => api.post<{ created: number }>("/signals/mock-scan", {}),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["signals"] });
    },
  });

  useEffect(() => {
    return subscribeToEvents({
      topic: topic === "all" ? undefined : topic,
      onEvent: event => {
        setLiveEvents(prev => [
          `${new Date().toLocaleTimeString()} ${event.type}`,
          ...prev.slice(0, 7),
        ]);
        if (event.type.startsWith("signal.")) {
          void queryClient.invalidateQueries({ queryKey: ["signals"] });
        }
        if (event.type.startsWith("inbound.")) {
          void queryClient.invalidateQueries({ queryKey: ["inbound-events"] });
        }
      },
      onError: () => {
        setLiveEvents(prev => [
          `${new Date().toLocaleTimeString()} SSE reconnecting`,
          ...prev.slice(0, 7),
        ]);
      },
    });
  }, [queryClient, topic]);

  const signals = signalsQuery.data ?? [];
  const inboundEvents = inboundQuery.data ?? [];
  const hotSignals = signals.filter(
    signal => (signal.signal_strength ?? 0) >= 0.8,
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">
            Phase 3
          </p>
          <h2 className="text-3xl font-bold tracking-tight">
            Signal Feed
          </h2>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Live inbound and buying-signal stream with Redis-backed SSE,
            retention filtering, and soft-dismiss workflow.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(["all", "signals", "inbound"] as const).map(value => (
            <Button
              key={value}
              variant={topic === value ? "default" : "outline"}
              onClick={() => setTopic(value)}
            >
              {value}
            </Button>
          ))}
          <Button
            variant="secondary"
            onClick={() => scanMutation.mutate()}
            disabled={scanMutation.isPending}
          >
            <Zap className="size-4" />
            Run Mock Scan
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          icon={<Rss className="size-4" />}
          label="Active Signals"
          value={signals.length}
        />
        <MetricCard
          icon={<BellRing className="size-4" />}
          label="Hot Signals"
          value={hotSignals.length}
        />
        <MetricCard
          icon={<Activity className="size-4" />}
          label="Inbound Events"
          value={inboundEvents.length}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Buying Signals</CardTitle>
            <CardDescription>
              Expired and dismissed signals are hidden by default.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {signals.map(signal => (
              <div
                key={signal.id}
                className="rounded-lg border bg-background p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <Badge variant="secondary">
                      {signal.signal_type}
                    </Badge>
                    <h3 className="mt-2 font-semibold">
                      {signal.signal_title}
                    </h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {signal.signal_body ?? "No additional signal context."}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => dismissMutation.mutate(signal.id)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span>
                    Strength: {Math.round((signal.signal_strength ?? 0) * 100)}
                    %
                  </span>
                  <span>
                    Lead: {signal.lead?.company_name ??
                      signal.lead?.company_domain ??
                      signal.lead?.email ??
                      "Unknown"}
                  </span>
                  <span>
                    Detected {new Date(signal.detected_at).toLocaleString()}
                  </span>
                </div>
              </div>
            ))}
            {!signals.length && (
              <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                No active signals yet. Run a mock scan or send an inbound
                webhook.
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Inbound Audit</CardTitle>
              <CardDescription>
                Recent webhook payloads and processing outcomes.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {inboundEvents.map(event => (
                <div key={event.id} className="rounded-lg border p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{event.source}</span>
                    <Badge
                      variant={event.processing_error ? "destructive" : "outline"}
                    >
                      {event.processing_error ?? event.event_type}
                    </Badge>
                  </div>
                  <p className="mt-1 text-muted-foreground">
                    {event.email ?? "No email"} ·{" "}
                    {event.created_lead_id ? "lead linked" : "audit only"}
                  </p>
                </div>
              ))}
              {!inboundEvents.length && (
                <p className="text-sm text-muted-foreground">
                  No inbound events captured yet.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Live Events</CardTitle>
              <CardDescription>
                SSE notifications from the unified event stream.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                {liveEvents.map((event, index) => (
                  <div key={`${event}-${index}`} className="rounded bg-muted p-2">
                    {event}
                  </div>
                ))}
                {!liveEvents.length && (
                  <p className="text-muted-foreground">
                    Waiting for live events...
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: number;
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
