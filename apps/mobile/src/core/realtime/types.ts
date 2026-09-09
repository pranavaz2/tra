/**
 * Real-Time Multi-User Synchronization & Presence Types.
 */

export type RealtimeConnectionStatus =
  | "connected"
  | "connecting"
  | "reconnecting"
  | "disconnected";

export interface CollaboratorPresence {
  user_id: string;
  display_name: string;
  role: "owner" | "editor" | "viewer" | string;
  joined_at: string;
  client_id?: string;
}

export interface TripRealtimeEvent {
  event_id: string;
  trip_id: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  action: string;
  version?: number | null;
  actor_id?: string | null;
  timestamp: string;
  payload: Record<string, any>;
}

export interface PresenceSyncPayload {
  collaborators: CollaboratorPresence[];
  connection_id: string;
}
