import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  ArrowLeft,
  Sparkles,
  Compass,
  DollarSign,
  Zap,
  Coffee,
  Check,
  AlertCircle,
} from "lucide-react-native";
import { useTrip } from "@/features/trips/hooks/use-trips";
import { useTripProposal } from "@/features/proposals/hooks/use-proposal";
import { useCollaboration } from "@/features/collaboration/hooks/use-collaboration";
import {
  BudgetLevel,
  TravelStyle,
  ProposalCreateRequest,
} from "@/core/api/types";
import { Input } from "@/shared/components/ui/Input";
import { Button } from "@/shared/components/ui/Button";
import { Card } from "@/shared/components/ui/Card";
import clsx from "clsx";

const BUDGET_OPTIONS: { value: BudgetLevel; label: string; desc: string }[] = [
  { value: "budget", label: "Budget", desc: "Cost-conscious & hostels" },
  { value: "mid_range", label: "Mid-Range", desc: "Boutique & balanced" },
  { value: "luxury", label: "Luxury", desc: "Premium stays & fine dining" },
];

const STYLE_OPTIONS: { value: TravelStyle; label: string; desc: string }[] = [
  { value: "relaxed", label: "Relaxed", desc: "Easy pace, plenty of downtime" },
  { value: "balanced", label: "Balanced", desc: "Mix of sights & leisurely breaks" },
  { value: "active", label: "Active", desc: "Packed itineraries & full days" },
];

const INTEREST_TAGS = [
  "Food & Dining",
  "History & Museums",
  "Sightseeing",
  "Outdoors & Nature",
  "Art & Architecture",
  "Local Markets",
  "Nightlife",
  "Hidden Gems",
];

