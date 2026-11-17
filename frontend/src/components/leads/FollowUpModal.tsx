"use client";

import { useState } from "react";
import { Loader2, Send, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";

export interface FollowUpModalProps {
  isOpen: boolean;
  onClose: () => void;
  leadId: string | null;
  customerName?: string;
  onSuccess?: (message: string) => void;
}

export function FollowUpModal({
  isOpen,
  onClose,
  leadId,
  customerName,
  onSuccess,
}: FollowUpModalProps) {
  const [message, setMessage] = useState("");
  const [generating, setGenerating] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClose = () => {
    setMessage("");
    setError(null);
    setGenerating(false);
    setSending(false);
    onClose();
  };

  const handleGenerateWithAI = async () => {
    if (!leadId || generating || sending) return;
    setError(null);
    setGenerating(true);
    try {
      const res = await api.post<{ draft: string }>(
        `/leads/${encodeURIComponent(leadId)}/draft-follow-up`,
        undefined,
        { timeout: 30000 }
      );
      if (res.data?.draft) {
        setMessage(res.data.draft);
      }
    } catch {
      setError("Failed to generate AI follow-up draft. Please try again.");
    } finally {
      setGenerating(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!leadId || !message.trim() || sending || generating) return;
    setError(null);
    setSending(true);
    try {
      await api.post<{ status: string }>(
        `/leads/${encodeURIComponent(leadId)}/send-follow-up`,
        { message: message.trim() }
      );
      const sentContent = message.trim();
      onSuccess?.(sentContent);
      handleClose();
    } catch {
      setError("Unable to send follow-up message. Verify the backend is running.");
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog
      open={isOpen && !!leadId}
      onOpenChange={(open) => {
        if (!open && !sending) handleClose();
      }}
    >
      <DialogHeader>
        <DialogTitle>
          Lead Follow-Up{customerName ? ` — ${customerName}` : ""}
        </DialogTitle>
        <DialogDescription>
          Write a personalized follow-up message or generate a context-aware draft using AI.
        </DialogDescription>
      </DialogHeader>

      <form onSubmit={handleSendMessage} className="space-y-4">
        {error && (
          <div className="rounded-xl border border-[#F5C6C2] bg-[#FCECEA] px-3.5 py-2.5 text-xs font-medium text-[#B9382C]">
            {error}
          </div>
        )}

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label
              htmlFor="lead-followup-textarea"
              className="text-xs font-medium text-[#52524E]"
            >
              Follow-Up Message
            </label>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleGenerateWithAI}
              disabled={generating || sending || !leadId}
              className="h-8 gap-1.5 border-[#5C8A67]/40 bg-[#EDF3EE]/60 text-[#2E7D4F] hover:bg-[#EDF3EE] hover:text-[#1E5B37]"
            >
              {generating ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Drafting...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>✨ Generate with AI</span>
                </>
              )}
            </Button>
          </div>

          <textarea
            id="lead-followup-textarea"
            rows={6}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Type your follow-up message here, or click 'Generate with AI'..."
            disabled={generating || sending}
            className="w-full resize-y rounded-xl border border-[#EAE9E4] bg-[#FAFAF8] p-3 text-xs leading-relaxed text-[#1A1A1A] placeholder:text-[#9C9C96] focus:border-[#5C8A67] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#5C8A67]/20 disabled:opacity-60"
          />
        </div>

        <div className="flex items-center justify-end gap-2 pt-1">
          <Button
            type="button"
            variant="outline"
            onClick={handleClose}
            disabled={sending}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={!message.trim() || sending || generating}
            className="gap-1.5 bg-[#5C8A67] text-white hover:bg-[#4D7757]"
          >
            {sending ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Sending...</span>
              </>
            ) : (
              <>
                <Send className="h-3.5 w-3.5" />
                <span>Send Message</span>
              </>
            )}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
