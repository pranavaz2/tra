import React from "react";
import { View, Text, TouchableOpacity, Alert } from "react-native";
import { Mail, Clock, XCircle } from "lucide-react-native";
import { InvitationResponse } from "@/core/api/types";
import { Card } from "@/shared/components/ui/Card";

interface InvitationCardProps {
  invitation: InvitationResponse;
  onRevoke: (invitationId: string) => void;
  isMutating?: boolean;
}

export const InvitationCard: React.FC<InvitationCardProps> = ({
  invitation,
  onRevoke,
  isMutating = false,
}) => {
  const isPending = invitation.status === "pending";

  const handleRevoke = () => {
    Alert.alert(
      "Revoke Invitation",
      `Revoke pending invitation for ${invitation.invitee_email}?`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Revoke",
          style: "destructive",
          onPress: () => onRevoke(invitation.invitation_id),
        },
      ]
    );
  };

  return (
    <Card className="p-4 bg-slate-900 border border-slate-800 mb-3">
      <View className="flex-row items-center justify-between">
        {/* Left: Icon & email */}
        <View className="flex-row items-center flex-1 mr-3">
          <View className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 items-center justify-center mr-3">
            <Mail size={18} color="#a78bfa" />
          </View>

          <View className="flex-1">
            <Text className="text-white font-semibold text-sm" numberOfLines={1}>
              {invitation.invitee_email}
            </Text>

            <View className="flex-row items-center mt-1 flex-wrap gap-1.5">
              <View className="px-2 py-0.5 rounded-full border bg-slate-800 border-slate-700">
                <Text className="text-slate-300 text-[11px] font-medium capitalize">
                  {invitation.role}
                </Text>
              </View>

              <View
                className={`px-2 py-0.5 rounded-full border ${
                  isPending
                    ? "bg-amber-950/50 border-amber-800/50 text-amber-400"
                    : "bg-slate-800 border-slate-700 text-slate-400"
                }`}
              >
                <Text
                  className={`text-[11px] font-medium capitalize ${
                    isPending ? "text-amber-400" : "text-slate-400"
                  }`}
                >
                  {invitation.status}
                </Text>
              </View>

              <View className="flex-row items-center ml-1">
                <Clock size={11} color="#64748b" />
                <Text className="text-slate-500 text-xs ml-1">
                  Expires {new Date(invitation.expires_at).toLocaleDateString()}
                </Text>
              </View>
            </View>
          </View>
        </View>

        {/* Right: Revoke button */}
        {isPending && (
          <TouchableOpacity
            onPress={handleRevoke}
            disabled={isMutating}
            className="flex-row items-center px-2.5 py-1.5 rounded-lg bg-rose-950/40 border border-rose-800/40 active:bg-rose-900/40"
            accessibilityLabel="Revoke invitation"
          >
            <XCircle size={13} color="#f43f5e" />
            <Text className="text-rose-400 text-xs font-semibold ml-1">Revoke</Text>
          </TouchableOpacity>
        )}
      </View>
    </Card>
  );
};
