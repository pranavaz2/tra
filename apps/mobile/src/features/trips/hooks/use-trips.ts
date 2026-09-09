/**
 * useTrips Hook.
 *
 * Manages fetching, pagination, and creation of trips.
 */

import { useState, useEffect, useCallback } from "react";
import { TripsApi, ListTripsParams } from "../api/trips-api";
import { TripCreateRequest, TripResponse, TripStatus } from "@/core/api/types";
import { TravixApiError } from "@/core/api/client";

export function useTrips(initialStatus?: TripStatus) {
  const [trips, setTrips] = useState<TripResponse[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<TripStatus | undefined>(initialStatus);

  const fetchTrips = useCallback(
    async (isRefresh = false, cursor?: string | null) => {
      if (isRefresh) {
        setIsRefreshing(true);
      } else {
        setIsLoading(true);
      }
      setError(null);

      try {
        const params: ListTripsParams = {
          limit: 20,
          cursor: isRefresh ? undefined : cursor,
          status: statusFilter,
        };

        const page = await TripsApi.listTrips(params);

        if (isRefresh || !cursor) {
          setTrips(page.items);
        } else {
          setTrips((prev) => [...prev, ...page.items]);
        }
        setNextCursor(page.next_cursor);
      } catch (err: any) {
        if (err instanceof TravixApiError) {
          setError(err.message);
        } else {
          setError("Failed to load trips. Please pull to refresh.");
        }
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [statusFilter]
  );

  useEffect(() => {
    fetchTrips(false);
  }, [fetchTrips]);

  const refresh = useCallback(() => {
    return fetchTrips(true);
  }, [fetchTrips]);

  const loadMore = useCallback(() => {
    if (nextCursor && !isLoading && !isRefreshing) {
      fetchTrips(false, nextCursor);
    }
  }, [nextCursor, isLoading, isRefreshing, fetchTrips]);

  const createTrip = async (payload: TripCreateRequest): Promise<TripResponse> => {
    const newTrip = await TripsApi.createTrip(payload);
    // Prepend new trip to list
    setTrips((prev) => [newTrip, ...prev]);
    return newTrip;
  };

  const removeTrip = useCallback((tripId: string) => {
    setTrips((prev) => prev.filter((t) => t.trip_id !== tripId));
  }, []);

  const updateTripInList = useCallback((updated: TripResponse) => {
    setTrips((prev) => prev.map((t) => (t.trip_id === updated.trip_id ? updated : t)));
  }, []);

  return {
    trips,
    isLoading,
    isRefreshing,
    error,
    hasMore: !!nextCursor,
    statusFilter,
    setStatusFilter,
    refresh,
    loadMore,
    createTrip,
    removeTrip,
    updateTripInList,
  };
}

export function useTrip(tripId?: string) {
  const [trip, setTrip] = useState<TripResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isMutating, setIsMutating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTrip = useCallback(async () => {
    if (!tripId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const data = await TripsApi.getTrip(tripId);
      setTrip(data);
    } catch (err: any) {
      if (err instanceof TravixApiError) {
        if (err.errorCode === "TRIP_NOT_FOUND") {
          setError("This trip could not be found.");
        } else {
          setError(err.message);
        }
      } else {
        setError("Failed to load trip details.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [tripId]);

  useEffect(() => {
    fetchTrip();
  }, [fetchTrip]);

  const updateTrip = async (payload: Parameters<typeof TripsApi.updateTrip>[1]) => {
    if (!tripId) return;
    setIsMutating(true);
    try {
      const updated = await TripsApi.updateTrip(tripId, payload);
      setTrip(updated);
      return updated;
    } finally {
      setIsMutating(false);
    }
  };

  const transitionStatus = async (newStatus: TripStatus) => {
    if (!tripId) return;
    setIsMutating(true);
    try {
      const updated = await TripsApi.transitionTripStatus(tripId, newStatus);
      setTrip(updated);
      return updated;
    } finally {
      setIsMutating(false);
    }
  };

  const deleteTrip = async () => {
    if (!tripId) return;
    setIsMutating(true);
    try {
      await TripsApi.deleteTrip(tripId);
      setTrip(null);
    } finally {
      setIsMutating(false);
    }
  };

  return {
    trip,
    isLoading,
    isMutating,
    error,
    refresh: fetchTrip,
    updateTrip,
    transitionStatus,
    deleteTrip,
  };
}

