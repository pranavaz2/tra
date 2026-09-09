/**
 * Hook for managing notification preferences state and mutations.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  NotificationPreferencesDTO,
  UpdatePreferencesPayload,
  fetchNotificationPreferences,
  updateNotificationPreferences,
  triggerTravelIntelligenceJob,
} from '../api/preferences-api';

export function useNotificationPreferences() {
  const [preferences, setPreferences] = useState<NotificationPreferencesDTO | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [triggerStats, setTriggerStats] = useState<Record<string, number> | null>(null);

  const loadPreferences = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchNotificationPreferences();
      setPreferences(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to load notification preferences.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPreferences();
  }, [loadPreferences]);

  const updateSetting = useCallback(
    async (patch: UpdatePreferencesPayload) => {
      if (!preferences) return;
      // Optimistic update
      const previous = { ...preferences };
      setPreferences((prev) => (prev ? { ...prev, ...patch } : prev));
      setIsSaving(true);
      setError(null);

      try {
        const updated = await updateNotificationPreferences(patch);
        setPreferences(updated);
      } catch (err: any) {
        // Rollback on failure
        setPreferences(previous);
        setError(err?.message || 'Failed to save settings.');
      } finally {
        setIsSaving(false);
      }
    },
    [preferences]
  );

  const runIntelligenceJobNow = useCallback(async () => {
    try {
      const res = await triggerTravelIntelligenceJob();
      setTriggerStats(res.telemetry);
      return res.telemetry;
    } catch (err: any) {
      setError(err?.message || 'Failed to run travel intelligence job.');
      return null;
    }
  }, []);

  return {
    preferences,
    isLoading,
    isSaving,
    error,
    triggerStats,
    reload: loadPreferences,
    updateSetting,
    runIntelligenceJobNow,
  };
}
