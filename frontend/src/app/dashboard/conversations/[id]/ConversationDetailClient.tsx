"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, Bot, Send, User } from "lucide-react";

import { CallButton } from "@/components/CallButton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, Conversation, Customer, Lead, Message } from "@/lib/api";
import { cn } from "@/lib/utils";

export function ConversationDetailClient() {
  const params = useParams<{ id: string }>();
  const conversationId = params?.id;

  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [lead, setLead] = useState<Lead | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  const [replyText, setReplyText] = useState("");
  const [sending, setSending] = useState(false);

  const fetchThread = useCallback(async () => {
    if (!conversationId) return;
    try {
      const [convRes, msgRes, leadsRes] = await Promise.all([
        api.get<Conversation>(`/conversations/${conversationId}`),
        api.get<Message[]>(`/messages?conversation_id=${conversationId}`),
        api.get<Lead[]>("/leads"),
      ]);
      const conv = convRes.data;
      setConversation(conv);
      setMessages(msgRes.data ?? []);

      const matchingLead = (leadsRes.data ?? []).find(
        (l) => l.conversation_id === conversationId
      );
      setLead(matchingLead ?? null);

      if (conv?.customer_id) {
        try {
          const custRes = await api.get<Customer>(
            `/customers/${conv.customer_id}`
          );
          setCustomer(custRes.data);
        } catch {
          // Optional customer fetch
        }
      }
      setApiError(null);
    } catch {
      setApiError(
        "Unable to load conversation thread. Verify the FastAPI server is running."
      );
    } finally {
      setLoading(false);
    }
  }, [conversationId]);

  useEffect(() => {
    const id = window.requestAnimationFrame(() => {
      void fetchThread();
    });
    return () => window.cancelAnimationFrame(id);
  }, [fetchThread]);

  const handleSendFollowUp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!replyText.trim() || !conversationId || !conversation?.customer_id) return;
    setSending(true);
    try {
      await api.post("/chat/receptionist", {
        customer_id: conversation.customer_id,
        conversation_id: conversationId,
        content: replyText.trim(),
      });
      setReplyText("");
      setApiError(null);
      await fetchThread();
    } catch {
      setApiError("Failed to send message. Please verify the FastAPI backend is reachable.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex items-center justify-between">
        <Link
          href="/dashboard/conversations"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-[#52524E] transition-colors hover:text-[#1A1A1A]"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Conversations
        </Link>
        {conversation && (
          <div className="flex items-center gap-2.5">
            <CallButton conversationId={conversationId} />
            <Badge variant="outline">{conversation.channel}</Badge>
            <Badge
              variant={
                conversation.status === "active" ? "qualified" : "low"
              }
            >
              {conversation.status}
            </Badge>
          </div>
        )}
      </div>

      {apiError && (
        <div className="rounded-xl border border-[#F5C6C2] bg-[#FCECEA] px-4 py-2.5 text-xs font-medium text-[#B9382C]">
          {apiError}
        </div>
      )}

      {loading ? (
        <div className="py-12 text-center text-sm text-[#737370]">
          Loading transcript...
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Transcript Column */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
            className="lg:col-span-8"
          >
            <Card className="flex h-[calc(100vh-12rem)] flex-col border-[#EAE9E4] bg-white">
              <CardHeader className="border-b border-[#F1F0EC] pb-4">
                <CardTitle className="text-base">
                  {customer?.full_name ?? "Customer Transcript"}
                </CardTitle>
                <p className="text-xs text-[#737370]">
                  {customer?.phone_number || customer?.email || conversationId}
                </p>
              </CardHeader>

              <CardContent className="flex-1 space-y-4 overflow-y-auto bg-[#FAFAF8] p-5">
                {messages.length === 0 ? (
                  <p className="py-10 text-center text-xs text-[#737370]">
                    No messages in this conversation yet.
                  </p>
                ) : (
                  messages.map((msg) => {
                    const isUser = msg.role === "user" || msg.role === "customer";
                    return (
                      <div
                        key={msg.id}
                        className={cn(
                          "flex items-start gap-2.5",
                          isUser ? "justify-end" : "justify-start"
                        )}
                      >
                        {!isUser && (
                          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#EDF3EE] text-[#2E7D4F]">
                            <Bot className="h-3.5 w-3.5" />
                          </div>
                        )}

                        <div
                          className={cn(
                            "max-w-[78%] rounded-2xl px-4 py-2.5 text-xs leading-relaxed shadow-xs",
                            isUser
                              ? "bg-[#5C8A67] text-white"
                              : "border border-[#EAE9E4] bg-white text-[#1A1A1A]"
                          )}
                        >
                          <p className="whitespace-pre-wrap">{msg.content}</p>
                          <p
                            className={cn(
                              "mt-1.5 text-[10px]",
                              isUser ? "text-white/75" : "text-[#9C9C96]"
                            )}
                          >
                            {msg.timestamp
                              ? new Date(msg.timestamp).toLocaleTimeString([], {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })
                              : ""}
                          </p>
                        </div>

                        {isUser && (
                          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#ECEBE6] text-[#52524E]">
                            <User className="h-3.5 w-3.5" />
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </CardContent>

              <form
                onSubmit={handleSendFollowUp}
                className="flex items-center gap-2 border-t border-[#F1F0EC] bg-white p-3.5"
              >
                <Input
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Simulate another customer message to the AI Receptionist..."
                  disabled={sending}
                />
                <Button
                  type="submit"
                  disabled={sending || !replyText.trim()}
                  className="bg-[#5C8A67] text-white hover:bg-[#4D7757]"
                >
                  <Send className="h-4 w-4" />
                </Button>
              </form>
            </Card>
          </motion.div>

          {/* Right Analyst Sidebar */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.08 }}
            className="space-y-5 lg:col-span-4"
          >
            {/* Terracotta AI Insight Summary Card */}
            <div className="rounded-2xl bg-gradient-to-br from-[#C86D44] to-[#B0552D] p-5 text-white shadow-[0_12px_28px_-12px_rgba(176,85,45,0.55)]">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/80">
                AI Insight · Conversation Summary
              </p>
              <p className="mt-2.5 text-sm font-medium leading-relaxed text-white">
                {conversation?.summary ||
                  "The AI Business Analyst has not generated a summary for this thread yet."}
              </p>
            </div>

            {/* Lead Qualification Card */}
            <Card className="border-[#EAE9E4] bg-white">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold">
                  Lead Qualification
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {lead ? (
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-xl border border-[#EAE9E4] bg-[#FAFAF8] p-3">
                        <p className="text-[11px] text-[#737370]">Score</p>
                        <p className="mt-0.5 text-lg font-semibold text-[#1A1A1A]">
                          {lead.score}/100
                        </p>
                      </div>
                      <div className="rounded-xl border border-[#EAE9E4] bg-[#FAFAF8] p-3">
                        <p className="text-[11px] text-[#737370]">Priority</p>
                        <div className="mt-1">
                          <Badge
                            variant={
                              lead.priority === "high"
                                ? "high"
                                : lead.priority === "medium"
                                ? "medium"
                                : "low"
                            }
                          >
                            {lead.priority}
                          </Badge>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center justify-between rounded-xl border border-[#EAE9E4] bg-[#FAFAF8] px-3 py-2.5">
                      <span className="text-xs text-[#737370]">Status</span>
                      <Badge
                        variant={
                          lead.status === "qualified"
                            ? "qualified"
                            : lead.status === "converted"
                            ? "converted"
                            : lead.status === "lost"
                            ? "lost"
                            : "outline"
                        }
                      >
                        {lead.status}
                      </Badge>
                    </div>

                    {lead.notes && (
                      <div className="rounded-xl border border-[#EAE9E4] bg-[#F7F7F5] p-3 text-xs leading-relaxed text-[#52524E]">
                        {lead.notes}
                      </div>
                    )}
                  </>
                ) : (
                  <p className="text-xs text-[#737370]">
                    No lead record linked to this conversation yet.
                  </p>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>
      )}
    </div>
  );
}
