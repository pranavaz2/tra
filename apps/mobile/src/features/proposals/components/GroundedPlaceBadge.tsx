import React from "react";
import { View, Text } from "react-native";
import { CheckCircle2, AlertCircle, MapPin, Star } from "lucide-react-native";
import clsx from "clsx";

interface GroundedPlaceBadgeProps {
  isVerified: boolean;
  placeName?: string | null;
  formattedAddress?: string | null;
  rating?: number | null;
  className?: string;
}

export const GroundedPlaceBadge: React.FC<GroundedPlaceBadgeProps> = ({
  isVerified,
  placeName,
  formattedAddress,
  rating,
  className = "",
}) => {
  return (
    <View
      className={clsx(
        "rounded-xl p-3 border",
        isVerified
          ? "bg-emerald-950/20 border-emerald-500/30"
          : "bg-amber-950/20 border-amber-500/30",
        className
      )}
    >
      {/* Verification Header */}
      <View className="flex-row items-center justify-between mb-1.5">
        <View className="flex-row items-center">
          {isVerified ? (
            <CheckCircle2 size={13} color="#34d399" />
          ) : (
            <AlertCircle size={13} color="#fbbf24" />
          )}
          <Text
            className={clsx(
              "text-[11px] font-bold uppercase tracking-wider ml-1.5",
              isVerified ? "text-emerald-400" : "text-amber-400"
            )}
          >
            {isVerified ? "Grounded Real Place" : "Unverified Concept"}
          </Text>
        </View>

        {rating !== null && rating !== undefined && (
          <View className="flex-row items-center bg-slate-900/80 px-2 py-0.5 rounded-md border border-slate-800">
            <Star size={11} color="#facc15" fill="#facc15" />
            <Text className="text-white text-xs font-semibold ml-1">
              {rating.toFixed(1)}
            </Text>
          </View>
        )}
      </View>

      {/* Verified Place Name */}
      {placeName ? (
        <Text className="text-white text-xs font-semibold mb-1">
          {placeName}
        </Text>
      ) : null}

      {/* Address */}
      {formattedAddress ? (
        <View className="flex-row items-start mt-0.5">
          <MapPin size={12} color="#94a3b8" className="mt-0.5 mr-1" />
          <Text className="text-slate-400 text-[11px] flex-1 leading-tight ml-1">
            {formattedAddress}
          </Text>
        </View>
      ) : null}
    </View>
  );
};
