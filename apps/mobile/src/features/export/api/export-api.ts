/**
 * Trip Export API client.
 */

import { ENV } from "@/core/config/env";
import { apiClient } from "@/core/api/client";

export const exportApi = {
  getICalUrl(tripId: string): string {
    const token = apiClient.getAccessToken() || "";
    return `${ENV.FULL_API_URL}/trips/${tripId}/export/ical?token=${encodeURIComponent(token)}`;
  },

  getPdfUrl(tripId: string): string {
    const token = apiClient.getAccessToken() || "";
    return `${ENV.FULL_API_URL}/trips/${tripId}/export/pdf?token=${encodeURIComponent(token)}`;
  },

  async downloadICal(tripId: string): Promise<string> {
    const token = apiClient.getAccessToken() || "";
    const response = await fetch(`${ENV.FULL_API_URL}/trips/${tripId}/export/ical`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok) {
      throw new Error(`Failed to download calendar (HTTP ${response.status})`);
    }
    return response.text();
  },
};
