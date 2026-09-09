/**
 * Authentication Context and State Provider.
 *
 * Manages user lifecycle, token rotation bootstrap, login, register, and logout.
 */

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { AuthApi } from "../api/auth-api";
import { apiClient, TravixApiError } from "@/core/api/client";
import { ENV } from "@/core/config/env";
import { StorageService } from "@/core/storage/secure-store";
import { UserResponse, LoginRequest, RegisterRequest } from "@/core/api/types";

interface AuthContextType {
  user: UserResponse | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<{ requiresVerification: boolean }>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Logout handler
  const logout = useCallback(async () => {
    try {
      const storedRefreshToken = await StorageService.getRefreshToken();
      const currentToken = apiClient.getAccessToken();
      if (currentToken && storedRefreshToken) {
        await AuthApi.logout(storedRefreshToken);
      }
    } catch {
      // Ignore network / auth errors during local logout cleanup
    } finally {
      await StorageService.clearRefreshToken();
      await StorageService.clearUserCache();
      apiClient.setAccessToken(null);
      setAccessToken(null);
      setUser(null);
    }
  }, []);

  // Hook API client unauthorized listener to logout
  useEffect(() => {
    apiClient.setOnUnauthorized(() => {
      logout();
    });
  }, [logout]);

  // Bootstrap auth state on app start
  useEffect(() => {
    async function bootstrapAuth() {
      try {
        const storedRefreshToken = await StorageService.getRefreshToken();
        if (!storedRefreshToken) {
          setIsLoading(false);
          return;
        }

        // Try hydrating user from cache first for fast display
        const cachedUser = await StorageService.getUserCache<UserResponse>();
        if (cachedUser) {
          setUser(cachedUser);
        }

        const response = await fetch(`${ENV.FULL_API_URL}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: storedRefreshToken }),
        });

        if (response.ok) {
          const json = await response.json();
          const data = json.data;
          apiClient.setAccessToken(data.access_token);
          setAccessToken(data.access_token);
          if (data.refresh_token) {
            await StorageService.setRefreshToken(data.refresh_token);
          }
          if (data.user) {
            setUser(data.user);
            await StorageService.setUserCache(data.user);
          }
        } else {
          // Stored token was invalid/expired
          await StorageService.clearRefreshToken();
          await StorageService.clearUserCache();
          setUser(null);
          setAccessToken(null);
        }
      } catch (err) {
        console.warn("Auth bootstrap failed", err);
      } finally {
        setIsLoading(false);
      }
    }

    bootstrapAuth();
  }, []);

  const login = async (credentials: LoginRequest): Promise<void> => {
    const response = await AuthApi.login(credentials);
    apiClient.setAccessToken(response.access_token);
    setAccessToken(response.access_token);
    setUser(response.user);

    await StorageService.setRefreshToken(response.refresh_token);
    await StorageService.setUserCache(response.user);
  };

  const register = async (
    data: RegisterRequest
  ): Promise<{ requiresVerification: boolean }> => {
    const response = await AuthApi.register(data);

    if (response.requires_verification) {
      return { requiresVerification: true };
    }

    // If verification was bypassed (Dev/CI MVP mode), tokens are issued immediately
    if (response.access_token && response.refresh_token) {
      apiClient.setAccessToken(response.access_token);
      setAccessToken(response.access_token);

      const userSummary: UserResponse = {
        user_id: response.user_id,
        email: response.email,
        is_email_verified: true,
      };
      setUser(userSummary);

      await StorageService.setRefreshToken(response.refresh_token);
      await StorageService.setUserCache(userSummary);
    }

    return { requiresVerification: false };
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        isAuthenticated: !!user && !!accessToken,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
