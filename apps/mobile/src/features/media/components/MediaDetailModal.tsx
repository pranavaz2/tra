import React, { useState, useEffect } from "react";
import {
  Modal,
  View,
  Text,
  Image,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import {
  X,
  Edit3,
  Trash2,
  Compass,
  DollarSign,
  Calendar,
  Layers,
  FileText,
  Check,
  Link,
  Shield,
  User,
} from "lucide-react-native";
import { MediaItemResponse } from "@/core/api/types";
import { Button } from "@/shared/components/ui/Button";
import { formatFileSize, getMediaTypeMeta } from "./MediaCard";

interface MediaDetailModalProps {
  visible: boolean;
  item: MediaItemResponse | null;
  onClose: () => void;
  onUpdateCaption: (mediaId: string, caption: string | null) => Promise<any>;
  onDeleteMedia: (mediaId: string) => Promise<any>;
  onOpenAttachActivity?: (item: MediaItemResponse) => void;
  onOpenAttachExpense?: (item: MediaItemResponse) => void;
  canManage?: boolean;
  isMutating?: boolean;
}

export const MediaDetailModal: React.FC<MediaDetailModalProps> = ({
  visible,
  item,
  onClose,
  onUpdateCaption,
  onDeleteMedia,
  onOpenAttachActivity,
  onOpenAttachExpense,
  canManage = false,
  isMutating = false,
}) => {
  const [isEditingCaption, setIsEditingCaption] = useState(false);
  const [captionText, setCaptionText] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (item) {
      setCaptionText(item.caption || "");
      setIsEditingCaption(false);
      setError(null);
    }
  }, [item, visible]);

  if (!item) return null;

  const meta = getMediaTypeMeta(item.media_type);
  const isImage = item.media_type === "photo" || item.mime_type.startsWith("image/");

  const handleSaveCaption = async () => {
    setError(null);
    try {
      await onUpdateCaption(item.media_id, captionText.trim() || null);
      setIsEditingCaption(false);
    } catch (err: any) {
      setError(err?.message || "Failed to update caption.");
    }
  };

  const handleDelete = () => {
    Alert.alert(
      "Delete Media",
      "Are you sure you want to remove this media item from the trip?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              await onDeleteMedia(item.media_id);
              onClose();
            } catch (err: any) {
              setError(err?.message || "Failed to delete media.");
            }
          },
        },
      ]
    );
  };

  return (
    <Modal
      visible={visible}
      animationType="fade"
      transparent={true}
      onRequestClose={onClose}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        className="flex-1 bg-black/85 justify-end"
      >
        <View className="bg-slate-900 border-t border-slate-800 rounded-t-3xl max-h-[90%] flex-1">
          {/* Header */}
          <View className="flex-row items-center justify-between px-6 py-4 border-b border-slate-800">
            <View className="flex-row items-center">
              <View
                className={`flex-row items-center px-2 py-0.5 rounded-full border mr-2 ${meta.style}`}
              >
                {meta.icon}
                <Text className="text-[11px] font-semibold ml-1 capitalize">
                  {meta.label}
                </Text>
              </View>
              <Text className="text-slate-400 text-xs font-mono">
                {item.media_id.slice(0, 8)}...
              </Text>
            </View>

            <TouchableOpacity
              onPress={onClose}
              className="w-8 h-8 rounded-full bg-slate-800 items-center justify-center"
            >
              <X size={18} color="#94a3b8" />
            </TouchableOpacity>
          </View>

          <ScrollView className="flex-1 p-6" showsVerticalScrollIndicator={false}>
            {/* Error Banner */}
            {error && (
              <View className="p-3 bg-rose-950/50 border border-rose-800/50 rounded-xl mb-4">
                <Text className="text-rose-400 text-xs font-medium">{error}</Text>
              </View>
            )}

            {/* Media Image / Preview Display */}
            <View className="w-full h-64 bg-slate-950 rounded-2xl border border-slate-800 overflow-hidden items-center justify-center mb-5">
              {isImage && item.url ? (
                <Image
                  source={{ uri: item.url }}
                  className="w-full h-full"
                  resizeMode="contain"
                />
              ) : (
                <View className="items-center justify-center p-6">
                  <View className="w-16 h-16 rounded-2xl bg-slate-800/80 border border-slate-700 items-center justify-center mb-2">
                    {meta.icon}
                  </View>
                  <Text className="text-white text-sm font-semibold text-center mb-1">
                    {item.file_name || meta.label}
                  </Text>
                  <Text className="text-slate-500 text-xs font-mono">
                    {item.mime_type}
                  </Text>
                </View>
              )}
            </View>

            {/* Caption Section */}
            <View className="bg-slate-950 border border-slate-800 rounded-2xl p-4 mb-5">
              <View className="flex-row items-center justify-between mb-2">
                <Text className="text-slate-400 text-xs font-semibold uppercase">
                  Caption / Description
                </Text>
                {canManage && !isEditingCaption && (
                  <TouchableOpacity
                    onPress={() => setIsEditingCaption(true)}
                    className="flex-row items-center"
                  >
                    <Edit3 size={13} color="#818cf8" />
                    <Text className="text-brand-400 text-xs font-semibold ml-1">
                      Edit
                    </Text>
                  </TouchableOpacity>
                )}
              </View>

              {isEditingCaption ? (
                <View>
                  <TextInput
                    value={captionText}
                    onChangeText={setCaptionText}
                    placeholder="Enter description..."
                    placeholderTextColor="#64748b"
                    maxLength={500}
                    className="bg-slate-900 border border-slate-700 rounded-xl p-3 text-white text-sm mb-3"
                    multiline
                  />
                  <View className="flex-row justify-end space-x-2">
                    <TouchableOpacity
                      onPress={() => {
                        setCaptionText(item.caption || "");
                        setIsEditingCaption(false);
                      }}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 mr-2"
                    >
                      <Text className="text-slate-400 text-xs">Cancel</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      onPress={handleSaveCaption}
                      disabled={isMutating}
                      className="flex-row items-center px-3 py-1.5 rounded-lg bg-brand-600"
                    >
                      <Check size={13} color="#ffffff" />
                      <Text className="text-white text-xs font-semibold ml-1">
                        Save
                      </Text>
                    </TouchableOpacity>
                  </View>
                </View>
              ) : (
                <Text className="text-white text-sm leading-5">
                  {item.caption || (
                    <Text className="text-slate-500 italic">No caption set.</Text>
                  )}
                </Text>
              )}
            </View>

            {/* Linked Attachments Section */}
            <View className="bg-slate-950 border border-slate-800 rounded-2xl p-4 mb-5">
              <Text className="text-slate-400 text-xs font-semibold uppercase mb-3">
                Linked Context
              </Text>

              <View className="space-y-2.5">
                {/* Activity link */}
                <View className="flex-row items-center justify-between py-1.5 border-b border-slate-800/80">
                  <View className="flex-row items-center">
                    <Compass size={15} color="#818cf8" />
                    <Text className="text-slate-300 text-xs ml-2">Itinerary Activity</Text>
                  </View>
                  {item.activity_id ? (
                    <View className="px-2 py-0.5 rounded bg-brand-950 border border-brand-700">
                      <Text className="text-brand-300 text-[11px] font-mono">
                        {item.activity_id.slice(0, 8)}...
                      </Text>
                    </View>
                  ) : canManage && onOpenAttachActivity ? (
                    <TouchableOpacity
                      onPress={() => onOpenAttachActivity(item)}
                      className="flex-row items-center"
                    >
                      <Link size={12} color="#818cf8" />
                      <Text className="text-brand-400 text-xs font-semibold ml-1">
                        Link Activity
                      </Text>
                    </TouchableOpacity>
                  ) : (
                    <Text className="text-slate-500 text-xs">None</Text>
                  )}
                </View>

                {/* Expense link */}
                <View className="flex-row items-center justify-between py-1.5">
                  <View className="flex-row items-center">
                    <DollarSign size={15} color="#34d399" />
                    <Text className="text-slate-300 text-xs ml-2">Budget Expense</Text>
                  </View>
                  {item.expense_id ? (
                    <View className="px-2 py-0.5 rounded bg-emerald-950 border border-emerald-700">
                      <Text className="text-emerald-300 text-[11px] font-mono">
                        {item.expense_id.slice(0, 8)}...
                      </Text>
                    </View>
                  ) : canManage && onOpenAttachExpense ? (
                    <TouchableOpacity
                      onPress={() => onOpenAttachExpense(item)}
                      className="flex-row items-center"
                    >
                      <Link size={12} color="#34d399" />
                      <Text className="text-emerald-400 text-xs font-semibold ml-1">
                        Link Expense
                      </Text>
                    </TouchableOpacity>
                  ) : (
                    <Text className="text-slate-500 text-xs">None</Text>
                  )}
                </View>
              </View>
            </View>

            {/* Metadata Properties */}
            <View className="bg-slate-950 border border-slate-800 rounded-2xl p-4 mb-6 space-y-2.5">
              <Text className="text-slate-400 text-xs font-semibold uppercase mb-2">
                File Properties
              </Text>

              <View className="flex-row items-center justify-between py-1 border-b border-slate-800/60">
                <Text className="text-slate-500 text-xs">File Size</Text>
                <Text className="text-slate-300 text-xs font-medium">
                  {formatFileSize(item.size_bytes)}
                </Text>
              </View>

              <View className="flex-row items-center justify-between py-1 border-b border-slate-800/60">
                <Text className="text-slate-500 text-xs">MIME Type</Text>
                <Text className="text-slate-300 text-xs font-mono">
                  {item.mime_type}
                </Text>
              </View>

              {item.width && item.height && (
                <View className="flex-row items-center justify-between py-1 border-b border-slate-800/60">
                  <Text className="text-slate-500 text-xs">Dimensions</Text>
                  <Text className="text-slate-300 text-xs">
                    {item.width} × {item.height} px
                  </Text>
                </View>
              )}

              <View className="flex-row items-center justify-between py-1 border-b border-slate-800/60">
                <Text className="text-slate-500 text-xs">Uploaded At</Text>
                <Text className="text-slate-300 text-xs">
                  {new Date(item.created_at).toLocaleString()}
                </Text>
              </View>

              <View className="flex-row items-center justify-between py-1">
                <Text className="text-slate-500 text-xs">Uploaded By</Text>
                <Text className="text-slate-300 text-xs font-mono">
                  User {item.uploaded_by.slice(0, 8)}...
                </Text>
              </View>
            </View>

            {/* Delete Action (only if canManage) */}
            {canManage && (
              <TouchableOpacity
                onPress={handleDelete}
                disabled={isMutating}
                className="flex-row items-center justify-center p-3.5 rounded-xl bg-rose-950/40 border border-rose-800/50 mb-8 active:bg-rose-900/40"
              >
                <Trash2 size={16} color="#f43f5e" />
                <Text className="text-rose-400 text-sm font-semibold ml-2">
                  Delete Media Item
                </Text>
              </TouchableOpacity>
            )}
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
};
