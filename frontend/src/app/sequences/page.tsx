"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  closestCenter,
  DndContext,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Play, Plus, Send, ToggleLeft } from "lucide-react";

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

type StepDraft = {
  id: string;
  step_number: number;
  step_type: "OUTREACH" | "ENGAGEMENT";
  channel:
    | "EMAIL"
    | "LINKEDIN_MESSAGE"
    | "LINKEDIN_CONNECTION"
    | "LINKEDIN_ENGAGE";
  delay_days: number;
  template: string;
  use_ai_personalization: boolean;
  requires_approval: boolean;
  engagement_action: string;
};

type Sequence = {
  id: string;
  name: string;
  icp_id: string | null;
  is_active: boolean;
  auto_enroll: boolean;
  auto_enroll_threshold: number | null;
  created_at: string;
  steps: StepDraft[];
};

type Lead = {
  id: string;
  email: string | null;
  company_name: string | null;
  company_domain: string | null;
};

const DEFAULT_STEP: StepDraft = {
  id: "step-1",
  step_number: 1,
  step_type: "OUTREACH",
  channel: "EMAIL",
  delay_days: 0,
  template: "Hi {{first_name}}, noticed a timely signal at {{company}}.",
  use_ai_personalization: true,
  requires_approval: false,
  engagement_action: "",
};

