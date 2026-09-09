import React, { useState, useMemo } from "react";
import { View, Text, TouchableOpacity, FlatList } from "react-native";
import { Image as ImageIcon, Receipt, FileText, Layers } from "lucide-react-native";
import { MediaItemResponse } from "@/core/api/types";
import { MediaCard } from "./MediaCard";
import { Card } from "@/shared/components/ui/Card";

interface MediaGridProps {
  mediaItems: MediaItemResponse[];
  onSelectMedia: (item: MediaItemResponse) => void;
  onDeleteMedia?: (mediaId: string) => void;
  canManage?: boolean;
  isMutating?: boolean;
  onOpenUpload?: () => void;
}

type TabType = "all" | "photos" | "receipts" | "docs";

export const MediaGrid: React.FC<MediaGridProps> = ({
  mediaItems,
  onSelectMedia,
  onDeleteMedia,
  canManage = false,
  isMutating = false,
  onOpenUpload,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>("all");

  const filteredItems = useMemo(() => {
    switch (activeTab) {
      case "photos":
        return mediaItems.filter(
          (m) => m.media_type === "photo" || m.mime_type.startsWith("image/")
        );
      case "receipts":
        return mediaItems.filter((m) => m.media_type === "receipt");
      case "docs":
        return mediaItems.filter(
          (m) =>
            m.media_type === "note" ||
            m.media_type === "video" ||
            m.media_type === "voice_memo"
        );
      case "all":
      default:
        return mediaItems;
    }
  }, [mediaItems, activeTab]);

  const tabs: { id: TabType; label: string; count: number; icon: any }[] = [
    {
      id: "all",
      label: "All",
      count: mediaItems.length,
      icon: Layers,
    },
    {
      id: "photos",
      label: "Photos",
      count: mediaItems.filter((m) => m.media_type === "photo" || m.mime_type.startsWith("image/")).length,
      icon: ImageIcon,
    },
    {
      id: "receipts",
      label: "Receipts",
      count: mediaItems.filter((m) => m.media_type === "receipt").length,
      icon: Receipt,
    },
    {
      id: "docs",
      label: "Docs",
      count: mediaItems.filter((m) => m.media_type === "note" || m.media_type === "video" || m.media_type === "voice_memo").length,
      icon: FileText,
    },
  ];

  return (
    <View className="flex-1">
      {/* Category Tabs */}
      <View className="flex-row items-center space-x-2 mb-4">
        {tabs.map((tab) => {
          const isSelected = activeTab === tab.id;
          const IconComponent = tab.icon;
          return (
            <TouchableOpacity
              key={tab.id}
              onPress={() => setActiveTab(tab.id)}
              className={`flex-row items-center px-3 py-1.5 rounded-full border mr-2 ${
                isSelected
                  ? "bg-brand-600 border-brand-500"
                  : "bg-slate-900 border-slate-800"
              }`}
            >
              <IconComponent
                size={13}
                color={isSelected ? "#ffffff" : "#94a3b8"}
              />
              <Text
                className={`text-xs font-semibold ml-1.5 ${
                  isSelected ? "text-white" : "text-slate-400"
                }`}
              >
                {tab.label}
              </Text>
              <View
                className={`ml-1.5 px-1.5 py-0.2 rounded-full ${
                  isSelected ? "bg-brand-700" : "bg-slate-800"
                }`}
              >
                <Text
                  className={`text-[10px] font-bold ${
                    isSelected ? "text-brand-100" : "text-slate-400"
                  }`}
                >
                  {tab.count}
                </Text>
              </View>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Grid Content */}
      {filteredItems.length === 0 ? (
        <Card className="p-8 bg-slate-900/60 border border-dashed border-slate-800 items-center justify-center my-4">
          <Text className="text-slate-400 text-sm font-medium mb-1">
            No media found in {tabs.find((t) => t.id === activeTab)?.label}
          </Text>
          <Text className="text-slate-500 text-xs text-center">
            {activeTab === "all"
              ? "Upload photos, receipts, or notes to attach them to your trip."
              : `No items categorized under ${activeTab}.`}
          </Text>
        </Card>
      ) : (
        <View className="flex-row flex-wrap -mx-1.5">
          {filteredItems.map((item) => (
            <View key={item.media_id} className="w-1/2">
              <MediaCard
                item={item}
                onPress={onSelectMedia}
                onDelete={onDeleteMedia}
                canManage={canManage}
                isMutating={isMutating}
              />
            </View>
          ))}
        </View>
      )}
    </View>
  );
};
