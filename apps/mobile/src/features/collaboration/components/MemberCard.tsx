import React from "react";
import { View, Text, TouchableOpacity, Alert } from "react-native";
import { Crown, Edit3, Eye, Shield, Trash2, User } from "lucide-react-native";
import { MemberResponse, MemberRole } from "@/core/api/types";
import { Card } from "@/shared/components/ui/Card";

interface MemberCardProps {
  member: MemberResponse;
  isCurrentUser: boolean;
  canManage: boolean;
  onChangeRole: (member: MemberResponse) => void;
  onRemove: (memberId: string) => void;
  isMutating?: boolean;
}

const getRoleBadge = (role: MemberRole) => {
  switch (role) {
    case "owner":
      return {
        label: "Owner",
        icon: <Crown size={12} color="#818cf8" />,
        style: "bg-brand-950/60 border-brand-700/60 text-brand-300",
      };
    case "editor":
      return {
        label: "Editor",
        icon: <Edit3 size={12} color="#38bdf8" />,
        style: "bg-sky-950/60 border-sky-700/60 text-sky-300",
      };
    case "viewer":
    default:
      return {
        label: "Viewer",
        icon: <Eye size={12} color="#34d399" />,
        style: "bg-emerald-950/60 border-emerald-700/60 text-emerald-300",
      };
  }
};

export const MemberCard: React.FC<MemberCardProps> = ({
  member,
  isCurrentUser,
  canManage,
  onChangeRole,
  onRemove,
  isMutating = false,
}) => {
  const badge = getRoleBadge(member.role);
  const isOwner = member.role === "owner";

  const handleRemove = () => {
    Alert.alert(
      "Remove Collaborator",
      "Are you sure you want to remove this member from the trip?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Remove",
          style: "destructive",
          onPress: () => onRemove(member.member_id),
        },
      ]
    );
  };

  return (
    <Card className="p-4 bg-slate-900 border border-slate-800 mb-3">
      <View className="flex-row items-center justify-between">
        {/* Left: Avatar & ID */}
        <View className="flex-row items-center flex-1 mr-3">
          <View className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 items-center justify-center mr-3">
            {isOwner ? (
              <Crown size={18} color="#818cf8" />
            ) : (
              <User size={18} color="#94a3b8" />
            )}
          </View>

          <View className="flex-1">
            <View className="flex-row items-center flex-wrap gap-1.5">
              <Text className="text-white font-semibold text-sm" numberOfLines={1}>
                User {member.user_id.slice(0, 8)}...
              </Text>
              {isCurrentUser && (
                <View className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700">
                  <Text className="text-slate-400 text-[10px] font-semibold">
                    You
                  </Text>
                </View>
              )}
            </View>

            <View className="flex-row items-center mt-1">
              <View
                className={`flex-row items-center px-2 py-0.5 rounded-full border mr-2 ${badge.style}`}
              >
                {badge.icon}
                <Text className="text-[11px] font-medium ml-1 capitalize">
                  {badge.label}
                </Text>
              </View>

              <Text className="text-slate-500 text-xs">
                Joined {new Date(member.joined_at).toLocaleDateString()}
              </Text>
            </View>
          </View>
        </View>

        {/* Right: Actions (only if caller is owner and target is not owner) */}
        {canManage && !isOwner && (
          <View className="flex-row items-center gap-2">
            <TouchableOpacity
              onPress={() => onChangeRole(member)}
              disabled={isMutating}
              className="p-2 rounded-lg bg-slate-800 border border-slate-700 active:bg-slate-700"
              accessibilityLabel="Change role"
            >
              <Shield size={14} color="#94a3b8" />
            </TouchableOpacity>

            <TouchableOpacity
              onPress={handleRemove}
              disabled={isMutating}
              className="p-2 rounded-lg bg-rose-950/40 border border-rose-800/40 active:bg-rose-900/40"
              accessibilityLabel="Remove member"
            >
              <Trash2 size={14} color="#f43f5e" />
            </TouchableOpacity>
          </View>
        )}
      </View>
    </Card>
  );
};
