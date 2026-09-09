/**
 * Trips API Client.
 *
 * Interacts with backend FastAPI /api/v1/trips routes.
 */

import { apiClient } from "@/core/api/client";
import {
  TripCreateRequest,
  TripPageResponse,
  TripResponse,
  TripStatus,
  TripUpdateRequest,
} from "@/core/api/types";

export interface ListTripsParams {
  limit?: number;
  cursor?: string | null;
  status?: TripStatus | null;
}

export const TripsApi = {
  async listTrips(params: ListTripsParams = {}): Promise<TripPageResponse> {
    const query = new URLSearchParams();
    if (params.limit) query.append("limit", params.limit.toString());
    if (params.cursor) query.append("cursor", params.cursor);
    if (params.status) query.append("status", params.status);

    const queryString = query.toString();
    const endpoint = `/trips${queryString ? `?${queryString}` : ""}`;
    return apiClient.get<TripPageResponse>(endpoint);
  },

  async getTrip(tripId: string): Promise<TripResponse> {
    return apiClient.get<TripResponse>(`/trips/${tripId}`);
  },

  async createTrip(payload: TripCreateRequest): Promise<TripResponse> {
    return apiClient.post<TripResponse>("/trips", payload);
  },

  async updateTrip(tripId: string, payload: TripUpdateRequest): Promise<TripResponse> {
    return apiClient.patch<TripResponse>(`/trips/${tripId}`, payload);
  },

  async transitionTripStatus(tripId: string, newStatus: TripStatus): Promise<TripResponse> {
    return apiClient.patch<TripResponse>(`/trips/${tripId}`, {
      new_status: newStatus,
      update_dates: false,
    });
  },

  async deleteTrip(tripId: string): Promise<void> {
    return apiClient.delete<void>(`/trips/${tripId}`);
  },
};
