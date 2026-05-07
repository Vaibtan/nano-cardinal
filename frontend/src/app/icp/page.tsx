"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
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
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api-client";

type ICP = {
  id: string;
  name: string;
  description: string | null;
  config: Partial<ICPConfig>;
  weights: Partial<Record<WeightField, number>>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

type MatchPreview = {
  matching_count: number;
  total_leads: number;
};

const signalTypes = [
  "funding_round",
  "job_change",
  "leadership_hire",
  "product_launch",
  "hiring_surge",
  "job_posting_icp_role",
  "news_mention",
  "tech_stack_change",
  "linkedin_post",
  "product_signup",
  "website_visit",
  "conference_attendance",
] as const;

const wizardSteps = ["firmographics", "persona", "signals", "weighting"] as const;
type WizardStep = (typeof wizardSteps)[number];

const stepLabels: Record<WizardStep, string> = {
  firmographics: "Firmographics",
  persona: "Persona",
  signals: "Signals",
  weighting: "Weighting",
};

const weightFields = [
  "industry",
  "company_size",
  "funding_stage",
  "title",
  "seniority",
  "department",
  "tech_stack",
  "region",
] as const;
type WeightField = (typeof weightFields)[number];

const configSchema = z.object({
  industries: z.array(z.string()),
  company_sizes: z.array(z.string()),
  funding_stages: z.array(z.string()),
  titles: z.array(z.string()),
  seniorities: z.array(z.string()),
  departments: z.array(z.string()),
  tech_stack: z.array(z.string()),
  regions: z.array(z.string()),
  selected_signal_types: z.array(z.string()),
  signal_recency_days: z.number().int().min(1).max(365),
  min_signal_strength: z.number().min(0).max(1),
  signal_keywords: z.array(z.string()),
});

const weightsSchema = z.object({
  industry: z.number().min(0),
  company_size: z.number().min(0),
  funding_stage: z.number().min(0),
  title: z.number().min(0),
  seniority: z.number().min(0),
  department: z.number().min(0),
  tech_stack: z.number().min(0),
  region: z.number().min(0),
});

const icpSchema = z.object({
  name: z.string().min(1, "Name is required"),
  description: z.string().optional(),
  config: configSchema,
  weights: weightsSchema,
});

type ICPConfig = z.infer<typeof configSchema>;
type ICPFormValues = z.infer<typeof icpSchema>;

type ArrayPath =
  | "config.industries"
  | "config.company_sizes"
  | "config.funding_stages"
  | "config.titles"
  | "config.seniorities"
  | "config.departments"
  | "config.tech_stack"
  | "config.regions"
  | "config.selected_signal_types"
  | "config.signal_keywords";

const defaultConfig: ICPConfig = {
  industries: [],
  company_sizes: [],
  funding_stages: [],
  titles: [],
  seniorities: [],
  departments: [],
  tech_stack: [],
  regions: [],
  selected_signal_types: ["funding_round", "job_change", "product_signup"],
  signal_recency_days: 30,
  min_signal_strength: 0,
  signal_keywords: [],
};

const defaultWeights: Record<WeightField, number> = Object.fromEntries(
  weightFields.map((field) => [field, 1]),
) as Record<WeightField, number>;

const defaultValues: ICPFormValues = {
  name: "",
  description: "",
  config: defaultConfig,
  weights: defaultWeights,
};

function normalizeWeights(weights: Record<WeightField, number>) {
  const total = weightFields.reduce((sum, field) => sum + weights[field], 0);
  if (total <= 0) return Object.fromEntries(weightFields.map((field) => [field, 0]));
  return Object.fromEntries(
    weightFields.map((field) => [field, Number((weights[field] / total).toFixed(4))]),
  ) as Record<WeightField, number>;
}

function mergeConfig(config: Partial<ICPConfig> | undefined): ICPConfig {
  return { ...defaultConfig, ...(config ?? {}) };
}

function mergeWeights(weights: Partial<Record<WeightField, number>> | undefined) {
  return { ...defaultWeights, ...(weights ?? {}) };
}

function TagInput({
  label,
  values,
  onChange,
  placeholder,
}: {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
}) {
  const [input, setInput] = useState("");

  function addValue() {
    const next = input.trim();
    if (!next || values.includes(next)) return;
    onChange([...values, next]);
    setInput("");
  }

  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className="flex flex-wrap gap-1.5">
        {values.map((value) => (
          <Badge
            key={value}
            variant="secondary"
            className="cursor-pointer"
            onClick={() => onChange(values.filter((item) => item !== value))}
          >
            {value} &times;
          </Badge>
        ))}
      </div>
      <div className="flex gap-2">
        <Input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              addValue();
            }
          }}
          placeholder={placeholder ?? `Add ${label.toLowerCase()}`}
        />
        <Button type="button" variant="outline" onClick={addValue}>
          Add
        </Button>
      </div>
    </div>
  );
}

