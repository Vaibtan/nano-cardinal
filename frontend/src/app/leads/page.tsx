"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api-client";

type Lead = {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  linkedin_url: string | null;
  github_url: string | null;
  twitter_url: string | null;
  company_name: string | null;
  company_domain: string | null;
  company_linkedin_url: string | null;
  company_size: number | null;
  industry: string | null;
  funding_stage: string | null;
  total_funding_usd: number | null;
  tech_stack: string[];
  title: string | null;
  seniority: string | null;
  department: string | null;
  enriched_data: Record<string, unknown> | null;
  enrichment_status: string;
  enrichment_sources: string[];
  enrichment_at: string | null;
  icp_score: number | null;
  icp_id: string | null;
  icp_score_breakdown: Record<string, number> | null;
  outreach_status: string;
  last_contacted_at: string | null;
  source: string;
  inbound_event_id: string | null;
  created_at: string;
  updated_at: string;
};

type LeadFilters = {
  enrichment_status: string;
  outreach_status: string;
  source: string;
  industry: string;
  min_icp_score: string;
  max_icp_score: string;
  signal_type: string;
};

const enrichmentStatuses = ["all", "PENDING", "RUNNING", "COMPLETE", "FAILED"];
const outreachStatuses = ["all", "UNTOUCHED", "IN_SEQUENCE", "REPLIED", "BOUNCED"];
const sources = ["all", "MANUAL", "CSV_IMPORT", "YC_SCRAPER", "INBOUND", "API"];
const signalTypes = [
  "all",
  "funding_round",
  "job_change",
  "leadership_hire",
  "product_launch",
  "hiring_surge",
  "news_mention",
  "tech_stack_change",
  "linkedin_post",
  "product_signup",
  "website_visit",
  "conference_attendance",
];

