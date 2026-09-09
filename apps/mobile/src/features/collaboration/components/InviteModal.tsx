import React, { useState, useEffect } from "react";
import {
  Modal,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { X, Mail, Edit3, Eye, Check } from "lucide-react-native";
import { Button } from "@/shared/components/ui/Button";

interface InviteModalProps {
  visible: boolean;
  onClose: () => void;
  onSubmit: (email: string, role: "editor" | "viewer") => Promise<void>;
  isSubmitting?: boolean;
}

export const InviteModal: React.FC<InviteModalProps> = ({
  visible,
  onClose,
  onSubmit,
  isSubmitting = false,
}) => {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"editor" | "viewer">("editor");
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (visible) {
      setEmail("");
      setRole("editor");
      setValidationError(null);
    }
  }, [visible]);

  const handleSubmit = async () => {
    setValidationError(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setValidationError("Please enter an email address.");
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmedEmail)) {
      setValidationError("Please enter a valid email address.");
      return;
    }

    try {
      await onSubmit(trimmedEmail, role);
    } catch (err: any) {
      setValidationError(err.message || "Failed to send invitation.");
    }
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={true}
      onRequestClose={onClose}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        className="flex-1 justify-end bg-black/60"
      >
        <View className="bg-slate-900 border-t border-slate-800 rounded-t-3xl p-6">
          {/* Header */}
          <View className="flex-row items-center justify-between pb-4 border-b border-slate-800 mb-4">
            <Text className="text-white text-xl font-bold">Invite Collaborator</Text>
            <TouchableOpacity
              onPress={onClose}
              className="w-8 h-8 rounded-full bg-slate-800 items-center justify-center"
            >
              <X size={18} color="#94a3b8" />
            </TouchableOpacity>
          </View>

          {validationError && (
            <View className="p-3 bg-rose-950/50 border border-rose-800/50 rounded-xl mb-4">
              <Text className="text-rose-400 text-xs font-medium">
                {validationError}
              </Text>
            </View>
          )}

          {/* Email Input */}
          <View className="mb-5">
            <Text className="text-slate-300 text-xs font-semibold uppercase mb-1.5">
              Invitee Email *
            </Text>
            <View className="flex-row items-center bg-slate-800 border border-slate-700 rounded-xl px-3 py-1">
              <Mail size={18} color="#94a3b8" />
              <TextInput
                value={email}
                onChangeText={setEmail}
                placeholder="colleague@example.com"
                placeholderTextColor="#64748b"
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
                className="flex-1 ml-2 py-3 text-white text-sm"
              />
            </View>
          </View>

          {/* Role Selection */}
          <View className="mb-6">
            <Text className="text-slate-300 text-xs font-semibold uppercase mb-2">
              Collaborator Role *
            </Text>
            <View className="flex-row gap-3">
              {/* Editor option */}
              <TouchableOpacity
                onPress={() => setRole("editor")}
                className={`flex-1 p-3.5 rounded-xl border ${
                  role === "editor"
                    ? "bg-sky-950/50 border-sky-500"
                    : "bg-slate-800 border-slate-700"
                }`}
              >
                <View className="flex-row items-center justify-between mb-1">
                  <View className="flex-row items-center">
                    <Edit3
                      size={16}
                      color={role === "editor" ? "#38bdf8" : "#94a3b8"}
                    />
                    <Text
                      className={`text-sm font-bold ml-2 ${
                        role === "editor" ? "text-sky-300" : "text-slate-200"
                      }`}
                    >
                      Editor
                    </Text>
                  </View>
                  {role === "editor" && <Check size={14} color="#38bdf8" />}
                </View>
                <Text className="text-slate-400 text-[11px]">
                  Can add and edit itinerary days, items, and expenses.
                </Text>
              </TouchableOpacity>

              {/* Viewer option */}
              <TouchableOpacity
                onPress={() => setRole("viewer")}
                className={`flex-1 p-3.5 rounded-xl border ${
                  role === "viewer"
                    ? "bg-emerald-950/50 border-emerald-500"
                    : "bg-slate-800 border-slate-700"
                }`}
              >
                <View className="flex-row items-center justify-between mb-1">
                  <View className="flex-row items-center">
                    <Eye
                      size={16}
                      color={role === "viewer" ? "#34d399" : "#94a3b8"}
                    />
                    <Text
                      className={`text-sm font-bold ml-2 ${
                        role === "viewer" ? "text-emerald-300" : "text-slate-200"
                      }`}
                    >
                      Viewer
                    </Text>
                  </View>
                  {role === "viewer" && <Check size={14} color="#34d399" />}
                </View>
                <Text className="text-slate-400 text-[11px]">
                  Read-only view of trip plans, schedule, and budget.
                </Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Submit */}
          <Button
            label="Send Invitation"
            onPress={handleSubmit}
            isLoading={isSubmitting}
            className="w-full"
          />
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
};
