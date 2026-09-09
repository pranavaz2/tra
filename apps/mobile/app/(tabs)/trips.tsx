import React from "react";
import {
  View,
  Text,
  FlatList,
  RefreshControl,
  TouchableOpacity,
  ScrollView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Plus, Calendar, MapPin, Eye, Lock } from "lucide-react-native";
import { useTrips } from "@/features/trips/hooks/use-trips";
import { Card } from "@/shared/components/ui/Card";
import { StatusBadge } from "@/shared/components/ui/StatusBadge";
import { Button } from "@/shared/components/ui/Button";
import { ErrorMessage } from "@/shared/components/feedback/ErrorMessage";
import { TripStatus } from "@/core/api/types";
import clsx from "clsx";

const STATUS_FILTERS: { label: string; value?: TripStatus }[] = [
  { label: "All" },
  { label: "Draft", value: "draft" },
  { label: "Planned", value: "planned" },
  { label: "Active", value: "active" },
  { label: "Completed", value: "completed" },
];

export default function TripsScreen() {
  const router = useRouter();
  const {
    trips,
    isLoading,
    isRefreshing,
    error,
    refresh,
    loadMore,
    statusFilter,
    setStatusFilter,
  } = useTrips();

  return (
    <SafeAreaView className="flex-1 bg-slate-950">
      {/* Screen Header */}
      <View className="px-5 pt-3 pb-3 flex-row items-center justify-between border-b border-slate-900">
        <View>
          <Text className="text-2xl font-bold text-white tracking-tight">My Trips</Text>
          <Text className="text-slate-400 text-xs mt-0.5">
            {trips.length} {trips.length === 1 ? "journey" : "journeys"} planned
          </Text>
        </View>

        <Button
          label="New Trip"
          variant="primary"
          size="sm"
          icon={<Plus size={16} color="#ffffff" />}
          onPress={() => router.push("/trips/new")}
        />
      </View>

      {/* Filter Tabs */}
      <View className="py-3 px-5 border-b border-slate-900/60">
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <View className="flex-row space-x-2">
            {STATUS_FILTERS.map((tab) => {
              const isSelected = statusFilter === tab.value;
              return (
                <TouchableOpacity
                  key={tab.label}
                  onPress={() => setStatusFilter(tab.value)}
                  className={clsx(
                    "px-4 py-1.5 rounded-full mr-2 border",
                    isSelected
                      ? "bg-brand-600 border-brand-500"
                      : "bg-slate-900 border-slate-800"
                  )}
                >
                  <Text
                    className={clsx(
                      "text-xs font-semibold",
                      isSelected ? "text-white" : "text-slate-400"
                    )}
                  >
                    {tab.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </ScrollView>
      </View>

      {error && (
        <View className="px-5 pt-3">
          <ErrorMessage message={error} onRetry={refresh} />
        </View>
      )}

      {/* Trips FlatList */}
      <FlatList
        data={trips}
        keyExtractor={(item) => item.trip_id}
        contentContainerStyle={{ padding: 20, flexGrow: 1 }}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={refresh}
            tintColor="#6366f1"
          />
        }
        onEndReached={loadMore}
        onEndReachedThreshold={0.5}
        ListEmptyComponent={
          !isLoading ? (
            <View className="flex-1 items-center justify-center py-20">
              <View className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 items-center justify-center mb-4">
                <MapPin size={28} color="#64748b" />
              </View>
              <Text className="text-white text-lg font-bold mb-1">
                No trips found
              </Text>
              <Text className="text-slate-400 text-sm text-center mb-6 max-w-xs leading-relaxed">
                {statusFilter
                  ? `You don't have any trips matching the "${statusFilter}" status.`
                  : "You haven't created any travel plans yet."}
              </Text>
              <Button
                label="Create a New Trip"
                variant="primary"
                onPress={() => router.push("/trips/new")}
              />
            </View>
          ) : null
        }
        renderItem={({ item }) => {
          let durationDays: number | null = null;
          if (item.departure_date && item.return_date) {
            const diff = new Date(item.return_date).getTime() - new Date(item.departure_date).getTime();
            if (diff >= 0) durationDays = Math.round(diff / (1000 * 60 * 60 * 24)) + 1;
          }

          return (
            <TouchableOpacity
              activeOpacity={0.8}
              className="mb-4"
              onPress={() =>
                router.push({ pathname: "/trips/[id]", params: { id: item.trip_id } })
              }
            >
              <Card className="p-5 bg-slate-900/90 border border-slate-800/90">
                <View className="flex-row items-center justify-between mb-3">
                  <StatusBadge status={item.status} />

                  <View className="flex-row items-center">
                    {item.privacy === "private" ? (
                      <Lock size={13} color="#94a3b8" />
                    ) : (
                      <Eye size={13} color="#94a3b8" />
                    )}
                    <Text className="text-slate-400 text-xs ml-1 font-medium capitalize">
                      {item.privacy.replace("_", " ")}
                    </Text>
                  </View>
                </View>

                <Text className="text-white text-lg font-bold mb-2">{item.title}</Text>

                <View className="flex-row items-center justify-between mt-1">
                  <View className="flex-row items-center flex-1 mr-2">
                    <Calendar size={14} color="#818cf8" />
                    <Text className="text-slate-300 text-xs ml-2 font-medium" numberOfLines={1}>
                      {item.departure_date
                        ? `${item.departure_date} ${item.return_date ? `→ ${item.return_date}` : ""}`
                        : item.is_date_flexible
                        ? "Flexible dates"
                        : "No dates specified"}
                    </Text>
                  </View>

                  {durationDays && (
                    <Text className="text-sky-400 text-xs font-semibold">
                      {durationDays}d
                    </Text>
                  )}
                </View>

                <View className="flex-row items-center justify-between mt-4 pt-3 border-t border-slate-800/60">
                  <Text className="text-slate-500 text-xs">
                    Created {new Date(item.created_at).toLocaleDateString()}
                  </Text>
                  <Text className="text-brand-400 text-xs font-semibold">
                    View Details →
                  </Text>
                </View>
              </Card>
            </TouchableOpacity>
          );
        }}
      />
    </SafeAreaView>
  );
}
