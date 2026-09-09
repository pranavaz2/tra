/**
 * Secure Storage wrapper for sensitive credentials (refresh tokens).
 *
 * Uses `expo-secure-store` on native platforms (iOS Keychain / Android Keystore)
 * and falls back safely to in-memory/localStorage on web.
 */

import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

const REFRESH_TOKEN_KEY = "travix_refresh_token";
const USER_CACHE_KEY = "travix_user_cache";

export const StorageService = {
  async getRefreshToken(): Promise<string | null> {
    try {
      if (Platform.OS === "web") {
        if (typeof window !== "undefined" && window.localStorage) {
          return window.localStorage.getItem(REFRESH_TOKEN_KEY);
        }
        return null;
      }
      return await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
    } catch (error) {
      console.warn("Failed to retrieve refresh token from secure store", error);
      return null;
    }
  },

  async setRefreshToken(token: string): Promise<void> {
    try {
      if (Platform.OS === "web") {
        if (typeof window !== "undefined" && window.localStorage) {
          window.localStorage.setItem(REFRESH_TOKEN_KEY, token);
        }
        return;
      }
      await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, token);
    } catch (error) {
      console.warn("Failed to persist refresh token to secure store", error);
    }
  },

  async clearRefreshToken(): Promise<void> {
    try {
      if (Platform.OS === "web") {
        if (typeof window !== "undefined" && window.localStorage) {
          window.localStorage.removeItem(REFRESH_TOKEN_KEY);
        }
        return;
      }
      await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
    } catch (error) {
      console.warn("Failed to delete refresh token from secure store", error);
    }
  },

  async getUserCache<T>(): Promise<T | null> {
    try {
      if (Platform.OS === "web") {
        if (typeof window !== "undefined" && window.localStorage) {
          const raw = window.localStorage.getItem(USER_CACHE_KEY);
          return raw ? JSON.parse(raw) : null;
        }
        return null;
      }
      const raw = await SecureStore.getItemAsync(USER_CACHE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },

  async setUserCache<T>(data: T): Promise<void> {
    try {
      const raw = JSON.stringify(data);
      if (Platform.OS === "web") {
        if (typeof window !== "undefined" && window.localStorage) {
          window.localStorage.setItem(USER_CACHE_KEY, raw);
        }
        return;
      }
      await SecureStore.setItemAsync(USER_CACHE_KEY, raw);
    } catch (error) {
      console.warn("Failed to persist user cache", error);
    }
  },

  async clearUserCache(): Promise<void> {
    try {
      if (Platform.OS === "web") {
        if (typeof window !== "undefined" && window.localStorage) {
          window.localStorage.removeItem(USER_CACHE_KEY);
        }
        return;
      }
      await SecureStore.deleteItemAsync(USER_CACHE_KEY);
    } catch (error) {
      console.warn("Failed to clear user cache", error);
    }
  },
};
