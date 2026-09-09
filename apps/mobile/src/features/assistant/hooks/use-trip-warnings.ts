/**
 * useTripWarnings Hook.
 *
 * Fetches and manages proactive travel warnings (itinerary conflicts, travel feasibility, budget risks).
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import { AssistantApi } from "../api/assistant-api";
import { TravelWarning, TripWarningsResponse } from "@/core/api/types";
import { TravixApiError } from "@/core/api/client";

export function useTripWarnings(tripId: string) {
  const [warningsResponse, setWarningsResponse] = useState<TripWarningsResponse | null>(null);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchWarnings = useCallback(async () => {
    if (!tripId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await AssistantApi.getWarnings(tripId);
      setWarningsResponse(data);
    } catch (err) {
      if (err instanceof TravixApiError) {
        setError(err.message);
      } else {
        setError("Failed to evaluate travel warnings.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [tripId]);

  useEffect(() => {
    fetchWarnings();
  }, [fetchWarnings]);

  const activeWarnings = useMemo(() => {
    if (!warningsResponse) return [];
    return warningsResponse.warnings.filter((w) => !dismissedIds.has(w.warning_id));
  }, [warningsResponse, dismissedIds]);

  const itineraryWarnings = useMemo(() => {
    return activeWarnings.filter(
      (w) => w.category === "timing" || w.category === "distance" || w.category === "feasibility"
    );
  }, [activeWarnings]);

  const budgetWarnings = useMemo(() => {
    return activeWarnings.filter((w) => w.category === "budget");
  }, [activeWarnings]);

  const dismissWarning = useCallback((warningId: string) => {
    setDismissedIds((prev) => new Set([...prev, warningId]));
  }, []);

  const hasCritical = useMemo(() => {
    return activeWarnings.some((w) => w.severity === "critical");
  }, [activeWarnings]);

  return {
    warnings: activeWarnings,
    allWarnings: warningsResponse?.warnings || [],
    itineraryWarnings,
    budgetWarnings,
    totalWarnings: activeWarnings.length,
    hasCritical,
    isLoading,
    error,
    refresh: fetchWarnings,
    dismissWarning,
  };
}
