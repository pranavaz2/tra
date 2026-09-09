/**
 * Assistant API Client.
 *
 * Provides typed endpoints to communicate with the trip-scoped AI assistant.
 */

import { apiClient } from "@/core/api/client";
import {
  ChatAssistantRequest,
  ChatAssistantResponse,
  ChatMessageSchema,
  ConfirmActionResponse,
  ConversationHistoryResponse,
  RejectActionResponse,
  TripWarningsResponse,
} from "@/core/api/types";

export const AssistantApi = {
  /**
   * Fetch trip assistant persisted conversation history.
   */
  async getHistory(tripId: string): Promise<ConversationHistoryResponse> {
    return apiClient.get<ConversationHistoryResponse>(
      `/trips/${tripId}/assistant/history`
    );
  },

  /**
   * Clear trip assistant persisted conversation history.
   */
  async clearHistory(tripId: string): Promise<{ cleared: boolean; message: string }> {
    return apiClient.delete<{ cleared: boolean; message: string }>(
      `/trips/${tripId}/assistant/history`
    );
  },

  /**
   * Send a chat prompt to the trip assistant with optional history.
   */
  async chat(
    tripId: string,
    message: string,
    history?: ChatMessageSchema[]
  ): Promise<ChatAssistantResponse> {
    const payload: ChatAssistantRequest = {
      message,
      history: history || [],
    };
    return apiClient.post<ChatAssistantResponse>(
      `/trips/${tripId}/assistant/chat`,
      payload
    );
  },

  /**
   * Confirm and apply a proposed mutation to the trip.
   */
  async confirmAction(
    tripId: string,
    actionId: string
  ): Promise<ConfirmActionResponse> {
    return apiClient.post<ConfirmActionResponse>(
      `/trips/${tripId}/assistant/actions/${actionId}/confirm`
    );
  },

  /**
   * Cancel/reject a proposed mutation without changing any trip data.
   */
  async rejectAction(
    tripId: string,
    actionId: string
  ): Promise<RejectActionResponse> {
    return apiClient.post<RejectActionResponse>(
      `/trips/${tripId}/assistant/actions/${actionId}/reject`
    );
  },

  /**
   * Fetch proactive travel warnings (itinerary conflicts, travel feasibility, budget risks).
   */
  async getWarnings(tripId: string): Promise<TripWarningsResponse> {
    return apiClient.get<TripWarningsResponse>(
      `/trips/${tripId}/warnings`
    );
  },
};

