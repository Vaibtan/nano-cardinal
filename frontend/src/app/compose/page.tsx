"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";
import { CheckCircle2, PenLine, RadioTower } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api-client";

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

type SignalItem = {
  id: string;
  lead_id: string;
  signal_type: string;
  signal_title: string;
  signal_strength: number | null;
};

type Draft = {
  id: string;
  lead_id: string;
  subject_line: string | null;
  email_body: string | null;
  linkedin_message: string | null;
  personalization_hook: string | null;
  hook_type: string | null;
  hook_strength: number | null;
  signal_used: string | null;
  critique_score: number | null;
  critique_breakdown: Record<string, number> | null;
  generation_iterations: number;
  status: string;
  created_at: string;
};

export default function ComposePage() {
  const queryClient = useQueryClient();
  const [isMounted, setIsMounted] = useState(false);
  const [selectedLeadId, setSelectedLeadId] = useState("");
  const [leadSearch, setLeadSearch] = useState("");
  const [selectedSignalId, setSelectedSignalId] = useState("");
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [streamedText, setStreamedText] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");
  const [editLinkedIn, setEditLinkedIn] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const leadsQuery = useQuery({
    queryKey: ["leads", "compose"],
    queryFn: () => api.get<Lead[]>("/leads", { limit: 100 }),
  });

  const signalsQuery = useQuery({
    queryKey: ["signals", "compose"],
    queryFn: () => api.get<SignalItem[]>("/signals", { limit: 200 }),
  });

  const draftsQuery = useQuery({
    queryKey: ["drafts"],
    queryFn: () => api.get<Draft[]>("/personalization/drafts"),
  });

  const generateMutation = useMutation({
    mutationFn: (leadId: string) =>
      api.post<Draft>("/personalization/generate", {
        lead_id: leadId,
        signal_id: selectedSignalId || null,
      }),
    onSuccess: draft => {
      setSelectedDraftId(draft.id);
      setNotice("Draft generated.");
      void queryClient.invalidateQueries({ queryKey: ["drafts"] });
    },
  });

  const approveMutation = useMutation({
    mutationFn: (draftId: string) =>
      api.post<Draft>(`/personalization/drafts/${draftId}/approve`, {}),
    onSuccess: draft => {
      setSelectedDraftId(draft.id);
      setNotice("Draft approved.");
      void queryClient.invalidateQueries({ queryKey: ["drafts"] });
    },
  });

  const patchMutation = useMutation({
    mutationFn: (draftId: string) =>
      api.patch<Draft>(`/personalization/drafts/${draftId}`, {
        subject_line: editSubject,
        email_body: editBody,
        linkedin_message: editLinkedIn,
      }),
    onSuccess: draft => {
      setSelectedDraftId(draft.id);
      setIsEditing(false);
      setNotice("Draft saved.");
      void queryClient.invalidateQueries({ queryKey: ["drafts"] });
    },
  });

  const leads = (leadsQuery.data ?? []).filter(lead => {
    const haystack = [
      lead.company_name,
      lead.company_domain,
      lead.email,
      lead.title,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(leadSearch.toLowerCase());
  });
  const drafts = draftsQuery.data ?? [];
  const selectedDraft =
    drafts.find(draft => draft.id === selectedDraftId) ?? drafts[0];
  const selectedLead = leads.find(lead => lead.id === selectedLeadId);
  const leadSignals = (signalsQuery.data ?? []).filter(
    signal => signal.lead_id === selectedLeadId,
  );
  const radarData = buildRadarData(selectedDraft);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (!selectedDraft || isEditing) return;
    setEditSubject(selectedDraft.subject_line ?? "");
    setEditBody(selectedDraft.email_body ?? "");
    setEditLinkedIn(selectedDraft.linkedin_message ?? "");
  }, [selectedDraft, isEditing]);

  async function streamDraft(draftId: string): Promise<void> {
    setStreamedText("");
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const source = new EventSource(
      `${base}/api/v1/personalization/drafts/${draftId}/stream`,
    );
    source.addEventListener("draft.token", message => {
      const event = JSON.parse((message as MessageEvent<string>).data) as {
        payload: { token: string };
      };
      setStreamedText(prev => `${prev}${event.payload.token}`);
    });
    source.addEventListener("error", () => {
      source.close();
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium text-muted-foreground">Phase 4</p>
        <h2 className="text-3xl font-bold tracking-tight">AI Composer</h2>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Executable LangGraph draft generation with commonality hooks, RAG
          snippets, bounded critique/rewrite, approval, and SSE token
          streaming.
        </p>
      </div>

      {notice && (
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">
          {notice}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[360px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Generate</CardTitle>
            <CardDescription>
              Pick a lead, optionally pin a signal, then create a draft.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              placeholder="Search leads by company, email, or title"
              value={leadSearch}
              onChange={event => setLeadSearch(event.target.value)}
            />
            <select
              className="h-10 w-full rounded-md border bg-background px-3 text-sm"
              value={selectedLeadId}
              onChange={event => {
                setSelectedLeadId(event.target.value);
                setSelectedSignalId("");
              }}
            >
              <option value="">Select a lead</option>
              {leads.map(lead => (
                <option key={lead.id} value={lead.id}>
                  {lead.company_name ??
                    lead.company_domain ??
                    lead.email ??
                    lead.id}
                </option>
              ))}
            </select>
            <select
              className="h-10 w-full rounded-md border bg-background px-3 text-sm"
              value={selectedSignalId}
              onChange={event => setSelectedSignalId(event.target.value)}
              disabled={!selectedLeadId}
            >
              <option value="">Auto-pick strongest signal</option>
              {leadSignals.map(signal => (
                <option key={signal.id} value={signal.id}>
                  {signal.signal_type}: {signal.signal_title}
                </option>
              ))}
            </select>
            <Button
              className="w-full"
              disabled={!selectedLeadId || generateMutation.isPending}
              onClick={() => generateMutation.mutate(selectedLeadId)}
            >
              <PenLine className="size-4" />
              Generate Draft
            </Button>
            {selectedLead && (
              <div className="rounded-lg border bg-muted/40 p-3 text-sm">
                <p className="font-medium">
                  {selectedLead.company_name ??
                    selectedLead.company_domain ??
                    "Selected lead"}
                </p>
                <p className="text-muted-foreground">
                  {selectedLead.title ?? "Unknown title"} · ICP{" "}
                  {selectedLead.icp_score ?? "n/a"}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <Card>
            <CardHeader className="flex flex-row items-start justify-between">
              <div>
                <CardTitle>Draft Workspace</CardTitle>
                <CardDescription>
                  Review, edit, approve, and stream the selected draft.
                </CardDescription>
              </div>
              {selectedDraft && <Badge>{selectedDraft.status}</Badge>}
            </CardHeader>
            <CardContent>
              {selectedDraft ? (
                <div className="space-y-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Subject</p>
                    {isEditing ? (
                      <Input
                        value={editSubject}
                        onChange={event => setEditSubject(event.target.value)}
                      />
                    ) : (
                      <h3 className="text-xl font-semibold">
                        {selectedDraft.subject_line}
                      </h3>
                    )}
                  </div>
                  {isEditing ? (
                    <Textarea
                      className="min-h-56"
                      value={editBody}
                      onChange={event => setEditBody(event.target.value)}
                    />
                  ) : (
                    <div className="whitespace-pre-wrap rounded-xl border bg-background p-4">
                      {selectedDraft.email_body}
                    </div>
                  )}
                  <div className="rounded-xl border bg-muted/40 p-4">
                    <p className="mb-2 text-sm font-medium">
                      LinkedIn variant
                    </p>
                    {isEditing ? (
                      <Textarea
                        value={editLinkedIn}
                        onChange={event => setEditLinkedIn(event.target.value)}
                      />
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        {selectedDraft.linkedin_message}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {isEditing ? (
                      <Button
                        variant="outline"
                        disabled={patchMutation.isPending}
                        onClick={() => patchMutation.mutate(selectedDraft.id)}
                      >
                        Save Edits
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        disabled={selectedDraft.status !== "DRAFT"}
                        onClick={() => setIsEditing(true)}
                      >
                        Edit
                      </Button>
                    )}
                    <Button
                      onClick={() => approveMutation.mutate(selectedDraft.id)}
                      disabled={approveMutation.isPending}
                    >
                      <CheckCircle2 className="size-4" />
                      Approve
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => void streamDraft(selectedDraft.id)}
                    >
                      <RadioTower className="size-4" />
                      Stream Tokens
                    </Button>
                  </div>
                  {streamedText && (
                    <div className="rounded-xl border border-primary/30 bg-primary/5 p-4">
                      <p className="mb-2 text-sm font-medium">
                        Streaming output
                      </p>
                      <p className="whitespace-pre-wrap text-sm">
                        {streamedText}
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground">
                  No drafts yet. Generate one from a lead.
                </div>
              )}
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Commonality</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <p className="rounded-lg border bg-background p-3">
                  {selectedDraft?.personalization_hook ??
                    "No strong commonality found. The composer falls back to signal/company context."}
                </p>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Hook type</span>
                  <Badge variant="outline">
                    {selectedDraft?.hook_type ?? "none"}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Strength</span>
                  <span>
                    {Math.round((selectedDraft?.hook_strength ?? 0) * 100)}%
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Quality Radar</CardTitle>
              </CardHeader>
              <CardContent className="h-64">
                {isMounted && (
                  <ResponsiveContainer
                    width="100%"
                    height="100%"
                    minHeight={220}
                  >
                    <RadarChart data={radarData}>
                      <PolarGrid />
                      <PolarAngleAxis dataKey="axis" />
                      <PolarRadiusAxis domain={[0, 10]} />
                      <Radar
                        dataKey="score"
                        fill="var(--primary)"
                        fillOpacity={0.25}
                        stroke="var(--primary)"
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Draft History</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {drafts.map(draft => (
            <button
              key={draft.id}
              className="rounded-lg border p-4 text-left transition hover:border-primary"
              onClick={() => setSelectedDraftId(draft.id)}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium">
                  {draft.subject_line ?? "Untitled draft"}
                </span>
                <Badge variant="secondary">{draft.status}</Badge>
              </div>
              <p className="mt-2 line-clamp-3 text-sm text-muted-foreground">
                {draft.email_body}
              </p>
            </button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function buildRadarData(draft?: Draft) {
  const breakdown = draft?.critique_breakdown ?? {};
  return [
    { axis: "Specificity", score: breakdown.specificity ?? 0 },
    { axis: "Relevance", score: breakdown.relevance ?? 0 },
    { axis: "Tone", score: breakdown.tone ?? 0 },
    { axis: "CTA", score: breakdown.cta_clarity ?? 0 },
    { axis: "Subject", score: breakdown.subject_line ?? 0 },
  ];
}
