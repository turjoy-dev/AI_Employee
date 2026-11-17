"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { CheckCircle2, ExternalLink, MessageSquarePlus, Search, Sparkles, Users } from "lucide-react";

import { FollowUpModal } from "@/components/leads/FollowUpModal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, Customer, Lead } from "@/lib/api";

export function LeadsClient() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [customers, setCustomers] = useState<Record<string, Customer>>({});
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [followUpLead, setFollowUpLead] = useState<Lead | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!toastMessage) return;
    const timer = window.setTimeout(() => setToastMessage(null), 4000);
    return () => window.clearTimeout(timer);
  }, [toastMessage]);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [leadsRes, custRes] = await Promise.all([
          api.get<Lead[]>("/leads"),
          api.get<Customer[]>("/customers"),
        ]);
        if (!active) return;

        setLeads(leadsRes.data ?? []);
        const custMap: Record<string, Customer> = {};
        for (const c of custRes.data ?? []) {
          custMap[c.id] = c;
        }
        setCustomers(custMap);
        setApiError(null);
      } catch {
        if (active) {
          setApiError(
            "Unable to load leads. Verify the FastAPI server is running."
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

  const filteredLeads = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return leads;
    return leads.filter((lead) => {
      const cust = customers[lead.customer_id];
      return (
        lead.status.toLowerCase().includes(q) ||
        lead.priority.toLowerCase().includes(q) ||
        lead.source.toLowerCase().includes(q) ||
        (lead.notes ?? "").toLowerCase().includes(q) ||
        (cust?.full_name ?? "").toLowerCase().includes(q) ||
        (cust?.phone_number ?? "").toLowerCase().includes(q)
      );
    });
  }, [leads, customers, search]);

  const priorityVariant = (priority: string) => {
    if (priority === "high") return "high" as const;
    if (priority === "medium") return "medium" as const;
    return "low" as const;
  };

  const statusVariant = (status: string) => {
    if (status === "qualified") return "qualified" as const;
    if (status === "converted") return "converted" as const;
    if (status === "lost") return "lost" as const;
    return "outline" as const;
  };

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
            Leads Pipeline
          </h1>
          <p className="mt-1 text-xs text-[#737370]">
            Automatically scored and prioritized by the AI Business Analyst.
          </p>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9C9C96]" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search customer, priority, status..."
            className="bg-white pl-9"
          />
        </div>
      </motion.div>

      <Card className="border-[#EAE9E4] bg-white">
        <CardHeader className="flex flex-row items-center justify-between border-b border-[#F1F0EC] pb-4">
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4 text-[#5C8A67]" />
            <CardTitle className="text-sm font-semibold">
              All Captured Leads ({filteredLeads.length})
            </CardTitle>
          </div>
          <span className="inline-flex items-center gap-1 rounded-full bg-[#EDF3EE] px-2.5 py-0.5 text-[11px] font-medium text-[#2E7D4F]">
            <Sparkles className="h-3 w-3" />
            Live SQLite Sync
          </span>
        </CardHeader>

        <CardContent className="p-0">
          {apiError ? (
            <div className="m-4 rounded-xl border border-[#F5C6C2] bg-[#FCECEA] px-4 py-3 text-xs font-medium text-[#B9382C]">
              {apiError}
            </div>
          ) : loading ? (
            <div className="py-12 text-center text-sm text-[#737370]">
              Loading leads...
            </div>
          ) : filteredLeads.length === 0 ? (
            <div className="py-12 text-center text-sm text-[#737370]">
              No matching leads found.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Customer</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredLeads.map((lead) => {
                  const customer = customers[lead.customer_id];
                  return (
                    <TableRow key={lead.id}>
                      <TableCell>
                        <div>
                          <p className="font-medium text-[#1A1A1A]">
                            {customer?.full_name ?? "Unknown Customer"}
                          </p>
                          <p className="text-xs text-[#737370]">
                            {customer?.phone_number || customer?.email || lead.customer_id}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-[#1A1A1A]">
                            {lead.score}
                          </span>
                          <span className="text-xs text-[#9C9C96]">/ 100</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={priorityVariant(lead.priority)}>
                          {lead.priority}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={statusVariant(lead.status)}>
                          {lead.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-[#52524E]">
                        {lead.source}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="inline-flex items-center justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setFollowUpLead(lead)}
                            className="gap-1.5 border-[#5C8A67]/40 text-[#2E7D4F] hover:bg-[#EDF3EE] hover:text-[#1E5B37]"
                          >
                            <MessageSquarePlus className="h-3.5 w-3.5" />
                            Follow Up
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setSelectedLead(lead)}
                          >
                            Inspect
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Lead Inspect Dialog */}
      <Dialog
        open={!!selectedLead}
        onOpenChange={(open) => {
          if (!open) setSelectedLead(null);
        }}
      >
        {selectedLead && (
          <>
            <DialogHeader>
              <DialogTitle>
                {customers[selectedLead.customer_id]?.full_name ?? "Lead Details"}
              </DialogTitle>
              <DialogDescription>
                AI Business Analyst qualification breakdown and notes.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-xl border border-[#EAE9E4] bg-[#FAFAF8] p-3">
                  <p className="text-[11px] text-[#737370]">Score</p>
                  <p className="mt-0.5 text-lg font-semibold text-[#1A1A1A]">
                    {selectedLead.score}/100
                  </p>
                </div>
                <div className="rounded-xl border border-[#EAE9E4] bg-[#FAFAF8] p-3">
                  <p className="text-[11px] text-[#737370]">Priority</p>
                  <div className="mt-1">
                    <Badge variant={priorityVariant(selectedLead.priority)}>
                      {selectedLead.priority}
                    </Badge>
                  </div>
                </div>
                <div className="rounded-xl border border-[#EAE9E4] bg-[#FAFAF8] p-3">
                  <p className="text-[11px] text-[#737370]">Status</p>
                  <div className="mt-1">
                    <Badge variant={statusVariant(selectedLead.status)}>
                      {selectedLead.status}
                    </Badge>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-[#EAE9E4] bg-[#F7F7F5] p-4">
                <p className="text-xs font-semibold text-[#1A1A1A]">
                  Analyst Notes
                </p>
                <p className="mt-1.5 text-xs leading-relaxed text-[#52524E]">
                  {selectedLead.notes || "No additional analyst notes recorded."}
                </p>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button
                  variant="outline"
                  onClick={() => setSelectedLead(null)}
                >
                  Close
                </Button>
                {selectedLead.conversation_id && (
                  <Link
                    href={`/dashboard/conversations/${selectedLead.conversation_id}`}
                    className="inline-flex h-9 items-center justify-center rounded-lg bg-[#5C8A67] px-3.5 text-xs font-medium text-white transition-colors hover:bg-[#4D7757]"
                  >
                    Open Transcript
                    <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                  </Link>
                )}
              </div>
            </div>
          </>
        )}
      </Dialog>

      {/* AI Lead Follow-Up Modal */}
      <FollowUpModal
        key={followUpLead?.id ?? "closed"}
        isOpen={!!followUpLead}
        onClose={() => setFollowUpLead(null)}
        leadId={followUpLead?.id ?? null}
        customerName={
          followUpLead ? customers[followUpLead.customer_id]?.full_name : undefined
        }
        onSuccess={async () => {
          setToastMessage("Follow-up message sent and saved to lead history.");
          try {
            const leadsRes = await api.get<Lead[]>("/leads");
            setLeads(leadsRes.data ?? []);
          } catch {
            // ignore background refresh error
          }
        }}
      />

      {toastMessage && (
        <div
          role="status"
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-xl border border-[#5C8A67]/40 bg-[#EDF3EE] px-4 py-3 text-xs font-medium text-[#1E5B37] shadow-lg"
        >
          <CheckCircle2 className="h-4 w-4 shrink-0 text-[#2E7D4F]" />
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
