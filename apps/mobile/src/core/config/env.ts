/**
 * Environment configuration for Travix Mobile.
 *
 * Resolves the backend API base URL based on environment variables
 * with sensible local development defaults for Android emulators,
 * iOS simulators, and Web.
 */

import { Platform } from "react-native";
import Constants from "expo-constants";

function resolveApiBaseUrl(): string {
  // 1. Web platform always talks to localhost:8000
  if (Platform.OS === "web") {
    return "http://localhost:8000";
  }

  // 2. Explicit env variable
  const customUrl =
    process.env.EXPO_PUBLIC_API_URL ||
    Constants.expoConfig?.extra?.apiUrl;

  if (customUrl) {
    return customUrl.replace(/\/+$/, "");
  }

  // 3. Dynamic resolution from Expo hostUri (works for physical phones & LAN)
  const hostUri =
    Constants.expoConfig?.hostUri ||
    (Constants as any).manifest2?.extra?.expoClient?.hostUri ||
    (Constants as any).manifest?.debuggerHost;

  if (hostUri) {
    const ip = hostUri.split(":")[0];
    if (ip && ip !== "localhost" && ip !== "127.0.0.1") {
      return `http://${ip}:8000`;
    }
  }

  // 4. Fallback defaults
  if (Platform.OS === "android") {
    return "http://10.52.14.15:8000";
  }

  // iOS Simulator
  return "http://localhost:8000";
}

export const ENV = {
  API_BASE_URL: resolveApiBaseUrl(),
  API_PREFIX: "/api/v1",
  get FULL_API_URL() {
    return `${this.API_BASE_URL}${this.API_PREFIX}`;
  },
  APP_VERSION: Constants.expoConfig?.version || "1.0.0",
  APP_NAME: "Travix AI",
};
