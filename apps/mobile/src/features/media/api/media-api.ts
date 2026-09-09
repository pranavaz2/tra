/**
 * Media API client.
 *
 * Typed operations strictly mirroring FastAPI /api/v1/trips/{trip_id}/media endpoints.
 */

import { apiClient } from "@/core/api/client";
import {
  MediaItemResponse,
  MediaListResponse,
  MediaCaptionUpdateRequest,
  AttachActivityRequest,
  AttachExpenseRequest,
} from "@/core/api/types";

export interface FileUploadPayload {
  uri: string;
  name: string;
  type: string;
}

export class MediaApi {
  /**
   * Upload media file (photo, receipt, document, etc.) to trip media collection.
   */
  static async uploadMedia(
    tripId: string,
    file: FileUploadPayload | FormData
  ): Promise<MediaItemResponse> {
    let formData: FormData;

    if (file instanceof FormData) {
      formData = file;
    } else {
      formData = new FormData();
      // React Native FormData format for file uploads
      formData.append("file", {
        uri: file.uri,
        name: file.name,
        type: file.type,
      } as any);
    }

    return apiClient.upload<MediaItemResponse>(
      `/api/v1/trips/${tripId}/media`,
      formData
    );
  }

  /**
   * List trip media items with cursor-based pagination.
   */
  static async listMedia(
    tripId: string,
    limit: number = 20,
    cursor?: string
  ): Promise<MediaListResponse> {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    if (cursor) params.set("cursor", cursor);

    return apiClient.get<MediaListResponse>(
      `/api/v1/trips/${tripId}/media?${params.toString()}`
    );
  }

  /**
   * Get single media item details.
   */
  static async getMedia(
    tripId: string,
    mediaId: string
  ): Promise<MediaItemResponse> {
    return apiClient.get<MediaItemResponse>(
      `/api/v1/trips/${tripId}/media/${mediaId}`
    );
  }

  /**
   * Update caption of a media item.
   */
  static async updateCaption(
    tripId: string,
    mediaId: string,
    caption: string | null
  ): Promise<MediaItemResponse> {
    return apiClient.patch<MediaItemResponse>(
      `/api/v1/trips/${tripId}/media/${mediaId}`,
      { caption } as MediaCaptionUpdateRequest
    );
  }

  /**
   * Delete a media item (soft delete).
   */
  static async deleteMedia(
    tripId: string,
    mediaId: string
  ): Promise<void> {
    return apiClient.delete<void>(
      `/api/v1/trips/${tripId}/media/${mediaId}`
    );
  }

  /**
   * Attach a media item to an itinerary activity (ItineraryItemId).
   */
  static async attachToActivity(
    tripId: string,
    mediaId: string,
    activityId: string
  ): Promise<MediaItemResponse> {
    return apiClient.post<MediaItemResponse>(
      `/api/v1/trips/${tripId}/media/${mediaId}/activity`,
      { activity_id: activityId } as AttachActivityRequest
    );
  }

  /**
   * Attach a media item to a budget expense (ExpenseId).
   */
  static async attachToExpense(
    tripId: string,
    mediaId: string,
    expenseId: string
  ): Promise<MediaItemResponse> {
    return apiClient.post<MediaItemResponse>(
      `/api/v1/trips/${tripId}/media/${mediaId}/expense`,
      { expense_id: expenseId } as AttachExpenseRequest
    );
  }
}
