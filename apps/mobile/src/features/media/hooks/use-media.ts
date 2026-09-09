/**
 * useMedia Hook.
 *
 * Manages media collection items, cursor pagination, uploading, caption editing,
 * activity/expense attachment, deletion, and role-based permissions.
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import { MediaApi, FileUploadPayload } from "../api/media-api";
import { useCollaboration } from "@/features/collaboration/hooks/use-collaboration";
import { MediaItemResponse } from "@/core/api/types";
import { TravixApiError } from "@/core/api/client";

export function useMedia(tripId?: string, tripOwnerId?: string) {
  const { isViewer, isOwner, isEditor, userRole } = useCollaboration(tripId, tripOwnerId);

  const [mediaItems, setMediaItems] = useState<MediaItemResponse[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isLoadingMore, setIsLoadingMore] = useState<boolean>(false);
  const [isMutating, setIsMutating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Can upload/edit/delete if owner, editor, or not explicitly viewer
  const canManageMedia = !isViewer;

  const fetchMedia = useCallback(
    async (reset = true) => {
      if (!tripId) {
        setIsLoading(false);
        return;
      }

      if (reset) {
        setIsLoading(true);
        setError(null);
      } else {
        setIsLoadingMore(true);
      }

      try {
        const cursor = reset ? undefined : nextCursor || undefined;
        const response = await MediaApi.listMedia(tripId, 30, cursor);

        if (reset) {
          setMediaItems(response.items || []);
        } else {
          setMediaItems((prev) => [...prev, ...(response.items || [])]);
        }

        setNextCursor(response.next_cursor || null);
        setHasMore(response.has_more);
      } catch (err: any) {
        if (err instanceof TravixApiError && err.status === 404) {
          // Media collection not initialized yet (empty collection)
          setMediaItems([]);
          setNextCursor(null);
          setHasMore(false);
        } else {
          const msg =
            err instanceof TravixApiError
              ? err.message
              : "Failed to load media collection.";
          setError(msg);
        }
      } finally {
        setIsLoading(false);
        setIsLoadingMore(false);
      }
    },
    [tripId, nextCursor]
  );

  useEffect(() => {
    fetchMedia(true);
  }, [tripId]);

  const loadMore = useCallback(async () => {
    if (!hasMore || isLoadingMore || !nextCursor) return;
    await fetchMedia(false);
  }, [hasMore, isLoadingMore, nextCursor, fetchMedia]);

  const uploadMedia = async (
    file: FileUploadPayload | FormData,
    caption?: string
  ): Promise<MediaItemResponse> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);

    try {
      const uploaded = await MediaApi.uploadMedia(tripId, file);

      // If caption provided, update it immediately
      let finalItem = uploaded;
      if (caption && caption.trim()) {
        try {
          finalItem = await MediaApi.updateCaption(
            tripId,
            uploaded.media_id,
            caption.trim()
          );
        } catch {
          // Upload still succeeded
        }
      }

      // Prepend newly uploaded item to list
      setMediaItems((prev) => [finalItem, ...prev.filter((i) => i.media_id !== finalItem.media_id)]);
      return finalItem;
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError
          ? err.message
          : "Failed to upload media file.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  const updateCaption = async (
    mediaId: string,
    caption: string | null
  ): Promise<MediaItemResponse> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);

    try {
      const updated = await MediaApi.updateCaption(tripId, mediaId, caption);
      setMediaItems((prev) =>
        prev.map((item) => (item.media_id === mediaId ? updated : item))
      );
      return updated;
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError
          ? err.message
          : "Failed to update caption.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  const deleteMedia = async (mediaId: string): Promise<void> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);

    try {
      await MediaApi.deleteMedia(tripId, mediaId);
      setMediaItems((prev) => prev.filter((item) => item.media_id !== mediaId));
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError
          ? err.message
          : "Failed to delete media item.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  const attachToActivity = async (
    mediaId: string,
    activityId: string
  ): Promise<MediaItemResponse> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);

    try {
      const updated = await MediaApi.attachToActivity(
        tripId,
        mediaId,
        activityId
      );
      setMediaItems((prev) =>
        prev.map((item) => (item.media_id === mediaId ? updated : item))
      );
      return updated;
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError
          ? err.message
          : "Failed to attach media to activity.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  const attachToExpense = async (
    mediaId: string,
    expenseId: string
  ): Promise<MediaItemResponse> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);

    try {
      const updated = await MediaApi.attachToExpense(tripId, mediaId, expenseId);
      setMediaItems((prev) =>
        prev.map((item) => (item.media_id === mediaId ? updated : item))
      );
      return updated;
    } catch (err: any) {
      const msg =
        err instanceof TravixApiError
          ? err.message
          : "Failed to attach media to expense.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  // Filtered selectors
  const photos = useMemo(
    () => mediaItems.filter((m) => m.media_type === "photo"),
    [mediaItems]
  );
  const receipts = useMemo(
    () => mediaItems.filter((m) => m.media_type === "receipt"),
    [mediaItems]
  );
  const documents = useMemo(
    () => mediaItems.filter((m) => m.media_type === "note" || m.media_type === "video"),
    [mediaItems]
  );

  return {
    mediaItems,
    photos,
    receipts,
    documents,
    totalCount: mediaItems.length,
    isLoading,
    isLoadingMore,
    isMutating,
    error,
    hasMore,
    userRole,
    isOwner,
    isEditor,
    isViewer,
    canManageMedia,
    refresh: () => fetchMedia(true),
    loadMore,
    uploadMedia,
    updateCaption,
    deleteMedia,
    attachToActivity,
    attachToExpense,
  };
}
