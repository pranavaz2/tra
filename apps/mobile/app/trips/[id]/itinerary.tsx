import React, { useState, useMemo } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  ArrowLeft,
  Plus,
  Calendar,
  Clock,
  Compass,
  Trash2,
  AlertCircle,
  Sparkles,
  Layers,
} from "lucide-react-native";
import { useItinerary } from "@/features/itinerary/hooks/use-itinerary";
import { useCollaboration } from "@/features/collaboration/hooks/use-collaboration";
import { useTripRealtime } from "@/core/realtime/use-trip-realtime";
import { TripLivePresenceBar } from "@/features/collaboration/components/TripLivePresenceBar";
import { useTripWarnings } from "@/features/assistant/hooks/use-trip-warnings";
import { TravelWarningBanner } from "@/features/assistant/components/TravelWarningBanner";
import { ItineraryItemCard } from "@/features/itinerary/components/ItineraryItemCard";
import { ItemFormModal } from "@/features/itinerary/components/ItemFormModal";
import { DayFormModal } from "@/features/itinerary/components/DayFormModal";
import {
  ItineraryDayResponse,
  ItineraryItemResponse,
  ItineraryItemCreateRequest,
  ItineraryItemUpdateRequest,
  ItineraryDayCreateRequest,
} from "@/core/api/types";
import { Card } from "@/shared/components/ui/Card";
import { Button } from "@/shared/components/ui/Button";
import { LoadingScreen } from "@/shared/components/feedback/LoadingScreen";
import { ErrorMessage } from "@/shared/components/feedback/ErrorMessage";

