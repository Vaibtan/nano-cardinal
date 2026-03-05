"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api-client";

/* ── Types ─────────────────────────────────────────────── */

interface ICP {
  id: string;
  name: string;
  description: string | null;
  config: Record<string, string[]>;
  weights: Record<string, number>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

const WIZARD_STEPS = [
  "basics",
  "firmographics",
  "persona",
  "weights",
] as const;
type WizardStep = (typeof WIZARD_STEPS)[number];

const STEP_LABELS: Record<WizardStep, string> = {
  basics: "Basics",
  firmographics: "Firmographics",
  persona: "Persona",
  weights: "Weights",
};

const WEIGHT_FIELDS = [
  "industry",
  "company_size",
  "funding_stage",
  "title",
  "seniority",
  "department",
  "tech_stack",
  "region",
] as const;

/* ── Tag Input Helper ──────────────────────────────────── */

function TagInput({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
}) {
  const [input, setInput] = useState("");

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && input.trim()) {
      e.preventDefault();
      onChange([...value, input.trim()]);
      setInput("");
    }
  }

  function remove(idx: number) {
    onChange(value.filter((_, i) => i !== idx));
  }

  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <div className="flex flex-wrap gap-1.5">
        {value.map((v, i) => (
          <Badge
            key={i}
            variant="secondary"
            className="cursor-pointer"
            onClick={() => remove(i)}
          >
            {v} &times;
          </Badge>
        ))}
      </div>
      <Input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder ?? `Add ${label.toLowerCase()} and press Enter`}
      />
    </div>
  );
}

/* ── ICP Builder Page ──────────────────────────────────── */

