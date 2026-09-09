import React, { useState } from "react";
import {
  View,
  Text,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  X,
  Sparkles,
  Check,
  Compass,
  DollarSign,
  Zap,
  Coffee,
  AlertCircle,
  MapPin,
  Calendar,
} from "lucide-react-native";
import { TripsApi } from "@/features/trips/api/trips-api";
import { ProposalsApi } from "@/features/proposals/api/proposals-api";
import { Input } from "@/shared/components/ui/Input";
import { Button } from "@/shared/components/ui/Button";
import { Card } from "@/shared/components/ui/Card";
import { ErrorMessage } from "@/shared/components/feedback/ErrorMessage";
import { BudgetLevel, TravelStyle, ProposalCreateRequest } from "@/core/api/types";
import { TravixApiError } from "@/core/api/client";
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

export default function CreateTripScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{
    destination?: string;
    nlInput?: string;
    durationDays?: string;
    targetBudget?: string;
    currency?: string;
    interests?: string;
    travelStyle?: string;
  }>();

  // Pre-fill from NL parsed params (passed from Home screen AI input)
  const [destination, setDestination] = useState(params.destination || "");
  const [durationDays, setDurationDays] = useState(params.durationDays || "3");
  const [budgetLevel, setBudgetLevel] = useState<BudgetLevel>("mid_range");
  const [targetBudget, setTargetBudget] = useState(params.targetBudget || "15000");
  const [travelStyle, setTravelStyle] = useState<TravelStyle>(
    (params.travelStyle as TravelStyle) || "balanced"
  );
  const [selectedInterests, setSelectedInterests] = useState<string[]>(() => {
    if (params.interests) {
      return params.interests.split(",").filter(Boolean);
    }
    return ["History & Museums", "Food & Dining", "Sightseeing"];
  });
  const [specialRequirements, setSpecialRequirements] = useState("");
  const [currency, setCurrency] = useState(params.currency || "INR");


  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
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
    } else if (destination.trim().length > 100) {
      errs.destination = "Destination must be 100 characters or less";
    }

    const days = parseInt(durationDays.trim(), 10);
    if (isNaN(days) || days < 1 || days > 30) {
      errs.durationDays = "Duration must be between 1 and 30 days";
    }

    setValidationErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleCreateAndPlan = async () => {
    setErrorMessage(null);
    if (!validate()) return;

    setIsSubmitting(true);
    setStatusMessage("Setting up your trip container...");

    try {
      // 1. Create Trip entity named after destination
      const tripTitle = destination.trim();
      const trip = await TripsApi.createTrip({
        title: tripTitle,
        privacy: "private",
        is_date_flexible: true,
      });

      // 2. Request Grounded Gemini AI Proposal
      setStatusMessage("Gemini is researching and grounding verified places...");
      const proposalPayload: ProposalCreateRequest = {
        destination: destination.trim(),
        duration_days: parseInt(durationDays.trim(), 10),
        budget_level: budgetLevel,
        travel_style: travelStyle,
        interests: selectedInterests.map((i) => i.toLowerCase()),
        special_requirements: specialRequirements.trim() || undefined,
        currency: currency || "INR",
        target_budget: targetBudget.trim() || undefined,
      };

      const proposal = await ProposalsApi.requestProposal(trip.trip_id, proposalPayload);

      // 3. Navigate directly to Proposal Preview
      router.replace({
        pathname: "/trips/[id]/proposal/[proposalId]",
        params: {
          id: trip.trip_id,
          proposalId: proposal.proposal_id,
          targetBudget: targetBudget.trim() || undefined,
        },
      } as any);
    } catch (err: any) {
      if (err instanceof TravixApiError) {
        if (err.errorCode === "TRIP_CONFLICT") {
          setErrorMessage(`A trip titled "${destination.trim()}" already exists. Please customize the name.`);
        } else {
          setErrorMessage(err.message || "Failed to generate travel plan.");
        }
      } else {
        setErrorMessage("Network error. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
      setStatusMessage(null);
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-slate-950">
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        className="flex-1"
      >
        {/* Top Header */}
        <View className="px-6 py-4 flex-row items-center justify-between border-b border-slate-900 bg-slate-950">
          <View className="flex-row items-center">
            <View className="w-9 h-9 rounded-xl bg-brand-600/20 border border-brand-500/40 items-center justify-center mr-3">
              <Sparkles size={18} color="#818cf8" />
            </View>
            <View>
              <Text className="text-xl font-bold text-white tracking-tight">
                Plan Trip with AI
              </Text>
              <Text className="text-slate-400 text-xs mt-0.5">
                Grounded real places & verified itinerary
              </Text>
            </View>
          </View>

          <TouchableOpacity
            onPress={() => router.back()}
            disabled={isSubmitting}
            className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 items-center justify-center active:bg-slate-800"
          >
            <X size={20} color="#94a3b8" />
          </TouchableOpacity>
        </View>

        <ScrollView
          contentContainerStyle={{ padding: 24, paddingBottom: 40 }}
          keyboardShouldPersistTaps="handled"
          className="flex-1"
        >
          {errorMessage && <ErrorMessage message={errorMessage} className="mb-6" />}

          {/* Destination */}
          <Input
            label="Where do you want to go? *"
            placeholder="e.g. Mysore, India or Kyoto, Japan"
            value={destination}
            onChangeText={(text) => {
              setDestination(text);
              if (validationErrors.destination) {
                setValidationErrors((prev) => ({ ...prev, destination: "" }));
              }
            }}
            error={validationErrors.destination}
            editable={!isSubmitting}
          />

          {/* Duration in Days */}
          <Input
            label="How many days? (1 - 30) *"
            placeholder="3"
            keyboardType="number-pad"
            value={durationDays}
            onChangeText={(text) => {
              setDurationDays(text);
              if (validationErrors.durationDays) {
                setValidationErrors((prev) => ({ ...prev, durationDays: "" }));
              }
            }}
            error={validationErrors.durationDays}
            editable={!isSubmitting}
          />

          {/* Target Budget */}
          <Input
            label="Approximate Budget (₹ / Currency)"
            placeholder="15000"
            keyboardType="number-pad"
            value={targetBudget}
            onChangeText={setTargetBudget}
            editable={!isSubmitting}
          />

          {/* Budget Level Selection */}
          <Text className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Budget Tier
          </Text>
          <View className="space-y-2 mb-6">
            {BUDGET_OPTIONS.map((opt) => {
              const isSelected = budgetLevel === opt.value;
              return (
                <TouchableOpacity
                  key={opt.value}
                  disabled={isSubmitting}
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
                    <Text className="text-slate-400 text-xs mt-0.5">{opt.desc}</Text>
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

          {/* Travel Pace & Style */}
          <Text className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Travel Pace & Style
          </Text>
          <View className="space-y-2 mb-6">
            {STYLE_OPTIONS.map((opt) => {
              const isSelected = travelStyle === opt.value;
              return (
                <TouchableOpacity
                  key={opt.value}
                  disabled={isSubmitting}
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
                    <Text className="text-slate-400 text-xs mt-0.5">{opt.desc}</Text>
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
            Interests & Preferences
          </Text>
          <View className="flex-row flex-wrap gap-2 mb-6">
            {INTEREST_TAGS.map((tag) => {
              const isSelected = selectedInterests.includes(tag);
              return (
                <TouchableOpacity
                  key={tag}
                  disabled={isSubmitting}
                  onPress={() => toggleInterest(tag)}
                  className={clsx(
                    "px-3 py-1.5 rounded-full border mr-1.5 mb-1.5",
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
            placeholder="e.g. Authentic local food, avoid crowded afternoon spots, kid friendly"
            value={specialRequirements}
            onChangeText={setSpecialRequirements}
            multiline
            numberOfLines={2}
            textAlignVertical="top"
            className="h-16 py-2"
            editable={!isSubmitting}
          />

          {/* Submission / Status */}
          <View className="mt-4 space-y-3">
            {isSubmitting ? (
              <Card className="p-4 bg-brand-950/40 border border-brand-500/40 items-center">
                <ActivityIndicator size="small" color="#818cf8" />
                <Text className="text-brand-300 text-xs font-semibold mt-2.5 text-center">
                  {statusMessage || "Gemini is building your travel plan..."}
                </Text>
              </Card>
            ) : (
              <Button
                label="Generate AI Itinerary"
                variant="primary"
                size="lg"
                icon={<Sparkles size={18} color="#ffffff" />}
                onPress={handleCreateAndPlan}
              />
            )}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