export default function ICPPage() {
  const [step, setStep] = useState<WizardStep>("firmographics");
  const [editId, setEditId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const form = useForm<ICPFormValues>({
    resolver: zodResolver(icpSchema),
    defaultValues,
  });

  const config = useWatch({ control: form.control, name: "config" });
  const weights = useWatch({ control: form.control, name: "weights" });
  const normalizedWeights = useMemo(() => normalizeWeights(weights), [weights]);

  const icpsQuery = useQuery({
    queryKey: ["icps"],
    queryFn: () => api.get<ICP[]>("/icps"),
  });

  const matchPreviewQuery = useQuery({
    queryKey: ["icp-match-count", config],
    queryFn: () =>
      api.post<MatchPreview>("/icps/match-count", {
        config,
      }),
  });

  const saveMutation = useMutation({
    mutationFn: (values: ICPFormValues) => {
      const payload = {
        name: values.name,
        description: values.description || null,
        config: values.config,
        weights: normalizeWeights(values.weights),
      };
      return editId
        ? api.patch<ICP>(`/icps/${editId}`, payload)
        : api.post<ICP>("/icps", payload);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["icps"] });
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/icps/${id}`),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["icps"] });
      resetForm();
    },
  });

  function resetForm() {
    setEditId(null);
    setStep("firmographics");
    form.reset(defaultValues);
  }

  function loadForEdit(icp: ICP) {
    setEditId(icp.id);
    setStep("firmographics");
    form.reset({
      name: icp.name,
      description: icp.description ?? "",
      config: mergeConfig(icp.config),
      weights: mergeWeights(icp.weights),
    });
  }

  function updateArray(path: ArrayPath, values: string[]) {
    form.setValue(path, values, { shouldDirty: true, shouldValidate: true });
  }

  const stepIndex = wizardSteps.indexOf(step);
  const isLastStep = stepIndex === wizardSteps.length - 1;
  const preview = matchPreviewQuery.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">ICP Builder</h2>
          <p className="text-muted-foreground">
            Define firmographics, persona, signal preferences, and normalized scoring weights.
          </p>
        </div>
        <Card className="lg:w-80">
          <CardContent className="p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Matching preview
            </p>
            <p className="text-2xl font-semibold">
              {matchPreviewQuery.isLoading ? "..." : preview?.matching_count ?? 0}
              <span className="text-sm font-normal text-muted-foreground">
                /{preview?.total_leads ?? 0} leads
              </span>
            </p>
          </CardContent>
        </Card>
      </div>

      <form
        onSubmit={form.handleSubmit((values) => saveMutation.mutate(values))}
        className="grid grid-cols-1 gap-6 lg:grid-cols-3"
      >
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{editId ? "Edit ICP" : "New ICP"}</CardTitle>
            <CardDescription>
              Metadata is separate from the wizard: the steps follow Firmographics → Persona → Signals → Weighting.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="icp-name">Name *</Label>
                <Input id="icp-name" {...form.register("name")} placeholder="Mid-market SaaS" />
                {form.formState.errors.name && (
                  <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
                )}
              </div>
              <div className="space-y-2 md:col-span-1">
                <Label htmlFor="icp-description">Description</Label>
                <Textarea
                  id="icp-description"
                  {...form.register("description")}
                  rows={2}
                  placeholder="Who this ICP represents"
                />
              </div>
            </div>

            <Separator />

            <div className="flex gap-2">
              {wizardSteps.map((item, index) => (
                <button
                  type="button"
                  key={item}
                  onClick={() => setStep(item)}
                  className={`flex-1 rounded-full px-3 py-2 text-xs font-medium transition-colors ${
                    index <= stepIndex
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {stepLabels[item]}
                </button>
              ))}
            </div>

            {step === "firmographics" && (
              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                <TagInput label="Industries" values={config.industries} onChange={(values) => updateArray("config.industries", values)} />
                <TagInput label="Company Sizes" values={config.company_sizes} onChange={(values) => updateArray("config.company_sizes", values)} placeholder="50-200, 1001+" />
                <TagInput label="Funding Stages" values={config.funding_stages} onChange={(values) => updateArray("config.funding_stages", values)} placeholder="Seed, Series A" />
                <TagInput label="Regions" values={config.regions} onChange={(values) => updateArray("config.regions", values)} placeholder="USA, EU, India" />
              </div>
            )}

            {step === "persona" && (
              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                <TagInput label="Titles" values={config.titles} onChange={(values) => updateArray("config.titles", values)} placeholder="CTO, VP Sales" />
                <TagInput label="Seniorities" values={config.seniorities} onChange={(values) => updateArray("config.seniorities", values)} placeholder="Director, VP, C-Suite" />
                <TagInput label="Departments" values={config.departments} onChange={(values) => updateArray("config.departments", values)} placeholder="Sales, Engineering" />
                <TagInput label="Tech Stack" values={config.tech_stack} onChange={(values) => updateArray("config.tech_stack", values)} placeholder="HubSpot, Stripe" />
              </div>
            )}

            {step === "signals" && (
              <div className="space-y-5">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="signal-recency">Signal recency window</Label>
                    <Input id="signal-recency" type="number" min={1} max={365} {...form.register("config.signal_recency_days", { valueAsNumber: true })} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="min-strength">Minimum signal strength</Label>
                    <Input id="min-strength" type="number" min={0} max={1} step={0.05} {...form.register("config.min_signal_strength", { valueAsNumber: true })} />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Signal types this ICP cares about</Label>
                  <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                    {signalTypes.map((signalType) => {
                      const selected = config.selected_signal_types.includes(signalType);
                      return (
                        <button
                          type="button"
                          key={signalType}
                          onClick={() => {
                            const next = selected
                              ? config.selected_signal_types.filter((item) => item !== signalType)
                              : [...config.selected_signal_types, signalType];
                            updateArray("config.selected_signal_types", next);
                          }}
                          className={`rounded-md border px-3 py-2 text-left text-sm transition-colors ${
                            selected ? "border-primary bg-primary text-primary-foreground" : "bg-background hover:bg-muted"
                          }`}
                        >
                          {signalType.replaceAll("_", " ")}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <TagInput label="Signal Keywords" values={config.signal_keywords} onChange={(values) => updateArray("config.signal_keywords", values)} placeholder="SOC2, migration, hiring" />
              </div>
            )}

            {step === "weighting" && (
              <div className="space-y-4">
                <div className="rounded-lg border bg-muted/30 p-3 text-sm">
                  Displayed weights auto-normalize to 1.0 before save.
                </div>
                {weightFields.map((field) => (
                  <div key={field} className="grid grid-cols-[150px_1fr_60px] items-center gap-3">
                    <Label className="capitalize">{field.replaceAll("_", " ")}</Label>
                    <input
                      type="range"
                      min="0"
                      max="5"
                      step="0.1"
                      value={weights[field]}
                      onChange={(event) =>
                        form.setValue(`weights.${field}`, Number(event.target.value), {
                          shouldDirty: true,
                          shouldValidate: true,
                        })
                      }
                    />
                    <span className="text-right text-sm tabular-nums">{normalizedWeights[field].toFixed(2)}</span>
                  </div>
                ))}
              </div>
            )}

            <Separator />

            <div className="flex justify-between">
              <Button type="button" variant="outline" disabled={stepIndex === 0} onClick={() => setStep(wizardSteps[stepIndex - 1])}>
                Back
              </Button>
              <div className="flex gap-2">
                <Button type="button" variant="ghost" onClick={resetForm}>
                  Cancel
                </Button>
                {isLastStep ? (
                  <Button type="submit" disabled={saveMutation.isPending}>
                    {saveMutation.isPending ? "Saving..." : editId ? "Update ICP" : "Create ICP"}
                  </Button>
                ) : (
                  <Button type="button" onClick={() => setStep(wizardSteps[stepIndex + 1])}>
                    Next
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-3">
          <h3 className="font-semibold">Saved ICPs</h3>
          {icpsQuery.isLoading && <p className="text-sm text-muted-foreground">Loading ICPs...</p>}
          {icpsQuery.data?.length === 0 && <p className="text-sm text-muted-foreground">No ICPs created yet.</p>}
          {icpsQuery.data?.map((icp) => (
            <Card key={icp.id}>
              <CardContent className="flex items-start justify-between gap-2 p-4">
                <div>
                  <p className="font-medium">{icp.name}</p>
                  {icp.description && <p className="line-clamp-2 text-xs text-muted-foreground">{icp.description}</p>}
                  <Badge variant={icp.is_active ? "default" : "secondary"} className="mt-1">
                    {icp.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
                <div className="flex gap-1">
                  <Button type="button" size="sm" variant="ghost" onClick={() => loadForEdit(icp)}>
                    Edit
                  </Button>
                  <Button type="button" size="sm" variant="ghost" className="text-destructive" onClick={() => deleteMutation.mutate(icp.id)}>
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </form>
    </div>
  );
}
