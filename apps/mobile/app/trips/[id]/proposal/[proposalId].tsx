import React, { useState } from "react";
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
  Sparkles,
  Calendar,
  Clock,
  DollarSign,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RotateCcw,
  Check,
  Compass,
  MapPin,
} from "lucide-react-native";
import { useProposal } from "@/features/proposals/hooks/use-proposal";
import { useTrip } from "@/features/trips/hooks/use-trips";
import { useBudget } from "@/features/budget/hooks/use-budget";
import { useCollaboration } from "@/features/collaboration/hooks/use-collaboration";
import { ProposedActivityCard } from "@/features/proposals/components/ProposedActivityCard";
import { Card } from "@/shared/components/ui/Card";
import { Button } from "@/shared/components/ui/Button";
import { LoadingScreen } from "@/shared/components/feedback/LoadingScreen";
import { ErrorMessage } from "@/shared/components/feedback/ErrorMessage";
import { ProposalStatus, ProposedDayResponse } from "@/core/api/types";
import clsx from "clsx";

export const getStatusBadgeMeta = (status: ProposalStatus) => {
  switch (status) {
    case "ready":
      return {
        label: "Ready to Save",
        bg: "bg-sky-500/10 border-sky-500/30",
        color: "#38bdf8",
        icon: Sparkles,
      };
    case "accepted":
      return {
        label: "Saved to Itinerary",
        bg: "bg-emerald-500/10 border-emerald-500/30",
        color: "#34d399",
        icon: CheckCircle2,
      };
    case "rejected":
      return {
        label: "Declined",
        bg: "bg-rose-500/10 border-rose-500/30",
        color: "#f43f5e",
        icon: XCircle,
      };
    case "generating":
    case "queued":
      return {
        label: "Crafting Plan...",
        bg: "bg-brand-500/10 border-brand-500/30",
        color: "#818cf8",
        icon: Clock,
      };
    case "failed":
      return {
        label: "Generation Failed",
        bg: "bg-rose-500/10 border-rose-500/30",
        color: "#f43f5e",
        icon: AlertTriangle,
      };
    case "expired":
      return {
        label: "Expired",
        bg: "bg-slate-800 border-slate-700",
        color: "#94a3b8",
        icon: Clock,
      };
  }
};

