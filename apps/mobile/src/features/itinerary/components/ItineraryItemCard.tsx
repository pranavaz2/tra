import React from "react";
import { View, Text, TouchableOpacity, Alert } from "react-native";
import {
  Compass,
  Car,
  Bed,
  Utensils,
  Clock,
  DollarSign,
  Edit2,
  Trash2,
} from "lucide-react-native";
import { ItineraryItemResponse, ItineraryItemType } from "@/core/api/types";
import { Card } from "@/shared/components/ui/Card";
import clsx from "clsx";

interface ItineraryItemCardProps {
  item: ItineraryItemResponse;
  onEdit: (item: ItineraryItemResponse) => void;
  onDelete: (itemId: string) => void;
  isMutating?: boolean;
  canEdit?: boolean;
}

export const getItemTypeMeta = (type: ItineraryItemType) => {
  switch (type) {
    case "transport":
      return {
        label: "Transport",
        icon: Car,
        bg: "bg-sky-500/10 border-sky-500/20 text-sky-400",
        color: "#38bdf8",
      };
    case "lodging":
      return {
        label: "Lodging",
        icon: Bed,
        bg: "bg-purple-500/10 border-purple-500/20 text-purple-400",
        color: "#c084fc",
      };
    case "restaurant":
      return {
        label: "Restaurant",
        icon: Utensils,
        bg: "bg-amber-500/10 border-amber-500/20 text-amber-400",
        color: "#fbbf24",
      };
    case "activity":
    default:
      return {
        label: "Activity",
        icon: Compass,
        bg: "bg-brand-500/10 border-brand-500/20 text-brand-400",
        color: "#818cf8",
      };
  }
};

export const ItineraryItemCard: React.FC<ItineraryItemCardProps> = ({
  item,
  onEdit,
  onDelete,
  isMutating = false,
  canEdit = true,
}) => {
  const meta = getItemTypeMeta(item.item_type);
  const IconComponent = meta.icon;

  const handleDelete = () => {
    Alert.alert(
      "Delete Activity",
      `Are you sure you want to remove "${item.title}"?`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => onDelete(item.item_id),
        },
      ]
    );
  };

  const formatTime = (timeStr?: string | null) => {
    if (!timeStr) return null;
    return timeStr.slice(0, 5);
  };

  const startFormatted = formatTime(item.start_time);
  const endFormatted = formatTime(item.end_time);
  const timeRange = startFormatted
    ? endFormatted
      ? `${startFormatted} - ${endFormatted}`
      : startFormatted
    : null;

  return (
    <Card className="p-4 bg-slate-900 border border-slate-800/80 mb-3">
      {/* Top row: Type Badge & Action Buttons */}
      <View className="flex-row items-center justify-between mb-2.5">
        <View
          className={clsx(
            "flex-row items-center px-2.5 py-1 rounded-full border",
            meta.bg
          )}
        >
          <IconComponent size={13} color={meta.color} />
          <Text className="text-[11px] font-semibold uppercase tracking-wider ml-1.5" style={{ color: meta.color }}>
            {meta.label}
          </Text>
        </View>

        {canEdit && (
          <View className="flex-row items-center space-x-2">
            <TouchableOpacity
              onPress={() => onEdit(item)}
              disabled={isMutating}
              className="w-7 h-7 rounded-lg bg-slate-800 items-center justify-center mr-1 active:bg-slate-700"
            >
              <Edit2 size={13} color="#94a3b8" />
            </TouchableOpacity>
            <TouchableOpacity
              onPress={handleDelete}
              disabled={isMutating}
              className="w-7 h-7 rounded-lg bg-rose-950/40 border border-rose-800/40 items-center justify-center active:bg-rose-900/40"
            >
              <Trash2 size={13} color="#f43f5e" />
            </TouchableOpacity>
          </View>
        )}
      </View>

      {/* Item Title */}
      <Text className="text-white text-base font-bold mb-1.5">{item.title}</Text>

      {/* Description / Notes */}
      {item.description ? (
        <Text className="text-slate-400 text-xs leading-relaxed mb-3">
          {item.description}
        </Text>
      ) : null}

      {/* Details Bar: Time & Cost */}
      <View className="flex-row items-center justify-between pt-2 border-t border-slate-800/60">
        {timeRange ? (
          <View className="flex-row items-center">
            <Clock size={13} color="#94a3b8" />
            <Text className="text-slate-300 text-xs font-medium ml-1.5">{timeRange}</Text>
          </View>
        ) : (
          <View />
        )}

        {item.cost !== null && item.cost !== undefined ? (
          <View className="flex-row items-center">
            <DollarSign size={13} color="#34d399" />
            <Text className="text-emerald-400 text-xs font-semibold ml-0.5">
              {Number(item.cost).toFixed(2)} {item.currency || ""}
            </Text>
          </View>
        ) : null}
      </View>
    </Card>
  );
};