export default function ICPPage() {
  const [icps, setIcps] = useState<ICP[]>([]);
  const [step, setStep] = useState<WizardStep>("basics");
  const [saving, setSaving] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [config, setConfig] = useState<Record<string, string[]>>({
    industries: [],
    company_sizes: [],
    funding_stages: [],
    titles: [],
    seniorities: [],
    departments: [],
    tech_stack: [],
    regions: [],
  });
  const [weights, setWeights] = useState<Record<string, number>>(
    Object.fromEntries(WEIGHT_FIELDS.map((f) => [f, 1.0])),
  );

  async function loadICPs() {
    const data = await api.get<ICP[]>("/icps");
    setIcps(data);
  }

   
  useEffect(() => { loadICPs(); }, []);

  function resetForm() {
    setName("");
    setDescription("");
    setConfig({
      industries: [],
      company_sizes: [],
      funding_stages: [],
      titles: [],
      seniorities: [],
      departments: [],
      tech_stack: [],
      regions: [],
    });
    setWeights(
      Object.fromEntries(WEIGHT_FIELDS.map((f) => [f, 1.0])),
    );
    setStep("basics");
    setEditId(null);
  }

  function loadForEdit(icp: ICP) {
    setEditId(icp.id);
    setName(icp.name);
    setDescription(icp.description ?? "");
    setConfig({ ...config, ...icp.config });
    setWeights({ ...weights, ...icp.weights });
    setStep("basics");
  }

  async function handleSave() {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const payload = { name, description, config, weights };
      if (editId) {
        await api.patch<ICP>(`/icps/${editId}`, payload);
      } else {
        await api.post<ICP>("/icps", payload);
      }
      await loadICPs();
      resetForm();
    } catch (err) {
      console.error("Failed to save ICP:", err);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.delete(`/icps/${id}`);
      await loadICPs();
      if (editId === id) resetForm();
    } catch (err) {
      console.error("Failed to delete ICP:", err);
    }
  }

  const stepIdx = WIZARD_STEPS.indexOf(step);
  const isLast = stepIdx === WIZARD_STEPS.length - 1;

  function updateConfig(key: string, value: string[]) {
    setConfig((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight">ICP Builder</h2>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Wizard */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>
              {editId ? "Edit ICP" : "New ICP"}
            </CardTitle>
            <CardDescription>
              Step {stepIdx + 1} of {WIZARD_STEPS.length}:{" "}
              {STEP_LABELS[step]}
            </CardDescription>
            {/* Step indicators */}
            <div className="flex gap-2 pt-2">
              {WIZARD_STEPS.map((s, i) => (
                <button
                  key={s}
                  onClick={() => setStep(s)}
                  className={`h-2 flex-1 rounded-full transition-colors ${
                    i <= stepIdx ? "bg-primary" : "bg-muted"
                  }`}
                />
              ))}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Step 1 — Basics */}
            {step === "basics" && (
              <>
                <div className="space-y-1.5">
                  <Label htmlFor="icp-name">Name *</Label>
                  <Input
                    id="icp-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Mid-market SaaS"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="icp-desc">Description</Label>
                  <Textarea
                    id="icp-desc"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Describe this ICP..."
                    rows={3}
                  />
                </div>
              </>
            )}

            {/* Step 2 — Firmographics */}
            {step === "firmographics" && (
              <>
                <TagInput
                  label="Industries"
                  value={config.industries ?? []}
                  onChange={(v) => updateConfig("industries", v)}
                />
                <TagInput
                  label="Company Sizes"
                  value={config.company_sizes ?? []}
                  onChange={(v) => updateConfig("company_sizes", v)}
                  placeholder="e.g. 50-200, 200-1000"
                />
                <TagInput
                  label="Funding Stages"
                  value={config.funding_stages ?? []}
                  onChange={(v) => updateConfig("funding_stages", v)}
                  placeholder="e.g. Series A, Series B"
                />
                <TagInput
                  label="Regions"
                  value={config.regions ?? []}
                  onChange={(v) => updateConfig("regions", v)}
                  placeholder="e.g. US, EU, APAC"
                />
              </>
            )}

            {/* Step 3 — Persona */}
            {step === "persona" && (
              <>
                <TagInput
                  label="Titles"
                  value={config.titles ?? []}
                  onChange={(v) => updateConfig("titles", v)}
                  placeholder="e.g. CTO, VP Engineering"
                />
                <TagInput
                  label="Seniorities"
                  value={config.seniorities ?? []}
                  onChange={(v) => updateConfig("seniorities", v)}
                  placeholder="e.g. C-Level, VP, Director"
                />
                <TagInput
                  label="Departments"
                  value={config.departments ?? []}
                  onChange={(v) => updateConfig("departments", v)}
                  placeholder="e.g. Engineering, Product"
                />
                <TagInput
                  label="Tech Stack"
                  value={config.tech_stack ?? []}
                  onChange={(v) => updateConfig("tech_stack", v)}
                  placeholder="e.g. Python, React, AWS"
                />
              </>
            )}

            {/* Step 4 — Weights */}
            {step === "weights" && (
              <div className="grid grid-cols-2 gap-4">
                {WEIGHT_FIELDS.map((field) => (
                  <div key={field} className="space-y-1.5">
                    <Label className="capitalize">
                      {field.replace("_", " ")}
                    </Label>
                    <Input
                      type="number"
                      step="0.1"
                      min="0"
                      max="5"
                      value={weights[field]}
                      onChange={(e) =>
                        setWeights((prev) => ({
                          ...prev,
                          [field]: parseFloat(e.target.value) || 0,
                        }))
                      }
                    />
                  </div>
                ))}
              </div>
            )}

            <Separator />

            {/* Navigation */}
            <div className="flex justify-between">
              <Button
                variant="outline"
                onClick={() =>
                  setStep(WIZARD_STEPS[stepIdx - 1])
                }
                disabled={stepIdx === 0}
              >
                Back
              </Button>
              <div className="flex gap-2">
                <Button variant="ghost" onClick={resetForm}>
                  Cancel
                </Button>
                {isLast ? (
                  <Button
                    onClick={handleSave}
                    disabled={!name.trim() || saving}
                  >
                    {saving ? "Saving..." : editId ? "Update" : "Create"}
                  </Button>
                ) : (
                  <Button
                    onClick={() =>
                      setStep(WIZARD_STEPS[stepIdx + 1])
                    }
                  >
                    Next
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Existing ICPs list */}
        <div className="space-y-3">
          <h3 className="font-semibold">Saved ICPs</h3>
          {icps.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No ICPs created yet.
            </p>
          )}
          {icps.map((icp) => (
            <Card key={icp.id}>
              <CardContent className="flex items-start justify-between gap-2 p-4">
                <div>
                  <p className="font-medium">{icp.name}</p>
                  {icp.description && (
                    <p className="text-xs text-muted-foreground line-clamp-2">
                      {icp.description}
                    </p>
                  )}
                  <Badge
                    variant={icp.is_active ? "default" : "secondary"}
                    className="mt-1"
                  >
                    {icp.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
                <div className="flex gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => loadForEdit(icp)}
                  >
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive"
                    onClick={() => handleDelete(icp.id)}
                  >
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
