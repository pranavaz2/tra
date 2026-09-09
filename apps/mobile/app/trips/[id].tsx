import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  ArrowLeft,
  Calendar,
  Clock,
  Edit3,
  Trash2,
  Lock,
  Eye,
  Globe,
  CheckCircle2,
  Play,
  Archive,
  Compass,
  DollarSign,
  MapPin,
  Sparkles,
  ChevronRight,
  Users,
  Image as ImageIcon,
  Bot,
  MessageSquare,
  Activity,
  Share2,
  Bell,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  TrendingUp,
} from "lucide-react-native";
import { useTrip } from "@/features/trips/hooks/use-trips";
import { useItinerary } from "@/features/itinerary/hooks/use-itinerary";
import { useTripProposal } from "@/features/proposals/hooks/use-proposal";
import { useBudget } from "@/features/budget/hooks/use-budget";
import { useCollaboration } from "@/features/collaboration/hooks/use-collaboration";
import { useTripRealtime } from "@/core/realtime/use-trip-realtime";
import { TripLivePresenceBar } from "@/features/collaboration/components/TripLivePresenceBar";
import { useMedia } from "@/features/media/hooks/use-media";
import { ExportTripModal } from "@/features/export/components/ExportTripModal";
import { usePushNotifications } from "@/features/notifications/hooks/use-push-notifications";
import { useTripWarnings } from "@/features/assistant/hooks/use-trip-warnings";
import { TravelWarningBanner } from "@/features/assistant/components/TravelWarningBanner";
import { Card } from "@/shared/components/ui/Card";
import { Button } from "@/shared/components/ui/Button";
import { StatusBadge } from "@/shared/components/ui/StatusBadge";
import { ErrorMessage } from "@/shared/components/feedback/ErrorMessage";
import { LoadingScreen } from "@/shared/components/feedback/LoadingScreen";
import { TripStatus, ItineraryDayResponse } from "@/core/api/types";
import { TravixApiError } from "@/core/api/client";
import clsx from "clsx";

function calculateDurationDays(dep?: string | null, ret?: string | null): number | null {
  if (!dep || !ret) return null;
  const d1 = new Date(dep);
  const d2 = new Date(ret);
  const diffTime = d2.getTime() - d1.getTime();
  if (diffTime < 0) return null;
  return Math.round(diffTime / (1000 * 60 * 60 * 24)) + 1;
}