function statusColor(status: string): string {
  switch (status) {
    case "COMPLETE":
    case "REPLIED":
      return "bg-green-100 text-green-800";
    case "RUNNING":
      return "bg-blue-100 text-blue-800";
    case "FAILED":
    case "BOUNCED":
      return "bg-red-100 text-red-800";
    case "PENDING":
      return "bg-yellow-100 text-yellow-800";
    case "IN_SEQUENCE":
      return "bg-purple-100 text-purple-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
}

function leadName(lead: Lead) {
  const name = `${lead.first_name ?? ""} ${lead.last_name ?? ""}`.trim();
  return name || lead.email || lead.company_name || "Unnamed lead";
}

function EmptySection({ label }: { label: string }) {
  return (
    <div className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
      {label} will populate in later phases.
    </div>
  );
}

function LeadDrawer({
  lead,
  onClose,
  onEnrich,
}: {
  lead: Lead;
  onClose: () => void;
  onEnrich: (id: string) => void;
}) {
  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-xl overflow-y-auto border-l bg-background p-6 shadow-lg">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-xl font-semibold">{leadName(lead)}</h3>
          <p className="text-sm text-muted-foreground">
            {lead.title || "Unknown title"} {lead.company_name ? `at ${lead.company_name}` : ""}
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>

      <Separator className="my-4" />

      <div className="space-y-5 text-sm">
        <section className="space-y-3">
          <h4 className="font-semibold">Enriched Profile</h4>
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-muted-foreground">Email</Label><p>{lead.email || "-"}</p></div>
            <div><Label className="text-muted-foreground">LinkedIn</Label><p>{lead.linkedin_url || "-"}</p></div>
            <div><Label className="text-muted-foreground">Company</Label><p>{lead.company_name || "-"}</p></div>
            <div><Label className="text-muted-foreground">Domain</Label><p>{lead.company_domain || "-"}</p></div>
            <div><Label className="text-muted-foreground">Industry</Label><p>{lead.industry || "-"}</p></div>
            <div><Label className="text-muted-foreground">Company Size</Label><p>{lead.company_size ?? "-"}</p></div>
            <div><Label className="text-muted-foreground">Funding</Label><p>{lead.funding_stage || "-"}</p></div>
            <div><Label className="text-muted-foreground">Department</Label><p>{lead.department || "-"}</p></div>
          </div>
          <div>
            <Label className="text-muted-foreground">Tech Stack</Label>
            <div className="mt-1 flex flex-wrap gap-1">
              {lead.tech_stack.length > 0 ? lead.tech_stack.map((item) => <Badge key={item} variant="secondary">{item}</Badge>) : "-"}
            </div>
          </div>
        </section>

        <Separator />

        <section className="space-y-3">
          <h4 className="font-semibold">Scoring & Status</h4>
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-muted-foreground">ICP Score</Label><p>{lead.icp_score != null ? `${lead.icp_score}%` : "-"}</p></div>
            <div><Label className="text-muted-foreground">ICP ID</Label><p className="break-all">{lead.icp_id || "-"}</p></div>
            <div><Label className="text-muted-foreground">Enrichment</Label><Badge className={statusColor(lead.enrichment_status)}>{lead.enrichment_status}</Badge></div>
            <div><Label className="text-muted-foreground">Outreach</Label><Badge className={statusColor(lead.outreach_status)}>{lead.outreach_status}</Badge></div>
            <div><Label className="text-muted-foreground">Last Contacted</Label><p>{lead.last_contacted_at ? new Date(lead.last_contacted_at).toLocaleString() : "Never"}</p></div>
            <div><Label className="text-muted-foreground">Source</Label><Badge variant="outline">{lead.source}</Badge></div>
          </div>
        </section>

        <Separator />

        <section className="space-y-3">
          <h4 className="font-semibold">Signal Timeline</h4>
          <EmptySection label="Signals from Phase 3" />
        </section>

        <section className="space-y-3">
          <h4 className="font-semibold">Commonality Panel</h4>
          <EmptySection label="Commonality hooks from Phase 4" />
        </section>

        <section className="space-y-3">
          <h4 className="font-semibold">Draft List</h4>
          <EmptySection label="Personalization drafts from Phase 4" />
        </section>

        <section className="space-y-3">
          <h4 className="font-semibold">Sequence Position</h4>
          <EmptySection label="Enrollment state from Phase 5" />
        </section>

        <Separator />

        <Button size="sm" onClick={() => onEnrich(lead.id)} disabled={lead.enrichment_status === "RUNNING"}>
          {lead.enrichment_status === "RUNNING" ? "Enriching..." : "Enrich Lead"}
        </Button>
      </div>
    </div>
  );
}

