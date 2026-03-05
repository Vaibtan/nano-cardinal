import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Orion — Precision Outbound",
  description: "AI-powered precision outbound engine",
};

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/icp", label: "ICP Builder" },
  { href: "/sender", label: "Sender Profile" },
  { href: "/leads", label: "Leads" },
  { href: "/tam", label: "TAM Explorer" },
  { href: "/feed", label: "Signal Feed" },
  { href: "/compose", label: "Composer" },
  { href: "/sequences", label: "Sequences" },
  { href: "/analytics", label: "Analytics" },
] as const;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <div className="flex h-screen">
          {/* Sidebar */}
          <aside className="w-56 shrink-0 border-r bg-muted/40 p-4">
            <h1 className="mb-6 text-lg font-bold tracking-tight">
              Orion
            </h1>
            <nav className="flex flex-col gap-1">
              {NAV_ITEMS.map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  className="rounded-md px-3 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground transition-colors"
                >
                  {label}
                </Link>
              ))}
            </nav>
          </aside>

          {/* Main content */}
          <main className="flex-1 overflow-y-auto p-6">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
