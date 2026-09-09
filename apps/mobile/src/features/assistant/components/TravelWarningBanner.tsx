/**
 * TravelWarningBanner Component.
 *
 * Renders proactive travel intelligence warnings (schedule overlaps, feasibility, budget overages).
 */

import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  X,
  Clock,
  Navigation,
  DollarSign,
  Compass,
  CloudRain,
} from "lucide-react-native";
import { TravelWarning } from "@/core/api/types";

interface TravelWarningBannerProps {
  warnings: TravelWarning[];
  onDismiss?: (warningId: string) => void;
  compact?: boolean;
}

export const TravelWarningBanner: React.FC<TravelWarningBannerProps> = ({
  warnings,
  onDismiss,
  compact = false,
}) => {
  if (!warnings || warnings.length === 0) {
    return null;
  }

  const getCategoryIcon = (category: string, color: string) => {
    switch (category) {
      case "timing":
        return <Clock size={16} color={color} />;
      case "distance":
        return <Navigation size={16} color={color} />;
      case "budget":
        return <DollarSign size={16} color={color} />;
      case "weather":
        return <CloudRain size={16} color={color} />;
      default:
        return <Compass size={16} color={color} />;
    }
  };

  const getSeverityStyles = (severity: string) => {
    switch (severity) {
      case "critical":
        return {
          bg: "rgba(239, 68, 68, 0.12)",
          border: "rgba(239, 68, 68, 0.35)",
          text: "#fca5a5",
          accent: "#ef4444",
          badgeBg: "rgba(239, 68, 68, 0.25)",
        };
      case "warning":
        return {
          bg: "rgba(245, 158, 11, 0.12)",
          border: "rgba(245, 158, 11, 0.35)",
          text: "#fde68a",
          accent: "#f59e0b",
          badgeBg: "rgba(245, 158, 11, 0.25)",
        };
      default:
        return {
          bg: "rgba(59, 130, 246, 0.12)",
          border: "rgba(59, 130, 246, 0.35)",
          text: "#93c5fd",
          accent: "#3b82f6",
          badgeBg: "rgba(59, 130, 246, 0.25)",
        };
    }
  };

  return (
    <View style={styles.container}>
      {warnings.map((warning) => {
        const stylesConfig = getSeverityStyles(warning.severity);

        return (
          <View
            key={warning.warning_id}
            style={[
              styles.card,
              {
                backgroundColor: stylesConfig.bg,
                borderColor: stylesConfig.border,
              },
            ]}
          >
            <View style={styles.header}>
              <View style={styles.headerLeft}>
                {warning.severity === "critical" ? (
                  <AlertTriangle size={18} color={stylesConfig.accent} />
                ) : warning.severity === "warning" ? (
                  <AlertCircle size={18} color={stylesConfig.accent} />
                ) : (
                  <Info size={18} color={stylesConfig.accent} />
                )}

                <View
                  style={[
                    styles.categoryBadge,
                    { backgroundColor: stylesConfig.badgeBg },
                  ]}
                >
                  {getCategoryIcon(warning.category, stylesConfig.accent)}
                  <Text
                    style={[
                      styles.categoryText,
                      { color: stylesConfig.text },
                    ]}
                  >
                    {warning.category.toUpperCase()}
                  </Text>
                </View>

                {warning.day_number !== undefined && warning.day_number !== null && (
                  <View style={styles.dayBadge}>
                    <Text style={styles.dayText}>Day {warning.day_number}</Text>
                  </View>
                )}
              </View>

              {onDismiss && (
                <TouchableOpacity
                  onPress={() => onDismiss(warning.warning_id)}
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                >
                  <X size={16} color="#94a3b8" />
                </TouchableOpacity>
              )}
            </View>

            <Text style={[styles.title, { color: stylesConfig.accent }]}>
              {warning.title}
            </Text>
            <Text style={[styles.message, { color: stylesConfig.text }]}>
              {warning.message}
            </Text>

            {/* Routing & Travel-Time Intelligence Badge */}
            {(warning.metadata?.estimated_duration_minutes !== undefined ||
              warning.metadata?.route_distance_km !== undefined) && (
              <View style={styles.routeFooter}>
                <View style={styles.routePill}>
                  <Navigation size={12} color="#38bdf8" />
                  <Text style={styles.routePillText}>
                    {warning.metadata.travel_mode === "walk" ? "🚶" : "🚗"}{" "}
                    {warning.metadata.estimated_duration_minutes !== undefined
                      ? `~${warning.metadata.estimated_duration_minutes} min`
                      : ""}
                    {warning.metadata.route_distance_km !== undefined
                      ? ` (${warning.metadata.route_distance_km} km)`
                      : ""}
                    {warning.metadata.is_fallback ? " · approx" : " · real route"}
                  </Text>
                </View>
                {warning.metadata.gap_minutes !== undefined && (
                  <Text style={styles.routeGapText}>
                    Buffer: {warning.metadata.gap_minutes}m
                  </Text>
                )}
              </View>
            )}
          </View>
        );
      })}
    </View>
  );
};


const styles = StyleSheet.create({
  container: {
    marginVertical: 8,
    gap: 8,
  },
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 6,
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  categoryBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  categoryText: {
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  dayBadge: {
    backgroundColor: "rgba(255, 255, 255, 0.1)",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  dayText: {
    fontSize: 11,
    color: "#cbd5e1",
    fontWeight: "600",
  },
  title: {
    fontSize: 13,
    fontWeight: "700",
    marginBottom: 2,
  },
  message: {
    fontSize: 13,
    lineHeight: 18,
  },
  routeFooter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 8,
    paddingTop: 6,
    borderTopWidth: 1,
    borderTopColor: "rgba(255, 255, 255, 0.08)",
  },
  routePill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "rgba(56, 189, 248, 0.12)",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  routePillText: {
    fontSize: 11,
    color: "#38bdf8",
    fontWeight: "600",
  },
  routeGapText: {
    fontSize: 11,
    color: "#94a3b8",
    fontWeight: "500",
  },
});