export default function LeadsPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filters, setFilters] = useState<LeadFilters>({
    enrichment_status: "all",
    outreach_status: "all",
    source: "all",
    industry: "",
    min_icp_score: "",
    max_icp_score: "",
    signal_type: "all",
  });
  const [debouncedIndustry, setDebouncedIndustry] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedIndustry(filters.industry), 300);
    return () => clearTimeout(timer);
  }, [filters.industry]);

  const queryParams = useMemo(
    () => ({
      enrichment_status: filters.enrichment_status === "all" ? undefined : filters.enrichment_status,
      outreach_status: filters.outreach_status === "all" ? undefined : filters.outreach_status,
      source: filters.source === "all" ? undefined : filters.source,
      signal_type: filters.signal_type === "all" ? undefined : filters.signal_type,
      industry: debouncedIndustry || undefined,
      min_icp_score: filters.min_icp_score || undefined,
      max_icp_score: filters.max_icp_score || undefined,
    }),
    [debouncedIndustry, filters],
  );

  const leadsQuery = useQuery({
    queryKey: ["leads", queryParams],
    queryFn: () => api.get<Lead[]>("/leads", queryParams),
  });

  const enrichMutation = useMutation({
    mutationFn: (id: string) => api.post<Lead>(`/leads/${id}/enrich`, {}),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/leads/${id}`),
    onSuccess: async () => {
      setSelectedId(null);
      await queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });

  const leads = leadsQuery.data ?? [];
  const selected = leads.find((lead) => lead.id === selectedId) ?? null;

  function setFilter<K extends keyof LeadFilters>(key: K, value: LeadFilters[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">Lead Board</h2>
        <Button variant="outline" size="sm" onClick={() => leadsQuery.refetch()}>
          Refresh
        </Button>
      </div>

      <Card>
        <CardContent className="grid grid-cols-1 gap-4 p-4 md:grid-cols-4 xl:grid-cols-7">
          <div>
            <Label className="text-xs">Enrichment</Label>
            <Select value={filters.enrichment_status} onValueChange={(value) => setFilter("enrichment_status", value)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{enrichmentStatuses.map((item) => <SelectItem key={item} value={item}>{item === "all" ? "All" : item}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Outreach</Label>
            <Select value={filters.outreach_status} onValueChange={(value) => setFilter("outreach_status", value)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{outreachStatuses.map((item) => <SelectItem key={item} value={item}>{item === "all" ? "All" : item}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Source</Label>
            <Select value={filters.source} onValueChange={(value) => setFilter("source", value)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{sources.map((item) => <SelectItem key={item} value={item}>{item === "all" ? "All" : item}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Signal Type</Label>
            <Select value={filters.signal_type} onValueChange={(value) => setFilter("signal_type", value)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{signalTypes.map((item) => <SelectItem key={item} value={item}>{item === "all" ? "All" : item.replaceAll("_", " ")}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Industry</Label>
            <Input value={filters.industry} onChange={(event) => setFilter("industry", event.target.value)} placeholder="SaaS" />
          </div>
          <div>
            <Label className="text-xs">Min ICP</Label>
            <Input type="number" min={0} max={100} value={filters.min_icp_score} onChange={(event) => setFilter("min_icp_score", event.target.value)} />
          </div>
          <div>
            <Label className="text-xs">Max ICP</Label>
            <Input type="number" min={0} max={100} value={filters.max_icp_score} onChange={(event) => setFilter("max_icp_score", event.target.value)} />
          </div>
        </CardContent>
      </Card>

      {leadsQuery.isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : leads.length === 0 ? (
        <p className="text-muted-foreground">No leads found. Import some via CSV or YC import.</p>
      ) : (
        <div className="overflow-hidden rounded-md border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="p-3 text-left font-medium">Name</th>
                <th className="p-3 text-left font-medium">Company</th>
                <th className="p-3 text-left font-medium">Source</th>
                <th className="p-3 text-left font-medium">ICP Score</th>
                <th className="p-3 text-left font-medium">Enrichment</th>
                <th className="p-3 text-left font-medium">Outreach</th>
                <th className="p-3 text-left font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((lead) => (
                <tr key={lead.id} className="cursor-pointer border-b hover:bg-muted/30" onClick={() => setSelectedId(lead.id)}>
                  <td className="p-3">{leadName(lead)}</td>
                  <td className="p-3">{lead.company_name || "-"}</td>
                  <td className="p-3"><Badge variant="outline">{lead.source}</Badge></td>
                  <td className="p-3">
                    {lead.icp_score != null ? (
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-20 rounded-full bg-muted">
                          <div className="h-2 rounded-full bg-primary" style={{ width: `${Math.min(lead.icp_score, 100)}%` }} />
                        </div>
                        <span className="text-xs">{lead.icp_score}%</span>
                      </div>
                    ) : "-"}
                  </td>
                  <td className="p-3"><Badge className={statusColor(lead.enrichment_status)}>{lead.enrichment_status}</Badge></td>
                  <td className="p-3"><Badge className={statusColor(lead.outreach_status)}>{lead.outreach_status}</Badge></td>
                  <td className="p-3">
                    <div className="flex gap-1" onClick={(event) => event.stopPropagation()}>
                      <Button size="sm" variant="ghost" onClick={() => enrichMutation.mutate(lead.id)}>Enrich</Button>
                      <Button size="sm" variant="ghost" className="text-destructive" onClick={() => deleteMutation.mutate(lead.id)}>Delete</Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <LeadDrawer
          lead={selected}
          onClose={() => setSelectedId(null)}
          onEnrich={(id) => enrichMutation.mutate(id)}
        />
      )}
    </div>
  );
}
