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
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api-client";

/* ── Types ─────────────────────────────────────────────── */

interface SenderProfile {
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
}

const LIST_FIELDS = [
  { key: "education", label: "Education" },
  { key: "past_employers", label: "Past Employers" },
  { key: "cities_lived", label: "Cities Lived" },
  { key: "hobbies_and_interests", label: "Hobbies & Interests" },
  { key: "investors", label: "Investors" },
  { key: "languages_spoken", label: "Languages Spoken" },
  { key: "conferences_attended", label: "Conferences Attended" },
] as const;

type ListFieldKey = (typeof LIST_FIELDS)[number]["key"];

/* ── Dynamic Array Input ───────────────────────────────── */

function ArrayField({
  label,
  values,
  onChange,
}: {
  label: string;
  values: string[];
  onChange: (v: string[]) => void;
}) {
  function handleAdd() {
    onChange([...values, ""]);
  }

  function handleChange(idx: number, val: string) {
    const next = [...values];
    next[idx] = val;
    onChange(next);
  }

  function handleRemove(idx: number) {
    onChange(values.filter((_, i) => i !== idx));
  }

  function handleKeyDown(
    e: React.KeyboardEvent<HTMLInputElement>,
    idx: number,
  ) {
    if (e.key === "Enter") {
      e.preventDefault();
      if (values[idx].trim()) handleAdd();
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>{label}</Label>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleAdd}
        >
          + Add
        </Button>
      </div>
      {values.length === 0 && (
        <p className="text-xs text-muted-foreground">
          None added yet.
        </p>
      )}
      {values.map((v, i) => (
        <div key={i} className="flex gap-2">
          <Input
            value={v}
            onChange={(e) => handleChange(i, e.target.value)}
            onKeyDown={(e) => handleKeyDown(e, i)}
            placeholder={`${label} ${i + 1}`}
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-destructive shrink-0"
            onClick={() => handleRemove(i)}
          >
            Remove
          </Button>
        </div>
      ))}
    </div>
  );
}

/* ── Sender Profile Page ───────────────────────────────── */

export default function SenderPage() {
  const [profile, setProfile] = useState<SenderProfile | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [currentTitle, setCurrentTitle] = useState("");
  const [currentCompany, setCurrentCompany] = useState("");
  const [lists, setLists] = useState<Record<ListFieldKey, string[]>>({
    education: [],
    past_employers: [],
    cities_lived: [],
    hobbies_and_interests: [],
    investors: [],
    languages_spoken: [],
    conferences_attended: [],
  });

  async function loadProfile() {
    setLoading(true);
    try {
      const data = await api.get<SenderProfile>("/sender");
      setProfile(data);
      setName(data.name);
      setCurrentTitle(data.current_title ?? "");
      setCurrentCompany(data.current_company ?? "");
      const loaded = {} as Record<ListFieldKey, string[]>;
      for (const { key } of LIST_FIELDS) {
        loaded[key] = data[key] ?? [];
      }
      setLists(loaded);
    } catch {
      // 404 — no profile yet.
      setProfile(null);
    }
    setLoading(false);
  }

   
  useEffect(() => { loadProfile(); }, []);

  async function handleSave() {
    if (!name.trim()) return;
    setSaving(true);
    try {
      // Filter out empty strings from list fields.
      const cleanLists = Object.fromEntries(
        Object.entries(lists).map(([k, arr]) => [
          k,
          arr.filter((v) => v.trim()),
        ]),
      );

      const payload = {
        name,
        current_title: currentTitle || null,
        current_company: currentCompany || null,
        ...cleanLists,
      };

      await api.post<SenderProfile>("/sender", payload);
      await loadProfile();
    } catch (err) {
      console.error("Failed to save sender profile:", err);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div>
        <h2 className="text-2xl font-bold tracking-tight">
          Sender Profile
        </h2>
        <p className="mt-2 text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">
            Sender Profile
          </h2>
          <p className="text-muted-foreground">
            Your background powers the commonality engine.
          </p>
        </div>
        {profile && (
          <Badge variant="secondary">
            Last updated:{" "}
            {new Date(profile.updated_at).toLocaleDateString()}
          </Badge>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Your Details</CardTitle>
          <CardDescription>
            Fill in your background. The commonality matcher will use
            these to find shared connections with prospects.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Identity */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="sender-name">Name *</Label>
              <Input
                id="sender-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your full name"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="sender-title">Current Title</Label>
              <Input
                id="sender-title"
                value={currentTitle}
                onChange={(e) => setCurrentTitle(e.target.value)}
                placeholder="e.g. CEO"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="sender-company">
                Current Company
              </Label>
              <Input
                id="sender-company"
                value={currentCompany}
                onChange={(e) => setCurrentCompany(e.target.value)}
                placeholder="e.g. Acme Inc"
              />
            </div>
          </div>

          <Separator />

          {/* Dynamic array fields */}
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {LIST_FIELDS.map(({ key, label }) => (
              <ArrayField
                key={key}
                label={label}
                values={lists[key]}
                onChange={(v) =>
                  setLists((prev) => ({ ...prev, [key]: v }))
                }
              />
            ))}
          </div>

          <Separator />

          <div className="flex justify-end">
            <Button
              onClick={handleSave}
              disabled={!name.trim() || saving}
            >
              {saving
                ? "Saving..."
                : profile
                  ? "Update Profile"
                  : "Create Profile"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