export default function ProposalPreviewScreen() {
  const router = useRouter();
  const { id, proposalId, targetBudget } = useLocalSearchParams<{
    id: string;
    proposalId: string;
    targetBudget?: string;
  }>();

  const {
    proposal,
    isLoading,
    isMutating,
    error,
    refresh,
    acceptAndApplyToItinerary,
    rejectProposal,
  } = useProposal(proposalId);

  const { transitionStatus } = useTrip(id);
  const { createBudget } = useBudget(id);
  const { isViewer } = useCollaboration(id);

  const [saving, setSaving] = useState(false);
  const [saveStatusText, setSaveStatusText] = useState("");

  const handleSaveToTrip = async () => {
    setSaving(true);
    setSaveStatusText("Saving grounded stops to your itinerary...");

    try {
      // 1. Accept and apply proposal to itinerary
      await acceptAndApplyToItinerary(id);

      // 2. Automatically initialize budget target if specified or estimated
      const budgetNum = targetBudget ? parseFloat(targetBudget) : null;
      if (budgetNum && !isNaN(budgetNum) && budgetNum > 0) {
        setSaveStatusText("Initializing trip budget tracker...");
        try {
          await createBudget({
            limit_amount: budgetNum,
            currency: "INR",
          });
        } catch {
          // Non-blocking: budget can be adjusted later in budget tab
        }
      }

      // 3. Move status to planned if currently draft
      setSaveStatusText("Updating trip status to Planned...");
      try {
        await transitionStatus("planned");
      } catch {
        // Non-blocking
      }

      // 4. Navigate directly to the Trip Hub
      router.replace(`/trips/${id}` as any);
    } catch (err: any) {
      Alert.alert("Error", err?.message || "Failed to save proposal to your trip.");
    } finally {
      setSaving(false);
      setSaveStatusText("");
    }
  };

  const handleReject = () => {
    Alert.alert(
      "Decline Plan",
      "Would you like to discard this plan and customize your preferences?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Decline & Re-plan",
          style: "destructive",
          onPress: async () => {
            try {
              await rejectProposal();
              router.replace(`/trips/${id}/plan` as any);
            } catch (err: any) {
              Alert.alert("Error", err?.message || "Failed to decline plan.");
            }
          },
        },
      ]
    );
  };

  if (isLoading && !proposal) {
    return <LoadingScreen message="Loading your AI travel plan..." />;
  }

  if (error || !proposal) {
    return (
      <SafeAreaView className="flex-1 bg-slate-950 px-6 justify-center">
        <ErrorMessage
          message={error || "Travel plan not found"}
          onRetry={refresh}
        />
        <Button
          label="Back to Trip"
          variant="secondary"
          className="mt-4"
          onPress={() => router.back()}
        />
      </SafeAreaView>
    );
  }

  const statusMeta = getStatusBadgeMeta(proposal.status);
  const StatusIcon = statusMeta.icon;
  const result = proposal.result;

  return (
    <SafeAreaView className="flex-1 bg-slate-950" edges={["top", "bottom"]}>
      {/* Header */}
      <View className="flex-row items-center justify-between px-6 py-4 border-b border-slate-900 bg-slate-950">
        <View className="flex-row items-center flex-1">
          <TouchableOpacity
            onPress={() => router.back()}
            disabled={isMutating || saving}
            className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 items-center justify-center mr-3 active:bg-slate-800"
            accessibilityLabel="Go back"
          >
            <ArrowLeft size={20} color="#f8fafc" />
          </TouchableOpacity>
          <View className="flex-1 mr-2">
            <Text className="text-white text-lg font-bold" numberOfLines={1}>
              {proposal.preferences.destination}
            </Text>
            <Text className="text-slate-400 text-xs mt-0.5">
              {proposal.preferences.duration_days} Days • {proposal.preferences.travel_style} Pace
            </Text>
          </View>
        </View>

        {/* Status Badge */}
        <View
          className={clsx(
            "flex-row items-center px-2.5 py-1 rounded-full border",
            statusMeta.bg
          )}
        >
          <StatusIcon size={12} color={statusMeta.color} />
          <Text
            className="text-[11px] font-bold uppercase tracking-wider ml-1.5"
            style={{ color: statusMeta.color }}
          >
            {statusMeta.label}
          </Text>
        </View>
      </View>

      {/* Main Content */}
      <ScrollView
        className="flex-1 px-6"
        contentContainerStyle={{ paddingVertical: 16 }}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={refresh}
            tintColor="#38bdf8"
            colors={["#38bdf8"]}
          />
        }
      >
        {/* Plan Overview Card */}
        {result ? (
          <Card className="p-5 bg-gradient-to-br from-brand-950/60 to-slate-900 border border-brand-500/40 mb-6 shadow-lg shadow-brand-950/40">
            <View className="flex-row items-center justify-between mb-3">
              <View className="flex-row items-center">
                <Sparkles size={16} color="#818cf8" />
                <Text className="text-brand-300 text-xs font-bold uppercase tracking-wider ml-2">
                  Trip Overview & Concept
                </Text>
              </View>
              <View className="px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/20">
                <Text className="text-emerald-400 text-[10px] font-semibold">
                  Verified Places
                </Text>
              </View>
            </View>

            <Text className="text-slate-200 text-sm leading-relaxed mb-4 font-medium">
              {result.summary}
            </Text>

            <View className="flex-row items-center justify-between pt-3 border-t border-slate-800">
              <View>
                <Text className="text-slate-400 text-[10px] uppercase font-semibold">
                  Style
                </Text>
                <Text className="text-white text-xs font-bold capitalize mt-0.5">
                  {proposal.preferences.travel_style}
                </Text>
              </View>

              <View>
                <Text className="text-slate-400 text-[10px] uppercase font-semibold">
                  Tier
                </Text>
                <Text className="text-white text-xs font-bold capitalize mt-0.5">
                  {proposal.preferences.budget_level.replace("_", "-")}
                </Text>
              </View>

              {result.estimated_total_cost && (
                <View>
                  <Text className="text-slate-400 text-[10px] uppercase font-semibold">
                    Est. Total
                  </Text>
                  <Text className="text-emerald-400 text-xs font-bold mt-0.5">
                    {result.estimated_total_cost}
                  </Text>
                </View>
              )}
            </View>
          </Card>
        ) : null}

        {/* Failure Banner */}
        {proposal.status === "failed" && (
          <Card className="p-4 bg-rose-950/20 border border-rose-800 mb-6">
            <Text className="text-rose-400 text-sm font-bold mb-1">
              Plan Generation Failed
            </Text>
            <Text className="text-slate-400 text-xs">
              {proposal.failure_reason || "Unable to generate plan with given parameters."}
            </Text>
          </Card>
        )}

        {/* Days & Proposed Activities */}
        {result && result.days ? (
          <View>
            <Text className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-4 px-1">
              Your Daily Itinerary ({result.days.length} Days)
            </Text>

            {result.days.map((day: ProposedDayResponse) => (
              <View key={day.day_number} className="mb-6">
                {/* Day Header */}
                <View className="flex-row items-center justify-between bg-slate-900 px-4 py-3 rounded-2xl border border-slate-800 mb-3">
                  <View className="flex-row items-center flex-1 mr-2">
                    <View className="px-2.5 py-1 rounded-lg bg-brand-600/20 border border-brand-500/30 mr-2.5">
                      <Text className="text-brand-300 text-xs font-bold">
                        Day {day.day_number}
                      </Text>
                    </View>
                    <View className="flex-1">
                      <Text className="text-white font-bold text-sm" numberOfLines={1}>
                        {day.title}
                      </Text>
                      {day.description ? (
                        <Text className="text-slate-400 text-xs mt-0.5" numberOfLines={1}>
                          {day.description}
                        </Text>
                      ) : null}
                    </View>
                  </View>
                  <View className="px-2 py-0.5 rounded-md bg-slate-800">
                    <Text className="text-slate-400 text-[10px] font-semibold">
                      {day.activities?.length || 0} stops
                    </Text>
                  </View>
                </View>

                {/* Day Activities */}
                {day.activities && day.activities.length > 0 ? (
                  <View className="space-y-2">
                    {day.activities.map((activity, idx) => (
                      <ProposedActivityCard
                        key={`${day.day_number}-${idx}`}
                        activity={activity}
                      />
                    ))}
                  </View>
                ) : (
                  <Text className="text-slate-500 text-xs italic px-2">
                    No activities listed for this day.
                  </Text>
                )}
              </View>
            ))}
          </View>
        ) : null}
      </ScrollView>

      {/* Action Footer */}
      <View className="p-4 px-6 border-t border-slate-800 bg-slate-950">
        {saving ? (
          <View className="items-center py-2">
            <ActivityIndicator size="small" color="#34d399" />
            <Text className="text-emerald-400 text-xs font-semibold mt-2">
              {saveStatusText || "Saving your plan..."}
            </Text>
          </View>
        ) : proposal.status === "ready" ? (
          isViewer ? (
            <View className="py-2.5 px-4 bg-slate-900 border border-slate-800 rounded-xl items-center">
              <Text className="text-slate-400 text-xs text-center">
                Viewer access: only editors and owners can accept travel plans.
              </Text>
            </View>
          ) : (
            <View className="flex-row space-x-3">
              <Button
                label="Customize"
                variant="secondary"
                className="flex-1 mr-2"
                onPress={handleReject}
                disabled={isMutating}
              />
              <Button
                label="Save to My Trip"
                variant="primary"
                icon={<Check size={18} color="#ffffff" />}
                className="flex-[2] ml-2 bg-emerald-600 active:bg-emerald-700"
                onPress={handleSaveToTrip}
                disabled={isMutating}
              />
            </View>
          )
        ) : proposal.status === "accepted" ? (
          <Button
            label="View Saved Itinerary"
            className="w-full bg-brand-600 active:bg-brand-700"
            onPress={() => router.push(`/trips/${id}/itinerary` as any)}
          />
        ) : isViewer ? (
          <View className="py-2.5 px-4 bg-slate-900 border border-slate-800 rounded-xl items-center">
            <Text className="text-slate-400 text-xs text-center">
              Viewing proposal (read-only)
            </Text>
          </View>
        ) : (
          <Button
            label="Generate New Plan"
            className="w-full bg-brand-600 active:bg-brand-700"
            onPress={() => router.push(`/trips/${id}/plan` as any)}
          />
        )}
      </View>
    </SafeAreaView>
  );
}
