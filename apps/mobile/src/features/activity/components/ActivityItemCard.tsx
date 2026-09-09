/**
 * ActivityItemCard Component.
 *
 * Renders an audit log/timeline item in the activity feed.
 */

import React from "react";
import { View, Text } from "react-native";
import {
  Calendar,
  Clock,
  DollarSign,
  Users,
  Compass,
  Sparkles,
  Edit3,
  Plus,
  Trash2,
  Share2,
} from "lucide-react-native";
import { ActivityLogItem } from "../api/activity-api";
import { Card } from "@/shared/components/ui/Card";

interface ActivityItemCardProps {
  item: ActivityLogItem;
}

function formatRelativeTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - d.getTime()) / 1000);

    if (diffSec < 60) return "Just now";
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`;

    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export const ActivityItemCard: React.FC<ActivityItemCardProps> = ({ item }) => {
  const getActivityIcon = () => {
    switch (item.action) {
      case "day_added":
      case "day_updated":
      case "day_removed":
      case "item_added":
      case "item_updated":
      case "item_removed":
        return <Calendar size={16} color="#818cf8" />;

      case "budget_created":
      case "budget_limit_updated":
      case "expense_added":
      case "expense_updated":
      case "expense_deleted":
        return <DollarSign size={16} color="#10b981" />;

      case "member_invited":
      case "member_joined":
      case "member_removed":
      case "role_changed":
        return <Users size={16} color="#f59e0b" />;

      case "proposal_accepted":
        return <Sparkles size={16} color="#a855f7" />;

      default:
        return <Compass size={16} color="#38bdf8" />;
    }
  };

  const timeStr = formatRelativeTime(item.created_at);

  return (
    <Card className="p-4 bg-slate-900/80 border border-slate-800 mb-3">
      <View className="flex-row items-start justify-between">
        <View className="flex-row items-center flex-1">
          <View className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 items-center justify-center mr-3">
            {getActivityIcon()}
          </View>
          <View className="flex-1">
            <Text className="text-white text-sm font-semibold" numberOfLines={1}>
              {item.title}
            </Text>
            <Text className="text-slate-400 text-xs mt-0.5">
              by <Text className="text-indigo-400 font-medium">{item.actor_name || "Collaborator"}</Text>
            </Text>
          </View>
        </View>

        <View className="flex-row items-center ml-2">
          <Clock size={12} color="#64748b" />
          <Text className="text-slate-500 text-[11px] ml-1">{timeStr}</Text>
        </View>
      </View>

      {item.description ? (
        <Text className="text-slate-300 text-xs mt-2 pl-11" numberOfLines={3}>
          {item.description}
        </Text>
      ) : null}
    </Card>
  );
};