export default function PlanTripScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();

  const { trip } = useTrip(id);
  const { requestProposal, isGenerating, error } = useTripProposal(id);
  const { isViewer } = useCollaboration(id);

  // Form State
  const [destination, setDestination] = useState(trip?.title || "");
  const [durationDays, setDurationDays] = useState("3");
  const [budgetLevel, setBudgetLevel] = useState<BudgetLevel>("mid_range");
  const [travelStyle, setTravelStyle] = useState<TravelStyle>("balanced");
  const [selectedInterests, setSelectedInterests] = useState<string[]>([
    "Food & Dining",
    "Sightseeing",
  ]);
  const [specialRequirements, setSpecialRequirements] = useState("");

  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  const toggleInterest = (interest: string) => {
    if (selectedInterests.includes(interest)) {
      setSelectedInterests(selectedInterests.filter((i) => i !== interest));
    } else {
      setSelectedInterests([...selectedInterests, interest]);
    }
  };

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!destination.trim()) {
      errs.destination = "Destination is required";
    } else if (destination.trim().length > 200) {
      errs.destination = "Destination cannot exceed 200 characters";
    }

    const days = parseInt(durationDays.trim(), 10);
    if (isNaN(days) || days < 1 || days > 30) {
      errs.durationDays = "Duration must be between 1 and 30 days";
    }

    setValidationErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleGenerate = async () => {
    if (!validate()) return;

    const payload: ProposalCreateRequest = {
      destination: destination.trim(),
      duration_days: parseInt(durationDays.trim(), 10),
      budget_level: budgetLevel,
      travel_style: travelStyle,
      interests: selectedInterests.map((i) => i.toLowerCase()),
      special_requirements: specialRequirements.trim() || undefined,
    };

    try {
      const generated = await requestProposal(payload);
      router.replace(`/trips/${id}/proposal/${generated.proposal_id}` as any);
    } catch {
      // Error handled by hook
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-slate-950" edges={["top", "bottom"]}>
      {/* Header */}
      <View className="flex-row items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950">
        <View className="flex-row items-center">
          <TouchableOpacity
            onPress={() => router.back()}
            disabled={isGenerating}
            className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 items-center justify-center mr-3 active:bg-slate-800"
            accessibilityLabel="Go back"
          >
            <ArrowLeft size={20} color="#f8fafc" />
          </TouchableOpacity>
          <View>
            <Text className="text-white text-lg font-bold">Plan with AI</Text>
            <Text className="text-slate-400 text-xs mt-0.5">
              Grounded AI Proposal
            </Text>
          </View>
        </View>
      </View>

      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        className="flex-1"
      >
        <ScrollView
          className="flex-1 px-6 py-4"
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {/* AI Banner */}
          <Card className="p-4 bg-sky-950/20 border border-sky-500/30 flex-row items-start mb-6">
            <View className="w-9 h-9 rounded-xl bg-sky-500/20 items-center justify-center mr-3 mt-0.5">
              <Sparkles size={18} color="#38bdf8" />
            </View>
            <View className="flex-1">
              <Text className="text-white text-sm font-bold">
                Real Places & Verified Details
              </Text>
              <Text className="text-slate-400 text-xs mt-1 leading-relaxed">
                Travix grounds itinerary candidates with real Google Places data. No hallucinated places.
              </Text>
            </View>
          </Card>

          {/* Error Banner */}
          {error && (
            <View className="mb-4 p-3.5 bg-rose-950/40 border border-rose-800 rounded-xl flex-row items-center">
              <AlertCircle size={18} color="#f43f5e" />
              <Text className="text-rose-400 text-xs font-medium ml-2.5 flex-1 leading-tight">
                {error}
              </Text>
            </View>
          )}

          {/* Destination */}
          <Input
            label="Target Destination *"
            placeholder="e.g. Rome, Italy or Kyoto"
            value={destination}
            onChangeText={setDestination}
            error={validationErrors.destination}
            editable={!isGenerating}
          />

          {/* Duration Days */}
          <Input
            label="Duration in Days (1 - 30) *"
            placeholder="3"
            keyboardType="number-pad"
            value={durationDays}
            onChangeText={setDurationDays}
            error={validationErrors.durationDays}
            editable={!isGenerating}
          />

          {/* Budget Level */}
          <Text className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Budget Level
          </Text>
          <View className="space-y-2 mb-5">
            {BUDGET_OPTIONS.map((opt) => {
              const isSelected = budgetLevel === opt.value;
              return (
                <TouchableOpacity
                  key={opt.value}
                  disabled={isGenerating}
                  onPress={() => setBudgetLevel(opt.value)}
                  className={clsx(
                    "p-3 rounded-xl border flex-row items-center justify-between mb-2",
                    isSelected
                      ? "bg-brand-600/20 border-brand-500"
                      : "bg-slate-900 border-slate-800"
                  )}
                >
                  <View>
                    <Text
                      className={clsx(
                        "text-sm font-bold",
                        isSelected ? "text-brand-300" : "text-white"
                      )}
                    >
                      {opt.label}
                    </Text>
                    <Text className="text-slate-400 text-xs mt-0.5">
                      {opt.desc}
                    </Text>
                  </View>
                  {isSelected && (
                    <View className="w-5 h-5 rounded-full bg-brand-500 items-center justify-center">
                      <Check size={12} color="#ffffff" />
                    </View>
                  )}
                </TouchableOpacity>
              );
            })}
          </View>

          {/* Travel Style */}
          <Text className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Travel Pace & Style
          </Text>
          <View className="space-y-2 mb-5">
            {STYLE_OPTIONS.map((opt) => {
              const isSelected = travelStyle === opt.value;
              return (
                <TouchableOpacity
                  key={opt.value}
                  disabled={isGenerating}
                  onPress={() => setTravelStyle(opt.value)}
                  className={clsx(
                    "p-3 rounded-xl border flex-row items-center justify-between mb-2",
                    isSelected
                      ? "bg-sky-600/20 border-sky-500"
                      : "bg-slate-900 border-slate-800"
                  )}
                >
                  <View>
                    <Text
                      className={clsx(
                        "text-sm font-bold",
                        isSelected ? "text-sky-300" : "text-white"
                      )}
                    >
                      {opt.label}
                    </Text>
                    <Text className="text-slate-400 text-xs mt-0.5">
                      {opt.desc}
                    </Text>
                  </View>
                  {isSelected && (
                    <View className="w-5 h-5 rounded-full bg-sky-500 items-center justify-center">
                      <Check size={12} color="#ffffff" />
                    </View>
                  )}
                </TouchableOpacity>
              );
            })}
          </View>

          {/* Interests */}
          <Text className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Interests & Highlights
          </Text>
          <View className="flex-row flex-wrap gap-2 mb-5">
            {INTEREST_TAGS.map((tag) => {
              const isSelected = selectedInterests.includes(tag);
              return (
                <TouchableOpacity
                  key={tag}
                  disabled={isGenerating}
                  onPress={() => toggleInterest(tag)}
                  className={clsx(
                    "px-3 py-1.5 rounded-full border",
                    isSelected
                      ? "bg-brand-600/20 border-brand-500"
                      : "bg-slate-900 border-slate-800"
                  )}
                >
                  <Text
                    className={clsx(
                      "text-xs font-semibold",
                      isSelected ? "text-brand-300" : "text-slate-400"
                    )}
                  >
                    {tag}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {/* Special Requirements */}
          <Input
            label="Special Requirements (Optional)"
            placeholder="e.g. Vegetarian dining, walking friendly, kid-safe"
            value={specialRequirements}
            onChangeText={setSpecialRequirements}
            multiline
            numberOfLines={3}
            textAlignVertical="top"
            className="h-20 py-2.5"
            editable={!isGenerating}
          />

          <View className="h-6" />
        </ScrollView>

        {/* Generate Button Footer */}
        <View className="p-4 px-6 border-t border-slate-800 bg-slate-950">
          {isGenerating ? (
            <View className="items-center py-2">
              <ActivityIndicator size="small" color="#38bdf8" />
              <Text className="text-sky-300 text-xs font-semibold mt-2 text-center">
                Gemini is researching and grounding places...
              </Text>
            </View>
          ) : isViewer ? (
            <View className="py-2.5 px-4 bg-slate-900 border border-slate-800 rounded-xl items-center">
              <Text className="text-slate-400 text-xs text-center">
                Viewer access: only editors and owners can generate new AI proposals.
              </Text>
            </View>
          ) : (
            <Button
              label="Generate AI Proposal"
              onPress={handleGenerate}
              className="w-full bg-brand-600 active:bg-brand-700"
            />
          )}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
