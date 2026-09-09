/**
 * Itinerary API Client.
 *
 * Interacts with backend FastAPI /api/v1/trips/{trip_id}/itinerary routes.
 */

import { apiClient } from "@/core/api/client";
import {
  ItineraryDayCreateRequest,
  ItineraryDayUpdateRequest,
  ItineraryItemCreateRequest,
  ItineraryItemUpdateRequest,
  ItineraryResponse,
} from "@/core/api/types";

export const ItineraryApi = {
  async getItinerary(tripId: string): Promise<ItineraryResponse> {
    return apiClient.get<ItineraryResponse>(`/trips/${tripId}/itinerary`);
  },

  async addDay(
    tripId: string,
    payload: ItineraryDayCreateRequest
  ): Promise<ItineraryResponse> {
    return apiClient.post<ItineraryResponse>(`/trips/${tripId}/itinerary/days`, payload);
  },

  async updateDay(
    tripId: string,
    dayId: string,
    payload: ItineraryDayUpdateRequest
  ): Promise<ItineraryResponse> {
    return apiClient.patch<ItineraryResponse>(
      `/trips/${tripId}/itinerary/days/${dayId}`,
      payload
    );
  },

  async removeDay(tripId: string, dayId: string): Promise<ItineraryResponse> {
    return apiClient.delete<ItineraryResponse>(
      `/trips/${tripId}/itinerary/days/${dayId}`
    );
  },

  async addItem(
    tripId: string,
    payload: ItineraryItemCreateRequest
  ): Promise<ItineraryResponse> {
    return apiClient.post<ItineraryResponse>(`/trips/${tripId}/itinerary/items`, payload);
  },

  async updateItem(
    tripId: string,
    itemId: string,
    payload: ItineraryItemUpdateRequest
  ): Promise<ItineraryResponse> {
    return apiClient.patch<ItineraryResponse>(
      `/trips/${tripId}/itinerary/items/${itemId}`,
      payload
    );
  },

  async removeItem(tripId: string, itemId: string): Promise<ItineraryResponse> {
    return apiClient.delete<ItineraryResponse>(
      `/trips/${tripId}/itinerary/items/${itemId}`
    );
  },
};