export default function SequencesPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("High-intent outbound");
  const [isActive, setIsActive] = useState(true);
  const [autoEnroll, setAutoEnroll] = useState(true);
  const [threshold, setThreshold] = useState(75);
  const [steps, setSteps] = useState<StepDraft[]>([DEFAULT_STEP]);
  const [selectedSequenceId, setSelectedSequenceId] = useState("");
  const [selectedLeadId, setSelectedLeadId] = useState("");

  const sequencesQuery = useQuery({
    queryKey: ["sequences"],
    queryFn: () => api.get<Sequence[]>("/sequences"),
  });
  const leadsQuery = useQuery({
    queryKey: ["leads", "sequences"],
    queryFn: () => api.get<Lead[]>("/leads", { limit: 100 }),
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      api.post<Sequence>("/sequences", {
        name,
        is_active: isActive,
        auto_enroll: autoEnroll,
        auto_enroll_threshold: threshold,
        steps: normalizeSteps(steps),
      }),
    onSuccess: sequence => {
      setSelectedSequenceId(sequence.id);
      void queryClient.invalidateQueries({ queryKey: ["sequences"] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (sequence: Sequence) =>
      api.patch<Sequence>(`/sequences/${sequence.id}`, {
        is_active: !sequence.is_active,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["sequences"] });
    },
  });

  const enrollMutation = useMutation({
    mutationFn: () =>
      api.post(
        `/sequences/${selectedSequenceId}/enrollments`,
        { lead_id: selectedLeadId },
      ),
  });

  const executeMutation = useMutation({
    mutationFn: () => api.post<{ executed: number }>("/sequences/execute-due", {}),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["sequences"] });
    },
  });

  const sequences = sequencesQuery.data ?? [];
  const leads = leadsQuery.data ?? [];
  const selectedSequence = sequences.find(
    sequence => sequence.id === selectedSequenceId,
  );

  function onDragEnd(event: DragEndEvent): void {
    const { active, over } = event;
    if (!over || active.id === over.id) {
      return;
    }
    setSteps(current => {
      const oldIndex = current.findIndex(step => step.id === active.id);
      const newIndex = current.findIndex(step => step.id === over.id);
      return normalizeSteps(arrayMove(current, oldIndex, newIndex));
    });
  }

  function addStep(): void {
    setSteps(current => [
      ...current,
      {
        ...DEFAULT_STEP,
        id: `step-${crypto.randomUUID()}`,
        step_number: current.length + 1,
        delay_days: 2,
      },
    ]);
  }

  function updateStep(id: string, patch: Partial<StepDraft>): void {
    setSteps(current =>
      current.map(step => {
        if (step.id !== id) {
          return step;
        }
        const next = { ...step, ...patch };
        if (next.step_type === "ENGAGEMENT") {
          next.channel = "LINKEDIN_ENGAGE";
        }
        if (
          next.step_type === "OUTREACH" &&
          next.channel === "LINKEDIN_ENGAGE"
        ) {
          next.channel = "EMAIL";
        }
        return next;
      }),
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">
            Phase 5
          </p>
          <h2 className="text-3xl font-bold tracking-tight">
            Sequences
          </h2>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Create approval-aware outreach and engagement sequences, reorder
            steps, enroll leads, and run deterministic mock delivery.
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() => executeMutation.mutate()}
          disabled={executeMutation.isPending}
        >
          <Play className="size-4" />
          Execute Due
        </Button>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Builder</CardTitle>
            <CardDescription>
              Drag steps to reorder. The backend enforces channel/step type
              compatibility.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-4">
              <Input
                className="md:col-span-2"
                value={name}
                onChange={event => setName(event.target.value)}
                placeholder="Sequence name"
              />
              <Input
                type="number"
                value={threshold}
                onChange={event => setThreshold(Number(event.target.value))}
                min={0}
                max={100}
              />
              <Button
                variant={isActive ? "default" : "outline"}
                onClick={() => setIsActive(value => !value)}
              >
                {isActive ? "Active" : "Paused"}
              </Button>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={autoEnroll}
                onChange={event => setAutoEnroll(event.target.checked)}
              />
              Auto-enroll inbound leads above threshold
            </label>

            <DndContext
              collisionDetection={closestCenter}
              onDragEnd={onDragEnd}
            >
              <SortableContext
                items={steps.map(step => step.id)}
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-3">
                  {steps.map(step => (
                    <SortableStep
                      key={step.id}
                      step={step}
                      onChange={patch => updateStep(step.id, patch)}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>

            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={addStep}>
                <Plus className="size-4" />
                Add Step
              </Button>
              <Button
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending}
              >
                <Send className="size-4" />
                Save Sequence
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Saved Sequences</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {sequences.map(sequence => (
                <button
                  key={sequence.id}
                  className="w-full rounded-lg border p-4 text-left hover:border-primary"
                  onClick={() => setSelectedSequenceId(sequence.id)}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{sequence.name}</span>
                    <Badge variant={sequence.is_active ? "default" : "outline"}>
                      {sequence.is_active ? "ACTIVE" : "PAUSED"}
                    </Badge>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {sequence.steps.length} steps · auto-enroll{" "}
                    {sequence.auto_enroll ? "on" : "off"}
                  </p>
                  <Button
                    className="mt-3"
                    size="sm"
                    variant="secondary"
                    onClick={event => {
                      event.stopPropagation();
                      toggleMutation.mutate(sequence);
                    }}
                  >
                    <ToggleLeft className="size-4" />
                    Toggle Active
                  </Button>
                </button>
              ))}
              {!sequences.length && (
                <p className="text-sm text-muted-foreground">
                  No sequences yet.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Enroll Lead</CardTitle>
              <CardDescription>
                Use this for the deterministic demo path.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <select
                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                value={selectedSequenceId}
                onChange={event => setSelectedSequenceId(event.target.value)}
              >
                <option value="">Select sequence</option>
                {sequences.map(sequence => (
                  <option key={sequence.id} value={sequence.id}>
                    {sequence.name}
                  </option>
                ))}
              </select>
              <select
                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                value={selectedLeadId}
                onChange={event => setSelectedLeadId(event.target.value)}
              >
                <option value="">Select lead</option>
                {leads.map(lead => (
                  <option key={lead.id} value={lead.id}>
                    {lead.company_name ??
                      lead.company_domain ??
                      lead.email ??
                      lead.id}
                  </option>
                ))}
              </select>
              <Button
                className="w-full"
                disabled={!selectedSequenceId || !selectedLeadId}
                onClick={() => enrollMutation.mutate()}
              >
                Enroll
              </Button>
              {selectedSequence && (
                <p className="text-xs text-muted-foreground">
                  Selected: {selectedSequence.name}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function SortableStep({
  step,
  onChange,
}: {
  step: StepDraft;
  onChange: (patch: Partial<StepDraft>) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: step.id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div ref={setNodeRef} style={style} className="rounded-xl border p-4">
      <div className="mb-3 flex items-center gap-3">
        <button
          className="cursor-grab rounded border p-2 text-muted-foreground"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="size-4" />
        </button>
        <Badge>Step {step.step_number}</Badge>
        <select
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={step.step_type}
          onChange={event =>
            onChange({ step_type: event.target.value as StepDraft["step_type"] })
          }
        >
          <option value="OUTREACH">Outreach</option>
          <option value="ENGAGEMENT">Engagement</option>
        </select>
        <select
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={step.channel}
          onChange={event =>
            onChange({ channel: event.target.value as StepDraft["channel"] })
          }
        >
          {step.step_type === "ENGAGEMENT" ? (
            <option value="LINKEDIN_ENGAGE">LinkedIn engage</option>
          ) : (
            <>
              <option value="EMAIL">Email</option>
              <option value="LINKEDIN_MESSAGE">LinkedIn message</option>
              <option value="LINKEDIN_CONNECTION">LinkedIn connect</option>
            </>
          )}
        </select>
      </div>
      <div className="grid gap-3 md:grid-cols-[120px_1fr]">
        <Input
          type="number"
          value={step.delay_days}
          onChange={event => onChange({ delay_days: Number(event.target.value) })}
          min={0}
        />
        <Textarea
          value={step.template}
          onChange={event => onChange({ template: event.target.value })}
          placeholder="Template or AI guidance"
        />
      </div>
      <div className="mt-3 flex flex-wrap gap-4 text-sm">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={step.use_ai_personalization}
            onChange={event =>
              onChange({ use_ai_personalization: event.target.checked })
            }
          />
          Use AI personalization
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={step.requires_approval}
            onChange={event =>
              onChange({ requires_approval: event.target.checked })
            }
          />
          Requires approval
        </label>
      </div>
    </div>
  );
}

function normalizeSteps(steps: StepDraft[]): StepDraft[] {
  return steps.map((step, index) => ({
    ...step,
    step_number: index + 1,
    engagement_action:
      step.channel === "LINKEDIN_ENGAGE"
        ? step.engagement_action || "VIEW_PROFILE"
        : "",
  }));
}
