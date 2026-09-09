/**
 * Trip Activity Feed Screen.
 *
 * Displays a chronological audit timeline of changes made across the trip.
 */

import React from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ArrowLeft, Activity, Compass } from "lucide-react-native";
import { useTripActivity } from "@/features/activity/hooks/use-trip-activity";
import { ActivityItemCard } from "@/features/activity/components/ActivityItemCard";
import { useTripRealtime } from "@/core/realtime/use-trip-realtime";
import { TripLivePresenceBar } from "@/features/collaboration/components/TripLivePresenceBar";
import { ErrorMessage } from "@/shared/components/feedback/ErrorMessage";
import { LoadingScreen } from "@/shared/components/feedback/LoadingScreen";

export default function TripActivitiesScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();

  const {
    activities,
    total,
    hasMore,
    isLoading,
    isLoadingMore,
    error,
    refresh,
    loadMore,
  } = useTripActivity(id);

  const { collaborators, connectionStatus } = useTripRealtime(id, () => {
    // Auto-refresh activity feed on real-time mutation events
    refresh();
  });

  if (isLoading && activities.length === 0) {
    return <LoadingScreen message="Loading activity timeline..." />;
  }

  return (
    <SafeAreaView className="flex-1 bg-slate-950" edges={["top", "bottom"]}>
      {/* Top Header */}
      <View className="flex-row items-center justify-between px-5 py-3 border-b border-slate-900 bg-slate-950">
        <View className="flex-row items-center flex-1">
          <TouchableOpacity
            onPress={() => router.back()}
            className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 items-center justify-center mr-3 active:bg-slate-800"
            accessibilityLabel="Go back"
          >
            <ArrowLeft size={20} color="#f8fafc" />
          </TouchableOpacity>
          <View className="flex-1">
            <Text className="text-white text-lg font-bold" numberOfLines={1}>
              Trip Activity
            </Text>
            <Text className="text-slate-400 text-xs mt-0.5">
              {total} {total === 1 ? "event recorded" : "events recorded"}
            </Text>
          </View>
        </View>
      </View>

      {/* Realtime Presence Bar */}
      <TripLivePresenceBar
        collaborators={collaborators}
        connectionStatus={connectionStatus}
      />

      {/* Feed List */}
      <FlatList
        data={activities}
        keyExtractor={(item) => item.activity_id}
        renderItem={({ item }) => <ActivityItemCard item={item} />}
        contentContainerStyle={{ padding: 20, paddingBottom: 40 }}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={refresh}
            tintColor="#818cf8"
            colors={["#818cf8"]}
          />
        }
        onEndReached={loadMore}
        onEndReachedThreshold={0.3}
        ListHeaderComponent={
          error ? (
            <View className="mb-4">
              <ErrorMessage message={error} onRetry={refresh} />
            </View>
          ) : null
        }
        ListEmptyComponent={
          !isLoading ? (
            <View className="items-center justify-center py-16 px-4">
              <View className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 items-center justify-center mb-4">
                <Activity size={32} color="#64748b" />
              </View>
              <Text className="text-white text-base font-semibold mb-1">
                No activity yet
              </Text>
              <Text className="text-slate-400 text-xs text-center max-w-xs leading-5">
                Changes made to the itinerary, budget, or collaborators will appear here in chronological order.
              </Text>
            </View>
          ) : null
        }
        ListFooterComponent={
          isLoadingMore ? (
            <View className="py-4 items-center">
              <ActivityIndicator size="small" color="#818cf8" />
            </View>
          ) : null
        }
      />
    </SafeAreaView>
  );
}
