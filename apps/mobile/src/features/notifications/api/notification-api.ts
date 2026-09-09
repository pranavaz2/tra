/**
 * Notifications API client.
 */

import { apiClient } from "@/core/api/client";

export interface RegisterDeviceTokenRequest {
  token: string;
  platform?: string;
  device_name?: string;
}

export interface DeviceTokenResponse {
  token_id: string;
  user_id: string;
  token: string;
  platform: string;
  device_name: string | null;
  created_at: string;
}

export const notificationApi = {
  async registerDeviceToken(
    data: RegisterDeviceTokenRequest
  ): Promise<DeviceTokenResponse> {
    return apiClient.post<DeviceTokenResponse>(
      "/notifications/devices",
      data
    );
  },

  async unregisterDeviceToken(token: string): Promise<void> {
    await apiClient.delete<void>(`/notifications/devices/${encodeURIComponent(token)}`);
  },
};
