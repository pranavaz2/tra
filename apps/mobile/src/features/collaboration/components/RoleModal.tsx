import React, { useState, useEffect } from "react";
import { Modal, View, Text, TouchableOpacity } from "react-native";
import { X, Edit3, Eye, Check } from "lucide-react-native";
import { MemberResponse } from "@/core/api/types";
import { Button } from "@/shared/components/ui/Button";

interface RoleModalProps {
  visible: boolean;
  onClose: () => void;
  member: MemberResponse | null;
  onSubmit: (memberId: string, newRole: "editor" | "viewer") => Promise<void>;
  isSubmitting?: boolean;
}

export const RoleModal: React.FC<RoleModalProps> = ({
  visible,
  onClose,
  member,
  onSubmit,
  isSubmitting = false,
}) => {
  const [role, setRole] = useState<"editor" | "viewer">("editor");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (visible && member) {
      setRole(member.role === "viewer" ? "viewer" : "editor");
      setError(null);
    }
  }, [visible, member]);

  const handleSubmit = async () => {
    if (!member) return;
    setError(null);
    try {
      await onSubmit(member.member_id, role);
    } catch (err: any) {
      setError(err.message || "Failed to change role.");
    }
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={true}
      onRequestClose={onClose}
    >
      <View className="flex-1 justify-end bg-black/60">
        <View className="bg-slate-900 border-t border-slate-800 rounded-t-3xl p-6">
          {/* Header */}
          <View className="flex-row items-center justify-between pb-4 border-b border-slate-800 mb-4">
            <Text className="text-white text-xl font-bold">Change Role</Text>
            <TouchableOpacity
              onPress={onClose}
              className="w-8 h-8 rounded-full bg-slate-800 items-center justify-center"
            >
              <X size={18} color="#94a3b8" />
            </TouchableOpacity>
          </View>

          {error && (
            <View className="p-3 bg-rose-950/50 border border-rose-800/50 rounded-xl mb-4">
              <Text className="text-rose-400 text-xs font-medium">{error}</Text>
            </View>
          )}

          <Text className="text-slate-400 text-xs mb-3">
            Select a new access level for User {member?.user_id.slice(0, 8)}...
          </Text>

          {/* Role Options */}
          <View className="space-y-3 mb-6">
            <TouchableOpacity
              onPress={() => setRole("editor")}
              className={`p-4 rounded-xl border flex-row items-center justify-between mb-2 ${
                role === "editor"
                  ? "bg-sky-950/50 border-sky-500"
                  : "bg-slate-800 border-slate-700"
              }`}
            >
              <View className="flex-row items-center flex-1 mr-2">
                <Edit3
                  size={18}
                  color={role === "editor" ? "#38bdf8" : "#94a3b8"}
                />
                <View className="ml-3">
                  <Text
                    className={`text-sm font-bold ${
                      role === "editor" ? "text-sky-300" : "text-slate-200"
                    }`}
                  >
                    Editor
                  </Text>
                  <Text className="text-slate-400 text-xs mt-0.5">
                    Can manage itinerary items, days, and log expenses.
                  </Text>
                </View>
              </View>
              {role === "editor" && <Check size={18} color="#38bdf8" />}
            </TouchableOpacity>

            <TouchableOpacity
              onPress={() => setRole("viewer")}
              className={`p-4 rounded-xl border flex-row items-center justify-between ${
                role === "viewer"
                  ? "bg-emerald-950/50 border-emerald-500"
                  : "bg-slate-800 border-slate-700"
              }`}
            >
              <View className="flex-row items-center flex-1 mr-2">
                <Eye
                  size={18}
                  color={role === "viewer" ? "#34d399" : "#94a3b8"}
                />
                <View className="ml-3">
                  <Text
                    className={`text-sm font-bold ${
                      role === "viewer" ? "text-emerald-300" : "text-slate-200"
                    }`}
                  >
                    Viewer
                  </Text>
                  <Text className="text-slate-400 text-xs mt-0.5">
                    Read-only access to view plans and budget.
                  </Text>
                </View>
              </View>
              {role === "viewer" && <Check size={18} color="#34d399" />}
            </TouchableOpacity>
          </View>

          {/* Submit */}
          <Button
            label="Save Role"
            onPress={handleSubmit}
            isLoading={isSubmitting}
            className="w-full"
          />
        </View>
      </View>
    </Modal>
  );
};
