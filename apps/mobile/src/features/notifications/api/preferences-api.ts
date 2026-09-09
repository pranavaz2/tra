import { apiClient } from '@/core/api/client';

export interface NotificationPreferencesDTO {
  user_id: string;
  push_enabled: boolean;
  email_enabled: boolean;
  trip_reminders: boolean;
  itinerary_reminders: boolean;
  collaboration: boolean;
  budget_alerts: boolean;
  travel_warnings: boolean;
  weather_alerts: boolean;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  updated_at: string;
}

export interface UpdatePreferencesPayload {
  push_enabled?: boolean;
  email_enabled?: boolean;
  trip_reminders?: boolean;
  itinerary_reminders?: boolean;
  collaboration?: boolean;
  budget_alerts?: boolean;
  travel_warnings?: boolean;
  weather_alerts?: boolean;
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
}

export async function fetchNotificationPreferences(): Promise<NotificationPreferencesDTO> {
  return apiClient.get<NotificationPreferencesDTO>('/notifications/preferences');
}

export async function updateNotificationPreferences(
  payload: UpdatePreferencesPayload
): Promise<NotificationPreferencesDTO> {
  return apiClient.patch<NotificationPreferencesDTO>('/notifications/preferences', payload);
}

export async function triggerTravelIntelligenceJob(): Promise<{ status: string; telemetry: Record<string, number> }> {
  return apiClient.post<{ status: string; telemetry: Record<string, number> }>(
    '/jobs/travel-intelligence/run',
    {}
  );
}
