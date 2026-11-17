"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutGrid,
  LogOut,
  MessageSquare,
  Plus,
  Send,
  Sparkles,
  Users,
} from "lucide-react";

import { BackgroundScene } from "@/components/canvas/BackgroundScene";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/useAuthStore";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Overview", icon: LayoutGrid },
  { href: "/dashboard/leads", label: "Leads", icon: Users },
  { href: "/dashboard/conversations", label: "Conversations", icon: MessageSquare },
];

const CHANNEL_ITEMS = [
  { label: "Web Chat", dotColor: "bg-[#2E7D4F]", href: "/dashboard/conversations" },
  { label: "Voice Line", dotColor: "bg-[#C86D44]", href: "/dashboard/conversations" },
  { label: "Qualified", dotColor: "bg-[#B9382C]", href: "/dashboard/leads" },
  { label: "Escalations", dotColor: "bg-[#3B6EA5]", href: "/dashboard/leads" },
];

function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, user, hydrate, logout } = useAuthStore();
  const [hydrated, setHydrated] = useState(false);

  // Quick Entry / New AI Receptionist Chat modal state
  const [newEntryOpen, setNewEntryOpen] = useState(false);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [initialMessage, setInitialMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    hydrate();
    const id = window.requestAnimationFrame(() => setHydrated(true));
    return () => window.cancelAnimationFrame(id);
  }, [hydrate]);

  useEffect(() => {
    if (hydrated && !isAuthenticated) {
      router.replace("/login");
    }
  }, [hydrated, isAuthenticated, router]);

  if (!hydrated || !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#F7F7F5] text-sm text-[#737370]">
        Loading workspace...
      </div>
    );
  }

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  const handleQuickEntry = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    if (!customerName.trim() || !initialMessage.trim()) {
      setSubmitError("Please enter a customer name and an opening message.");
      return;
    }

    setSubmitting(true);
    try {
      const custRes = await api.post<{ id: string }>("/customers", {
        full_name: customerName.trim(),
        phone_number: customerPhone.trim() || "+1-555-0199",
        preferred_language: "en",
      });
      const convRes = await api.post<{ id: string }>("/conversations", {
        customer_id: custRes.data.id,
        channel: "web_chat",
        status: "active",
      });
      await api.post("/chat/receptionist", {
        customer_id: custRes.data.id,
        conversation_id: convRes.data.id,
        content: initialMessage.trim(),
      });
      setNewEntryOpen(false);
      setCustomerName("");
      setCustomerPhone("");
      setInitialMessage("");
      router.push(`/dashboard/conversations/${convRes.data.id}`);
    } catch {
      setSubmitError("Could not start conversation. Verify backend is running.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative flex min-h-screen bg-[#F7F7F5] text-[#1A1A1A]">
      <BackgroundScene />

      {/* Left Sidebar */}
      <aside className="relative z-20 hidden w-64 shrink-0 flex-col justify-between border-r border-[#EAE9E4] bg-white/95 px-4 py-5 backdrop-blur-sm md:flex">
        <div className="space-y-6">
          {/* Top CTA Pill */}
          <Button
            onClick={() => setNewEntryOpen(true)}
            className="h-10 w-full rounded-xl bg-[#5C8A67] text-sm font-medium text-white shadow-sm hover:bg-[#4D7757]"
          >
            <Plus className="mr-1.5 h-4 w-4" />
            New Entry
          </Button>

          {/* Menu Section */}
          <div>
            <p className="mb-2 px-2.5 text-[11px] font-medium uppercase tracking-wider text-[#9C9C96]">
              Menu
            </p>
            <nav className="space-y-1">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const isActive =
                  item.href === "/dashboard"
                    ? pathname === "/dashboard"
                    : pathname.startsWith(item.href);

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-[#F3F2EE] text-[#1A1A1A]"
                        : "text-[#737370] hover:bg-[#F7F7F5] hover:text-[#1A1A1A]"
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-4 w-4",
                        isActive ? "text-[#1A1A1A]" : "text-[#9C9C96]"
                      )}
                    />
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Channels Section */}
          <div>
            <p className="mb-2 px-2.5 text-[11px] font-medium uppercase tracking-wider text-[#9C9C96]">
              Channels
            </p>
            <div className="space-y-1">
              {CHANNEL_ITEMS.map((channel) => (
                <Link
                  key={channel.label}
                  href={channel.href}
                  className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-[#52524E] transition-colors hover:bg-[#F7F7F5] hover:text-[#1A1A1A]"
                >
                  <span
                    className={cn("h-2 w-2 rounded-full", channel.dotColor)}
                  />
                  <span>{channel.label}</span>
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom Workspace Card & Profile */}
        <div className="space-y-3">
          <div className="rounded-2xl border border-[#EAE9E4] bg-[#FAFAF8] p-4 text-center">
            <div className="mx-auto mb-2 flex h-9 w-9 items-center justify-center rounded-xl bg-[#EDF3EE] text-[#2E7D4F]">
              <Sparkles className="h-4 w-4" />
            </div>
            <p className="text-xs font-semibold text-[#1A1A1A]">
              AI Receptionist Live
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-[#737370]">
              Background analyst scores leads automatically after every chat.
            </p>
          </div>

          <div className="flex items-center justify-between rounded-xl border border-[#EAE9E4] bg-white px-3 py-2.5">
            <div className="flex items-center gap-2.5 overflow-hidden">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#EDF3EE] text-xs font-semibold text-[#2E7D4F]">
                {(user?.email?.[0] ?? "A").toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-[#1A1A1A]">
                  {user?.email ?? "Admin"}
                </p>
                <p className="text-[11px] capitalize text-[#737370]">
                  {user?.role ?? "operator"}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              title="Sign out"
              className="rounded-lg p-1.5 text-[#737370] transition-colors hover:bg-[#F7F7F5] hover:text-[#1A1A1A]"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile Top Bar */}
      <div className="relative z-10 flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-[#EAE9E4] bg-white/90 px-4 py-3 backdrop-blur-sm md:hidden">
          <span className="text-sm font-semibold text-[#1A1A1A]">
            AI Employee
          </span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={() => setNewEntryOpen(true)}
              className="h-8 rounded-lg bg-[#5C8A67] px-3 text-xs text-white"
            >
              <Plus className="mr-1 h-3.5 w-3.5" />
              New
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={handleLogout}
              className="h-8 px-2.5 text-xs"
            >
              Sign out
            </Button>
          </div>
        </header>

        <main className="flex-1 px-4 py-6 sm:px-8 sm:py-7">{children}</main>
      </div>

      {/* Quick Entry Dialog */}
      <Dialog open={newEntryOpen} onOpenChange={setNewEntryOpen}>
        <DialogHeader>
          <DialogTitle>Start New Receptionist Session</DialogTitle>
          <DialogDescription>
            Simulate or initiate an inbound customer inquiry. The AI Analyst
            will automatically score the resulting lead.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleQuickEntry} className="space-y-3.5">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <label className="text-xs font-medium text-[#52524E]">
                Customer Name
              </label>
              <Input
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                placeholder="e.g. Elena Rostova"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-[#52524E]">
                Phone (optional)
              </label>
              <Input
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                placeholder="+1-555-0142"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-[#52524E]">
              Opening Inquiry
            </label>
            <Input
              value={initialMessage}
              onChange={(e) => setInitialMessage(e.target.value)}
              placeholder="Hi, I'd like pricing for your enterprise automation plan..."
            />
          </div>
          {submitError && (
            <p className="rounded-lg bg-[#FCECEA] px-3 py-2 text-xs text-[#B9382C]">
              {submitError}
            </p>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setNewEntryOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={submitting}
              className="bg-[#5C8A67] text-white hover:bg-[#4D7757]"
            >
              <Send className="mr-1.5 h-3.5 w-3.5" />
              {submitting ? "Starting..." : "Send to Receptionist"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[#F7F7F5] text-sm text-[#737370]">
          Loading workspace...
        </div>
      }
    >
      <DashboardShell>{children}</DashboardShell>
    </Suspense>
  );
}
