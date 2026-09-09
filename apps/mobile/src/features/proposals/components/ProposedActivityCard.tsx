import React from "react";
import { View, Text } from "react-native";
import { Clock, DollarSign, Tag } from "lucide-react-native";
import { ProposedActivityResponse } from "@/core/api/types";
import { Card } from "@/shared/components/ui/Card";
import { GroundedPlaceBadge } from "./GroundedPlaceBadge";

interface ProposedActivityCardProps {
  activity: ProposedActivityResponse;
}

export const ProposedActivityCard: React.FC<ProposedActivityCardProps> = ({
  activity,
}) => {
  return (
    <Card className="p-4 bg-slate-900/90 border border-slate-800 mb-3">
      {/* Category & Meta Header */}
      <View className="flex-row items-center justify-between mb-2">
        <View className="flex-row items-center bg-brand-600/10 border border-brand-500/20 px-2.5 py-0.5 rounded-full">
          <Tag size={11} color="#818cf8" />
          <Text className="text-brand-400 text-[10px] font-semibold uppercase tracking-wider ml-1.5">
            {activity.category}
          </Text>
        </View>

        <View className="flex-row items-center space-x-3">
          {activity.duration_minutes > 0 && (
            <View className="flex-row items-center mr-2">
              <Clock size={12} color="#94a3b8" />
              <Text className="text-slate-400 text-xs ml-1">
                {activity.duration_minutes >= 60
                  ? `${Math.floor(activity.duration_minutes / 60)}h ${
                      activity.duration_minutes % 60 > 0
                        ? `${activity.duration_minutes % 60}m`
                        : ""
                    }`
                  : `${activity.duration_minutes}m`}
              </Text>
            </View>
          )}

          {activity.estimated_cost && (
            <View className="flex-row items-center">
              <DollarSign size={12} color="#34d399" />
              <Text className="text-emerald-400 text-xs font-semibold">
                {activity.estimated_cost}
              </Text>
            </View>
          )}
        </View>
      </View>

      {/* Activity Title */}
      <Text className="text-white text-base font-bold mb-1.5">
        {activity.title}
      </Text>

      {/* Description */}
      {activity.description ? (
        <Text className="text-slate-400 text-xs leading-relaxed mb-3">
          {activity.description}
        </Text>
      ) : null}

      {/* Grounded Place Card */}
      <GroundedPlaceBadge
        isVerified={activity.is_verified}
        placeName={activity.place_name}
        formattedAddress={activity.formatted_address}
        rating={activity.rating}
      />
    </Card>
  );
};
