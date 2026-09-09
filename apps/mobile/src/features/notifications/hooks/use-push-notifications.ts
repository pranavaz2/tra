/**
 * usePushNotifications Hook.
 *
 * Registers device push tokens with the Travix backend on authentication.
 */

import { useEffect, useState } from "react";
import { Platform } from "react-native";
import { notificationApi } from "../api/notification-api";
import { useAuth } from "@/features/auth/context/auth-context";

export function usePushNotifications() {
  const { isAuthenticated, user } = useAuth();
  const [isRegistered, setIsRegistered] = useState(false);

  useEffect(() => {
    if (!isAuthenticated || !user) {
      setIsRegistered(false);
      return;
    }

    const registerToken = async () => {
      try {
        // Mock / placeholder Expo push token for development and simulators
        const dummyToken = `ExponentPushToken[user_${user.user_id.substring(0, 8)}_dev]`;
        await notificationApi.registerDeviceToken({
          token: dummyToken,
          platform: Platform.OS,
          device_name: `${Platform.OS.toUpperCase()} Device`,
        });
        setIsRegistered(true);
      } catch (err) {
        // Non-blocking
      }
    };

    registerToken();
  }, [isAuthenticated, user?.user_id]);

  return { isRegistered };
}
