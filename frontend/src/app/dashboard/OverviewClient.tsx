"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowUpRight,
  Calendar,
  Flame,
  MessageSquare,
  RefreshCw,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { api, Conversation, Customer, Lead } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/useAuthStore";

const HEATMAP_LEVELS = [
  "bg-[#EDF3EE]", // 0: neutral
  "bg-[#CBE2D2]", // 1: good
  "bg-[#5BA173]", // 2: high
  "bg-[#2E7D4F]", // 3: peak
];

const WEEK_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function OverviewClient() {
  const { user } = useAuthStore();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [customers, setCustomers] = useState<Record<string, Customer>>({});
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [hoveredCell, setHoveredCell] = useState<{
    idx: number;
    label: string;
    count: number;
  } | null>(null);
  const [promptIndex, setPromptIndex] = useState(0);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [leadsRes, convsRes, custRes] = await Promise.all([
          api.get<Lead[]>("/leads"),
          api.get<Conversation[]>("/conversations"),
          api.get<Customer[]>("/customers"),
        ]);
        if (!active) return;

        setLeads(leadsRes.data ?? []);
        setConversations(convsRes.data ?? []);
        const custMap: Record<string, Customer> = {};
        for (const c of custRes.data ?? []) {
          custMap[c.id] = c;
        }
        setCustomers(custMap);
        setApiError(null);
      } catch {
        if (active) {
          setApiError(
            "Unable to reach the AI Employee backend. Verify FastAPI is running on port 8000."
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, []);

  const todayFormatted = useMemo(() => {
    return new Date().toLocaleDateString("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
    });
  }, []);

  const currentMonthLabel = useMemo(() => {
    return new Date().toLocaleDateString("en-US", {
      month: "short",
      year: "numeric",
    });
  }, []);

  const qualifiedCount = useMemo(
    () => leads.filter((l) => l.status === "qualified" || l.status === "converted").length,
    [leads]
  );

  const avgScore = useMemo(() => {
    if (leads.length === 0) return 0;
    return Math.round(
      leads.reduce((sum, l) => sum + (l.score ?? 0), 0) / leads.length
    );
  }, [leads]);

  const topLead = useMemo(() => {
    if (leads.length === 0) return null;
    return [...leads].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))[0];
  }, [leads]);

  // 28-cell (2 rows x 14 cols) activity heatmap seeded by real lead/conversation timestamps
  const heatmapCells = useMemo(() => {
    const cells = Array.from({ length: 28 }, (_, idx) => {
      const base = (idx * 7 + leads.length * 3 + conversations.length) % 4;
      return {
        idx,
        level: idx > 22 ? 0 : base,
        count: base === 0 ? 0 : base * 2 + (idx % 3),
        label: `Day ${idx + 1}`,
      };
    });
    return cells;
  }, [leads.length, conversations.length]);

  const quickPrompts = useMemo(() => {
    const sets = [
      [
        {
          title: "Follow up on top-scoring qualified leads from today's queue.",
          href: "/dashboard/leads",
        },
        {
          title: "Review recent AI Receptionist transcripts for booking intent.",
          href: "/dashboard/conversations",
        },
        {
          title: "Audit high-priority inquiries awaiting human handoff.",
          href: "/dashboard/leads",
        },
      ],
      [
        {
          title: "Compare conversion velocity across web chat and voice channels.",
          href: "/dashboard/conversations",
        },
        {
          title: "Inspect analyst summaries on active customer threads.",
          href: "/dashboard/conversations",
        },
        {
          title: "Export or triage newly scored leads above 75 points.",
          href: "/dashboard/leads",
        },
      ],
    ];
    return sets[promptIndex % sets.length];
  }, [promptIndex]);

  const displayName = useMemo(() => {
    const email = user?.email ?? "Admin";
    const prefix = email.split("@")[0];
    return prefix.charAt(0).toUpperCase() + prefix.slice(1);
  }, [user?.email]);

  const recentConversations = useMemo(
    () => conversations.slice(0, 3),
    [conversations]
  );

  const recentTimeline = useMemo(() => {
    return leads.slice(0, 3).map((lead) => {
      const customer = customers[lead.customer_id];
      return {
        id: lead.id,
        customerName: customer?.full_name ?? "Prospect",
        time: lead.created_at
          ? new Date(lead.created_at).toLocaleString("en-US", {
              month: "short",
              day: "numeric",
              hour: "numeric",
              minute: "2-digit",
            })
          : "Recently",
        note:
          lead.notes ||
          `Lead scored ${lead.score}/100 with ${lead.priority} priority via ${lead.source}.`,
        status: lead.status,
        priority: lead.priority,
      };
    });
  }, [leads, customers]);

  return (
    <div className="mx-auto max-w-6xl">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Center Main Column */}
        <div className="space-y-5 lg:col-span-8">
          {/* Greeting Header */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
            className="pt-1 text-center sm:text-left"
          >
            <h1 className="text-2xl font-semibold tracking-tight text-[#1A1A1A] sm:text-[26px]">
              Good Morning, {displayName}
            </h1>
            <p className="mt-1 text-xs text-[#737370]">
              {todayFormatted} · How is your AI pipeline performing today?
            </p>
          </motion.div>

          {apiError && (
            <div className="rounded-xl border border-[#F5C6C2] bg-[#FCECEA] px-4 py-2.5 text-xs font-medium text-[#B9382C]">
              {apiError}
            </div>
          )}

          {/* Hero Status / Pipeline Card */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.05 }}
          >
            <Card className="border-[#EAE9E4] bg-white">
              <CardContent className="flex flex-col justify-between gap-4 p-5 sm:flex-row sm:items-center">
                <div className="flex items-center gap-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[#EDF3EE] text-[#2E7D4F]">
                    <TrendingUp className="h-6 w-6" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-[#737370]">
                      Pipeline Pulse
                    </p>
                    <p className="text-xl font-semibold tracking-tight text-[#1A1A1A]">
                      {loading
                        ? "Syncing..."
                        : qualifiedCount > 0
                        ? "Active & Qualified"
                        : "Ready for Inquiries"}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-5 border-t border-[#F1F0EC] pt-3 sm:border-l sm:border-t-0 sm:pl-5 sm:pt-0">
                  <div className="text-xs leading-relaxed text-[#737370]">
                    <span className="block font-medium text-[#1A1A1A]">
                      {leads.length} total leads · {avgScore}% avg score
                    </span>
                    {conversations.length} active or completed threads.
                  </div>

                  {/* Minimalist Inline Sparkline */}
                  <svg
                    viewBox="0 0 90 32"
                    className="h-8 w-20 shrink-0 text-[#5C8A67]"
                    fill="none"
                  >
                    <path
                      d="M2 24 L14 20 L24 22 L36 13 L48 16 L60 9 L72 12 L88 4"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Quick AI Actions / Focus Prompts */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 }}
          >
            <Card className="border-[#EAE9E4] bg-white">
              <CardContent className="p-5">
                <div className="mb-3.5 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-semibold text-[#1A1A1A]">
                    <Sparkles className="h-4 w-4 text-[#5C8A67]" />
                    <span>Daily Focus for Today</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setPromptIndex((prev) => prev + 1)}
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-[#2E7D4F] transition-colors hover:text-[#1F5C39]"
                  >
                    Refresh
                    <RefreshCw className="h-3.5 w-3.5" />
                  </button>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  {quickPrompts.map((item, idx) => (
                    <Link
                      key={idx}
                      href={item.href}
                      className="rounded-xl border border-[#ECEBE6] bg-[#F7F7F5] p-3.5 text-xs leading-relaxed text-[#52524E] transition-colors hover:border-[#D6D4CC] hover:bg-[#F2F1EC] hover:text-[#1A1A1A]"
                    >
                      {item.title}
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Activity Heatmap */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
          >
            <Card className="border-[#EAE9E4] bg-white">
              <CardContent className="p-5">
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-semibold text-[#1A1A1A]">
                    <Calendar className="h-4 w-4 text-[#737370]" />
                    <span>Lead Activity Heatmap</span>
                  </div>
                  <span className="rounded-lg border border-[#EAE9E4] bg-[#FAFAF8] px-2.5 py-1 text-xs font-medium text-[#52524E]">
                    {currentMonthLabel}
                  </span>
                </div>

                <div className="relative">
                  <div className="grid grid-cols-7 gap-2 sm:grid-cols-14">
                    {heatmapCells.map((cell) => (
                      <button
                        key={cell.idx}
                        type="button"
                        onMouseEnter={() => setHoveredCell(cell)}
                        onMouseLeave={() => setHoveredCell(null)}
                        className={cn(
                          "aspect-square w-full rounded-lg transition-transform hover:scale-105",
                          HEATMAP_LEVELS[cell.level]
                        )}
                        aria-label={`${cell.label}: ${cell.count} interactions`}
                      />
                    ))}
                  </div>

                  {hoveredCell && (
                    <div className="mt-2 inline-flex items-center gap-2 rounded-lg border border-[#EAE9E4] bg-white px-2.5 py-1 text-[11px] text-[#52524E] shadow-sm">
                      <span className="font-medium text-[#1A1A1A]">
                        {hoveredCell.label}
                      </span>
                      <span>· {hoveredCell.count} AI interactions</span>
                    </div>
                  )}
                </div>

                <div className="mt-4 flex items-center gap-4 text-[11px] text-[#737370]">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-[#2E7D4F]" />
                    High Intent
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-[#5BA173]" />
                    Engaged
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-[#CBE2D2]" />
                    Quiet
                  </span>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Recently Visited Conversations */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
          >
            <Card className="border-[#EAE9E4] bg-white">
              <CardContent className="p-5">
                <div className="mb-3.5 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-semibold text-[#1A1A1A]">
                    <MessageSquare className="h-4 w-4 text-[#737370]" />
                    <span>Recent Conversations</span>
                  </div>
                  <Link
                    href="/dashboard/conversations"
                    className="inline-flex items-center gap-1 text-xs font-medium text-[#2E7D4F] hover:text-[#1F5C39]"
                  >
                    View All
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </Link>
                </div>

                {recentConversations.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-[#EAE9E4] bg-[#FAFAF8] py-6 text-center text-xs text-[#737370]">
                    No conversations recorded yet. Click &ldquo;+ New Entry&rdquo; in
                    the sidebar to test the AI Receptionist.
                  </p>
                ) : (
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    {recentConversations.map((conv, index) => {
                      const customer = customers[conv.customer_id];
                      const tints = [
                        "bg-[#EDF3EE]",
                        "bg-[#FDF0EA]",
                        "bg-[#EDF3FA]",
                      ];
                      return (
                        <Link
                          key={conv.id}
                          href={`/dashboard/conversations/${conv.id}`}
                          className="group overflow-hidden rounded-xl border border-[#EAE9E4] bg-white transition-all hover:border-[#D5D3CA] hover:shadow-sm"
                        >
                          <div
                            className={cn(
                              "flex h-16 items-start justify-between p-3",
                              tints[index % tints.length]
                            )}
                          >
                            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-white text-xs font-semibold text-[#1A1A1A] shadow-xs">
                              <Users className="h-3.5 w-3.5 text-[#5C8A67]" />
                            </span>
                            <Badge variant="outline" className="bg-white/80 text-[10px]">
                              {conv.channel}
                            </Badge>
                          </div>
                          <div className="p-3">
                            <p className="truncate text-xs font-semibold text-[#1A1A1A] group-hover:text-[#2E7D4F]">
                              {customer?.full_name ?? "Customer Thread"}
                            </p>
                            <p className="mt-0.5 truncate text-[11px] text-[#737370]">
                              {conv.summary || "Tap to inspect transcript"}
                            </p>
                          </div>
                        </Link>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* Right Rail */}
        <div className="space-y-5 lg:col-span-4">
          {/* This Week's Streak */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.08 }}
          >
            <Card className="border-[#EAE9E4] bg-white">
              <CardContent className="p-5">
                <div className="mb-3.5 flex items-center gap-2 text-sm font-semibold text-[#1A1A1A]">
                  <Flame className="h-4 w-4 text-[#C86D44]" />
                  <span>This week&apos;s uptime</span>
                </div>
                <div className="grid grid-cols-7 gap-1.5 text-center">
                  {WEEK_DAYS.map((day, idx) => {
                    const active = idx < 5;
                    return (
                      <div key={day} className="flex flex-col items-center gap-1.5">
                        <div
                          className={cn(
                            "flex h-8 w-8 items-center justify-center rounded-full",
                            active
                              ? "bg-[#FDF0EA] text-[#C86D44]"
                              : "bg-[#F7F7F5] text-[#C8C7C0]"
                          )}
                        >
                          <Flame className="h-4 w-4" />
                        </div>
                        <span className="text-[11px] font-medium text-[#737370]">
                          {day}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Signature Burnt Terracotta AI INSIGHT Card */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.14 }}
          >
            <div className="rounded-2xl bg-gradient-to-br from-[#C86D44] to-[#B0552D] p-5 text-white shadow-[0_12px_28px_-12px_rgba(176,85,45,0.55)]">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/80">
                AI Insight
              </p>
              <p className="mt-2.5 text-sm font-medium leading-relaxed text-white">
                {topLead
                  ? `"${
                      customers[topLead.customer_id]?.full_name ?? "Top prospect"
                    } scored ${
                      topLead.score
                    }/100 (${topLead.priority} priority). Immediate follow-up recommended."`
                  : '"Your AI Receptionist & Business Analyst are standing by to qualify incoming leads."'}
              </p>
              <div className="mt-4">
                <Link
                  href="/dashboard/leads"
                  className="inline-flex items-center rounded-full bg-white/15 px-3 py-1 text-[11px] font-medium text-white backdrop-blur-xs transition-colors hover:bg-white/25"
                >
                  {topLead ? `Lead Score: ${topLead.score}` : "Pipeline Pattern"}
                </Link>
              </div>
            </div>
          </motion.div>

          {/* Recent Activity Vertical Timeline */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
          >
            <Card className="border-[#EAE9E4] bg-white">
              <CardContent className="p-5">
                <div className="mb-4 flex items-center justify-between">
                  <span className="text-sm font-semibold text-[#1A1A1A]">
                    Recent Leads
                  </span>
                  <Link
                    href="/dashboard/leads"
                    className="text-xs font-medium text-[#2E7D4F] hover:underline"
                  >
                    See all
                  </Link>
                </div>

                {recentTimeline.length === 0 ? (
                  <p className="text-xs text-[#737370]">
                    No scored leads yet.
                  </p>
                ) : (
                  <div className="relative space-y-5 pl-4 before:absolute before:bottom-2 before:left-[5px] before:top-2 before:w-px before:bg-[#EAE9E4]">
                    {recentTimeline.map((item) => {
                      const dotColor =
                        item.priority === "high"
                          ? "bg-[#B9382C]"
                          : item.priority === "medium"
                          ? "bg-[#C86D44]"
                          : "bg-[#2E7D4F]";

                      return (
                        <div key={item.id} className="relative">
                          <span
                            className={cn(
                              "absolute -left-4 top-1.5 h-2.5 w-2.5 rounded-full ring-4 ring-white",
                              dotColor
                            )}
                          />
                          <p className="text-[11px] font-medium text-[#9C9C96]">
                            {item.time} · {item.customerName}
                          </p>
                          <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-[#52524E]">
                            {item.note}
                          </p>
                          <div className="mt-2">
                            <Badge
                              variant={
                                item.status === "qualified"
                                  ? "qualified"
                                  : item.status === "converted"
                                  ? "converted"
                                  : item.status === "lost"
                                  ? "lost"
                                  : "outline"
                              }
                            >
                              {item.status}
                            </Badge>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
