/**
 * TripLivePresenceBar Component.
 *
 * Displays live collaborator presence and WebSocket connection status.
 */

import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Users, Radio } from "lucide-react-native";
import { CollaboratorPresence, RealtimeConnectionStatus } from "../../../core/realtime/types";

interface TripLivePresenceBarProps {
  collaborators: CollaboratorPresence[];
  connectionStatus: RealtimeConnectionStatus;
}

export const TripLivePresenceBar: React.FC<TripLivePresenceBarProps> = ({
  collaborators,
  connectionStatus,
}) => {
  const getStatusConfig = () => {
    switch (connectionStatus) {
      case "connected":
        return {
          label: "Live",
          dotColor: "#10b981",
          bgColor: "rgba(16, 185, 129, 0.12)",
          borderColor: "rgba(16, 185, 129, 0.25)",
          textColor: "#6ee7b7",
        };
      case "reconnecting":
      case "connecting":
        return {
          label: "Connecting...",
          dotColor: "#f59e0b",
          bgColor: "rgba(245, 158, 11, 0.12)",
          borderColor: "rgba(245, 158, 11, 0.25)",
          textColor: "#fde68a",
        };
      default:
        return {
          label: "Offline",
          dotColor: "#64748b",
          bgColor: "rgba(100, 116, 139, 0.12)",
          borderColor: "rgba(100, 116, 139, 0.25)",
          textColor: "#94a3b8",
        };
    }
  };

  const statusConfig = getStatusConfig();
  const activeCount = collaborators.length;

  return (
    <View style={styles.container}>
      {/* Connection State Pill */}
      <View
        style={[
          styles.statusPill,
          {
            backgroundColor: statusConfig.bgColor,
            borderColor: statusConfig.borderColor,
          },
        ]}
      >
        <View
          style={[styles.statusDot, { backgroundColor: statusConfig.dotColor }]}
        />
        <Text style={[styles.statusText, { color: statusConfig.textColor }]}>
          {statusConfig.label}
        </Text>
      </View>

      {/* Collaborator Presence Avatars / Count */}
      <View style={styles.presenceContainer}>
        <Users size={13} color="#94a3b8" />
        <Text style={styles.presenceCountText}>
          {activeCount > 0
            ? `${activeCount} online`
            : "No other collaborators"}
        </Text>

        {collaborators.length > 0 && (
          <View style={styles.avatarGroup}>
            {collaborators.slice(0, 3).map((collab) => {
              const initials = (collab.display_name || "U")
                .split(" ")
                .map((n) => n[0])
                .join("")
                .substring(0, 2)
                .toUpperCase();

              return (
                <View key={collab.user_id} style={styles.avatarCircle}>
                  <Text style={styles.avatarText}>{initials}</Text>
                </View>
              );
            })}
          </View>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 6,
    backgroundColor: "rgba(15, 23, 42, 0.6)",
    borderBottomWidth: 1,
    borderBottomColor: "rgba(30, 41, 59, 0.6)",
  },
  statusPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 9999,
    borderWidth: 1,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  statusText: {
    fontSize: 11,
    fontWeight: "600",
  },
  presenceContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  presenceCountText: {
    fontSize: 12,
    color: "#94a3b8",
    fontWeight: "500",
  },
  avatarGroup: {
    flexDirection: "row",
    alignItems: "center",
    marginLeft: 4,
  },
  avatarCircle: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: "rgba(99, 102, 241, 0.25)",
    borderWidth: 1.5,
    borderColor: "#0f172a",
    alignItems: "center",
    justifyContent: "center",
    marginLeft: -4,
  },
  avatarText: {
    fontSize: 9,
    fontWeight: "700",
    color: "#a5b4fc",
  },
});
