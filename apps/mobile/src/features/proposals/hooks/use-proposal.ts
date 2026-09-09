/**
 * useProposal Hook.
 *
 * Manages travel proposal lifecycle:
 * - Fetching proposal by trip or ID
 * - Requesting new AI proposal
 * - Accept / Reject transitions
 * - Converting approved proposal into real itinerary days & activities
 */

import { useState, useEffect, useCallback } from "react";
import { ProposalsApi } from "../api/proposals-api";
import { ItineraryApi } from "@/features/itinerary/api/itinerary-api";
import {
  ProposalResponse,
  ProposalCreateRequest,
  ItineraryItemType,
} from "@/core/api/types";
import { TravixApiError } from "@/core/api/client";

function mapCategoryToItemType(category?: string): ItineraryItemType {
  if (!category) return "activity";
  const cat = category.toLowerCase();
  if (cat.includes("din") || cat.includes("food") || cat.includes("restaur") || cat.includes("meal")) {
    return "restaurant";
  }
  if (cat.includes("trans") || cat.includes("flight") || cat.includes("train") || cat.includes("drive")) {
    return "transport";
  }
  if (cat.includes("lodg") || cat.includes("hotel") || cat.includes("stay") || cat.includes("hostel")) {
    return "lodging";
  }
  return "activity";
}

function parseCostString(costStr?: string | null): number | null {
  if (!costStr) return null;
  const cleaned = costStr.replace(/[^0-9.]/g, "");
  const num = parseFloat(cleaned);
  return isNaN(num) ? null : num;
}

export function useProposal(proposalId?: string) {
  const [proposal, setProposal] = useState<ProposalResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isMutating, setIsMutating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchProposal = useCallback(async () => {
    if (!proposalId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const data = await ProposalsApi.getProposal(proposalId);
      setProposal(data);
    } catch (err: any) {
      if (err instanceof TravixApiError) {
        setError(err.message);
      } else {
        setError("Failed to load proposal details.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [proposalId]);

  useEffect(() => {
    fetchProposal();
  }, [fetchProposal]);

  /**
   * Accept the proposal and transfer proposed days & activities into the real itinerary atomically on the server.
   */
  const acceptAndApplyToItinerary = async (_tripId?: string): Promise<void> => {
    if (!proposal || !proposalId) return;

    setIsMutating(true);
    setError(null);
    try {
      // The backend accepts the proposal and populates the itinerary in one atomic transaction!
      const acceptedProposal = await ProposalsApi.acceptProposal(proposalId, true);
      setProposal(acceptedProposal);
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError ? err.message : "Failed to apply proposal to itinerary.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  /**
   * Reject the proposal.
   */
  const rejectProposal = async (): Promise<ProposalResponse | undefined> => {
    if (!proposalId) return;

    setIsMutating(true);
    setError(null);
    try {
      const rejected = await ProposalsApi.rejectProposal(proposalId);
      setProposal(rejected);
      return rejected;
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError ? err.message : "Failed to reject proposal.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  return {
    proposal,
    isLoading,
    isMutating,
    error,
    refresh: fetchProposal,
    acceptAndApplyToItinerary,
    rejectProposal,
  };
}

/**
 * useTripProposal Hook.
 *
 * Checks if a trip already has a proposal and allows requesting a new one.
 */
export function useTripProposal(tripId?: string) {
  const [proposal, setProposal] = useState<ProposalResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTripProposal = useCallback(async () => {
    if (!tripId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const data = await ProposalsApi.getProposalByTrip(tripId);
      setProposal(data);
    } catch (err: any) {
      // 404 simply means no proposal has been created yet for this trip
      if (err instanceof TravixApiError && err.status === 404) {
        setProposal(null);
      } else if (err instanceof TravixApiError) {
        setError(err.message);
      } else {
        setError("Failed to check trip proposal.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [tripId]);

  useEffect(() => {
    fetchTripProposal();
  }, [fetchTripProposal]);

  const requestProposal = async (
    payload: ProposalCreateRequest
  ): Promise<ProposalResponse> => {
    if (!tripId) throw new Error("Trip ID is required");

    setIsGenerating(true);
    setError(null);
    try {
      const data = await ProposalsApi.requestProposal(tripId, payload);
      setProposal(data);
      return data;
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError ? err.message : "Failed to generate travel plan.";
      setError(msg);
      throw err;
    } finally {
      setIsGenerating(false);
    }
  };

  return {
    proposal,
    hasProposal: !!proposal,
    isLoading,
    isGenerating,
    error,
    refresh: fetchTripProposal,
    requestProposal,
  };
}
