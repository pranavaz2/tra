/**
 * useAssistant Hook.
 *
 * Manages trip-scoped AI assistant conversation state, persistent multi-turn history,
 * proposed actions, mutations, and role-based action enforcement.
 */

import { useState, useEffect, useCallback } from "react";
import { AssistantApi } from "../api/assistant-api";
import { useCollaboration } from "@/features/collaboration/hooks/use-collaboration";
import {
  AssistantResponseType,
  ChatMessageSchema,
  ProposedActionSchema,
} from "@/core/api/types";
import { TravixApiError } from "@/core/api/client";

export interface AssistantUIMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  responseType?: AssistantResponseType;
  proposedAction?: ProposedActionSchema | null;
  toolsUsed?: string[];
}

const DEFAULT_GREETING: AssistantUIMessage = {
  id: "initial-greeting",
  role: "assistant",
  content:
    "Hello! I am your Travix AI assistant for this trip. I can answer questions about your schedule, check expenses and budget, or propose adjustments to your itinerary and budget limit. How can I help you today?",
  timestamp: new Date().toISOString(),
  responseType: "informational",
};

export function useAssistant(tripId: string, tripOwnerId?: string) {
  const [messages, setMessages] = useState<AssistantUIMessage[]>([DEFAULT_GREETING]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isHistoryLoading, setIsHistoryLoading] = useState<boolean>(false);
  const [isMutating, setIsMutating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const { userRole, isViewer, isOwner, isEditor } = useCollaboration(
    tripId,
    tripOwnerId
  );

  // Load persisted conversation history on mount / trip change
  const loadHistory = useCallback(async () => {
    if (!tripId) return;
    setIsHistoryLoading(true);
    try {
      const historyData = await AssistantApi.getHistory(tripId);
      if (historyData && historyData.messages && historyData.messages.length > 0) {
        const loaded: AssistantUIMessage[] = historyData.messages.map((m) => ({
          id: m.message_id || `msg-${Math.random().toString(36).substring(2, 9)}`,
          role: m.role as "user" | "assistant" | "system",
          content: m.content,
          timestamp: m.created_at,
          responseType: m.response_type || undefined,
          toolsUsed: m.tools_used,
        }));
        setMessages(loaded);
      } else {
        setMessages([DEFAULT_GREETING]);
      }
    } catch (err: any) {
      // Non-fatal: keep default greeting on initial fetch failure
      console.warn("Failed to load assistant conversation history:", err);
    } finally {
      setIsHistoryLoading(false);
    }
  }, [tripId]);


  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) return;

      const userMsgId = `user-${Date.now()}`;
      const nowIso = new Date().toISOString();
      const userMessage: AssistantUIMessage = {
        id: userMsgId,
        role: "user",
        content: text.trim(),
        timestamp: nowIso,
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      setError(null);

      try {
        const historyPayload: ChatMessageSchema[] = messages.map((m) => ({
          role: m.role,
          content: m.content,
          timestamp: m.timestamp,
        }));

        const response = await AssistantApi.chat(
          tripId,
          text.trim(),
          historyPayload
        );

        const assistantMsgId = `assistant-${Date.now()}`;
        const assistantMessage: AssistantUIMessage = {
          id: assistantMsgId,
          role: "assistant",
          content: response.message,
          timestamp: new Date().toISOString(),
          responseType: response.response_type,
          proposedAction: response.proposed_action,
          toolsUsed: response.tools_used,
        };

        setMessages((prev) => [...prev, assistantMessage]);
      } catch (err: any) {
        if (err instanceof TravixApiError) {
          setError(err.message);
        } else {
          setError("Failed to communicate with assistant. Please try again.");
        }
      } finally {
        setIsLoading(false);
      }
    },
    [tripId, messages, isLoading]
  );

  const confirmAction = useCallback(
    async (actionId: string) => {
      if (isViewer) {
        setError("Viewers cannot execute trip modifications.");
        return;
      }

      setIsMutating(true);
      setError(null);
      try {
        const res = await AssistantApi.confirmAction(tripId, actionId);

        // Update action status in local messages
        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.proposedAction?.action_id === actionId) {
              return {
                ...msg,
                proposedAction: {
                  ...msg.proposedAction,
                  status: "applied",
                  applied_at: new Date().toISOString(),
                },
              };
            }
            return msg;
          })
        );

        // Append system confirmation notice
        const noticeMsg: AssistantUIMessage = {
          id: `system-${Date.now()}`,
          role: "system",
          content: `✅ ${res.message || "Changes applied successfully."}`,
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, noticeMsg]);
      } catch (err: any) {
        if (err instanceof TravixApiError) {
          setError(err.message);
        } else {
          setError("Failed to apply proposed action.");
        }
      } finally {
        setIsMutating(false);
      }
    },
    [tripId, isViewer]
  );

  const rejectAction = useCallback(
    async (actionId: string) => {
      setIsMutating(true);
      setError(null);
      try {
        await AssistantApi.rejectAction(tripId, actionId);

        // Update action status in local messages
        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.proposedAction?.action_id === actionId) {
              return {
                ...msg,
                proposedAction: {
                  ...msg.proposedAction,
                  status: "rejected",
                },
              };
            }
            return msg;
          })
        );

        // Append system cancellation notice
        const noticeMsg: AssistantUIMessage = {
          id: `system-${Date.now()}`,
          role: "system",
          content: "❌ Proposed change was cancelled.",
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, noticeMsg]);
      } catch (err: any) {
        if (err instanceof TravixApiError) {
          setError(err.message);
        } else {
          setError("Failed to cancel proposed action.");
        }
      } finally {
        setIsMutating(false);
      }
    },
    [tripId]
  );

  const clearHistory = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await AssistantApi.clearHistory(tripId);
      setMessages([DEFAULT_GREETING]);
    } catch (err: any) {
      if (err instanceof TravixApiError) {
        setError(err.message);
      } else {
        setError("Failed to clear chat history.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [tripId]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    messages,
    isLoading,
    isHistoryLoading,
    isMutating,
    error,
    clearError,
    sendMessage,
    confirmAction,
    rejectAction,
    clearHistory,
    refreshHistory: loadHistory,
    userRole,
    isViewer,
    isOwner,
    isEditor,
  };
}

