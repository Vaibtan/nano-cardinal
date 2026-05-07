import Link from "next/link";

const CARDS = [
  {
    href: "/feed",
    title: "Capture demand",
    body: "Inbound webhooks and buying signals flow into one live feed.",
  },
  {
    href: "/compose",
    title: "Personalize outreach",
    body: "Generate signal-aware drafts with commonality hooks and critique.",
  },
  {
    href: "/sequences",
    title: "Execute sequences",
    body: "Run deterministic email and LinkedIn outreach state transitions.",
  },
  {
    href: "/analytics",
    title: "Measure GTM motion",
    body: "Track lead, signal, inbound, sequence, and draft performance.",
  },
] as const;

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium text-muted-foreground">
          Orion GTM Engine
        </p>
        <h2 className="text-4xl font-bold tracking-tight">
          Precision outbound control plane
        </h2>
        <p className="mt-3 max-w-3xl text-muted-foreground">
          Define ICPs, enrich leads, detect buying signals, compose
          personalized outreach, execute sequences, and monitor the funnel from
          one local demo stack.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {CARDS.map(card => (
          <Link
            key={card.href}
            href={card.href}
            className="rounded-2xl border bg-card p-5 text-card-foreground shadow-sm transition hover:-translate-y-1 hover:border-primary"
          >
            <h3 className="font-semibold">{card.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{card.body}</p>
          </Link>
        ))}
      </div>

      <div className="rounded-3xl border bg-gradient-to-br from-emerald-50 via-orange-50 to-slate-100 p-8">
        <h3 className="text-2xl font-semibold">Demo path</h3>
        <p className="mt-2 max-w-2xl text-sm text-slate-700">
          Seed data, review leads, run a mock signal scan, generate a draft,
          execute a sequence step, then inspect analytics. The stack uses
          deterministic mock providers, so the flow is repeatable.
        </p>
      </div>
    </div>
  );
}
