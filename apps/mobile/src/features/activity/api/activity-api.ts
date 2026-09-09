/**
 * Trip Activity API client.
 */

import { apiClient } from "@/core/api/client";

export interface ActivityLogItem {
  activity_id: string;
  trip_id: string;
  actor_id: string;
  actor_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  title: string;
  description: string;
  metadata: Record<string, any>;
  created_at: string;
}

export interface ActivityFeedResponse {
  items: ActivityLogItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export const activityApi = {
  async getTripActivities(
    tripId: string,
    limit: number = 30,
    offset: number = 0
  ): Promise<ActivityFeedResponse> {
    return apiClient.get<ActivityFeedResponse>(
      `/trips/${tripId}/activities?limit=${limit}&offset=${offset}`
    );
  },
};
