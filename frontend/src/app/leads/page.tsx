"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api-client";

/* ── Types ─────────────────────────────────────────────── */

interface Lead {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  company_name: string | null;
  company_domain: string | null;
  title: string | null;
  industry: string | null;
  company_size: number | null;
  tech_stack: string[];
  enrichment_status: string;
  enrichment_sources: string[];
  icp_score: number | null;
  outreach_status: string;
  source: string;
  created_at: string;
  updated_at: string;
}

const ENRICHMENT_STATUSES = ["", "PENDING", "RUNNING", "COMPLETE", "FAILED"];
const OUTREACH_STATUSES = ["", "UNTOUCHED", "IN_SEQUENCE", "REPLIED", "BOUNCED"];
const SOURCES = ["", "MANUAL", "CSV_IMPORT", "YC_SCRAPER", "INBOUND", "API"];

function statusColor(status: string): string {
  switch (status) {
    case "COMPLETE":
      return "bg-green-100 text-green-800";
    case "RUNNING":
      return "bg-blue-100 text-blue-800";
    case "FAILED":
      return "bg-red-100 text-red-800";
    case "PENDING":
      return "bg-yellow-100 text-yellow-800";
    case "IN_SEQUENCE":
      return "bg-purple-100 text-purple-800";
    case "REPLIED":
      return "bg-green-100 text-green-800";
    case "BOUNCED":
      return "bg-red-100 text-red-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
}

/* ── Lead Detail Drawer ────────────────────────────────── */

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
    <div className="fixed inset-y-0 right-0 z-50 w-96 overflow-y-auto border-l bg-background p-6 shadow-lg">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">
          {lead.first_name} {lead.last_name}
        </h3>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>
      <Separator className="my-4" />

      <div className="space-y-3 text-sm">
        <div>
          <Label className="text-muted-foreground">Email</Label>
          <p>{lead.email || "—"}</p>
        </div>
        <div>
          <Label className="text-muted-foreground">Company</Label>
          <p>
            {lead.company_name || "—"}
            {lead.company_size ? ` (${lead.company_size} employees)` : ""}
          </p>
        </div>
        <div>
          <Label className="text-muted-foreground">Title</Label>
          <p>{lead.title || "—"}</p>
        </div>
        <div>
          <Label className="text-muted-foreground">Industry</Label>
          <p>{lead.industry || "—"}</p>
        </div>
        <div>
          <Label className="text-muted-foreground">Tech Stack</Label>
          <div className="flex flex-wrap gap-1 mt-1">
            {lead.tech_stack.length > 0
              ? lead.tech_stack.map((t) => (
                  <Badge key={t} variant="secondary">
                    {t}
                  </Badge>
                ))
              : "—"}
          </div>
        </div>
        <div>
          <Label className="text-muted-foreground">ICP Score</Label>
          <p>{lead.icp_score != null ? `${lead.icp_score}%` : "—"}</p>
        </div>
        <div>
          <Label className="text-muted-foreground">Source</Label>
          <Badge variant="outline">{lead.source}</Badge>
        </div>

        <Separator />

        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => onEnrich(lead.id)}
            disabled={lead.enrichment_status === "RUNNING"}
          >
            {lead.enrichment_status === "RUNNING"
              ? "Enriching..."
              : "Enrich"}
          </Button>
        </div>
      </div>
    </div>
  );
}

/* ── Leads Page ────────────────────────────────────────── */

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Lead | null>(null);

  // Filters
  const [enrichmentFilter, setEnrichmentFilter] = useState("");
  const [outreachFilter, setOutreachFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [industryFilter, setIndustryFilter] = useState("");

  async function loadLeads() {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (enrichmentFilter && enrichmentFilter !== "all")
        params.enrichment_status = enrichmentFilter;
      if (outreachFilter && outreachFilter !== "all")
        params.outreach_status = outreachFilter;
      if (sourceFilter && sourceFilter !== "all")
        params.source = sourceFilter;
      if (industryFilter) params.industry = industryFilter;
      const data = await api.get<Lead[]>("/leads", params);
      setLeads(data);
    } catch (err) {
      console.error("Failed to load leads:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadLeads();
  }, [enrichmentFilter, outreachFilter, sourceFilter, industryFilter]);

  async function handleEnrich(id: string) {
    try {
      const updated = await api.post<Lead>(`/leads/${id}/enrich`, {});
      setLeads((prev) => prev.map((l) => (l.id === id ? updated : l)));
      if (selected?.id === id) {
        setSelected(updated);
      }
    } catch (err) {
      console.error("Enrichment failed:", err);
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.delete(`/leads/${id}`);
      if (selected?.id === id) setSelected(null);
      await loadLeads();
    } catch (err) {
      console.error("Delete failed:", err);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">Lead Board</h2>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={loadLeads}>
            Refresh
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="flex flex-wrap gap-4 p-4">
          <div className="w-40">
            <Label className="text-xs">Enrichment</Label>
            <Select value={enrichmentFilter} onValueChange={setEnrichmentFilter}>
              <SelectTrigger>
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                {ENRICHMENT_STATUSES.map((s) => (
                  <SelectItem key={s || "all"} value={s || "all"}>
                    {s || "All"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="w-40">
            <Label className="text-xs">Outreach</Label>
            <Select value={outreachFilter} onValueChange={setOutreachFilter}>
              <SelectTrigger>
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                {OUTREACH_STATUSES.map((s) => (
                  <SelectItem key={s || "all"} value={s || "all"}>
                    {s || "All"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="w-40">
            <Label className="text-xs">Source</Label>
            <Select value={sourceFilter} onValueChange={setSourceFilter}>
              <SelectTrigger>
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                {SOURCES.map((s) => (
                  <SelectItem key={s || "all"} value={s || "all"}>
                    {s || "All"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="w-40">
            <Label className="text-xs">Industry</Label>
            <Input
              value={industryFilter}
              onChange={(e) => setIndustryFilter(e.target.value)}
              placeholder="e.g. SaaS"
            />
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      {loading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : leads.length === 0 ? (
        <p className="text-muted-foreground">
          No leads found. Import some via CSV or YC import.
        </p>
      ) : (
        <div className="rounded-md border">
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
                <tr
                  key={lead.id}
                  className="border-b cursor-pointer hover:bg-muted/30"
                  onClick={() => setSelected(lead)}
                >
                  <td className="p-3">
                    {lead.first_name} {lead.last_name}
                  </td>
                  <td className="p-3">{lead.company_name || "—"}</td>
                  <td className="p-3">
                    <Badge variant="outline">{lead.source}</Badge>
                  </td>
                  <td className="p-3">
                    {lead.icp_score != null ? (
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-16 rounded-full bg-muted">
                          <div
                            className="h-2 rounded-full bg-primary"
                            style={{
                              width: `${Math.min(lead.icp_score, 100)}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs">
                          {lead.icp_score}%
                        </span>
                      </div>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="p-3">
                    <Badge className={statusColor(lead.enrichment_status)}>
                      {lead.enrichment_status}
                    </Badge>
                  </td>
                  <td className="p-3">
                    <Badge className={statusColor(lead.outreach_status)}>
                      {lead.outreach_status}
                    </Badge>
                  </td>
                  <td className="p-3">
                    <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleEnrich(lead.id)}
                      >
                        Enrich
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-destructive"
                        onClick={() => handleDelete(lead.id)}
                      >
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail drawer */}
      {selected && (
        <LeadDrawer
          lead={selected}
          onClose={() => setSelected(null)}
          onEnrich={handleEnrich}
        />
      )}
    </div>
  );
}
