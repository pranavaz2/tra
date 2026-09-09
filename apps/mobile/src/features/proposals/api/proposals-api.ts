/**
 * Proposals API Service.
 *
 * Connects directly to FastAPI Travel Planning endpoints:
 * - POST /api/v1/trips/{trip_id}/planning/proposals (Generate proposal)
 * - GET  /api/v1/trips/{trip_id}/planning/proposals (Get proposal by trip)
 * - GET  /api/v1/planning/proposals/{proposal_id}   (Get proposal by ID)
 * - POST /api/v1/planning/proposals/{proposal_id}/accept (Accept proposal)
 * - POST /api/v1/planning/proposals/{proposal_id}/reject (Reject proposal)
 * - GET  /api/v1/planning/proposals                  (List user proposals)
 */

import { apiClient } from "@/core/api/client";
import {
  ProposalResponse,
  ProposalCreateRequest,
  ProposalPageResponse,
} from "@/core/api/types";

export const ProposalsApi = {
  /**
   * Request a new AI travel proposal for a trip.
   */
  async requestProposal(
    tripId: string,
    payload: ProposalCreateRequest
  ): Promise<ProposalResponse> {
    return apiClient.post<ProposalResponse>(
      `/trips/${tripId}/planning/proposals`,
      payload
    );
  },

  /**
   * Get the latest travel proposal for a given trip.
   */
  async getProposalByTrip(tripId: string): Promise<ProposalResponse> {
    return apiClient.get<ProposalResponse>(
      `/trips/${tripId}/planning/proposals`
    );
  },

  /**
   * Get a proposal by its unique ID.
   */
  async getProposal(proposalId: string): Promise<ProposalResponse> {
    return apiClient.get<ProposalResponse>(
      `/planning/proposals/${proposalId}`
    );
  },

  /**
   * Accept an AI proposal (transitions status to 'accepted' and atomically populates the itinerary).
   */
  async acceptProposal(
    proposalId: string,
    applyToItinerary: boolean = true
  ): Promise<ProposalResponse> {
    return apiClient.post<ProposalResponse>(
      `/planning/proposals/${proposalId}/accept?apply_to_itinerary=${applyToItinerary}`
    );
  },

  /**
   * Reject an AI proposal (transitions status to 'rejected').
   */
  async rejectProposal(proposalId: string): Promise<ProposalResponse> {
    return apiClient.post<ProposalResponse>(
      `/planning/proposals/${proposalId}/reject`
    );
  },

  /**
   * List paginated proposals owned by the authenticated user.
   */
  async listProposals(
    limit: number = 20,
    cursor?: string
  ): Promise<ProposalPageResponse> {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    if (cursor) params.set("cursor", cursor);

    return apiClient.get<ProposalPageResponse>(
      `/planning/proposals?${params.toString()}`
    );
  },
};
