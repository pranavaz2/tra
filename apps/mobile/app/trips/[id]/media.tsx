import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  ArrowLeft,
  Upload,
  Image as ImageIcon,
  HardDrive,
  Layers,
  Plus,
  Compass,
} from "lucide-react-native";
import { useTrip } from "@/features/trips/hooks/use-trips";
import { useMedia } from "@/features/media/hooks/use-media";
import { MediaGrid } from "@/features/media/components/MediaGrid";
import { MediaUploadModal } from "@/features/media/components/MediaUploadModal";
import { MediaDetailModal } from "@/features/media/components/MediaDetailModal";
import { AttachMediaModal } from "@/features/media/components/AttachMediaModal";
import { Card } from "@/shared/components/ui/Card";
import { Button } from "@/shared/components/ui/Button";
import { ErrorMessage } from "@/shared/components/feedback/ErrorMessage";
import { LoadingScreen } from "@/shared/components/feedback/LoadingScreen";
import { MediaItemResponse } from "@/core/api/types";
import { formatFileSize } from "@/features/media/components/MediaCard";

export default function TripMediaScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { trip } = useTrip(id);

  const {
    mediaItems,
    photos,
    receipts,
    documents,
    totalCount,
    isLoading,
    isLoadingMore,
    isMutating,
    error,
    hasMore,
    isViewer,
    canManageMedia,
    refresh,
    loadMore,
    uploadMedia,
    updateCaption,
    deleteMedia,
    attachToActivity,
    attachToExpense,
  } = useMedia(id, trip?.owner_id);

  const [refreshing, setRefreshing] = useState(false);
  const [isUploadModalVisible, setIsUploadModalVisible] = useState(false);
  const [selectedMediaDetail, setSelectedMediaDetail] =
    useState<MediaItemResponse | null>(null);

  // Attachment modal state
  const [attachModalVisible, setAttachModalVisible] = useState(false);
  const [attachMode, setAttachMode] = useState<"activity" | "expense">("activity");
  const [targetItemForAttach, setTargetItemForAttach] =
    useState<MediaItemResponse | null>(null);

  const [actionError, setActionError] = useState<string | null>(null);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      await refresh();
    } finally {
      setRefreshing(false);
    }
  };

  const totalBytes = mediaItems.reduce((acc, item) => acc + item.size_bytes, 0);

  const handleOpenAttachActivity = (item: MediaItemResponse) => {
    setTargetItemForAttach(item);
    setAttachMode("activity");
    setSelectedMediaDetail(null);
    setAttachModalVisible(true);
  };

  const handleOpenAttachExpense = (item: MediaItemResponse) => {
    setTargetItemForAttach(item);
    setAttachMode("expense");
    setSelectedMediaDetail(null);
    setAttachModalVisible(true);
  };

  if (isLoading && !refreshing) {
    return <LoadingScreen message="Loading media collection..." />;
  }

  return (
    <SafeAreaView className="flex-1 bg-slate-950" edges={["top", "bottom"]}>
      {/* Header */}
      <View className="flex-row items-center justify-between px-5 py-3 border-b border-slate-800/80 bg-slate-950">
        <TouchableOpacity
          onPress={() => router.back()}
          className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 items-center justify-center active:bg-slate-800"
          accessibilityLabel="Back to Trip"
        >
          <ArrowLeft size={18} color="#ffffff" />
        </TouchableOpacity>

        <View className="items-center">
          <Text className="text-white text-base font-bold">Media & Files</Text>
          <Text className="text-slate-400 text-[11px]" numberOfLines={1}>
            {trip?.title || "Trip Attachments"}
          </Text>
        </View>

        {canManageMedia ? (
          <TouchableOpacity
            onPress={() => {
              setActionError(null);
              setIsUploadModalVisible(true);
            }}
            className="w-10 h-10 rounded-full bg-brand-600 border border-brand-500 items-center justify-center active:bg-brand-700"
            accessibilityLabel="Add Media"
          >
            <Plus size={20} color="#ffffff" />
          </TouchableOpacity>
        ) : (
          <View className="w-10" />
        )}
      </View>

      <ScrollView
        className="flex-1"
        contentContainerStyle={{ padding: 20 }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#6366f1"
            colors={["#6366f1"]}
          />
        }
      >
        {/* Error Banners */}
        {error && <ErrorMessage message={error} className="mb-4" />}
        {actionError && <ErrorMessage message={actionError} className="mb-4" />}

        {/* Media Overview Banner */}
        <Card className="p-4 bg-slate-900 border border-slate-800 mb-5">
          <View className="flex-row items-center justify-between">
            <View className="flex-1 border-r border-slate-800 pr-3">
              <Text className="text-slate-400 text-[10px] uppercase font-semibold">
                Total Files
              </Text>
              <Text className="text-white text-lg font-bold mt-0.5">
                {totalCount}
              </Text>
            </View>

            <View className="flex-1 border-r border-slate-800 px-3">
              <Text className="text-slate-400 text-[10px] uppercase font-semibold">
                Photos
              </Text>
              <Text className="text-sky-400 text-lg font-bold mt-0.5">
                {photos.length}
              </Text>
            </View>

            <View className="flex-1 border-r border-slate-800 px-3">
              <Text className="text-slate-400 text-[10px] uppercase font-semibold">
                Receipts
              </Text>
              <Text className="text-emerald-400 text-lg font-bold mt-0.5">
                {receipts.length}
              </Text>
            </View>

            <View className="flex-1 pl-3">
              <Text className="text-slate-400 text-[10px] uppercase font-semibold">
                Storage
              </Text>
              <Text className="text-slate-300 text-sm font-bold mt-1" numberOfLines={1}>
                {formatFileSize(totalBytes)}
              </Text>
            </View>
          </View>
        </Card>

        {/* Viewer Read-Only Notice */}
        {isViewer && (
          <View className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl mb-4">
            <Text className="text-slate-400 text-xs text-center">
              Viewing media in read-only mode. Only trip editors and owners can upload or delete media.
            </Text>
          </View>
        )}

        {/* Media Gallery Grid */}
        {totalCount === 0 && !isLoading ? (
          <Card className="p-8 bg-slate-900/80 border border-slate-800 items-center text-center mt-4">
            <View className="w-16 h-16 rounded-2xl bg-brand-500/10 border border-brand-500/20 items-center justify-center mb-4">
              <ImageIcon size={32} color="#818cf8" />
            </View>
            <Text className="text-white text-xl font-bold mb-2">
              No Media Uploaded
            </Text>
            <Text className="text-slate-400 text-sm text-center mb-6 leading-5">
              Keep travel photos, booking confirmations, boarding passes, and receipts all in one place.
            </Text>
            {canManageMedia && (
              <Button
                label="Upload First Photo"
                onPress={() => setIsUploadModalVisible(true)}
                className="w-full"
              />
            )}
          </Card>
        ) : (
          <>
            <MediaGrid
              mediaItems={mediaItems}
              onSelectMedia={(item) => setSelectedMediaDetail(item)}
              onDeleteMedia={deleteMedia}
              canManage={canManageMedia}
              isMutating={isMutating}
            />

            {/* Load More Button */}
            {hasMore && (
              <TouchableOpacity
                onPress={loadMore}
                disabled={isLoadingMore}
                className="mt-4 p-3 bg-slate-900 border border-slate-800 rounded-xl items-center"
              >
                {isLoadingMore ? (
                  <ActivityIndicator size="small" color="#818cf8" />
                ) : (
                  <Text className="text-brand-400 text-xs font-semibold">
                    Load More Media
                  </Text>
                )}
              </TouchableOpacity>
            )}
          </>
        )}
      </ScrollView>

      {/* Upload Modal */}
      <MediaUploadModal
        visible={isUploadModalVisible}
        onClose={() => setIsUploadModalVisible(false)}
        onUpload={uploadMedia}
        isUploading={isMutating}
      />

      {/* Detail / Edit Modal */}
      <MediaDetailModal
        visible={!!selectedMediaDetail}
        item={selectedMediaDetail}
        onClose={() => setSelectedMediaDetail(null)}
        onUpdateCaption={updateCaption}
        onDeleteMedia={deleteMedia}
        onOpenAttachActivity={handleOpenAttachActivity}
        onOpenAttachExpense={handleOpenAttachExpense}
        canManage={canManageMedia}
        isMutating={isMutating}
      />

      {/* Attach Activity/Expense Modal */}
      <AttachMediaModal
        visible={attachModalVisible}
        item={targetItemForAttach}
        mode={attachMode}
        tripId={id}
        onClose={() => {
          setAttachModalVisible(false);
          setTargetItemForAttach(null);
        }}
        onAttachActivity={attachToActivity}
        onAttachExpense={attachToExpense}
        isSubmitting={isMutating}
      />
    </SafeAreaView>
  );
}
