/**
 * Trip Realtime WebSocket Client.
 *
 * Provides:
 * - Scoped connection per trip
 * - Heartbeat ping/pong management
 * - Automatic exponential backoff reconnects
 * - Event subscriber dispatching
 */

import { ENV } from "../config/env";
import { apiClient } from "../api/client";
import { RealtimeConnectionStatus, TripRealtimeEvent } from "./types";

export type RealtimeEventListener = (event: TripRealtimeEvent) => void;
export type StatusChangeListener = (status: RealtimeConnectionStatus) => void;

export class TripRealtimeClient {
  private tripId: string;
  private socket: WebSocket | null = null;
  private status: RealtimeConnectionStatus = "disconnected";
  private eventListeners: Set<RealtimeEventListener> = new Set();
  private statusListeners: Set<StatusChangeListener> = new Set();
  private pingIntervalTimer: any = null;
  private reconnectTimer: any = null;
  private reconnectAttempts = 0;
  private isManuallyClosed = false;

  constructor(tripId: string) {
    this.tripId = tripId;
  }

  public getStatus(): RealtimeConnectionStatus {
    return this.status;
  }

  public onEvent(listener: RealtimeEventListener): () => void {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  }

  public onStatusChange(listener: StatusChangeListener): () => void {
    this.statusListeners.add(listener);
    listener(this.status);
    return () => this.statusListeners.delete(listener);
  }

  private setStatus(newStatus: RealtimeConnectionStatus): void {
    if (this.status !== newStatus) {
      this.status = newStatus;
      this.statusListeners.forEach((listener) => listener(newStatus));
    }
  }

  private getWebSocketUrl(): string {
    const baseUrl = ENV.API_BASE_URL || "http://localhost:8000";
    const wsBase = baseUrl.replace(/^http:\/\//i, "ws://").replace(/^https:\/\//i, "wss://");
    const token = apiClient.getAccessToken() || "";
    return `${wsBase}/api/v1/trips/${this.tripId}/ws?token=${encodeURIComponent(token)}`;
  }

  public connect(): void {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isManuallyClosed = false;
    this.setStatus(this.reconnectAttempts > 0 ? "reconnecting" : "connecting");

    try {
      const url = this.getWebSocketUrl();
      this.socket = new WebSocket(url);

      this.socket.onopen = () => {
        this.reconnectAttempts = 0;
        this.setStatus("connected");
        this.startHeartbeat();
      };

      this.socket.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          if (parsed && parsed.event_type) {
            this.eventListeners.forEach((listener) => listener(parsed as TripRealtimeEvent));
          }
        } catch (e) {
          // Ignore non-json or malformed messages
        }
      };

      this.socket.onerror = () => {
        // Socket error will trigger onclose
      };

      this.socket.onclose = (event) => {
        this.stopHeartbeat();
        this.socket = null;

        if (this.isManuallyClosed || event.code === 4001 || event.code === 4003 || event.code === 4004) {
          this.setStatus("disconnected");
        } else {
          this.scheduleReconnect();
        }
      };
    } catch (err) {
      this.scheduleReconnect();
    }
  }

  public disconnect(): void {
    this.isManuallyClosed = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.setStatus("disconnected");
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.pingIntervalTimer = setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: "ping" }));
      }
    }, 25000);
  }

  private stopHeartbeat(): void {
    if (this.pingIntervalTimer) {
      clearInterval(this.pingIntervalTimer);
      this.pingIntervalTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.isManuallyClosed) return;

    this.setStatus("reconnecting");
    this.reconnectAttempts += 1;
    // Exponential backoff: 1s, 2s, 4s, 8s max
    const delay = Math.min(8000, 1000 * Math.pow(2, this.reconnectAttempts - 1));

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }
    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }
}
