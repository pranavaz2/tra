/**
 * Authentication API Service.
 *
 * Interacts with backend FastAPI /api/v1/auth routes.
 */

import { apiClient } from "@/core/api/client";
import {
  LoginRequest,
  LoginResponse,
  LogoutRequest,
  RegisterRequest,
  RegisterResponse,
} from "@/core/api/types";

export const AuthApi = {
  async login(payload: LoginRequest): Promise<LoginResponse> {
    return apiClient.post<LoginResponse>("/auth/login", payload);
  },

  async register(payload: RegisterRequest): Promise<RegisterResponse> {
    return apiClient.post<RegisterResponse>("/auth/register", payload);
  },

  async logout(refreshToken?: string | null): Promise<void> {
    const payload: LogoutRequest = { refresh_token: refreshToken || null };
    await apiClient.post<void>("/auth/logout", payload);
  },
};
