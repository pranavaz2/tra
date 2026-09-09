import React from "react";
import { View, Text, TouchableOpacity, Image } from "react-native";
import {
  Image as ImageIcon,
  Receipt,
  FileText,
  Film,
  Mic,
  Compass,
  DollarSign,
  Trash2,
} from "lucide-react-native";
import { MediaItemResponse, MediaType } from "@/core/api/types";
import { Card } from "@/shared/components/ui/Card";

interface MediaCardProps {
  item: MediaItemResponse;
  onPress: (item: MediaItemResponse) => void;
  onDelete?: (mediaId: string) => void;
  canManage?: boolean;
  isMutating?: boolean;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function getMediaTypeMeta(type: MediaType) {
  switch (type) {
    case "photo":
      return {
        label: "Photo",
        icon: <ImageIcon size={12} color="#38bdf8" />,
        style: "bg-sky-950/60 border-sky-700/60 text-sky-300",
      };
    case "receipt":
      return {
        label: "Receipt",
        icon: <Receipt size={12} color="#34d399" />,
        style: "bg-emerald-950/60 border-emerald-700/60 text-emerald-300",
      };
    case "video":
      return {
        label: "Video",
        icon: <Film size={12} color="#a78bfa" />,
        style: "bg-purple-950/60 border-purple-700/60 text-purple-300",
      };
    case "voice_memo":
      return {
        label: "Voice",
        icon: <Mic size={12} color="#f59e0b" />,
        style: "bg-amber-950/60 border-amber-700/60 text-amber-300",
      };
    case "note":
    default:
      return {
        label: "Doc",
        icon: <FileText size={12} color="#94a3b8" />,
        style: "bg-slate-800 border-slate-700 text-slate-300",
      };
  }
}

export const MediaCard: React.FC<MediaCardProps> = ({
  item,
  onPress,
  onDelete,
  canManage = false,
  isMutating = false,
}) => {
  const meta = getMediaTypeMeta(item.media_type);
  const isImage = item.media_type === "photo" || item.mime_type.startsWith("image/");

  return (
    <TouchableOpacity
      onPress={() => onPress(item)}
      activeOpacity={0.8}
      className="flex-1 m-1.5"
    >
      <Card className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden p-0">
        {/* Preview Container */}
        <View className="h-36 bg-slate-950 items-center justify-center relative overflow-hidden">
          {isImage && item.url ? (
            <Image
              source={{ uri: item.url }}
              className="w-full h-full"
              resizeMode="cover"
            />
          ) : (
            <View className="items-center justify-center p-4">
              <View className="w-12 h-12 rounded-xl bg-slate-800/80 border border-slate-700 items-center justify-center mb-1">
                {meta.icon}
              </View>
              <Text className="text-slate-400 text-[11px] font-medium" numberOfLines={1}>
                {item.file_name || meta.label}
              </Text>
            </View>
          )}

          {/* Type Badge Floating Overlay */}
          <View
            className={`absolute top-2 left-2 flex-row items-center px-2 py-0.5 rounded-full border ${meta.style}`}
          >
            {meta.icon}
            <Text className="text-[10px] font-semibold ml-1 capitalize">
              {meta.label}
            </Text>
          </View>

          {/* Attachment Badges */}
          <View className="absolute bottom-2 left-2 flex-row gap-1">
            {item.activity_id && (
              <View className="flex-row items-center px-1.5 py-0.5 rounded bg-brand-950/80 border border-brand-700/70">
                <Compass size={10} color="#818cf8" />
                <Text className="text-brand-300 text-[9px] font-semibold ml-1">
                  Activity
                </Text>
              </View>
            )}
            {item.expense_id && (
              <View className="flex-row items-center px-1.5 py-0.5 rounded bg-emerald-950/80 border border-emerald-700/70">
                <DollarSign size={10} color="#34d399" />
                <Text className="text-emerald-300 text-[9px] font-semibold ml-1">
                  Expense
                </Text>
              </View>
            )}
          </View>
        </View>

        {/* Info Content */}
        <View className="p-2.5">
          <Text className="text-white text-xs font-semibold" numberOfLines={1}>
            {item.caption || item.file_name || "Untitled Media"}
          </Text>

          <View className="flex-row items-center justify-between mt-1">
            <Text className="text-slate-500 text-[10px]">
              {formatFileSize(item.size_bytes)}
            </Text>
            <Text className="text-slate-500 text-[10px]">
              {new Date(item.created_at).toLocaleDateString()}
            </Text>
          </View>
        </View>
      </Card>
    </TouchableOpacity>
  );
};
