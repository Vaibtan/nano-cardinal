"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
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
import { api } from "@/lib/api-client";

type SenderProfile = {
  id: string;
  user_id: string;
  name: string;
  current_title: string | null;
  current_company: string | null;
  education: string[];
  past_employers: string[];
  cities_lived: string[];
  hobbies_and_interests: string[];
  investors: string[];
  languages_spoken: string[];
  conferences_attended: string[];
  updated_at: string;
};

const listFields = [
  { key: "education", label: "Education" },
  { key: "past_employers", label: "Past Employers" },
  { key: "cities_lived", label: "Cities Lived" },
  { key: "hobbies_and_interests", label: "Hobbies & Interests" },
  { key: "investors", label: "Investors" },
  { key: "languages_spoken", label: "Languages Spoken" },
  { key: "conferences_attended", label: "Conferences Attended" },
] as const;

const senderSchema = z.object({
  name: z.string().min(1, "Name is required"),
  current_title: z.string().optional(),
  current_company: z.string().optional(),
  education: z.array(z.string()),
  past_employers: z.array(z.string()),
  cities_lived: z.array(z.string()),
  hobbies_and_interests: z.array(z.string()),
  investors: z.array(z.string()),
  languages_spoken: z.array(z.string()),
  conferences_attended: z.array(z.string()),
});

type SenderFormValues = z.infer<typeof senderSchema>;

const defaultValues: SenderFormValues = {
  name: "",
  current_title: "",
  current_company: "",
  education: [],
  past_employers: [],
  cities_lived: [],
  hobbies_and_interests: [],
  investors: [],
  languages_spoken: [],
  conferences_attended: [],
};

function cleanList(values: string[]) {
  return values.map((value) => value.trim()).filter(Boolean);
}

function ArrayField({
  label,
  values,
  onChange,
}: {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
}) {
  function update(index: number, value: string) {
    const next = [...values];
    next[index] = value;
    onChange(next);
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>{label}</Label>
        <Button type="button" variant="ghost" size="sm" onClick={() => onChange([...values, ""])}>
          + Add
        </Button>
      </div>
      {values.length === 0 && <p className="text-xs text-muted-foreground">None added yet.</p>}
      {values.map((value, index) => (
        <div key={`${label}-${index}`} className="flex gap-2">
          <Input
            value={value}
            onChange={(event) => update(index, event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && value.trim()) {
                event.preventDefault();
                onChange([...values, ""]);
              }
            }}
            placeholder={`${label} ${index + 1}`}
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="shrink-0 text-destructive"
            onClick={() => onChange(values.filter((_, itemIndex) => itemIndex !== index))}
          >
            Remove
          </Button>
        </div>
      ))}
    </div>
  );
}

function profileToForm(profile: SenderProfile | null): SenderFormValues {
  if (!profile) return defaultValues;
  return {
    name: profile.name,
    current_title: profile.current_title ?? "",
    current_company: profile.current_company ?? "",
    education: profile.education ?? [],
    past_employers: profile.past_employers ?? [],
    cities_lived: profile.cities_lived ?? [],
    hobbies_and_interests: profile.hobbies_and_interests ?? [],
    investors: profile.investors ?? [],
    languages_spoken: profile.languages_spoken ?? [],
    conferences_attended: profile.conferences_attended ?? [],
  };
}

export default function SenderPage() {
  const queryClient = useQueryClient();
  const form = useForm<SenderFormValues>({
    resolver: zodResolver(senderSchema),
    defaultValues,
  });
  const watchedValues = useWatch({ control: form.control });

  const profileQuery = useQuery({
    queryKey: ["sender-profile"],
    queryFn: async () => {
      try {
        return await api.get<SenderProfile>("/sender");
      } catch {
        return null;
      }
    },
  });

  const saveMutation = useMutation({
    mutationFn: (values: SenderFormValues) =>
      api.post<SenderProfile>("/sender", {
        name: values.name,
        current_title: values.current_title || null,
        current_company: values.current_company || null,
        education: cleanList(values.education),
        past_employers: cleanList(values.past_employers),
        cities_lived: cleanList(values.cities_lived),
        hobbies_and_interests: cleanList(values.hobbies_and_interests),
        investors: cleanList(values.investors),
        languages_spoken: cleanList(values.languages_spoken),
        conferences_attended: cleanList(values.conferences_attended),
      }),
    onSuccess: async (profile) => {
      form.reset(profileToForm(profile));
      await queryClient.invalidateQueries({ queryKey: ["sender-profile"] });
    },
  });

  useEffect(() => {
    if (!profileQuery.isSuccess || form.formState.isDirty) return;
    form.reset(profileToForm(profileQuery.data));
  }, [form, form.formState.isDirty, profileQuery.data, profileQuery.isSuccess]);

  if (profileQuery.isLoading) {
    return (
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Sender Profile</h2>
        <p className="mt-2 text-muted-foreground">Loading...</p>
      </div>
    );
  }

  const profile = profileQuery.data;

  return (
    <form onSubmit={form.handleSubmit((values) => saveMutation.mutate(values))} className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Sender Profile</h2>
          <p className="text-muted-foreground">
            Your background powers the commonality engine.
          </p>
        </div>
        {profile && (
          <Badge variant="secondary">
            Last updated: {new Date(profile.updated_at).toLocaleDateString()}
          </Badge>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Your Details</CardTitle>
          <CardDescription>
            Complete profiles produce stronger personalization because the commonality matcher has more credible hooks.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="sender-name">Name *</Label>
              <Input id="sender-name" {...form.register("name")} placeholder="Your full name" />
              {form.formState.errors.name && (
                <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="sender-title">Current Title</Label>
              <Input id="sender-title" {...form.register("current_title")} placeholder="CEO" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="sender-company">Current Company</Label>
              <Input id="sender-company" {...form.register("current_company")} placeholder="Acme Inc" />
            </div>
          </div>

          <Separator />

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {listFields.map(({ key, label }) => {
              const values = watchedValues[key] ?? [];
              return (
                <ArrayField
                  key={key}
                  label={label}
                  values={values}
                  onChange={(next) => form.setValue(key, next, { shouldDirty: true })}
                />
              );
            })}
          </div>

          <Card className="border-dashed bg-muted/30">
            <CardContent className="p-4 text-sm text-muted-foreground">
              Preview scaffold: Phase 4 will show a sample commonality analysis against a mock lead here.
            </CardContent>
          </Card>

          <Separator />

          <div className="flex justify-end">
            <Button type="submit" disabled={saveMutation.isPending || !(watchedValues.name ?? "").trim()}>
              {saveMutation.isPending ? "Saving..." : profile ? "Update Profile" : "Create Profile"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </form>
  );
}