export default function TripDetailsScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();

  const {
    trip,
    isLoading,
    isMutating,
    error,
    refresh,
    transitionStatus,
    deleteTrip,
  } = useTrip(id);

  const { days: itineraryDays, isLoading: isItineraryLoading } = useItinerary(id);
  const { proposal: tripProposal } = useTripProposal(id);
  const { budget, hasBudget, budgetSummary, isLoading: isBudgetLoading } = useBudget(id);
  const {
    members: collabMembers,
    userRole,
    isOwner,
    isViewer,
  } = useCollaboration(id);

  const { collaborators, connectionStatus } = useTripRealtime(id);
  const { totalCount: mediaCount } = useMedia(id, trip?.owner_id);
  const { warnings, dismissWarning } = useTripWarnings(id);

  const [transitionError, setTransitionError] = useState<string | null>(null);
  const [isExportModalVisible, setIsExportModalVisible] = useState(false);
  const [showAdvancedTools, setShowAdvancedTools] = useState(false);

  usePushNotifications();

  if (isLoading && !trip) {
    return <LoadingScreen message="Loading trip details..." />;
  }

  if (error || !trip) {
    return (
      <SafeAreaView className="flex-1 bg-slate-950 px-6 justify-center">
        <View className="items-center mb-6">
          <View className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 items-center justify-center mb-4">
            <MapPin size={28} color="#64748b" />
          </View>
          <Text className="text-white text-xl font-bold mb-2">Trip Not Found</Text>
          <Text className="text-slate-400 text-sm text-center mb-6 max-w-xs">
            {error || "We couldn't locate this trip. It may have been deleted."}
          </Text>
          <Button
            label="Go Back"
            variant="outline"
            size="md"
            onPress={() => router.back()}
          />
        </View>
      </SafeAreaView>
    );
  }

  const durationDays = calculateDurationDays(trip.departure_date, trip.return_date);
  const itineraryDaysCount = itineraryDays.length;
  const itineraryItemsCount = itineraryDays.reduce(
    (acc: number, d: ItineraryDayResponse) => acc + (d.items?.length || 0),
    0
  );

  // First stop of the first day for highlight
  const firstDay = itineraryDays[0];
  const highlightActivity = firstDay?.items?.[0];

  const handleTransition = async (newStatus: TripStatus) => {
    setTransitionError(null);
    try {
      await transitionStatus(newStatus);
    } catch (err: any) {
      if (err instanceof TravixApiError) {
        setTransitionError(err.message || `Cannot transition to ${newStatus}.`);
      } else {
        setTransitionError("Network error. Could not update status.");
      }
    }
  };

  const handleDelete = () => {
    Alert.alert(
      "Delete Trip",
      `Are you sure you want to delete "${trip.title}"? This cannot be undone.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              await deleteTrip();
              router.replace("/(tabs)/trips");
            } catch (err: any) {
              Alert.alert("Error", err.message || "Failed to delete trip.");
            }
          },
        },
      ]
    );
  };

  return (
    <SafeAreaView className="flex-1 bg-slate-950">
      {/* Navigation Top Bar */}
      <View className="px-5 py-3 flex-row items-center justify-between border-b border-slate-900 bg-slate-950">
        <TouchableOpacity
          onPress={() => router.back()}
          className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 items-center justify-center active:bg-slate-800"
        >
          <ArrowLeft size={20} color="#cbd5e1" />
        </TouchableOpacity>

        <View className="flex-row items-center space-x-2">
          <TouchableOpacity
            onPress={() => setIsExportModalVisible(true)}
            className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 items-center justify-center mr-2 active:bg-slate-800"
            accessibilityLabel="Export Itinerary"
          >
            <Share2 size={18} color="#38bdf8" />
          </TouchableOpacity>

          {!isViewer && (
            <TouchableOpacity
              onPress={() => router.push({ pathname: "/trips/edit", params: { id: trip.trip_id } })}
              className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 items-center justify-center mr-2 active:bg-slate-800"
            >
              <Edit3 size={18} color="#818cf8" />
            </TouchableOpacity>
          )}

          {isOwner && (
            <TouchableOpacity
              onPress={handleDelete}
              disabled={isMutating}
              className="w-10 h-10 rounded-full bg-rose-950/40 border border-rose-800/50 items-center justify-center active:bg-rose-900/40"
            >
              <Trash2 size={18} color="#f43f5e" />
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Live Presence Bar */}
      <TripLivePresenceBar
        collaborators={collaborators}
        connectionStatus={connectionStatus}
      />

      <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 40 }} className="flex-1">
        {transitionError && (
          <ErrorMessage message={transitionError} className="mb-4" />
        )}

        {/* Travel Warnings Banner */}
        {warnings && warnings.length > 0 && (
          <View className="mb-4">
            <TravelWarningBanner warnings={warnings} onDismiss={dismissWarning} />
          </View>
        )}

        {/* Hero Destination Card */}
        <Card className="p-6 bg-gradient-to-br from-slate-900 via-slate-900/90 to-brand-950/40 border border-slate-800 mb-6 relative overflow-hidden">
          <View className="flex-row items-center justify-between mb-3">
            <StatusBadge status={trip.status} size="md" />

            <View className="flex-row items-center px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700/60">
              {trip.privacy === "private" ? (
                <Lock size={12} color="#94a3b8" />
              ) : trip.privacy === "link_only" ? (
                <Eye size={12} color="#94a3b8" />
              ) : (
                <Globe size={12} color="#94a3b8" />
              )}
              <Text className="text-slate-300 text-xs ml-1.5 font-semibold capitalize">
                {trip.privacy.replace("_", " ")}
              </Text>
            </View>
          </View>

          <Text className="text-white text-2xl font-extrabold mb-2 tracking-tight">
            {trip.title}
          </Text>

          <View className="flex-row items-center mt-1">
            <Calendar size={15} color="#818cf8" />
            <Text className="text-slate-200 text-sm ml-2 font-medium">
              {trip.departure_date
                ? `${trip.departure_date} ${trip.return_date ? `→ ${trip.return_date}` : ""}`
                : trip.is_date_flexible
                ? "Flexible travel dates"
                : "Dates not scheduled"}
            </Text>
          </View>

          {/* Quick Lifecycle Action if Planned */}
          {trip.status === "planned" && (
            <View className="mt-5 pt-4 border-t border-slate-800 flex-row items-center justify-between">
              <View className="flex-1 mr-3">
                <Text className="text-emerald-400 text-xs font-bold uppercase tracking-wider">
                  Ready to Go
                </Text>
                <Text className="text-slate-400 text-xs mt-0.5">
                  Your itinerary is set and verified
                </Text>
              </View>
              <Button
                label="Start Journey"
                variant="primary"
                size="sm"
                icon={<Play size={14} color="#ffffff" />}
                isLoading={isMutating}
                onPress={() => handleTransition("active")}
              />
            </View>
          )}

          {trip.status === "draft" && itineraryDaysCount === 0 && (
            <View className="mt-5 pt-4 border-t border-slate-800 flex-row items-center justify-between">
              <View className="flex-1 mr-3">
                <Text className="text-brand-300 text-xs font-bold uppercase tracking-wider">
                  Next Step
                </Text>
                <Text className="text-slate-400 text-xs mt-0.5">
                  Generate your grounded 3-day plan
                </Text>
              </View>
              <Button
                label="Plan with AI"
                variant="primary"
                size="sm"
                icon={<Sparkles size={14} color="#ffffff" />}
                onPress={() => router.push(`/trips/${trip.trip_id}/plan` as any)}
              />
            </View>
          )}
        </Card>

        {/* Next Highlight Stop (if planned) */}
        {highlightActivity && (
          <Card className="p-4 bg-brand-950/30 border border-brand-500/30 mb-5 flex-row items-center justify-between">
            <View className="flex-row items-center flex-1 mr-3">
              <View className="w-9 h-9 rounded-xl bg-brand-600/20 border border-brand-500/40 items-center justify-center mr-3">
                <MapPin size={18} color="#818cf8" />
              </View>
              <View className="flex-1">
                <Text className="text-brand-300 text-[11px] font-bold uppercase tracking-wider">
                  Day 1 Kickoff Stop
                </Text>
                <Text className="text-white text-sm font-bold" numberOfLines={1}>
                  {highlightActivity.title}
                </Text>
              </View>
            </View>
            <TouchableOpacity
              onPress={() => router.push(`/trips/${trip.trip_id}/itinerary` as any)}
              className="px-2.5 py-1.5 rounded-lg bg-brand-500/20 border border-brand-500/40"
            >
              <Text className="text-brand-300 text-xs font-semibold">View</Text>
            </TouchableOpacity>
          </Card>
        )}

        {/* Core Traveler Tools Grid */}
        <Text className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-3 px-1">
          Your Journey
        </Text>

        {/* 1. Trip Itinerary Card */}
        <TouchableOpacity
          onPress={() => router.push(`/trips/${trip.trip_id}/itinerary` as any)}
          activeOpacity={0.7}
          className="mb-3"
        >
          <Card className="p-4 bg-slate-900 border border-brand-500/40 flex-row items-center justify-between">
            <View className="flex-row items-center flex-1 mr-3">
              <View className="w-11 h-11 rounded-2xl bg-brand-600/20 border border-brand-500/40 items-center justify-center mr-3.5">
                <Compass size={22} color="#818cf8" />
              </View>
              <View className="flex-1">
                <Text className="text-white text-base font-bold">Trip Itinerary</Text>
                <Text className="text-slate-400 text-xs mt-0.5">
                  {isItineraryLoading
                    ? "Loading schedule..."
                    : itineraryDaysCount === 0
                    ? "No schedule yet • Tap to plan"
                    : `${itineraryDaysCount} days • ${itineraryItemsCount} verified stops`}
                </Text>
              </View>
            </View>
            <ChevronRight size={20} color="#818cf8" />
          </Card>
        </TouchableOpacity>

        {/* 2. AI Travel Copilot */}
        <TouchableOpacity
          onPress={() => router.push(`/trips/${trip.trip_id}/assistant` as any)}
          activeOpacity={0.7}
          className="mb-3"
        >
          <Card className="p-4 bg-slate-900 border border-violet-500/40 flex-row items-center justify-between">
            <View className="flex-row items-center flex-1 mr-3">
              <View className="w-11 h-11 rounded-2xl bg-violet-600/20 border border-violet-500/40 items-center justify-center mr-3.5">
                <Bot size={22} color="#a78bfa" />
              </View>
              <View className="flex-1">
                <Text className="text-white text-base font-bold">AI Travel Copilot</Text>
                <Text className="text-slate-400 text-xs mt-0.5" numberOfLines={1}>
                  Ask questions, check pacing & modify schedule
                </Text>
              </View>
            </View>
            <ChevronRight size={20} color="#a78bfa" />
          </Card>
        </TouchableOpacity>

        {/* 3. Budget & Expense Card */}
        <TouchableOpacity
          onPress={() => router.push(`/trips/${trip.trip_id}/budget` as any)}
          activeOpacity={0.7}
          className="mb-6"
        >
          <Card className="p-4 bg-slate-900 border border-emerald-500/40 flex-row items-center justify-between">
            <View className="flex-row items-center flex-1 mr-3">
              <View className="w-11 h-11 rounded-2xl bg-emerald-600/20 border border-emerald-500/40 items-center justify-center mr-3.5">
                <DollarSign size={22} color="#34d399" />
              </View>
              <View className="flex-1">
                <Text className="text-white text-base font-bold">Budget & Spending</Text>
                <Text className="text-slate-400 text-xs mt-0.5">
                  {hasBudget && budget
                    ? (() => {
                        const curr = budget.currency || "INR";
                        const limit = budget.limit ?? budget.limit_amount ?? 0;
                        const sym = curr === "INR" ? "₹" : curr === "USD" ? "$" : curr;
                        const formatted =
                          curr === "INR"
                            ? limit.toLocaleString("en-IN")
                            : limit.toLocaleString();
                        return `Limit: ${sym}${formatted}`;
                      })()
                    : "Track expenses & stay on budget"}
                </Text>
              </View>
            </View>
            <ChevronRight size={20} color="#34d399" />
          </Card>
        </TouchableOpacity>

        {/* Secondary Trip Tools Section (Collapsible) */}
        <View className="mb-4">
          <TouchableOpacity
            onPress={() => setShowAdvancedTools(!showAdvancedTools)}
            className="flex-row items-center justify-between p-3 bg-slate-900/60 rounded-xl border border-slate-800"
          >
            <View className="flex-row items-center">
              <Sparkles size={15} color="#94a3b8" />
              <Text className="text-slate-300 text-xs font-semibold ml-2">
                Trip Tools & Sharing ({collabMembers.length} members • {mediaCount} media)
              </Text>
            </View>
            {showAdvancedTools ? (
              <ChevronUp size={16} color="#94a3b8" />
            ) : (
              <ChevronDown size={16} color="#94a3b8" />
            )}
          </TouchableOpacity>

          {showAdvancedTools && (
            <View className="mt-3 space-y-2">
              {/* Collaboration */}
              <TouchableOpacity
                onPress={() => router.push(`/trips/${trip.trip_id}/collaboration` as any)}
                className="p-3.5 bg-slate-900/90 rounded-xl border border-slate-800 flex-row items-center justify-between mb-2"
              >
                <View className="flex-row items-center flex-1">
                  <Users size={18} color="#818cf8" />
                  <Text className="text-slate-200 text-sm font-medium ml-3">
                    Collaborators & Roles
                  </Text>
                </View>
                <Text className="text-slate-400 text-xs">{collabMembers.length} Members</Text>
              </TouchableOpacity>

              {/* Media Gallery */}
              <TouchableOpacity
                onPress={() => router.push(`/trips/${trip.trip_id}/media` as any)}
                className="p-3.5 bg-slate-900/90 rounded-xl border border-slate-800 flex-row items-center justify-between mb-2"
              >
                <View className="flex-row items-center flex-1">
                  <ImageIcon size={18} color="#38bdf8" />
                  <Text className="text-slate-200 text-sm font-medium ml-3">
                    Tickets & Photos
                  </Text>
                </View>
                <Text className="text-slate-400 text-xs">{mediaCount} Items</Text>
              </TouchableOpacity>

              {/* Activity Audit Timeline */}
              <TouchableOpacity
                onPress={() => router.push(`/trips/${trip.trip_id}/activities` as any)}
                className="p-3.5 bg-slate-900/90 rounded-xl border border-slate-800 flex-row items-center justify-between mb-2"
              >
                <View className="flex-row items-center flex-1">
                  <Activity size={18} color="#a78bfa" />
                  <Text className="text-slate-200 text-sm font-medium ml-3">
                    Activity Timeline
                  </Text>
                </View>
                <ChevronRight size={16} color="#64748b" />
              </TouchableOpacity>

              {/* Notifications */}
              <TouchableOpacity
                onPress={() => router.push("/notifications/preferences")}
                className="p-3.5 bg-slate-900/90 rounded-xl border border-slate-800 flex-row items-center justify-between mb-2"
              >
                <View className="flex-row items-center flex-1">
                  <Bell size={18} color="#f59e0b" />
                  <Text className="text-slate-200 text-sm font-medium ml-3">
                    Notification Preferences
                  </Text>
                </View>
                <ChevronRight size={16} color="#64748b" />
              </TouchableOpacity>
            </View>
          )}
        </View>
      </ScrollView>

      {/* Export Modal */}
      <ExportTripModal
        visible={isExportModalVisible}
        onClose={() => setIsExportModalVisible(false)}
        tripId={trip.trip_id}
        tripTitle={trip.title}
      />
    </SafeAreaView>
  );
}
