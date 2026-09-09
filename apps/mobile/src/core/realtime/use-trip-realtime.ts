/**
 * useTripRealtime Hook.
 *
 * Connects to the trip WebSocket room, tracks collaborator presence,
 * and notifies listeners on external entity updates.
 */

import { useEffect, useState } from "react";
import { TripRealtimeClient } from "./realtime-client";
import { CollaboratorPresence, RealtimeConnectionStatus, TripRealtimeEvent } from "./types";

const clientInstances: Map<string, TripRealtimeClient> = new Map();

export function getOrCreateTripRealtimeClient(tripId: string): TripRealtimeClient {
  let client = clientInstances.get(tripId);
  if (!client) {
    client = new TripRealtimeClient(tripId);
    clientInstances.set(tripId, client);
  }
  return client;
}

export function useTripRealtime(
  tripId: string | undefined,
  onEventReceived?: (event: TripRealtimeEvent) => void
) {
  const [collaborators, setCollaborators] = useState<CollaboratorPresence[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<RealtimeConnectionStatus>("disconnected");
  const [lastEvent, setLastEvent] = useState<TripRealtimeEvent | null>(null);

  useEffect(() => {
    if (!tripId) return;

    const client = getOrCreateTripRealtimeClient(tripId);

    const unsubscribeStatus = client.onStatusChange((status) => {
      setConnectionStatus(status);
    });

    const unsubscribeEvent = client.onEvent((event) => {
      setLastEvent(event);

      // Handle presence sync
      if (event.event_type === "presence.sync") {
        const syncCollaborators: CollaboratorPresence[] = event.payload?.collaborators || [];
        setCollaborators(syncCollaborators);
      } else if (event.event_type === "presence.joined") {
        const joinedUser: CollaboratorPresence = {
          user_id: event.payload?.user_id || event.entity_id,
          display_name: event.payload?.display_name || "Collaborator",
          role: event.payload?.role || "viewer",
          joined_at: event.payload?.joined_at || event.timestamp,
        };
        setCollaborators((prev) => {
          const exists = prev.some((c) => c.user_id === joinedUser.user_id);
          return exists ? prev : [...prev, joinedUser];
        });
      } else if (event.event_type === "presence.left") {
        const leftUserId = event.payload?.user_id || event.entity_id;
        setCollaborators((prev) => prev.filter((c) => c.user_id !== leftUserId));
      }

      if (onEventReceived) {
        onEventReceived(event);
      }
    });

    client.connect();

    return () => {
      unsubscribeStatus();
      unsubscribeEvent();
    };
  }, [tripId, onEventReceived]);

  return {
    collaborators,
    connectionStatus,
    lastEvent,
  };
}