export default function ItineraryScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();

  const {
    itinerary,
    days,
    isLoading,
    isMutating,
    error,
    refresh,
    addDay,
    removeDay,
    addItem,
    updateItem,
    removeItem,
  } = useItinerary(id);

  const { isViewer, userRole } = useCollaboration(id);
  const { itineraryWarnings, dismissWarning } = useTripWarnings(id);
  const { collaborators, connectionStatus } = useTripRealtime(id);

  // Modals state
  const [dayModalVisible, setDayModalVisible] = useState(false);
  const [itemModalVisible, setItemModalVisible] = useState(false);
  const [activeDayId, setActiveDayId] = useState<string>("");
  const [editingItem, setEditingItem] = useState<ItineraryItemResponse | null>(null);

  // Stats calculation
  const stats = useMemo(() => {
    let totalItems = 0;
    let totalCost = 0;
    const currencies = new Set<string>();

    days.forEach((day: ItineraryDayResponse) => {
      totalItems += day.items ? day.items.length : 0;
      day.items?.forEach((item: ItineraryItemResponse) => {
        if (item.cost !== null && item.cost !== undefined) {
          totalCost += Number(item.cost);
          if (item.currency) currencies.add(item.currency);
        }
      });
    });

    return {
      daysCount: days.length,
      itemsCount: totalItems,
      totalCost,
      currencyStr: Array.from(currencies).join(", ") || "",
    };
  }, [days]);

  // Suggested next day number
  const suggestedDayNumber = useMemo(() => {
    if (days.length === 0) return 1;
    const maxDay = Math.max(...days.map((d: ItineraryDayResponse) => d.day_number));
    return maxDay + 1;
  }, [days]);

  // Handlers for Day Actions
  const handleOpenAddDay = () => {
    setDayModalVisible(true);
  };

  const handleSaveDay = async (data: ItineraryDayCreateRequest) => {
    await addDay(data);
  };

  const handleDeleteDay = (day: ItineraryDayResponse) => {
    Alert.alert(
      "Delete Day",
      `Are you sure you want to delete Day ${day.day_number}? This will also delete all ${day.items?.length || 0} items within it.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              await removeDay(day.day_id);
            } catch (e: any) {
              Alert.alert("Error", e?.message || "Failed to remove day");
            }
          },
        },
      ]
    );
  };

  // Handlers for Item Actions
  const handleOpenAddItem = (dayId: string) => {
    setEditingItem(null);
    setActiveDayId(dayId);
    setItemModalVisible(true);
  };

  const handleOpenEditItem = (item: ItineraryItemResponse) => {
    setEditingItem(item);
    setActiveDayId(item.day_id);
    setItemModalVisible(true);
  };

  const handleSaveItem = async (
    data: ItineraryItemCreateRequest | ItineraryItemUpdateRequest
  ) => {
    if (editingItem) {
      await updateItem(editingItem.item_id, data as ItineraryItemUpdateRequest);
    } else {
      await addItem(data as ItineraryItemCreateRequest);
    }
  };

  const handleDeleteItem = async (itemId: string) => {
    try {
      await removeItem(itemId);
    } catch (e: any) {
      Alert.alert("Error", e?.message || "Failed to delete item");
    }
  };

  if (isLoading && !itinerary) {
    return <LoadingScreen message="Loading itinerary..." />;
  }

  return (
    <SafeAreaView className="flex-1 bg-slate-950" edges={["top", "bottom"]}>
      {/* Header */}
      <View className="flex-row items-center justify-between px-6 py-4 border-b border-slate-800/80 bg-slate-950">
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
              Trip Itinerary
            </Text>
            <Text className="text-slate-400 text-xs mt-0.5">
              {stats.daysCount} {stats.daysCount === 1 ? "day" : "days"} •{" "}
              {stats.itemsCount} {stats.itemsCount === 1 ? "item" : "items"}
            </Text>
          </View>
        </View>

        {!isViewer && (
          <TouchableOpacity
            onPress={handleOpenAddDay}
            disabled={isMutating}
            className="flex-row items-center bg-brand-600 px-3 py-2 rounded-xl active:bg-brand-700"
          >
            <Plus size={16} color="#ffffff" />
            <Text className="text-white text-xs font-semibold ml-1">Add Day</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Live Presence Bar */}
      <TripLivePresenceBar
        collaborators={collaborators}
        connectionStatus={connectionStatus}
      />

      {/* Main Content */}
      <ScrollView
        className="flex-1 px-6"
        contentContainerStyle={{ paddingVertical: 16 }}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={refresh}
            tintColor="#818cf8"
            colors={["#818cf8"]}
          />
        }
      >
        {/* Error Banner */}
        {error && (
          <View className="mb-4">
            <ErrorMessage message={error} onRetry={refresh} />
          </View>
        )}

        {/* Itinerary Summary Bar */}
        {days.length > 0 && (
          <Card className="p-4 bg-slate-900/70 border border-slate-800 mb-6">
            <View className="flex-row items-center justify-between">
              <View className="flex-1 border-r border-slate-800 pr-3">
                <Text className="text-slate-400 text-[11px] uppercase font-semibold">
                  Days
                </Text>
                <Text className="text-white text-base font-bold mt-0.5">
                  {stats.daysCount}
                </Text>
              </View>

              <View className="flex-1 border-r border-slate-800 px-3">
                <Text className="text-slate-400 text-[11px] uppercase font-semibold">
                  Activities
                </Text>
                <Text className="text-white text-base font-bold mt-0.5">
                  {stats.itemsCount}
                </Text>
              </View>

              <View className="flex-1 pl-3">
                <Text className="text-slate-400 text-[11px] uppercase font-semibold">
                  Est. Cost
                </Text>
                <Text className="text-emerald-400 text-base font-bold mt-0.5" numberOfLines={1}>
                  {stats.totalCost > 0
                    ? (() => {
                        const curr = stats.currencyStr || "INR";
                        const sym = curr === "INR" ? "₹" : curr === "USD" ? "$" : curr + " ";
                        const formatted = curr === "INR"
                          ? stats.totalCost.toLocaleString("en-IN", { maximumFractionDigits: 0 })
                          : stats.totalCost.toFixed(2);
                        return `${sym}${formatted}`;
                      })()
                    : "—"}
                </Text>
              </View>
            </View>
          </Card>
        )}

        {/* Proactive Travel Warnings */}
        {itineraryWarnings.length > 0 && (
          <View className="mb-4">
            <TravelWarningBanner
              warnings={itineraryWarnings}
              onDismiss={dismissWarning}
            />
          </View>
        )}

        {/* Empty State: No Days */}
        {days.length === 0 && !isLoading && (
          <Card className="p-8 items-center justify-center bg-slate-900/60 border border-brand-500/30 my-8">
            <View className="w-16 h-16 rounded-2xl bg-brand-500/20 border border-brand-500/40 items-center justify-center mb-4">
              <Sparkles size={32} color="#818cf8" />
            </View>
            <Text className="text-white text-xl font-bold text-center mb-2">
              No Stops Planned Yet
            </Text>
            <Text className="text-slate-300 text-sm text-center leading-relaxed mb-6">
              Ask the AI Copilot to suggest verified places — or generate a complete plan with Travix AI.
            </Text>
            <View className="w-full space-y-2.5">
              <Button
                label="Plan with Travix AI"
                variant="primary"
                size="lg"
                icon={<Sparkles size={18} color="#ffffff" />}
                onPress={() => router.push(`/trips/${id}/plan` as any)}
                className="w-full mb-2"
              />
              {!isViewer && (
                <Button
                  label="Or Add Day 1 Manually"
                  variant="outline"
                  size="md"
                  onPress={handleOpenAddDay}
                  className="w-full"
                />
              )}
            </View>
          </Card>
        )}

        {/* Days List */}
        {days.map((day: ItineraryDayResponse) => {
          const items = day.items || [];
          return (
            <View key={day.day_id} className="mb-6">
              {/* Day Header */}
              <View className="flex-row items-center justify-between bg-slate-900 px-4 py-3 rounded-2xl border border-slate-800 mb-3">
                <View className="flex-row items-center flex-1 mr-2">
                  <View className="px-2.5 py-1 rounded-lg bg-brand-600/20 border border-brand-500/30 mr-2.5">
                    <Text className="text-brand-300 text-xs font-bold">
                      Day {day.day_number}
                    </Text>
                  </View>

                  <View className="flex-1">
                    {day.title ? (
                      <Text
                        className="text-white font-bold text-sm"
                        numberOfLines={1}
                      >
                        {day.title}
                      </Text>
                    ) : (
                      <Text className="text-slate-400 font-medium text-sm">
                        Day {day.day_number}
                      </Text>
                    )}

                    {day.date && (
                      <View className="flex-row items-center mt-0.5">
                        <Calendar size={11} color="#94a3b8" />
                        <Text className="text-slate-400 text-[11px] ml-1">
                          {day.date}
                        </Text>
                      </View>
                    )}
                  </View>
                </View>

                {/* Day Action Buttons */}
                {!isViewer && (
                  <View className="flex-row items-center space-x-1.5">
                    <TouchableOpacity
                      onPress={() => handleOpenAddItem(day.day_id)}
                      disabled={isMutating}
                      className="flex-row items-center px-2.5 py-1.5 rounded-lg bg-slate-800 border border-slate-700 mr-1.5 active:bg-slate-700"
                    >
                      <Plus size={13} color="#818cf8" />
                      <Text className="text-brand-300 text-[11px] font-semibold ml-1">
                        Item
                      </Text>
                    </TouchableOpacity>

                    <TouchableOpacity
                      onPress={() => handleDeleteDay(day)}
                      disabled={isMutating}
                      className="w-7 h-7 rounded-lg bg-rose-950/40 border border-rose-800/40 items-center justify-center active:bg-rose-900/40"
                      accessibilityLabel="Delete day"
                    >
                      <Trash2 size={13} color="#f43f5e" />
                    </TouchableOpacity>
                  </View>
                )}
              </View>

              {/* Day Items */}
              {items.length === 0 ? (
                <View className="p-4 rounded-xl border border-dashed border-slate-800/80 bg-slate-950/40 items-center justify-center mb-2">
                  <Text className="text-slate-500 text-xs text-center mb-2">
                    No activities planned for Day {day.day_number} yet.
                  </Text>
                  {!isViewer && (
                    <TouchableOpacity
                      onPress={() => handleOpenAddItem(day.day_id)}
                      disabled={isMutating}
                      className="flex-row items-center"
                    >
                      <Plus size={12} color="#818cf8" />
                      <Text className="text-brand-400 text-xs font-semibold ml-1">
                        Add First Item
                      </Text>
                    </TouchableOpacity>
                  )}
                </View>
              ) : (
                <View className="space-y-2">
                  {items.map((item: ItineraryItemResponse) => (
                    <ItineraryItemCard
                      key={item.item_id}
                      item={item}
                      onEdit={handleOpenEditItem}
                      onDelete={handleDeleteItem}
                      isMutating={isMutating}
                      canEdit={!isViewer}
                    />
                  ))}
                </View>
              )}
            </View>
          );
        })}
      </ScrollView>

      {/* Add / Edit Day Modal */}
      <DayFormModal
        visible={dayModalVisible}
        onClose={() => setDayModalVisible(false)}
        onSubmit={handleSaveDay}
        suggestedDayNumber={suggestedDayNumber}
        isSubmitting={isMutating}
      />

      {/* Add / Edit Item Modal */}
      <ItemFormModal
        visible={itemModalVisible}
        onClose={() => setItemModalVisible(false)}
        onSubmit={handleSaveItem}
        initialItem={editingItem}
        dayId={activeDayId}
        days={days}
        isSubmitting={isMutating}
      />
    </SafeAreaView>
  );
}
