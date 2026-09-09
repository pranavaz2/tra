/**
 * Trip AI Assistant Screen.
 *
 * Provides a conversational trip-scoped chat interface allowing users to
 * ask travel questions, inspect itinerary/budget state, and safely confirm/cancel
 * structured AI proposed schedule changes.
 */

import React, { useRef, useEffect } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ArrowLeft, Sparkles, Trash2, RotateCcw } from "lucide-react-native";
import { useTrip } from "@/features/trips/hooks/use-trips";
import { useAssistant } from "@/features/assistant/hooks/use-assistant";
import { useItinerary } from "@/features/itinerary/hooks/use-itinerary";
import { useTripWarnings } from "@/features/assistant/hooks/use-trip-warnings";
import { TravelWarningBanner } from "@/features/assistant/components/TravelWarningBanner";
import { AssistantMessageBubble } from "@/features/assistant/components/AssistantMessageBubble";
import { AssistantInputBar } from "@/features/assistant/components/AssistantInputBar";
import { ErrorMessage } from "@/shared/components/feedback/ErrorMessage";
import { LoadingScreen } from "@/shared/components/feedback/LoadingScreen";

export default function TripAssistantScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const flatListRef = useRef<FlatList>(null);

  const { trip, isLoading: isTripLoading } = useTrip(id);
  const { days } = useItinerary(id);
  const {
    messages,
    isLoading,
    isHistoryLoading,
    isMutating,
    error,
    clearError,
    sendMessage,
    confirmAction,
    rejectAction,
    clearHistory,
    userRole,
    isViewer,
  } = useAssistant(id, trip?.owner_id);
  const { warnings: proactiveWarnings, dismissWarning } = useTripWarnings(id);

  // Auto scroll to bottom when new messages arrive
  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  }, [messages.length, isLoading]);

  if ((isTripLoading && !trip) || isHistoryLoading) {
    return <LoadingScreen message="Loading conversation history..." />;
  }

  return (
    <SafeAreaView className="flex-1 bg-slate-950">
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        className="flex-1"
      >
        {/* Header Bar */}
        <View className="px-5 py-3 flex-row items-center justify-between border-b border-slate-900 bg-slate-950">
          <View className="flex-row items-center flex-1">
            <TouchableOpacity
              onPress={() => router.back()}
              className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 items-center justify-center mr-3 active:bg-slate-800"
            >
              <ArrowLeft size={20} color="#cbd5e1" />
            </TouchableOpacity>

            <View className="flex-1">
              <View className="flex-row items-center space-x-1.5">
                <Text className="text-white text-base font-bold">Travix Assistant</Text>
                <Sparkles size={14} color="#818cf8" />
              </View>
              <Text className="text-slate-400 text-xs mt-0.5" numberOfLines={1}>
                {trip?.title || "Trip Planning Assistant"}
              </Text>
            </View>
          </View>

          <View className="flex-row items-center space-x-2">
            {userRole && (
              <View className="px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 mr-2">
                <Text className="text-slate-300 text-[11px] font-semibold capitalize">
                  {userRole}
                </Text>
              </View>
            )}

            <TouchableOpacity
              onPress={clearHistory}
              disabled={isLoading || isMutating}
              className="w-8 h-8 rounded-full bg-slate-900 border border-slate-800 items-center justify-center active:bg-slate-800"
              accessibilityLabel="Clear chat history"
            >
              <RotateCcw size={14} color="#94a3b8" />
            </TouchableOpacity>
          </View>
        </View>


        {/* Error notification */}
        {error && (
          <View className="px-4 pt-3">
            <ErrorMessage message={error} onRetry={clearError} />
          </View>
        )}

        {/* Proactive Intelligence Warnings Banner */}
        {proactiveWarnings.length > 0 && (
          <View className="px-4 pt-2">
            <TravelWarningBanner
              warnings={proactiveWarnings}
              onDismiss={dismissWarning}
            />
          </View>
        )}

        {/* Message List */}
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(item) => item.id}
          contentContainerStyle={{ paddingHorizontal: 16, paddingVertical: 16 }}
          renderItem={({ item }) => (
            <AssistantMessageBubble
              message={item}
              onConfirmAction={confirmAction}
              onRejectAction={rejectAction}
              isMutating={isMutating}
              isViewer={isViewer}
            />
          )}
          ListFooterComponent={
            isLoading ? (
              <View className="my-2 flex-row items-center bg-slate-900/60 self-start px-4 py-3 rounded-2xl border border-slate-800/80">
                <ActivityIndicator size="small" color="#818cf8" />
                <Text className="text-slate-400 text-xs ml-2.5 font-medium">
                  Assistant is thinking...
                </Text>
              </View>
            ) : null
          }
        />

        {/* Input Bar */}
        <AssistantInputBar
          onSend={sendMessage}
          isLoading={isLoading}
          tripTitle={trip?.title}
          itineraryDaysCount={days?.length ?? 0}
          firstStopName={days?.[0]?.items?.[0]?.title ?? undefined}
        />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
