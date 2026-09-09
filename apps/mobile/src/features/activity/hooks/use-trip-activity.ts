/**
 * useTripActivity Hook.
 *
 * Manages fetching, pagination, and refresh for a trip's activity timeline.
 */

import { useState, useEffect, useCallback } from "react";
import { activityApi, ActivityLogItem } from "../api/activity-api";
import { TravixApiError } from "@/core/api/client";

export function useTripActivity(tripId: string | undefined) {
  const [activities, setActivities] = useState<ActivityLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchActivities = useCallback(
    async (isRefresh: boolean = false) => {
      if (!tripId) return;

      if (isRefresh) {
        setIsLoading(true);
        setError(null);
      } else {
        setIsLoadingMore(true);
      }

      try {
        const offset = isRefresh ? 0 : activities.length;
        const res = await activityApi.getTripActivities(tripId, 30, offset);

        if (isRefresh) {
          setActivities(res.items);
        } else {
          setActivities((prev) => [...prev, ...res.items]);
        }
        setTotal(res.total);
        setHasMore(res.has_more);
      } catch (err: any) {
        setError(err.message || "Failed to load activity timeline.");
      } finally {
        setIsLoading(false);
        setIsLoadingMore(false);
      }
    },
    [tripId, activities.length]
  );

  useEffect(() => {
    fetchActivities(true);
  }, [tripId]);

  const refresh = useCallback(() => {
    return fetchActivities(true);
  }, [fetchActivities]);

  const loadMore = useCallback(() => {
    if (!isLoading && !isLoadingMore && hasMore) {
      fetchActivities(false);
    }
  }, [isLoading, isLoadingMore, hasMore, fetchActivities]);

  return {
    activities,
    total,
    hasMore,
    isLoading,
    isLoadingMore,
    error,
    refresh,
    loadMore,
  };
}
