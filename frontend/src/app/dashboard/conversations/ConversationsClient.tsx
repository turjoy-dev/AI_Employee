"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, MessageSquare, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, Conversation, Customer } from "@/lib/api";

export function ConversationsClient() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [customers, setCustomers] = useState<Record<string, Customer>>({});
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [convsRes, custRes] = await Promise.all([
          api.get<Conversation[]>("/conversations"),
          api.get<Customer[]>("/customers"),
        ]);
        if (!active) return;

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
            "Unable to load conversations. Verify the FastAPI server is running."
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

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((conv) => {
      const customer = customers[conv.customer_id];
      return (
        conv.channel.toLowerCase().includes(q) ||
        conv.status.toLowerCase().includes(q) ||
        (conv.summary ?? "").toLowerCase().includes(q) ||
        (customer?.full_name ?? "").toLowerCase().includes(q)
      );
    });
  }, [conversations, customers, search]);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"
      >
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#1A1A1A]">
            Conversations
          </h1>
          <p className="mt-1 text-xs text-[#737370]">
            Browse customer threads handled by the AI Receptionist and summarized
            by the AI Analyst.
          </p>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9C9C96]" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search customer or summary..."
            className="bg-white pl-9"
          />
        </div>
      </motion.div>

      {apiError ? (
        <div className="rounded-xl border border-[#F5C6C2] bg-[#FCECEA] px-4 py-3 text-xs font-medium text-[#B9382C]">
          {apiError}
        </div>
      ) : loading ? (
        <div className="py-12 text-center text-sm text-[#737370]">
          Loading conversations...
        </div>
      ) : filtered.length === 0 ? (
        <Card className="border-[#EAE9E4] bg-white">
          <CardContent className="py-12 text-center text-sm text-[#737370]">
            No conversations found.
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {filtered.map((conv) => {
            const customer = customers[conv.customer_id];
            return (
              <Link
                key={conv.id}
                href={`/dashboard/conversations/${conv.id}`}
                className="group block"
              >
                <Card className="h-full border-[#EAE9E4] bg-white transition-all group-hover:border-[#D5D3CA] group-hover:shadow-md">
                  <CardContent className="flex h-full flex-col justify-between p-5">
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#EDF3EE] text-[#2E7D4F]">
                            <MessageSquare className="h-4 w-4" />
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-[#1A1A1A] group-hover:text-[#2E7D4F]">
                              {customer?.full_name ?? "Customer Thread"}
                            </p>
                            <p className="text-[11px] text-[#737370]">
                              {conv.started_at
                                ? new Date(conv.started_at).toLocaleString()
                                : "Recently"}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-1.5">
                          <Badge variant="outline">{conv.channel}</Badge>
                          <Badge
                            variant={
                              conv.status === "active" ? "qualified" : "low"
                            }
                          >
                            {conv.status}
                          </Badge>
                        </div>
                      </div>

                      <p className="mt-3.5 line-clamp-3 text-xs leading-relaxed text-[#52524E]">
                        {conv.summary ||
                          "No AI summary generated yet. Open transcript to inspect messages."}
                      </p>
                    </div>

                    <div className="mt-4 flex items-center justify-between border-t border-[#F1F0EC] pt-3 text-xs font-medium text-[#2E7D4F]">
                      <span>Inspect Transcript</span>
                      <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                    </div>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
