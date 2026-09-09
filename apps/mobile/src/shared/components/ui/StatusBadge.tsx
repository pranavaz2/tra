import React from "react";
import { View, Text } from "react-native";
import clsx from "clsx";
import { TripStatus, TripPrivacy } from "@/core/api/types";

interface StatusBadgeProps {
  status: TripStatus | TripPrivacy | string;
  size?: "sm" | "md";
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = "sm",
  className = "",
}) => {
  const getBadgeStyle = () => {
    switch (status) {
      case "active":
        return {
          bg: "bg-emerald-500/10 border-emerald-500/25",
          text: "text-emerald-400",
          dot: "bg-emerald-400",
        };
      case "planned":
        return {
          bg: "bg-brand-500/10 border-brand-500/25",
          text: "text-brand-400",
          dot: "bg-brand-400",
        };
      case "completed":
        return {
          bg: "bg-cyan-500/10 border-cyan-500/25",
          text: "text-cyan-400",
          dot: "bg-cyan-400",
        };
      case "archived":
        return {
          bg: "bg-slate-500/10 border-slate-500/25",
          text: "text-slate-400",
          dot: "bg-slate-400",
        };
      case "draft":
      default:
        return {
          bg: "bg-amber-500/10 border-amber-500/25",
          text: "text-amber-400",
          dot: "bg-amber-400",
        };
    }
  };

  const style = getBadgeStyle();
  const isSmall = size === "sm";

  return (
    <View
      className={clsx(
        "flex-row items-center rounded-full border self-start",
        isSmall ? "px-2.5 py-0.5" : "px-3 py-1",
        style.bg,
        className
      )}
    >
      <View className={clsx("rounded-full mr-1.5", isSmall ? "w-1.5 h-1.5" : "w-2 h-2", style.dot)} />
      <Text
        className={clsx(
          "font-semibold uppercase tracking-wider",
          isSmall ? "text-[10px]" : "text-xs",
          style.text
        )}
      >
        {status}
      </Text>
    </View>
  );
};
