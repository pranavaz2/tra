import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  TouchableOpacity,
  Switch,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { X, Lock, Eye, Globe, Calendar, Check } from "lucide-react-native";
import { useTrip } from "@/features/trips/hooks/use-trips";
import { useCollaboration } from "@/features/collaboration/hooks/use-collaboration";
import { Input } from "@/shared/components/ui/Input";
import { Button } from "@/shared/components/ui/Button";
import { ErrorMessage } from "@/shared/components/feedback/ErrorMessage";
import { LoadingScreen } from "@/shared/components/feedback/LoadingScreen";
import { DatePickerModal } from "@/shared/components/ui/DatePickerModal";
import { TripPrivacy } from "@/core/api/types";
import { TravixApiError } from "@/core/api/client";
import clsx from "clsx";

export default function EditTripScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { trip, isLoading, isMutating, updateTrip } = useTrip(id);
  const { isViewer } = useCollaboration(id, trip?.owner_id);

  const [title, setTitle] = useState("");
  const [privacy, setPrivacy] = useState<TripPrivacy>("private");
  const [departureDate, setDepartureDate] = useState("");
  const [returnDate, setReturnDate] = useState("");
  const [isDateFlexible, setIsDateFlexible] = useState(false);

  const [showDatePicker, setShowDatePicker] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [titleError, setTitleError] = useState<string | null>(null);

  // Hydrate fields once trip is loaded
  useEffect(() => {
    if (trip) {
      setTitle(trip.title);
      setPrivacy(trip.privacy);
      setDepartureDate(trip.departure_date || "");
      setReturnDate(trip.return_date || "");
      setIsDateFlexible(trip.is_date_flexible);
    }
  }, [trip]);

  if (isLoading && !trip) {
    return <LoadingScreen message="Loading trip..." />;
  }

  const validate = (): boolean => {
    if (!title.trim()) {
      setTitleError("Trip name is required");
      return false;
    }
    if (title.trim().length > 100) {
      setTitleError("Trip name must be 100 characters or less");
      return false;
    }
    setTitleError(null);
    return true;
  };

  const handleSave = async () => {
    setErrorMessage(null);
    if (!validate()) return;

    try {
      await updateTrip({
        title: title.trim(),
        privacy,
        update_dates: true,
        departure_date: isDateFlexible ? null : departureDate.trim() || null,
        return_date: isDateFlexible ? null : returnDate.trim() || null,
        is_date_flexible: isDateFlexible,
      });

      router.back();
    } catch (err: any) {
      if (err instanceof TravixApiError) {
        if (err.errorCode === "TRIP_CONFLICT") {
          setErrorMessage(`Another trip titled "${title.trim()}" already exists.`);
        } else {
          setErrorMessage(err.message || "Failed to update trip.");
        }
      } else {
        setErrorMessage("Network error. Please try again.");
      }
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-slate-950">
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        className="flex-1"
      >
        <ScrollView
          contentContainerStyle={{ padding: 24 }}
          keyboardShouldPersistTaps="handled"
          className="flex-1"
        >
          {/* Top Bar with Cancel */}
          <View className="flex-row items-center justify-between mb-6">
            <View>
              <Text className="text-2xl font-bold text-white tracking-tight">Edit Trip</Text>
              <Text className="text-slate-400 text-xs mt-0.5">
                Update name, visibility, or travel dates
              </Text>
            </View>

            <TouchableOpacity
              onPress={() => router.back()}
              className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 items-center justify-center active:bg-slate-800"
            >
              <X size={20} color="#94a3b8" />
            </TouchableOpacity>
          </View>

          {errorMessage && <ErrorMessage message={errorMessage} className="mb-6" />}

          {/* Title Input */}
          <Input
            label="Trip Name"
            placeholder="e.g. Vacation in Tokyo"
            value={title}
            onChangeText={(text) => {
              setTitle(text);
              if (titleError) setTitleError(null);
            }}
            error={titleError}
          />

          {/* Privacy Selector */}
          <View className="mb-6">
            <Text className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Privacy Setting
            </Text>
            <View className="flex-row space-x-2">
              {(
                [
                  { value: "private", label: "Private", icon: Lock },
                  { value: "link_only", label: "Link Only", icon: Eye },
                  { value: "public", label: "Public", icon: Globe },
                ] as const
              ).map((option) => {
                const isSelected = privacy === option.value;
                const IconComponent = option.icon;
                return (
                  <TouchableOpacity
                    key={option.value}
                    onPress={() => setPrivacy(option.value)}
                    className={clsx(
                      "flex-1 flex-row items-center justify-center py-3 px-2 rounded-xl border mr-2",
                      isSelected
                        ? "bg-brand-600/20 border-brand-500"
                        : "bg-slate-900 border-slate-800"
                    )}
                  >
                    <IconComponent
                      size={15}
                      color={isSelected ? "#818cf8" : "#94a3b8"}
                    />
                    <Text
                      className={clsx(
                        "text-xs font-semibold ml-1.5",
                        isSelected ? "text-white" : "text-slate-400"
                      )}
                    >
                      {option.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          {/* Flexible Dates Toggle */}
          <View className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 mb-6 flex-row items-center justify-between">
            <View className="flex-1 mr-4">
              <Text className="text-white text-sm font-semibold">Flexible Dates</Text>
              <Text className="text-slate-400 text-xs mt-0.5">
                Turn on if exact dates are undecided
              </Text>
            </View>
            <Switch
              value={isDateFlexible}
              onValueChange={setIsDateFlexible}
              trackColor={{ false: "#1e293b", true: "#4f46e5" }}
              thumbColor={isDateFlexible ? "#ffffff" : "#94a3b8"}
            />
          </View>

          {/* Date Picker Button / Display */}
          {!isDateFlexible && (
            <View className="mb-6">
              <Text className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Travel Dates
              </Text>

              <TouchableOpacity
                onPress={() => setShowDatePicker(true)}
                className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex-row items-center justify-between"
              >
                <View className="flex-row items-center">
                  <Calendar size={18} color="#818cf8" />
                  <Text className="text-white text-sm font-medium ml-3">
                    {departureDate
                      ? `${departureDate} ${returnDate ? `→ ${returnDate}` : ""}`
                      : "Tap to set dates"}
                  </Text>
                </View>
                <Text className="text-brand-400 text-xs font-semibold">Change</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Action Buttons */}
          <View className="mt-4 space-y-3">
            {isViewer ? (
              <View className="p-4 bg-slate-900 border border-slate-800 rounded-2xl mb-3">
                <Text className="text-slate-400 text-xs text-center">
                  You have read-only (Viewer) access to this trip. Only the trip owner and editors can modify details.
                </Text>
              </View>
            ) : (
              <Button
                label="Save Changes"
                variant="primary"
                size="lg"
                icon={<Check size={18} color="#ffffff" />}
                onPress={handleSave}
                isLoading={isMutating}
              />
            )}

            <Button
              label={isViewer ? "Back" : "Cancel"}
              variant="ghost"
              size="md"
              className="mt-2"
              onPress={() => router.back()}
            />
          </View>

          <DatePickerModal
            visible={showDatePicker}
            onClose={() => setShowDatePicker(false)}
            departureDate={departureDate}
            returnDate={returnDate}
            onSelectDates={(dep, ret) => {
              setDepartureDate(dep);
              setReturnDate(ret);
            }}
          />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
