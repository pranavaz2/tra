/**
 * ProposedActionCard Component.
 *
 * Renders an AI proposed mutation with action details, affected day / budget / verified places,
 * rationale, travel-time / budget impacts, and Save to My Trip / Reject buttons (restricted for Viewers).
 */

import React from "react";
import { View, Text } from "react-native";
import {
  CheckCircle2,
  XCircle,
  PlusCircle,
  Trash2,
  RefreshCw,
  TrendingUp,
  Receipt,
  MapPin,
  Star,
  ShieldCheck,
  Clock,
  ArrowRightLeft,
  CloudRain,
  Sparkles,
} from "lucide-react-native";
import { ProposedActionSchema } from "@/core/api/types";
import { Card } from "@/shared/components/ui/Card";
import { Button } from "@/shared/components/ui/Button";

interface ProposedActionCardProps {
  action: ProposedActionSchema;
  onConfirm: (actionId: string) => void;
  onReject: (actionId: string) => void;
  isMutating?: boolean;
  isViewer?: boolean;
}

export const ProposedActionCard: React.FC<ProposedActionCardProps> = ({
  action,
  onConfirm,
  onReject,
  isMutating = false,
  isViewer = false,
}) => {
  const isPending = action.status === "pending";
  const isApplied = action.status === "applied";
  const isRejected = action.status === "rejected";
  const isPlaceAction =
    action.action_type === "propose_adding_place" ||
    (action.payload && Boolean(action.payload.provider_place_id || action.payload.is_verified));

  const getActionIcon = () => {
    switch (action.action_type) {
      case "propose_adding_place":
      case "propose_adding_activity":
        return <PlusCircle size={18} color="#38bdf8" />;
      case "propose_removing_activity":
        return <Trash2 size={18} color="#f43f5e" />;
      case "propose_rescheduling_activity":
        return <Clock size={18} color="#a855f7" />;
      case "propose_replacing_activity":
        return <ArrowRightLeft size={18} color="#f59e0b" />;
      case "propose_reordering_activities":
        return <RefreshCw size={18} color="#818cf8" />;
      case "propose_adjusting_budget":
      case "propose_updating_budget_limit":
        return <TrendingUp size={18} color="#10b981" />;
      case "propose_adding_expense":
        return <Receipt size={18} color="#10b981" />;
      case "propose_itinerary_change":
      default:
        return <Sparkles size={18} color="#38bdf8" />;
    }
  };

  const getActionTypeLabel = () => {
    switch (action.action_type) {
      case "propose_adding_place":
        return "Grounded Place Proposal";
      case "propose_adding_activity":
        return "Add Activity Proposal";
      case "propose_removing_activity":
        return "Remove Activity Proposal";
      case "propose_rescheduling_activity":
        return "Reschedule Activity Proposal";
      case "propose_replacing_activity":
        return "Replace Activity Proposal";
      case "propose_reordering_activities":
        return "Reorder Activities Proposal";
      case "propose_adjusting_budget":
        return "Budget Optimization Proposal";
      case "propose_adding_expense":
        return "Add Expense Proposal";
      case "propose_updating_budget_limit":
        return "Update Budget Limit Proposal";
      case "propose_itinerary_change":
        return "Itinerary Adjustment Proposal";
      default:
        return action.action_type.replace(/_/g, " ").toUpperCase();
    }
  };

  return (
    <Card className="mt-3 p-4 bg-slate-900/90 border border-slate-800 rounded-2xl">
      {/* Header & Status */}
      <View className="flex-row items-center justify-between mb-2.5">
        <View className="flex-row items-center flex-1 mr-2">
          <View className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700/60 items-center justify-center mr-2.5">
            {getActionIcon()}
          </View>
          <View className="flex-1">
            <Text className="text-white text-sm font-semibold" numberOfLines={1}>
              {action.summary}
            </Text>
            <View className="flex-row items-center mt-0.5 space-x-1.5">
              <Text className="text-slate-400 text-[11px]">
                {getActionTypeLabel()}
              </Text>
              {isPlaceAction && action.payload?.is_verified && (
                <View className="ml-1.5 px-1.5 py-0.2 bg-emerald-500/10 border border-emerald-500/20 rounded flex-row items-center">
                  <ShieldCheck size={9} color="#34d399" />
                  <Text className="text-emerald-400 text-[9px] font-semibold ml-0.5">
                    Verified
                  </Text>
                </View>
              )}
            </View>
          </View>
        </View>

        <View>
          {isPending && (
            <View className="px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20">
              <Text className="text-amber-400 text-[10px] font-bold uppercase">
                Pending
              </Text>
            </View>
          )}
          {isApplied && (
            <View className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex-row items-center">
              <CheckCircle2 size={10} color="#34d399" />
              <Text className="text-emerald-400 text-[10px] font-bold uppercase ml-1">
                Applied
              </Text>
            </View>
          )}
          {isRejected && (
            <View className="px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 flex-row items-center">
              <XCircle size={10} color="#94a3b8" />
              <Text className="text-slate-400 text-[10px] font-bold uppercase ml-1">
                Rejected
              </Text>
            </View>
          )}
        </View>
      </View>

      {/* Description */}
      {action.description ? (
        <Text className="text-slate-300 text-xs mb-3 leading-relaxed">
          {action.description}
        </Text>
      ) : null}

      {/* Payload details preview */}
      {action.payload && (
        <View className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80 mb-3 space-y-1.5">
          {action.payload.day_number && (
            <View className="flex-row items-center justify-between">
              <Text className="text-slate-500 text-[11px]">Itinerary Day</Text>
              <Text className="text-slate-300 text-[11px] font-semibold">
                Day {action.payload.day_number}
              </Text>
            </View>
          )}
          {(action.payload.place_name || action.payload.title || action.payload.item_title) && (
            <View className="flex-row items-center justify-between">
              <Text className="text-slate-500 text-[11px]">Venue / Activity</Text>
              <Text className="text-slate-200 text-[11px] font-semibold flex-1 text-right ml-2" numberOfLines={1}>
                {action.payload.place_name || action.payload.title || action.payload.item_title}
              </Text>
            </View>
          )}
          {action.payload.rating !== undefined && action.payload.rating !== null && (
            <View className="flex-row items-center justify-between">
              <Text className="text-slate-500 text-[11px]">Rating</Text>
              <View className="flex-row items-center">
                <Star size={11} color="#f59e0b" fill="#f59e0b" />
                <Text className="text-amber-400 text-[11px] font-bold ml-1">
                  {action.payload.rating}
                </Text>
              </View>
            </View>
          )}
          {action.payload.formatted_address && (
            <View className="flex-row items-start justify-between">
              <Text className="text-slate-500 text-[11px] mt-0.5">Address</Text>
              <Text className="text-slate-300 text-[11px] flex-1 text-right ml-2" numberOfLines={2}>
                {action.payload.formatted_address}
              </Text>
            </View>
          )}
          {action.payload.amount !== undefined && (
            <View className="flex-row items-center justify-between">
              <Text className="text-slate-500 text-[11px]">Amount</Text>
              <Text className="text-emerald-400 text-[11px] font-bold">
                {action.payload.amount} {action.payload.currency || "USD"}
              </Text>
            </View>
          )}
          {action.payload.new_limit !== undefined && (
            <View className="flex-row items-center justify-between">
              <Text className="text-slate-500 text-[11px]">New Budget Limit</Text>
              <Text className="text-amber-400 text-[11px] font-bold">
                {action.payload.new_limit} {action.payload.currency || "USD"}
              </Text>
            </View>
          )}
          {action.payload.target_budget !== undefined && (
            <View className="flex-row items-center justify-between">
              <Text className="text-slate-500 text-[11px]">Optimized Target</Text>
              <Text className="text-emerald-400 text-[11px] font-bold">
                {action.payload.target_budget} {action.payload.currency || "INR"}
              </Text>
            </View>
          )}
          {action.payload.item_type && (
            <View className="flex-row items-center justify-between">
              <Text className="text-slate-500 text-[11px]">Type</Text>
              <Text className="text-slate-300 text-[11px] capitalize">
                {action.payload.item_type}
              </Text>
            </View>
          )}
          {action.payload.start_time && (
            <View className="flex-row items-center justify-between">
              <Text className="text-slate-500 text-[11px]">Time</Text>
              <Text className="text-slate-300 text-[11px]">
                {action.payload.start_time}{" "}
                {action.payload.end_time ? `– ${action.payload.end_time}` : ""}
              </Text>
            </View>
          )}
          {action.payload.cost && (
            <View className="flex-row items-center justify-between">
              <Text className="text-slate-500 text-[11px]">Est. Cost</Text>
              <Text className="text-emerald-400 text-[11px] font-semibold">
                {action.payload.cost} {action.payload.currency || "USD"}
              </Text>
            </View>
          )}
          {action.payload.rationale && (
            <View className="pt-1.5 border-t border-slate-800/80">
              <Text className="text-slate-400 text-[10px] uppercase font-semibold mb-0.5">Why Travix Recommends This</Text>
              <Text className="text-sky-300 text-[11px] leading-snug">
                {action.payload.rationale}
              </Text>
            </View>
          )}
          {action.payload.travel_time_impact && (
            <View className="flex-row items-center justify-between pt-0.5">
              <Text className="text-slate-500 text-[11px]">Transit Impact</Text>
              <Text className="text-slate-300 text-[11px] font-medium">
                {action.payload.travel_time_impact}
              </Text>
            </View>
          )}
          {action.payload.budget_impact && (
            <View className="flex-row items-center justify-between pt-0.5">
              <Text className="text-slate-500 text-[11px]">Budget Impact</Text>
              <Text className="text-emerald-400 text-[11px] font-medium">
                {action.payload.budget_impact}
              </Text>
            </View>
          )}
        </View>
      )}

      {/* Action Buttons (Pending only) */}
      {isPending && (
        <View className="flex-row space-x-2 pt-1">
          {!isViewer ? (
            <>
              <Button
                label="Save to My Trip"
                variant="primary"
                size="sm"
                className="flex-1 mr-2"
                isLoading={isMutating}
                onPress={() => onConfirm(action.action_id)}
                icon={<CheckCircle2 size={14} color="#ffffff" />}
              />
              <Button
                label="Reject"
                variant="outline"
                size="sm"
                isLoading={isMutating}
                onPress={() => onReject(action.action_id)}
              />
            </>
          ) : (
            <View className="p-2.5 bg-slate-950/40 rounded-xl border border-slate-800 flex-1">
              <Text className="text-slate-400 text-[11px] text-center">
                Viewers have read-only access and cannot modify trip itinerary.
              </Text>
            </View>
          )}
        </View>
      )}
    </Card>
  );
};


