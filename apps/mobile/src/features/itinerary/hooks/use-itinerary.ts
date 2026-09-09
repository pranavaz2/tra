/**
 * useItinerary Hook.
 *
 * Manages itinerary aggregate state, loading, refresh, and mutations.
 */

import { useState, useEffect, useCallback } from "react";
import { ItineraryApi } from "../api/itinerary-api";
import {
  ItineraryDayCreateRequest,
  ItineraryDayUpdateRequest,
  ItineraryItemCreateRequest,
  ItineraryItemUpdateRequest,
  ItineraryResponse,
} from "@/core/api/types";
import { TravixApiError } from "@/core/api/client";

export function useItinerary(tripId?: string) {
  const [itinerary, setItinerary] = useState<ItineraryResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isMutating, setIsMutating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchItinerary = useCallback(async () => {
    if (!tripId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const data = await ItineraryApi.getItinerary(tripId);
      // Sort days in ascending order by day_number
      data.days.sort((a, b) => a.day_number - b.day_number);
      setItinerary(data);
    } catch (err: any) {
      if (err instanceof TravixApiError) {
        setError(err.message);
      } else {
        setError("Failed to load itinerary. Please pull to refresh.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [tripId]);

  useEffect(() => {
    fetchItinerary();
  }, [fetchItinerary]);

  const addDay = async (payload: ItineraryDayCreateRequest) => {
    if (!tripId) return;
    setIsMutating(true);
    try {
      const updated = await ItineraryApi.addDay(tripId, payload);
      updated.days.sort((a, b) => a.day_number - b.day_number);
      setItinerary(updated);
      return updated;
    } finally {
      setIsMutating(false);
    }
  };

  const updateDay = async (dayId: string, payload: ItineraryDayUpdateRequest) => {
    if (!tripId) return;
    setIsMutating(true);
    try {
      const updated = await ItineraryApi.updateDay(tripId, dayId, payload);
      updated.days.sort((a, b) => a.day_number - b.day_number);
      setItinerary(updated);
      return updated;
    } finally {
      setIsMutating(false);
    }
  };

  const removeDay = async (dayId: string) => {
    if (!tripId) return;
    setIsMutating(true);
    try {
      const updated = await ItineraryApi.removeDay(tripId, dayId);
      updated.days.sort((a, b) => a.day_number - b.day_number);
      setItinerary(updated);
      return updated;
    } finally {
      setIsMutating(false);
    }
  };

  const addItem = async (payload: ItineraryItemCreateRequest) => {
    if (!tripId) return;
    setIsMutating(true);
    try {
      const updated = await ItineraryApi.addItem(tripId, payload);
      updated.days.sort((a, b) => a.day_number - b.day_number);
      setItinerary(updated);
      return updated;
    } finally {
      setIsMutating(false);
    }
  };

  const updateItem = async (itemId: string, payload: ItineraryItemUpdateRequest) => {
    if (!tripId) return;
    setIsMutating(true);
    try {
      const updated = await ItineraryApi.updateItem(tripId, itemId, payload);
      updated.days.sort((a, b) => a.day_number - b.day_number);
      setItinerary(updated);
      return updated;
    } finally {
      setIsMutating(false);
    }
  };

  const removeItem = async (itemId: string) => {
    if (!tripId) return;
    setIsMutating(true);
    try {
      const updated = await ItineraryApi.removeItem(tripId, itemId);
      updated.days.sort((a, b) => a.day_number - b.day_number);
      setItinerary(updated);
      return updated;
    } finally {
      setIsMutating(false);
    }
  };

  return {
    itinerary,
    days: itinerary ? itinerary.days : [],
    isLoading,
    isMutating,
    error,
    refresh: fetchItinerary,
    addDay,
    updateDay,
    removeDay,
    addItem,
    updateItem,
    removeItem,
  };
}
