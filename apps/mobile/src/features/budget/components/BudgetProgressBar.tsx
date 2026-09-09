import React from "react";
import { View, Text } from "react-native";
import clsx from "clsx";

interface BudgetProgressBarProps {
  spentPercentage: number;
  totalSpent: number;
  limit: number;
  currency: string;
}

export const BudgetProgressBar: React.FC<BudgetProgressBarProps> = ({
  spentPercentage,
  totalSpent,
  limit,
  currency,
}) => {
  const clampedPercent = Math.min(Math.max(spentPercentage, 0), 100);

  const getBarColor = () => {
    if (spentPercentage >= 90) return "bg-rose-500";
    if (spentPercentage >= 75) return "bg-amber-500";
    if (spentPercentage >= 50) return "bg-sky-500";
    return "bg-emerald-500";
  };

  const getTextColor = () => {
    if (spentPercentage >= 90) return "text-rose-400";
    if (spentPercentage >= 75) return "text-amber-400";
    if (spentPercentage >= 50) return "text-sky-400";
    return "text-emerald-400";
  };

  return (
    <View className="w-full">
      {/* Progress Track */}
      <View className="h-2.5 w-full bg-slate-800 rounded-full overflow-hidden mb-2">
        <View
          className={clsx("h-full rounded-full transition-all", getBarColor())}
          style={{ width: `${clampedPercent}%` }}
        />
      </View>

      {/* Percentage label & status */}
      <View className="flex-row items-center justify-between">
        <Text className={clsx("text-xs font-bold", getTextColor())}>
          {spentPercentage.toFixed(1)}% Spent
        </Text>
        <Text className="text-slate-400 text-xs">
          {Number(totalSpent).toFixed(2)} / {Number(limit).toFixed(2)} {currency}
        </Text>
      </View>
    </View>
  );
};
