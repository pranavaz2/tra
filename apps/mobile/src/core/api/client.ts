/**
 * Travix Typed HTTP Client.
 *
 * Provides:
 * - Request/response handling with base URL
 * - In-memory access token injection
 * - Transparent refresh-token rotation on 401
 * - Concurrency lock for refresh requests
 * - Typed RFC 7807 problem details error mapping
 */

import { ENV } from "../config/env";
import { StorageService } from "../storage/secure-store";
import { ApiProblemDetails, DataEnvelope, LoginResponse, RefreshRequest } from "./types";

export class TravixApiError extends Error {
  public readonly status: number;
  public readonly errorCode?: string;
  public readonly details: ApiProblemDetails;

  constructor(details: ApiProblemDetails) {
    super(details.detail || details.title || "An unexpected API error occurred");
    this.name = "TravixApiError";
    this.status = details.status;
    this.errorCode = details.error_code;
    this.details = details;
  }
}

type TokenRefreshCallback = (newToken: string) => void;
type LogoutCallback = () => void;

class ApiClient {
  private accessToken: string | null = null;
  private isRefreshing = false;
  private refreshSubscribers: TokenRefreshCallback[] = [];
  private onUnauthorizedCallback: LogoutCallback | null = null;

  public setAccessToken(token: string | null): void {
    this.accessToken = token;
  }

  public getAccessToken(): string | null {
    return this.accessToken;
  }

  public setOnUnauthorized(callback: LogoutCallback): void {
    this.onUnauthorizedCallback = callback;
  }

  private subscribeTokenRefresh(cb: TokenRefreshCallback): void {
    this.refreshSubscribers.push(cb);
  }

  private onTokenRefreshed(newToken: string): void {
    this.refreshSubscribers.forEach((cb) => cb(newToken));
    this.refreshSubscribers = [];
  }

  private async tryRefreshToken(): Promise<string | null> {
    const refreshToken = await StorageService.getRefreshToken();
    if (!refreshToken) {
      return null;
    }

    try {
      const response = await fetch(`${ENV.FULL_API_URL}/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh_token: refreshToken } as RefreshRequest),
      });

      if (!response.ok) {
        // Refresh token expired or revoked
        await StorageService.clearRefreshToken();
        await StorageService.clearUserCache();
        this.setAccessToken(null);
        if (this.onUnauthorizedCallback) {
          this.onUnauthorizedCallback();
        }
        return null;
      }

      const json: DataEnvelope<LoginResponse> = await response.json();
      const newAccessToken = json.data.access_token;
      const newRefreshToken = json.data.refresh_token;

      this.setAccessToken(newAccessToken);
      if (newRefreshToken) {
        await StorageService.setRefreshToken(newRefreshToken);
      }
      if (json.data.user) {
        await StorageService.setUserCache(json.data.user);
      }

      return newAccessToken;
    } catch (err) {
      console.error("Token refresh network failure", err);
      return null;
    }
  }

  public async request<T>(
    endpoint: string,
    options: RequestInit = {},
    retryOnAuthFailure = true
  ): Promise<T> {
    const cleanEndpoint = endpoint.replace(/^\/?api\/v1\/?/, "");
    const url = endpoint.startsWith("http")
      ? endpoint
      : `${ENV.FULL_API_URL}/${cleanEndpoint.replace(/^\/+/, "")}`;

    const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
    const headers: Record<string, string> = {
      Accept: "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (!isFormData && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    if (this.accessToken && !headers["Authorization"]) {
      headers["Authorization"] = `Bearer ${this.accessToken}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 12000);

    const config: RequestInit = {
      ...options,
      headers,
      signal: controller.signal,
    };

    let response: Response;
    try {
      response = await fetch(url, config);
    } catch (networkError: any) {
      const isTimeout = networkError?.name === "AbortError";
      throw new TravixApiError({
        type: "https://errors.travix.ai/network-error",
        title: "Network Error",
        status: 0,
        detail: isTimeout
          ? `Connection to backend server timed out (${url}). Ensure FastAPI is running on your computer.`
          : networkError?.message ||
            "Unable to connect to Travix server. Please check your connection.",
        error_code: "NETWORK_ERROR",
      });
    } finally {
      clearTimeout(timeoutId);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return undefined as unknown as T;
    }

    // Do not attempt refresh or fire onUnauthorized for auth endpoints (login, register, logout, refresh)
    const isAuthRoute = endpoint.includes("/auth/");
    if (response.status === 401 && retryOnAuthFailure && !isAuthRoute) {
      if (!this.isRefreshing) {
        this.isRefreshing = true;
        const newAccessToken = await this.tryRefreshToken();
        this.isRefreshing = false;

        if (newAccessToken) {
          this.onTokenRefreshed(newAccessToken);
          return this.request<T>(endpoint, options, false);
        } else {
          // Token refresh failed, prompt logout
          if (this.onUnauthorizedCallback) {
            this.onUnauthorizedCallback();
          }
        }
      } else {
        // Wait for active refresh in progress
        return new Promise<T>((resolve, reject) => {
          this.subscribeTokenRefresh((newToken) => {
            if (!newToken) {
              reject(
                new TravixApiError({
                  type: "https://errors.travix.ai/auth/session-expired",
                  title: "Session Expired",
                  status: 401,
                  detail: "Your session has expired. Please log in again.",
                  error_code: "SESSION_EXPIRED",
                })
              );
            } else {
              resolve(this.request<T>(endpoint, options, false));
            }
          });
        });
      }
    }

    // Parse response body
    let jsonBody: any = null;
    const text = await response.text();
    if (text) {
      try {
        jsonBody = JSON.parse(text);
      } catch {
        jsonBody = { detail: text };
      }
    }

    if (!response.ok) {
      const problemDetails: ApiProblemDetails = {
        type: jsonBody?.type || "https://errors.travix.ai/error",
        title: jsonBody?.title || response.statusText || "Error",
        status: response.status,
        detail: jsonBody?.detail || "An unexpected error occurred.",
        instance: jsonBody?.instance || endpoint,
        error_code: jsonBody?.error_code || "UNKNOWN_ERROR",
        trace_id: jsonBody?.trace_id,
        invalid_params: jsonBody?.invalid_params,
      };
      throw new TravixApiError(problemDetails);
    }

    // Check if the backend response is wrapped in { data: T }
    if (jsonBody && typeof jsonBody === "object" && "data" in jsonBody) {
      return jsonBody.data as T;
    }

    return jsonBody as T;
  }

  // HTTP Method conveniences
  public get<T>(endpoint: string, headers?: Record<string, string>): Promise<T> {
    return this.request<T>(endpoint, { method: "GET", headers });
  }

  public post<T>(
    endpoint: string,
    body?: any,
    headers?: Record<string, string>
  ): Promise<T> {
    return this.request<T>(endpoint, {
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
      headers,
    });
  }

  public patch<T>(
    endpoint: string,
    body?: any,
    headers?: Record<string, string>
  ): Promise<T> {
    return this.request<T>(endpoint, {
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
      headers,
    });
  }

  public delete<T>(endpoint: string, headers?: Record<string, string>): Promise<T> {
    return this.request<T>(endpoint, { method: "DELETE", headers });
  }

  public upload<T>(endpoint: string, formData: FormData, headers?: Record<string, string>): Promise<T> {
    return this.request<T>(endpoint, {
      method: "POST",
      body: formData,
      headers,
    });
  }
}

export const apiClient = new ApiClient();
